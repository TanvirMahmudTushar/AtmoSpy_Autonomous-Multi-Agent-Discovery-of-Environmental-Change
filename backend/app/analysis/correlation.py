"""Correlation between two aligned annual time series.

Used by the Relationship Agent. Results are reported with explicit
correlation-language guardrails applied downstream (never as causation).
"""

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
from scipy import stats


@dataclass
class CorrelationResult:
    method: str  # "pearson" | "spearman"
    r: float
    p_value: float
    n: int
    aligned_years: list[int]

    def to_dict(self) -> dict:
        return asdict(self)


def align_annual(dates_a: list[date], values_a: list[float], dates_b: list[date], values_b: list[float]):
    years_a = {d.year: v for d, v in zip(dates_a, values_a)}
    years_b = {d.year: v for d, v in zip(dates_b, values_b)}
    common = sorted(set(years_a) & set(years_b))
    return common, [years_a[y] for y in common], [years_b[y] for y in common]


def correlate(x: list[float], y: list[float], years: list[int]) -> CorrelationResult | None:
    if len(x) < 5:
        return None

    xa, ya = np.asarray(x), np.asarray(y)
    # Choose Pearson only if both series pass a normality screen; otherwise
    # fall back to the rank-based Spearman correlation, which makes no
    # distributional assumption.
    normal = True
    for series in (xa, ya):
        if len(series) >= 8:
            _, p_norm = stats.shapiro(series)
            if p_norm < 0.05:
                normal = False
    method = "pearson" if normal else "spearman"

    if method == "pearson":
        r, p = stats.pearsonr(xa, ya)
    else:
        r, p = stats.spearmanr(xa, ya)

    return CorrelationResult(method=method, r=float(r), p_value=float(p), n=len(x), aligned_years=years)
