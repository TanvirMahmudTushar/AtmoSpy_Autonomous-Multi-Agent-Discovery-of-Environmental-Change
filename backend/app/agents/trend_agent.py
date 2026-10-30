"""Agent 4 — Temporal Trend Agent."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.nasa.catalog import VARIABLES_BY_CODE
from app.services.events import StepRecorder
from app.tools import analysis_tools

# Shorter records can't separate a trend from natural variability; the
# skeptic agent separately flags records under 15 years as short.
MIN_RECORD_YEARS = 8


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    await recorder.emit(
        "TREND_AGENT", "running",
        "Building monthly means, removing the seasonal cycle, and calculating the trend...",
    )

    bundle = analysis_tools.prepare_monthly(state.point_series)
    state.monthly = bundle
    state.years = [int(y) for y in bundle.annual.index]
    state.values = [float(v) for v in bundle.annual.values]

    if bundle.coverage_years < MIN_RECORD_YEARS or len(state.years) < 5:
        state.status = "insufficient_data"
        await recorder.emit(
            "TREND_AGENT", "error",
            f"Only {bundle.coverage_years:.1f} years of usable monthly data ({len(state.years)} complete years) — "
            f"at least {MIN_RECORD_YEARS} years are needed to separate a trend from natural variability.",
        )
        return state

    trend_result = analysis_tools.calculate_primary_trend(bundle)
    state.trend_result = trend_result
    state.seasonal_trends = analysis_tools.calculate_seasonal_trends(bundle)
    state.change_points = analysis_tools.detect_change_points(state.years, state.values)
    state.persistence = analysis_tools.calculate_persistence(state.years, state.values)

    var_info = VARIABLES_BY_CODE[state.plan.variable_code]
    direction = "increasing" if trend_result.sen_slope_per_year > 0 else "decreasing"
    pct = f", {trend_result.percent_change:+.1f}% total change" if trend_result.percent_change is not None else ""
    basis = (
        f"{trend_result.n_points} monthly anomalies, seasonal cycle removed"
        if trend_result.basis == "monthly_anomaly"
        else f"{trend_result.n_points} annual means"
    )
    await recorder.emit(
        "TREND_AGENT", "done",
        f"{var_info.name} is {direction} at {trend_result.slope_per_decade:+.4g} {var_info.units} per decade "
        f"(Sen's slope on {basis}){pct}. Found {len(state.change_points)} change point(s).",
        {
            "trend": trend_result.to_dict(),
            "seasonal_trends": state.seasonal_trends,
            "change_points": state.change_points,
            "persistence": state.persistence,
        },
    )
    return state
