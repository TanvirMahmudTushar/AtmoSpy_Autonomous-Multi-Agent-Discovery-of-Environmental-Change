"""Tool surface the Temporal Trend, Spatial, Statistics, and Relationship
Agents call. Every function is a deterministic computation — no LLM
involvement, matching the spec's "LLM must not invent numbers" rule.
"""

import pandas as pd

from app.analysis import changepoint, correlation, quality, significance, spatial, trend
from app.nasa.base import GridSeries, PointSeries


def calculate_time_series(point_series: PointSeries, freq: str = "annual") -> tuple[list[int], list[float]]:
    """Aggregates a daily (or monthly) point series to annual means using
    pandas — the standard way to remove seasonal noise before trend testing.
    """
    if not point_series.dates:
        return [], []
    s = pd.Series(point_series.values, index=pd.to_datetime(point_series.dates))
    if freq == "annual":
        annual = s.resample("YE").mean().dropna()
        years = [ts.year for ts in annual.index]
        values = [float(v) for v in annual.values]
        return years, values
    raise ValueError(f"Unsupported frequency: {freq}")


def validate_dataset(point_series: PointSeries, requested_start, requested_end, valid_min=None, valid_max=None):
    return quality.assess_quality(
        dates=point_series.dates,
        values=point_series.values,
        missing_dates=point_series.missing_dates,
        requested_start=requested_start,
        requested_end=requested_end,
        valid_min=valid_min,
        valid_max=valid_max,
    )


def calculate_trend(years: list[int], values: list[float]):
    return trend.compute_trend(years, values)


def calculate_trend_band(years: list[int], values: list[float], trend_result) -> list[dict]:
    return trend.bootstrap_trend_band(years, values, trend_result)


def calculate_change_rate(trend_result) -> dict:
    return {"slope_per_year": trend_result.sen_slope_per_year, "method": "sen_slope"}


def calculate_percent_change(trend_result) -> float | None:
    return trend_result.percent_change


def detect_change_points(years: list[int], values: list[float]) -> list[dict]:
    return changepoint.detect_change_points(years, values)


def calculate_statistical_significance(trend_result, alpha: float = 0.05) -> dict:
    return {
        "p_value": trend_result.mk_p_value,
        "classification": significance.classify_significance(trend_result.mk_p_value, alpha),
        "alpha": alpha,
        "method": "mann_kendall",
    }


def calculate_confidence_interval(years: list[int], values: list[float], alpha: float = 0.05) -> dict:
    return trend.sen_slope_confidence_interval(years, values, alpha)


def calculate_importance_note(trend_result) -> str:
    return significance.importance_note(trend_result.total_change, trend_result.std_dev, trend_result.percent_change)


def calculate_persistence(years: list[int], values: list[float]) -> dict:
    return trend.first_half_second_half_persistence(years, values)


def calculate_spatial_trends(grid_series: GridSeries, alpha: float = 0.05):
    return spatial.compute_cell_trends(grid_series.cells, alpha)


def detect_opposite_regional_trends(cell_trends, alpha: float = 0.05) -> dict:
    return spatial.detect_opposite_trends(cell_trends, alpha)


def calculate_spatial_timelapse(grid_series: GridSeries) -> dict:
    return spatial.build_timelapse_frames(grid_series.cells)


def compare_regions(trend_a, trend_b, label_a: str, label_b: str) -> dict:
    return spatial.compare_regions(trend_a, trend_b, label_a, label_b)


def calculate_correlation(dates_a, values_a, dates_b, values_b):
    years, xa, xb = correlation.align_annual(dates_a, values_a, dates_b, values_b)
    return correlation.correlate(xa, xb, years)
