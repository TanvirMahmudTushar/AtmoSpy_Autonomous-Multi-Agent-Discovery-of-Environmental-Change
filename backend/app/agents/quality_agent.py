"""Agent 3 — Data Quality Agent. This is the one hard gate in the pipeline:
if data quality fails, the orchestrator must not proceed to trend analysis
on it (spec section 5's "must not silently analyze bad data")."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.services.events import StepRecorder
from app.tools import nasa_tools


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    await recorder.emit("DATA_QUALITY_AGENT", "running", "Checking temporal coverage, gaps, and outliers...")

    report = nasa_tools.validate_dataset(state.point_series, state.start_date, state.end_date)
    state.quality_report = report

    if not report.passed:
        state.status = "insufficient_data"
        await recorder.emit(
            "DATA_QUALITY_AGENT", "error",
            "Data quality checks failed — stopping before trend analysis: " + " ".join(report.issues),
            {"quality_report": report.__dict__},
        )
        return state

    msg = f"Data quality OK — {report.completeness:.0%} complete, {report.coverage_years:.1f} years, {report.n_outliers} outliers flagged."
    if report.issues:
        msg += " Minor issues noted: " + " ".join(report.issues)
    await recorder.emit("DATA_QUALITY_AGENT", "done", msg, {"quality_report": report.__dict__})
    return state
