"""Builds chart-ready JSON payloads (consumed directly by Recharts/MapLibre
on the frontend). These functions only reshape numbers that analysis/*
already computed — they never compute new statistics themselves.
"""

from app.analysis.spatial import CellTrend
from app.analysis.trend import TrendResult


def build_timeseries_chart(
    years: list[int],
    values: list[float],
    trend: TrendResult,
    change_points: list[dict],
    variable_name: str,
    units: str,
    trend_band: list[dict] | None = None,
) -> dict:
    # pymannkendall's Sen's-slope intercept is fit against a 0-based sample
    # index (0, 1, 2, ...), not the calendar year itself — so the fitted
    # value must be evaluated at that same index, not at `year`.
    fitted_line = [
        {"year": y, "fitted": trend.sen_intercept + trend.sen_slope_per_year * i} for i, y in enumerate(years)
    ]
    return {
        "kind": "timeseries",
        "variable_name": variable_name,
        "units": units,
        "points": [{"year": y, "value": v} for y, v in zip(years, values)],
        "trend_line": fitted_line,
        "trend_band": trend_band or [],
        "change_points": change_points,
        "trend_summary": {
            "slope_per_year": trend.sen_slope_per_year,
            "p_value": trend.mk_p_value,
            "method": trend.primary_method,
        },
    }


def build_spatial_map(cell_trends: list[CellTrend], variable_name: str, units: str) -> dict:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [c.lon, c.lat]},
            "properties": {
                "slope_per_year": c.slope_per_year,
                "p_value": c.p_value,
                "significant": c.significant,
                "direction": "increasing" if c.slope_per_year > 0 else "decreasing",
            },
        }
        for c in cell_trends
    ]
    return {
        "kind": "spatial_map",
        "variable_name": variable_name,
        "units": units,
        "type": "FeatureCollection",
        "features": features,
    }


def build_spatial_timelapse(timelapse: dict, variable_name: str, units: str) -> dict:
    frames = {
        year: {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                    "properties": {"value": p["value"]},
                }
                for p in points
            ],
        }
        for year, points in timelapse["frames"].items()
    }
    return {
        "kind": "spatial_timelapse",
        "variable_name": variable_name,
        "units": units,
        "years": timelapse["years"],
        "value_min": timelapse["value_min"],
        "value_max": timelapse["value_max"],
        "frames": frames,
    }


def build_scatter(
    years: list[int],
    x_values: list[float],
    y_values: list[float],
    x_name: str,
    y_name: str,
    correlation: dict,
) -> dict:
    return {
        "kind": "scatter",
        "x_name": x_name,
        "y_name": y_name,
        "points": [{"year": y, "x": x, "y": val} for y, x, val in zip(years, x_values, y_values)],
        "correlation": correlation,
    }
