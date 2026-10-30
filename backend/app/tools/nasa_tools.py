"""Tool surface the NASA Data Agent and Data Quality Agent call. Each
function here is a real operation (an HTTP call, a cache lookup, a
validation), never a stand-in the LLM "pretends" to run.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.quality import QualityReport, assess_quality
from app.analysis.spatial import regional_mean
from app.analysis.timeseries import infer_cadence
from app.nasa.base import GridSeries, NASAAdapterError, PointSeries
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
    """Daily point time series at the region's centroid — the fallback when
    no grid is available for the region (see query_region_series)."""
    return await nasa_cache.get_point_series(
        session, dataset_code, variable, region.centroid_lat, region.centroid_lon, start, end, temporal="daily"
    )


@dataclass
class RegionalData:
    series: PointSeries  # what the trend is computed on
    grid: GridSeries | None  # reused by the Spatial Agent, so the region is fetched once
    sampling: dict  # how `series` represents the region, recorded in provenance


async def query_region_series(
    session: AsyncSession, dataset_code: str, variable: str, region: RegionDef, start: date, end: date
) -> RegionalData:
    """The region's area-weighted mean series, from one grid fetch. A
    region's trend is the trend of the whole box, not of its centre point —
    the two can differ, and even disagree in sign. Falls back to the
    centroid point only when the source can't give a monthly grid for the
    box (e.g. NASA POWER caps grid requests at 10 degrees)."""
    grid, reason = None, ""
    try:
        grid = await query_nasa_grid_data(session, dataset_code, variable, region, start, end)
    except NASAAdapterError as exc:
        reason = str(exc)

    if grid and grid.cells and infer_cadence(grid.cells[0].dates) != "annual":
        mean = regional_mean(grid.cells)
        if mean.dates:
            series = PointSeries(
                variable=variable, units=grid.units, lat=region.centroid_lat, lon=region.centroid_lon,
                dates=mean.dates, values=mean.values, missing_dates=mean.missing_dates,
                source_url=grid.source_url, retrieved_at=grid.retrieved_at,
            )
            return RegionalData(series, grid, {
                "method": "area_mean",
                "n_cells": mean.n_cells,
                "mean_valid_area_fraction": round(mean.mean_valid_area_fraction, 3),
            })
        reason = "no time step had enough of the region covered by data"
    elif grid is not None and not reason:
        reason = "the source returned no usable monthly grid for this box"

    point = await query_nasa_data(session, dataset_code, variable, region, start, end)
    return RegionalData(point, grid, {"method": "centroid_point", "reason": reason})


async def query_nasa_grid_data(
    session: AsyncSession, dataset_code: str, variable: str, region: RegionDef, start: date, end: date
) -> GridSeries:
    """Grid of point series across the region's bounding box — used by the
    Spatial Agent."""
    return await nasa_cache.get_grid_series(
        session, dataset_code, variable, region.min_lat, region.max_lat, region.min_lon, region.max_lon, start, end
    )


CADENCE_DAYS = {"daily": 1.0, "monthly": 30.44, "annual": 365.25}


def validate_dataset(point_series: PointSeries, requested_start: date, requested_end: date) -> QualityReport:
    """Completeness is judged against the series' own cadence: a monthly
    regional mean built from a daily source is complete at one value per
    month, not one per day."""
    var_info = VARIABLES_BY_CODE.get(point_series.variable)
    if point_series.dates:
        resolution_days = CADENCE_DAYS[infer_cadence(point_series.dates)]
    else:
        resolution_days = get_adapter(dataset_code_for_variable(point_series.variable)).get_metadata().temporal_resolution_days
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
