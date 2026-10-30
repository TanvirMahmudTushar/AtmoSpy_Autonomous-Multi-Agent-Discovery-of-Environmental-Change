"""Builds chart-ready JSON payloads (consumed directly by Recharts/MapLibre
on the frontend). These functions only reshape numbers that analysis/*
already computed — they never compute new statistics themselves.
"""

import math

import numpy as np

from app.analysis import timeseries
from app.analysis.spatial import CellTrend
from app.analysis.trend import TrendResult, annual_display_offset, ci_band, fitted


def _num(v) -> float | None:
    """JSON-safe float: NaN/inf become null."""
    v = float(v)
    return None if math.isnan(v) or math.isinf(v) else v


def _monthly_payload(bundle: timeseries.MonthlyBundle, trend: TrendResult) -> dict:
    idx = bundle.monthly.index
    x = timeseries.decimal_year(idx)
    clim = bundle.climatology[idx.month - 1]
    payload = {
        "dates": [d.strftime("%Y-%m") for d in idx],
        "raw": [_num(v) for v in bundle.monthly.values],
        "climatology": [_num(v) for v in clim],
        "anomaly": [_num(v) for v in bundle.anomalies.values],
        "climatology_by_month": [_num(v) for v in bundle.climatology],
    }
    if trend.basis == "monthly_anomaly":
        lo, hi = ci_band(trend, x)
        payload["fitted"] = [_num(v) for v in fitted(trend, x)]
        payload["ci_lower"] = [_num(v) for v in lo]
        payload["ci_upper"] = [_num(v) for v in hi]
    return payload


def build_timeseries_chart(
    years: list[int],
    values: list[float],
    trend: TrendResult,
    change_points: list[dict],
    variable_name: str,
    units: str,
    monthly: timeseries.MonthlyBundle | None = None,
) -> dict:
    # The trend is fit in calendar time; for an anomaly-basis trend, shift it
    # back onto the annual means (level = long-term mean, years at mid-year).
    level, x_shift = annual_display_offset(trend)
    x = np.asarray(years, dtype=float) + x_shift
    line = level + fitted(trend, x)
    lo, hi = ci_band(trend, x)
    chart = {
        "kind": "timeseries",
        "variable_name": variable_name,
        "units": units,
        "basis": trend.basis,
        "points": [{"year": y, "value": v} for y, v in zip(years, values)],
        # finite by construction (finite slope, intercept and CI)
        "trend_line": [{"year": y, "fitted": float(f)} for y, f in zip(years, line)],
        "trend_band": [{"year": y, "lower": float(level + a), "upper": float(level + b)} for y, a, b in zip(years, lo, hi)],
        "change_points": change_points,
        "trend_summary": {
            "slope_per_year": trend.sen_slope_per_year,
            "slope_per_decade": trend.slope_per_decade,
            "p_value": trend.mk_p_value,
            "method": trend.primary_method,
        },
    }
    if monthly is not None:
        chart["monthly"] = _monthly_payload(monthly, trend)
    return chart


def build_spatial_map(cell_trends: list[CellTrend], variable_name: str, units: str) -> dict:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [c.lon, c.lat]},
            "properties": {
                "slope_per_year": c.slope_per_year,
                "p_value": c.p_value,
                "q_value": c.q_value,
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
