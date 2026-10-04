"""Runs a scheduled watch's periodic re-check: same pipeline as
/investigate, entered directly with a known region/variable instead of a
parsed question (the same shape discover.py's candidates use), then
snapshots whether the result changed since the watch's previous check.

Investigation creation is split from execution (`create_watch_check_investigation`
vs. `execute_watch_check`) so a caller that needs the investigation_id right
away — the "check now" API endpoint, so the frontend can start streaming its
SSE events immediately — gets it synchronously, instead of having to guess
which background-created row was "the one" (a real race if two checks are
in flight for the same user at once). `run_watch_check` is the convenience
one-shot wrapper the scheduler uses, which doesn't need the id back.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.agents.orchestrator import run_pipeline
from app.agents.state import InvestigationState
from app.db.session import AsyncSessionLocal
from app.llm.planner import InvestigationPlan
from app.models import Investigation, Watch
from app.nasa.catalog import VARIABLES_BY_CODE
from app.nasa.regions import REGIONS_BY_CODE
from app.services.events import StepRecorder

logger = logging.getLogger(__name__)

DEFAULT_START_YEAR = 1990


def _build_note(watch: Watch, new_trend: float | None, new_significance: str | None) -> str:
    if new_trend is None:
        return "This check produced insufficient data — no finding to compare."
    if watch.last_trend_per_year is None:
        return "First check for this watch — nothing to compare against yet."

    sign_flipped = (watch.last_trend_per_year >= 0) != (new_trend >= 0)
    became_significant = watch.last_significance != "statistically_significant" and new_significance == "statistically_significant"
    lost_significance = watch.last_significance == "statistically_significant" and new_significance != "statistically_significant"

    if sign_flipped:
        return "Trend direction flipped since the last check — worth a closer look."
    if became_significant:
        return "Newly statistically significant since the last check."
    if lost_significance:
        return "No longer statistically significant since the last check."
    return "Consistent with the previous check — no material change."


async def create_watch_check_investigation(session, watch: Watch) -> Investigation:
    investigation = Investigation(user_id=watch.user_id, mode="watch", question=None, status="pending")
    session.add(investigation)
    await session.commit()
    await session.refresh(investigation)
    return investigation


async def execute_watch_check(watch_id: uuid.UUID, investigation_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        watch = (await session.execute(select(Watch).where(Watch.id == watch_id))).scalar_one_or_none()
        investigation = (
            await session.execute(select(Investigation).where(Investigation.id == investigation_id))
        ).scalar_one_or_none()
        if watch is None or investigation is None:
            logger.error("Watch check for watch=%s investigation=%s: row missing at execute time", watch_id, investigation_id)
            return

        region = REGIONS_BY_CODE.get(watch.region_code)
        var_info = VARIABLES_BY_CODE.get(watch.variable_code)
        if region is None or var_info is None:
            logger.error("Watch %s references an unknown region/variable code", watch_id)
            return

        recorder = StepRecorder(investigation.id, session)
        try:
            await recorder.emit(
                "ORCHESTRATOR", "running",
                f"Scheduled watch check: {var_info.name} in {region.name}...",
            )
            plan = InvestigationPlan(
                variable_code=watch.variable_code,
                region_code=watch.region_code,
                start_year=DEFAULT_START_YEAR,
                end_year=datetime.now(timezone.utc).year - 1,
                run_spatial_analysis=True,
                run_relationship_analysis=False,
                reasoning=f"Scheduled watch of {region.name} / {var_info.name}",
                source="watch",
            )
            investigation.plan = {
                "variable_code": plan.variable_code, "region_code": plan.region_code,
                "start_year": plan.start_year, "end_year": plan.end_year, "source": plan.source,
            }
            investigation.status = "running"
            await session.commit()
            await recorder.emit("ORCHESTRATOR", "done", f"Plan (watch): {plan.reasoning}", {"plan": investigation.plan})

            state = InvestigationState(
                investigation_id=investigation.id, question=None, mode="watch", plan=plan, region=region
            )
            state = await run_pipeline(session, recorder, state, allow_retry=True)

            investigation.status = state.status
            investigation.error = state.error
            investigation.completed_at = datetime.now(timezone.utc)
            await session.commit()

            new_trend = state.trend_result.sen_slope_per_year if state.trend_result else None
            new_significance = state.significance["classification"] if state.significance else None
            note = _build_note(watch, new_trend, new_significance)

            watch.last_checked_at = datetime.now(timezone.utc)
            watch.next_check_at = watch.last_checked_at + timedelta(days=watch.frequency_days)
            watch.last_investigation_id = investigation.id
            watch.last_finding_id = state.finding_id
            watch.prev_trend_per_year = watch.last_trend_per_year
            watch.prev_significance = watch.last_significance
            watch.last_trend_per_year = new_trend
            watch.last_significance = new_significance
            watch.last_check_note = note
            await session.commit()

            await recorder.emit("REPORT_AGENT", "done", f"Watch check complete: {note}")
        except Exception as exc:  # noqa: BLE001 - top-level guard, mirrors run_investigation
            logger.exception("Watch check %s failed", watch_id)
            investigation.status = "failed"
            investigation.error = str(exc)
            investigation.completed_at = datetime.now(timezone.utc)
            watch.last_checked_at = datetime.now(timezone.utc)
            watch.next_check_at = watch.last_checked_at + timedelta(days=watch.frequency_days)
            watch.last_check_note = f"Check failed: {exc}"
            await session.commit()
            await recorder.emit("ORCHESTRATOR", "error", f"Watch check failed: {exc}")
        finally:
            await recorder.close()


async def run_watch_check(watch_id: uuid.UUID) -> None:
    """One-shot convenience wrapper for the scheduler, which fires checks
    without needing the investigation id back."""
    async with AsyncSessionLocal() as session:
        watch = (await session.execute(select(Watch).where(Watch.id == watch_id))).scalar_one_or_none()
        if watch is None:
            return
        investigation = await create_watch_check_investigation(session, watch)

    await execute_watch_check(watch_id, investigation.id)
