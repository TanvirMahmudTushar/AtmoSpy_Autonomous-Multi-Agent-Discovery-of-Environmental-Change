"""Tool surface the Report Agent calls to turn computed results into
chart payloads and narrative text."""

from app.llm.narrator import generate_narrative
from app.services.visualization import build_scatter, build_spatial_map, build_spatial_timelapse, build_timeseries_chart

generate_time_series_chart = build_timeseries_chart
generate_spatial_map = build_spatial_map
generate_spatial_timelapse = build_spatial_timelapse
generate_relationship_scatter = build_scatter


async def create_investigation_report(facts: dict) -> dict:
    """facts must contain only already-computed values; see
    app.llm.narrator.generate_narrative for the guardrail against
    LLM-fabricated numbers."""
    return await generate_narrative(facts)
