"""Agent 7 — Relationship Agent. Investigates other variables in the same
region/period for association with the seed variable. Always reports
findings as correlation, never causation (spec section 1/10).

Correlations are computed on detrended annual anomalies of the two regional
series (see analysis/correlation.correlate_detrended), and the candidates'
p-values are adjusted for testing several at once (Benjamini-Hochberg).
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.analysis.spatial import benjamini_hochberg
from app.db.session import AsyncSessionLocal
from app.nasa.base import NASAAdapterError
from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable
from app.services.events import StepRecorder
from app.tools import analysis_tools, nasa_tools

# Cap how many other variables we probe per investigation — keeps latency
# bounded and the multiple-testing burden small.
logger = logging.getLogger(__name__)

MAX_CANDIDATES = 5
CORRELATION_ALPHA = 0.05
MIN_ABS_R = 0.3


def _candidates(state: InvestigationState) -> list[str]:
    seed = state.plan.variable_code
    return [c for c in state.plan.candidate_related_variables if c != seed and c in VARIABLES_BY_CODE][:MAX_CANDIDATES]


async def _fetch(code: str, region, start, end):
    """One candidate's regional series, or None. Own DB session: an
    AsyncSession can't be shared between concurrent tasks (the NASA cache
    layer still caps simultaneous upstream requests)."""
    try:
        async with AsyncSessionLocal() as s:
            return (await nasa_tools.query_region_series(s, dataset_code_for_variable(code), code, region, start, end)).series
    except NASAAdapterError:
        return None
    except Exception:  # noqa: BLE001 - a prefetch must never take the investigation down
        logger.exception("Prefetch of %s failed", code)
        return None


def start_prefetch(state: InvestigationState) -> None:
    """Start fetching the candidate variables now, in the background, so the
    downloads overlap the main data fetch and statistics instead of waiting
    for them. Keyed by period: a widened retry fetches its own window."""
    key = (state.start_date, state.end_date)
    for code in _candidates(state):
        if (code, *key) not in state.related_prefetch:
            state.related_prefetch[(code, *key)] = asyncio.create_task(
                _fetch(code, state.region, state.start_date, state.end_date)
            )


def cancel_prefetch(state: InvestigationState) -> None:
    for task in state.related_prefetch.values():
        task.cancel()


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    seed = VARIABLES_BY_CODE[state.plan.variable_code]
    candidates = _candidates(state)
    start_prefetch(state)  # no-op for candidates already prefetched for this period
    await recorder.emit(
        "RELATIONSHIP_AGENT", "running",
        f"Checking {len(candidates)} other variables in {state.region.name} for year-to-year association "
        f"with {seed.name} (trends removed first)...",
    )

    seed_years, seed_values = state.years, state.values
    seed_by_year = dict(zip(seed_years, seed_values))

    async def test_one(code: str):
        series = await state.related_prefetch[(code, state.start_date, state.end_date)]
        if series is None:
            return None
        years, values = analysis_tools.calculate_time_series(series, freq="annual")
        target = dict(zip(years, values))
        common = [y for y in seed_years if y in target]
        corr, dx, dy = analysis_tools.calculate_detrended_correlation(
            common, [seed_by_year[y] for y in common], [target[y] for y in common]
        )
        return None if corr is None else (code, corr, common, dx, dy)

    tested = [t for t in await asyncio.gather(*(test_one(c) for c in candidates)) if t is not None]

    q_values = benjamini_hochberg([corr.p_value for _, corr, *_ in tested])
    results = []
    for (code, corr, common, dx, dy), q in zip(tested, q_values):
        if abs(corr.r) >= MIN_ABS_R and q < CORRELATION_ALPHA:
            info = VARIABLES_BY_CODE[code]
            results.append({
                "variable_code": code,
                "variable_name": info.name,
                "units": info.units,
                "method": f"{corr.method} on detrended annual anomalies",
                "r": corr.r,
                "p_value": corr.p_value,
                "q_value": float(q),
                "n": corr.n,
                "aligned_years": corr.aligned_years,
                # what was actually correlated, for the scatter plot
                "target_years": common,
                "seed_anomalies": [float(v) for v in dx],
                "target_anomalies": [float(v) for v in dy],
            })

    results.sort(key=lambda r: abs(r["r"]), reverse=True)
    state.related_variables = results[:3]

    if state.related_variables:
        top = state.related_variables[0]
        msg = (
            f"In years when {seed.name} is unusually high or low, {top['variable_name']} tends to be too "
            f"({top['method']}, r={top['r']:.2f}, p={top['p_value']:.4f} before and q={top['q_value']:.4f} after "
            f"correcting for {len(tested)} tests) — an association worth investigating, not evidence of causation."
        )
    else:
        msg = (
            f"None of the {len(tested)} variables tested moved together with {seed.name} from year to year "
            "(|r| >= 0.3 after removing trends and correcting for multiple tests)."
        )
    await recorder.emit("RELATIONSHIP_AGENT", "done", msg, {"related_variables": state.related_variables})
    return state
