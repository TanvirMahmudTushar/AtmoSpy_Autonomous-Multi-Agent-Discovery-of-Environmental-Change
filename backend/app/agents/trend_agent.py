"""Agent 4 — Temporal Trend Agent."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.nasa.catalog import VARIABLES_BY_CODE
from app.services.events import StepRecorder
from app.tools import analysis_tools


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    await recorder.emit("TREND_AGENT", "running", "Aggregating to annual series and calculating trend...")

    years, values = analysis_tools.calculate_time_series(state.point_series, freq="annual")
    state.years, state.values = years, values

    if len(years) < 5:
        state.status = "insufficient_data"
        await recorder.emit(
            "TREND_AGENT", "error",
            f"Only {len(years)} annual data points available after aggregation — too few for a trend estimate.",
        )
        return state

    trend_result = analysis_tools.calculate_trend(years, values)
    state.trend_result = trend_result
    state.change_points = analysis_tools.detect_change_points(years, values)
    state.persistence = analysis_tools.calculate_persistence(years, values)
    state.trend_band = analysis_tools.calculate_trend_band(years, values, trend_result)

    var_info = VARIABLES_BY_CODE[state.plan.variable_code]
    direction = "increasing" if trend_result.sen_slope_per_year > 0 else "decreasing"
    pct = f", {trend_result.percent_change:+.1f}% total change" if trend_result.percent_change is not None else ""
    await recorder.emit(
        "TREND_AGENT", "done",
        f"{var_info.name} is {direction} at {trend_result.sen_slope_per_year:+.4g} {var_info.units}/year "
        f"(Sen's slope, {trend_result.n_years} years){pct}. Found {len(state.change_points)} change point(s).",
        {
            "trend": trend_result.to_dict(),
            "change_points": state.change_points,
            "persistence": state.persistence,
        },
    )
    return state
