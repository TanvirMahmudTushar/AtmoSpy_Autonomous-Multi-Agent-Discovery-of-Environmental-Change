"""Agent 5 — Spatial Agent. Determines WHERE change occurs, and specifically
looks for the case the challenge calls out: the same variable trending in
opposite directions in different places."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.nasa.base import NASAAdapterError
from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable
from app.nasa.regions import REGIONS_BY_CODE
from app.services.events import StepRecorder
from app.tools import analysis_tools, nasa_tools


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    var_info = VARIABLES_BY_CODE[state.plan.variable_code]
    dataset_code = dataset_code_for_variable(state.plan.variable_code)
    await recorder.emit(
        "SPATIAL_AGENT", "running",
        f"Sampling a spatial grid across {state.region.name} to check for regional differences...",
    )

    try:
        grid = await nasa_tools.query_nasa_grid_data(
            session, dataset_code, state.plan.variable_code, state.region, state.start_date, state.end_date
        )
        cell_trends = analysis_tools.calculate_spatial_trends(grid)
        opposite = analysis_tools.detect_opposite_regional_trends(cell_trends)
        state.grid_series = grid
        state.cell_trends = cell_trends
        state.opposite_trends = opposite
        state.timelapse = analysis_tools.calculate_spatial_timelapse(grid)

        if opposite["has_opposite_regional_trends"]:
            msg = (
                f"Found opposite regional trends within {state.region.name}: "
                f"{opposite['increasing_cells']} grid cells increasing, {opposite['decreasing_cells']} "
                f"decreasing (of {opposite['significant_cells']} statistically significant cells)."
            )
        else:
            msg = (
                f"Spatial pattern is consistent across {state.region.name}: "
                f"{opposite['increasing_cells']} increasing vs {opposite['decreasing_cells']} decreasing "
                f"significant cells — no strong opposite-direction split detected."
            )
        await recorder.emit("SPATIAL_AGENT", "done", msg, {"opposite_trends": opposite, "n_cells": len(cell_trends)})
    except NASAAdapterError as exc:
        await recorder.emit("SPATIAL_AGENT", "skipped", f"Spatial grid analysis skipped: {exc}")

    if state.plan.compare_region_code:
        await _compare_named_regions(session, recorder, state, var_info)

    return state


async def _compare_named_regions(session: AsyncSession, recorder: StepRecorder, state: InvestigationState, var_info) -> None:
    other_region = REGIONS_BY_CODE.get(state.plan.compare_region_code)
    if not other_region:
        return
    await recorder.emit(
        "SPATIAL_AGENT", "running", f"Comparing {state.region.name} against {other_region.name}...",
    )
    try:
        dataset_code = dataset_code_for_variable(state.plan.variable_code)
        other_series = await nasa_tools.query_nasa_data(
            session, dataset_code, state.plan.variable_code, other_region, state.start_date, state.end_date
        )
        other_years, other_values = analysis_tools.calculate_time_series(other_series, freq="annual")
        if len(other_years) < 5:
            await recorder.emit("SPATIAL_AGENT", "skipped", f"Not enough data for {other_region.name} to compare.")
            return
        other_trend = analysis_tools.calculate_trend(other_years, other_values)
        comparison = analysis_tools.compare_regions(state.trend_result, other_trend, state.region.name, other_region.name)
        state.compare_result = comparison

        opp = "opposite-signed" if comparison["opposite_signs"] else "same-signed"
        sig = "a statistically significant" if comparison["significantly_different"] else "not a statistically significant"
        await recorder.emit(
            "SPATIAL_AGENT", "done",
            f"{state.region.name} ({comparison['slope_a_per_year']:+.4g}/yr) vs {other_region.name} "
            f"({comparison['slope_b_per_year']:+.4g}/yr): {opp} difference, and {sig} difference "
            f"(p={comparison['p_value']:.4f}).",
            {"comparison": comparison},
        )
    except NASAAdapterError as exc:
        await recorder.emit("SPATIAL_AGENT", "skipped", f"Region comparison skipped: {exc}")
