"""Spatial Agent math: per-cell trends over a bounding-box grid, and
detection of regions where the same variable trends in opposite directions
— the central requirement called out in spec section 5 (Agent 5)."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy import stats

from app.analysis.trend import compute_trend
from app.nasa.base import GridCell


@dataclass
class CellTrend:
    lat: float
    lon: float
    n_years: int
    slope_per_year: float
    p_value: float
    significant: bool

    def to_dict(self) -> dict:
        return asdict(self)


def compute_cell_trends(cells: list[GridCell], alpha: float = 0.05) -> list[CellTrend]:
    results = []
    for cell in cells:
        years = [d.year for d in cell.dates]
        if len(years) < 5:
            continue
        try:
            trend = compute_trend(years, cell.values)
        except ValueError:
            continue
        results.append(
            CellTrend(
                lat=cell.lat,
                lon=cell.lon,
                n_years=trend.n_years,
                slope_per_year=trend.sen_slope_per_year,
                p_value=trend.mk_p_value,
                significant=trend.mk_p_value < alpha,
            )
        )
    return results


def detect_opposite_trends(cell_trends: list[CellTrend], alpha: float = 0.05) -> dict:
    sig = [c for c in cell_trends if c.p_value < alpha]
    increasing = [c for c in sig if c.slope_per_year > 0]
    decreasing = [c for c in sig if c.slope_per_year < 0]

    total = len(cell_trends)
    return {
        "total_cells": total,
        "significant_cells": len(sig),
        "increasing_cells": len(increasing),
        "decreasing_cells": len(decreasing),
        "increasing_fraction": round(len(increasing) / total, 3) if total else 0.0,
        "decreasing_fraction": round(len(decreasing) / total, 3) if total else 0.0,
        "has_opposite_regional_trends": len(increasing) > 0 and len(decreasing) > 0,
        "increasing_examples": [c.to_dict() for c in sorted(increasing, key=lambda c: c.p_value)[:5]],
        "decreasing_examples": [c.to_dict() for c in sorted(decreasing, key=lambda c: c.p_value)[:5]],
    }


def build_timelapse_frames(cells: list[GridCell], min_years: int = 5) -> dict:
    """Per-cell annual means, reshaped into one frame per year, for the
    time-lapse scrubber. Unlike compute_cell_trends (which needs enough
    points for a trend test), every cell with at least min_years of data
    contributes — the scrubber shows actual values, not trend significance.
    """
    per_cell_annual: list[tuple[float, float, dict[int, float]]] = []
    all_years: set[int] = set()

    for cell in cells:
        if not cell.dates:
            continue
        s = pd.Series(cell.values, index=pd.to_datetime(cell.dates))
        annual = s.resample("YE").mean().dropna()
        if len(annual) < min_years:
            continue
        year_map = {ts.year: float(v) for ts, v in annual.items()}
        per_cell_annual.append((cell.lat, cell.lon, year_map))
        all_years.update(year_map.keys())

    if not per_cell_annual:
        return {"years": [], "frames": {}, "value_min": None, "value_max": None}

    years_sorted = sorted(all_years)
    all_values = [v for _, _, year_map in per_cell_annual for v in year_map.values()]

    frames: dict[str, list[dict]] = {}
    for year in years_sorted:
        frames[str(year)] = [
            {"lat": lat, "lon": lon, "value": year_map[year]}
            for lat, lon, year_map in per_cell_annual
            if year in year_map
        ]

    return {
        "years": years_sorted,
        "frames": frames,
        "value_min": float(min(all_values)),
        "value_max": float(max(all_values)),
    }


def compare_regions(trend_a, trend_b, label_a: str, label_b: str) -> dict:
    """Statistically compare two independently-estimated OLS slopes via a
    two-sample z-test on the slope difference (Welch-style, using each
    slope's own standard error)."""
    diff = trend_a.ols_slope_per_year - trend_b.ols_slope_per_year
    se_diff = float(np.sqrt(trend_a.ols_std_err ** 2 + trend_b.ols_std_err ** 2))
    if se_diff == 0:
        z, p = 0.0, 1.0
    else:
        z = diff / se_diff
        p = 2 * (1 - stats.norm.cdf(abs(z)))

    return {
        "region_a": label_a,
        "region_b": label_b,
        "slope_a_per_year": trend_a.ols_slope_per_year,
        "slope_b_per_year": trend_b.ols_slope_per_year,
        "slope_difference": diff,
        "z_statistic": float(z),
        "p_value": float(p),
        "significantly_different": bool(p < 0.05),
        "opposite_signs": (trend_a.sen_slope_per_year > 0) != (trend_b.sen_slope_per_year > 0),
    }
