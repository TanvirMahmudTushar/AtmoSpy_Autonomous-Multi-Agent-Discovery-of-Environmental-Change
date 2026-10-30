"""Agent 2 — NASA Data Agent: resolves the plan into an actual NASA data
source query and retrieves the real observation series. Which source is
queried is derived from the requested variable (app.nasa.catalog), not
hardcoded — this is the only active source today (NASA POWER), but the
pipeline doesn't assume that."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.nasa.base import NASAAdapterError
from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable
from app.nasa.registry import get_adapter
from app.services.events import StepRecorder
from app.tools import nasa_tools


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    var_info = VARIABLES_BY_CODE[state.plan.variable_code]
    dataset_code = dataset_code_for_variable(state.plan.variable_code)
    dataset_name = get_adapter(dataset_code).get_metadata().name
    await recorder.emit(
        "NASA_DATA_AGENT", "running",
        f"Querying {dataset_name} for {var_info.name} ({var_info.code}) over {state.region.name}, "
        f"{state.plan.start_year}-{state.plan.end_year}...",
    )
    try:
        regional = await nasa_tools.query_region_series(
            session, dataset_code, state.plan.variable_code, state.region, state.start_date, state.end_date
        )
    except NASAAdapterError as exc:
        state.status = "failed"
        state.error = str(exc)
        await recorder.emit("NASA_DATA_AGENT", "error", f"{dataset_name} request failed: {exc}")
        return state

    state.point_series = regional.series
    state.grid_series = regional.grid
    state.sampling = regional.sampling

    n = len(state.point_series.values)
    if regional.sampling["method"] == "area_mean":
        how = (
            f"Averaged {regional.sampling['n_cells']} grid cells over {state.region.name} "
            f"(weighted by area) into {n} monthly values."
        )
    else:
        how = (
            f"Retrieved {n} observations at the centre of {state.region.name} "
            f"(no regional grid: {regional.sampling['reason']})."
        )
    await recorder.emit(
        "NASA_DATA_AGENT", "done",
        f"{how} Source: {dataset_name}.",
        {"source_url": state.point_series.source_url, "n_observations": n, "sampling": regional.sampling},
    )
    return state
