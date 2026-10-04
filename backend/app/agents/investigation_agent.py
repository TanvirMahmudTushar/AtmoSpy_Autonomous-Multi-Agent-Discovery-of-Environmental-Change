"""Agent 8 — Investigation Agent. A robustness "critic" pass: does the
result hold up under scrutiny (persistence across sub-periods, data quality
caveats, confound of a single abrupt change point vs. a sustained trend)?
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.services.events import StepRecorder


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    await recorder.emit("INVESTIGATION_AGENT", "running", "Checking robustness of the finding...")

    caveats: list[str] = []
    robust = True

    persistence = state.persistence or {}
    if persistence.get("applicable") and not persistence.get("consistent_direction", True):
        caveats.append(
            "The trend direction is not consistent between the first and second half of the period — "
            "treat the overall trend with caution."
        )
        robust = False

    if state.change_points:
        caveats.append(
            f"{len(state.change_points)} abrupt change point(s) detected — part of the overall trend may "
            "reflect a step shift rather than gradual change."
        )

    if state.quality_report and state.quality_report.issues:
        caveats.extend(state.quality_report.issues)

    if state.significance and state.significance["classification"] != "statistically_significant":
        caveats.append(
            "The trend did not reach statistical significance at alpha=0.05; treat any visual pattern as "
            "suggestive only."
        )

    verdict = "robust" if robust and not caveats else "robust with caveats" if robust else "not robust"
    await recorder.emit(
        "INVESTIGATION_AGENT", "done",
        f"Robustness verdict: {verdict}." + (" " + " ".join(caveats) if caveats else ""),
        {"verdict": verdict, "caveats": caveats},
    )
    state.robustness_verdict = verdict
    state.robustness_caveats = caveats
    return state
