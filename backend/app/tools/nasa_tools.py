"""Tool surface the NASA Data Agent and Data Quality Agent call. Each
function here is a real operation (an HTTP call, a cache lookup, a
validation), never a stand-in the LLM "pretends" to run.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.quality import QualityReport, assess_quality
from app.nasa.base import GridSeries, PointSeries
from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable
from app.nasa.regions import RegionDef
from app.nasa.registry import get_adapter, list_dataset_metadata
from app.services import nasa_cache


def search_nasa_datasets() -> list[dict]:
    """Lists every registered NASA data source (active + planned), honestly
    flagging which ones require credentials this deployment doesn't have."""
    return [
        {
            "code": d.code,
            "name": d.name,
            "provider": d.provider,
            "status": d.status,
            "requires_credentials": d.requires_credentials,
            "variables": [v.code for v in d.variables],
        }
        for d in list_dataset_metadata()
    ]


def get_dataset_metadata(dataset_code: str) -> dict:
    info = get_adapter(dataset_code).get_metadata()
    return {
        "code": info.code,
        "name": info.name,
        "provider": info.provider,
        "description": info.description,
        "base_url": info.base_url,
        "version": info.version,
        "status": info.status,
        "variables": [
            {"code": v.code, "name": v.name, "units": v.units, "description": v.description}
            for v in info.variables
        ],
    }


async def query_nasa_data(
    session: AsyncSession, dataset_code: str, variable: str, region: RegionDef, start: date, end: date
) -> PointSeries:
    """Daily point time series at the region's centroid. Daily (not
    pre-aggregated) resolution is fetched deliberately so the Data Quality
    Agent can assess real gap/completeness/outlier structure; the Temporal
    Trend Agent then aggregates this to annual via calculate_time_series."""
    return await nasa_cache.get_point_series(
        session, dataset_code, variable, region.centroid_lat, region.centroid_lon, start, end, temporal="daily"
    )


async def query_nasa_grid_data(
    session: AsyncSession, dataset_code: str, variable: str, region: RegionDef, start: date, end: date
) -> GridSeries:
    """Grid of point series across the region's bounding box — used by the
    Spatial Agent."""
    return await nasa_cache.get_grid_series(
        session, dataset_code, variable, region.min_lat, region.max_lat, region.min_lon, region.max_lon, start, end
    )


def validate_dataset(point_series: PointSeries, requested_start: date, requested_end: date) -> QualityReport:
    var_info = VARIABLES_BY_CODE.get(point_series.variable)
    dataset_code = dataset_code_for_variable(point_series.variable)
    resolution_days = get_adapter(dataset_code).get_metadata().temporal_resolution_days
    return assess_quality(
        dates=point_series.dates,
        values=point_series.values,
        missing_dates=point_series.missing_dates,
        requested_start=requested_start,
        requested_end=requested_end,
        valid_min=var_info.valid_min if var_info else None,
        valid_max=var_info.valid_max if var_info else None,
        expected_interval_days=resolution_days,
    )
