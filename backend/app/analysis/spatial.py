"""Spatial Agent math: per-cell trends over a bounding-box grid, and
detection of regions where the same variable trends in opposite directions
— the central requirement called out in spec section 5 (Agent 5).

Testing every grid cell at p < 0.05 guarantees false positives (100 cells
with no trend at all yield ~5 'significant' ones). Cell significance is
therefore controlled with the Benjamini-Hochberg false discovery rate at
alpha_FDR = 0.10, as recommended for spatially correlated climate fields
by Wilks (2016, BAMS 97:2263).
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy import stats

from app.analysis import timeseries
from app.analysis.trend import compute_trend, primary_trend
from app.nasa.base import GridCell

ALPHA_FDR = 0.10
MIN_MONTHS = 36
MIN_YEARS = 5


@dataclass
class CellTrend:
    lat: float
    lon: float
    n_years: int
    slope_per_year: float
    p_value: float  # per-cell, autocorrelation corrected
    significant: bool  # after false-discovery-rate control
    q_value: float = 1.0  # BH-adjusted p-value

    def to_dict(self) -> dict:
        return asdict(self)


def benjamini_hochberg(p_values: list[float]) -> np.ndarray:
    """BH-adjusted p-values (q-values): q_(i) = min_{k>=i} p_(k) * m / k."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(m)
    q[order] = np.minimum(q_sorted, 1.0)
    return q


def _cell_trend(cell: GridCell):
    if not cell.dates:
        return None
    if timeseries.infer_cadence(cell.dates) == "annual":
        years = [d.year for d in cell.dates]
        if len(years) < MIN_YEARS:
            return None
        return compute_trend(years, cell.values)
    bundle = timeseries.prepare(cell.dates, cell.values)
    if bundle.valid_months < MIN_MONTHS or len(bundle.annual) < MIN_YEARS:
        return None
    return primary_trend(bundle, seasonal_test=False)


def compute_cell_trends(cells: list[GridCell], alpha_fdr: float = ALPHA_FDR) -> list[CellTrend]:
    rows = []
    for cell in cells:
        try:
            trend = _cell_trend(cell)
        except ValueError:
            continue
        if trend is not None:
            rows.append((cell, trend))

    q_values = benjamini_hochberg([t.mk_p_value for _, t in rows])
    return [
        CellTrend(
            lat=cell.lat,
            lon=cell.lon,
            n_years=trend.n_years,
            slope_per_year=trend.sen_slope_per_year,
            p_value=trend.mk_p_value,
            significant=bool(q <= alpha_fdr),
            q_value=float(q),
        )
        for (cell, trend), q in zip(rows, q_values)
    ]


def detect_opposite_trends(cell_trends: list[CellTrend]) -> dict:
    """Counts cells whose trend survives FDR control in each direction, with
    cos(latitude) area weights so high-latitude cells don't count as much
    as equatorial ones."""
    sig = [c for c in cell_trends if c.significant]
    increasing = [c for c in sig if c.slope_per_year > 0]
    decreasing = [c for c in sig if c.slope_per_year < 0]

    def area(cs: list[CellTrend]) -> float:
        return float(sum(np.cos(np.radians(c.lat)) for c in cs))

    total = len(cell_trends)
    total_area = area(cell_trends)
    return {
        "total_cells": total,
        "significant_cells": len(sig),
        "increasing_cells": len(increasing),
        "decreasing_cells": len(decreasing),
        "increasing_fraction": round(len(increasing) / total, 3) if total else 0.0,
        "decreasing_fraction": round(len(decreasing) / total, 3) if total else 0.0,
        "increasing_area_fraction": round(area(increasing) / total_area, 3) if total_area else 0.0,
        "decreasing_area_fraction": round(area(decreasing) / total_area, 3) if total_area else 0.0,
        "has_opposite_regional_trends": len(increasing) > 0 and len(decreasing) > 0,
        "significance_control": f"benjamini_hochberg_fdr_{ALPHA_FDR}",
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
    two-sample z-test on the slope difference, using each slope's
    autocorrelation-inflated standard error (n_eff)."""
    diff = trend_a.ols_slope_per_year - trend_b.ols_slope_per_year
    se_diff = float(np.sqrt(trend_a.ols_std_err ** 2 + trend_b.ols_std_err ** 2))
    if se_diff == 0 or not np.isfinite(se_diff):
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
