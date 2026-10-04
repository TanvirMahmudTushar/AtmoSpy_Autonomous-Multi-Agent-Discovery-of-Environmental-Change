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
        state.point_series = await nasa_tools.query_nasa_data(
            session, dataset_code, state.plan.variable_code, state.region, state.start_date, state.end_date
        )
    except NASAAdapterError as exc:
        state.status = "failed"
        state.error = str(exc)
        await recorder.emit("NASA_DATA_AGENT", "error", f"{dataset_name} request failed: {exc}")
        return state

    n = len(state.point_series.values)
    await recorder.emit(
        "NASA_DATA_AGENT", "done",
        f"Retrieved {n} observations from {dataset_name}.",
        {"source_url": state.point_series.source_url, "n_observations": n},
    )
    return state
