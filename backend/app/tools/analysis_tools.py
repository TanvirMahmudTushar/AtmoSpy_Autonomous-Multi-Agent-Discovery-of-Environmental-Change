"""Tool surface the Temporal Trend, Spatial, Statistics, and Relationship
Agents call. Every function is a deterministic computation — no LLM
involvement, matching the spec's "LLM must not invent numbers" rule.
"""

import dataclasses

from app.analysis import changepoint, correlation, detectability, quality, significance, spatial, timeseries, trend
from app.core.config import get_settings
from app.nasa.base import GridSeries, PointSeries


def prepare_monthly(series: PointSeries) -> timeseries.MonthlyBundle:
    """Native samples -> monthly means -> climatology -> anomalies -> annual."""
    return timeseries.prepare(series.dates, series.values)


def calculate_time_series(point_series: PointSeries, freq: str = "annual") -> tuple[list[int], list[float]]:
    """Annual means built from monthly means (see timeseries.to_annual), so a
    year missing a seasonally extreme month isn't biased."""
    if freq != "annual":
        raise ValueError(f"Unsupported frequency: {freq}")
    if not point_series.dates:
        return [], []
    annual = prepare_monthly(point_series).annual
    return [int(y) for y in annual.index], [float(v) for v in annual.values]


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
    """Annual-basis trend (used for cross-checks and annual-only sources)."""
    return trend.compute_trend(years, values)


def calculate_primary_trend(bundle: timeseries.MonthlyBundle):
    return trend.primary_trend(bundle)


def calculate_seasonal_trends(bundle: timeseries.MonthlyBundle, min_years: int = 10) -> list[dict]:
    """Trend of each season's mean anomaly. Seasons often change at different
    rates (e.g. winters warming faster than summers)."""
    out = []
    for season in timeseries.SEASONS:
        s = timeseries.seasonal_means(bundle.anomalies.dropna(), season)
        if len(s) < min_years:
            continue
        t = trend.compute_trend(list(s.index), list(s.values))
        out.append({
            "season": season,
            "n_years": t.n_years,
            "slope_per_year": t.sen_slope_per_year,
            "slope_per_decade": t.slope_per_decade,
            "p_value": t.mk_p_value,
            "significant": t.mk_p_value < significance.ALPHA,
        })
    return out


def calculate_change_rate(trend_result) -> dict:
    return {"slope_per_year": trend_result.sen_slope_per_year, "method": "sen_slope"}


def calculate_percent_change(trend_result) -> float | None:
    return trend_result.percent_change


def detect_change_points(years: list[int], values: list[float]) -> list[dict]:
    return changepoint.detect_change_points(years, values)


def calculate_statistical_significance(trend_result, alpha: float = significance.ALPHA) -> dict:
    return {
        "p_value": trend_result.mk_p_value,
        "classification": significance.classify_significance(trend_result.mk_p_value, alpha),
        "alpha": alpha,
        "method": trend_result.primary_method,
        "basis": trend_result.basis,
        "t_test": {
            "p_value": trend_result.ols_p_value,
            "t_statistic": trend_result.ols_t,
            "n_eff": trend_result.n_eff,
            "lag1_autocorrelation": trend_result.lag1,
            "slope_ci": [trend_result.ols_ci_lower, trend_result.ols_ci_upper],
        },
        "cross_checks": {
            "mann_kendall_uncorrected_p": trend_result.mk_p_value_original,
            "mann_kendall_prewhitened_p": trend_result.mk_p_value_prewhitened,
            "seasonal_mann_kendall_p": trend_result.seasonal_mk_p_value,
        },
    }


def calculate_confidence_interval(trend_result, alpha: float = significance.ALPHA) -> dict:
    return {"lower": trend_result.sen_ci_lower, "upper": trend_result.sen_ci_upper, "confidence": 1 - alpha}


def calculate_detectability(trend_result) -> dict:
    return detectability.assess(trend_result)


def calculate_importance_note(trend_result) -> str:
    return significance.importance_note(trend_result.total_change, trend_result.std_dev, trend_result.percent_change)


def calculate_persistence(years: list[int], values: list[float]) -> dict:
    return trend.first_half_second_half_persistence(years, values)


def coarsen_for_map(grid_series: GridSeries) -> GridSeries:
    """At most MAX_SPATIAL_GRID_CELLS cells for the per-cell trend map."""
    cells = spatial.coarsen_cells(grid_series.cells, get_settings().MAX_SPATIAL_GRID_CELLS)
    return dataclasses.replace(grid_series, cells=cells) if cells is not grid_series.cells else grid_series


def calculate_spatial_trends(grid_series: GridSeries):
    return spatial.compute_cell_trends(grid_series.cells)


def detect_opposite_regional_trends(cell_trends) -> dict:
    return spatial.detect_opposite_trends(cell_trends)


def calculate_spatial_timelapse(grid_series: GridSeries) -> dict:
    return spatial.build_timelapse_frames(grid_series.cells)


def compare_regions(trend_a, trend_b, label_a: str, label_b: str) -> dict:
    return spatial.compare_regions(trend_a, trend_b, label_a, label_b)


def calculate_detrended_correlation(years: list[int], x: list[float], y: list[float]):
    return correlation.correlate_detrended(years, x, y)


def calculate_correlation(dates_a, values_a, dates_b, values_b):
    years, xa, xb = correlation.align_annual(dates_a, values_a, dates_b, values_b)
    return correlation.correlate(xa, xb, years)
