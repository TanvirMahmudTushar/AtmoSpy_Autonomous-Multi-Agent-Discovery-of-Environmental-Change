"""Agent 7 — Relationship Agent. Investigates other NASA POWER variables in
the same region/period for association with the seed variable. Always
reports findings as correlation, never causation (spec section 1/10)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.nasa.base import NASAAdapterError
from app.nasa.power import VARIABLES_BY_CODE
from app.services.events import StepRecorder
from app.tools import analysis_tools, nasa_tools

# Cap how many other variables we probe per investigation — keeps latency
# bounded and avoids fishing across so many variables that a spurious
# correlation becomes likely by chance alone.
MAX_CANDIDATES = 5
CORRELATION_ALPHA = 0.05
MIN_ABS_R = 0.3


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    candidates = [c for c in state.plan.candidate_related_variables if c != state.plan.variable_code][:MAX_CANDIDATES]
    await recorder.emit(
        "RELATIONSHIP_AGENT", "running",
        f"Checking {len(candidates)} other NASA POWER variables in {state.region.name} for association "
        f"with {VARIABLES_BY_CODE[state.plan.variable_code].name}...",
    )

    results = []
    for code in candidates:
        try:
            series = await nasa_tools.query_nasa_data(
                session, "NASA_POWER", code, state.region, state.start_date, state.end_date
            )
            years, values = analysis_tools.calculate_time_series(series, freq="annual")
            if len(years) < 5:
                continue
            corr = analysis_tools.calculate_correlation(
                [d for d in state.point_series.dates], state.point_series.values, series.dates, series.values
            )
            if corr is None:
                continue
            if abs(corr.r) >= MIN_ABS_R and corr.p_value < CORRELATION_ALPHA:
                results.append(
                    {
                        "variable_code": code,
                        "variable_name": VARIABLES_BY_CODE[code].name,
                        "units": VARIABLES_BY_CODE[code].units,
                        "method": corr.method,
                        "r": corr.r,
                        "p_value": corr.p_value,
                        "n": corr.n,
                        "aligned_years": corr.aligned_years,
                        "target_years": years,
                        "target_values": values,
                    }
                )
        except NASAAdapterError:
            continue

    results.sort(key=lambda r: abs(r["r"]), reverse=True)
    state.related_variables = results[:3]

    if state.related_variables:
        top = state.related_variables[0]
        msg = (
            f"{VARIABLES_BY_CODE[state.plan.variable_code].name} coincides with {top['variable_name']} "
            f"({top['method']} r={top['r']:.2f}, p={top['p_value']:.4f}) — a relationship worth further "
            "investigation, not evidence of causation."
        )
    else:
        msg = "No other NASA POWER variable showed a significant association (|r|>=0.3, p<0.05) in this region/period."
    await recorder.emit("RELATIONSHIP_AGENT", "done", msg, {"related_variables": state.related_variables})
    return state
