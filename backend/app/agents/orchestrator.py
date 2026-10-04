"""Agent 1 — Orchestrator. Owns InvestigationState and runs the pipeline,
with the one required adaptive branch: if data quality fails on the
requested period, it widens the window once and retries before giving up.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.agents import (
    investigation_agent,
    nasa_data_agent,
    quality_agent,
    relationship_agent,
    report_agent,
    skeptic_agent,
    spatial_agent,
    statistics_agent,
    trend_agent,
)
from app.agents.state import InvestigationState
from app.db.session import AsyncSessionLocal
from app.llm.planner import InvestigationPlan, build_plan
from app.models import Investigation
from app.nasa.catalog import dataset_code_for_variable
from app.nasa.regions import REGIONS_BY_CODE
from app.nasa.registry import get_adapter
from app.services.events import StepRecorder

logger = logging.getLogger(__name__)


async def run_investigation(investigation_id: uuid.UUID, question: str) -> None:
    async with AsyncSessionLocal() as session:
        investigation = (
            await session.execute(select(Investigation).where(Investigation.id == investigation_id))
        ).scalar_one()
        recorder = StepRecorder(investigation_id, session)

        try:
            await recorder.emit("ORCHESTRATOR", "running", "Understanding the question and building an investigation plan...")
            plan = await build_plan(question)
            region = REGIONS_BY_CODE[plan.region_code]

            investigation.plan = {
                "variable_code": plan.variable_code, "region_code": plan.region_code,
                "start_year": plan.start_year, "end_year": plan.end_year,
                "compare_region_code": plan.compare_region_code,
                "run_relationship_analysis": plan.run_relationship_analysis, "source": plan.source,
            }
            investigation.status = "running"
            await session.commit()

            plan_msg = f"Plan ({plan.source}): {plan.reasoning}"
            if plan.unsupported_variable_note:
                plan_msg += " " + plan.unsupported_variable_note
            await recorder.emit("ORCHESTRATOR", "done", plan_msg, {"plan": investigation.plan})

            state = InvestigationState(
                investigation_id=investigation_id, question=question, mode="nlp", plan=plan, region=region
            )

            state = await run_pipeline(session, recorder, state, allow_retry=True)

            investigation.status = state.status
            investigation.error = state.error
            investigation.completed_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception as exc:  # noqa: BLE001 - top-level guard so the UI always gets a terminal event
            logger.exception("Investigation %s failed", investigation_id)
            investigation.status = "failed"
            investigation.error = str(exc)
            investigation.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await recorder.emit("ORCHESTRATOR", "error", f"Investigation failed: {exc}")
        finally:
            await recorder.close()


async def run_pipeline(session, recorder: StepRecorder, state: InvestigationState, allow_retry: bool) -> InvestigationState:
    """The actual agent sequence (data -> quality -> trend -> ... -> report),
    public because it's reused by anything that builds an InvestigationState
    directly rather than parsing a question — app/agents/watch_runner.py, for
    the same reason discover.py's _run_candidate builds its own state."""
    state = await nasa_data_agent.run(session, recorder, state)
    if state.status == "failed":
        return state

    state = await quality_agent.run(session, recorder, state)
    dataset_code = dataset_code_for_variable(state.plan.variable_code)
    retry_floor_year = get_adapter(dataset_code).get_metadata().retry_floor_year
    if state.status == "insufficient_data" and allow_retry and state.plan.start_year > retry_floor_year:
        await recorder.emit(
            "ORCHESTRATOR", "running",
            f"Data quality was insufficient for {state.plan.start_year}-{state.plan.end_year}; widening the "
            f"time window to {retry_floor_year}-{state.plan.end_year} and retrying...",
        )
        widened_plan = InvestigationPlan(**{**state.plan.__dict__, "start_year": retry_floor_year})
        state.plan = widened_plan
        state.status = "running"
        return await run_pipeline(session, recorder, state, allow_retry=False)
    if state.status == "insufficient_data":
        return state

    state = await trend_agent.run(session, recorder, state)
    if state.status == "insufficient_data":
        return state

    state = await statistics_agent.run(session, recorder, state)

    if state.plan.run_spatial_analysis:
        state = await spatial_agent.run(session, recorder, state)
    else:
        await recorder.emit("SPATIAL_AGENT", "skipped", "Skipped — question did not require spatial comparison.")

    if state.plan.run_relationship_analysis:
        state = await relationship_agent.run(session, recorder, state)
    else:
        await recorder.emit("RELATIONSHIP_AGENT", "skipped", "Skipped — question did not ask about related variables.")

    state = await investigation_agent.run(session, recorder, state)
    state = await skeptic_agent.run(session, recorder, state)
    state = await report_agent.run(session, recorder, state)
    return state
