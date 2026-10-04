"""Deterministic trend statistics. No LLM involvement anywhere in this file —
every number returned here is produced by NumPy/SciPy/pymannkendall.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pymannkendall as mk
from scipy import stats


@dataclass
class TrendResult:
    n_years: int
    start_year: int
    end_year: int
    mean_value: float
    std_dev: float

    ols_slope_per_year: float
    ols_intercept: float
    ols_r_squared: float
    ols_p_value: float
    ols_std_err: float

    mk_trend: str  # "increasing" | "decreasing" | "no trend"
    mk_p_value: float
    mk_z: float
    mk_tau: float
    sen_slope_per_year: float
    sen_intercept: float

    total_change: float
    percent_change: float | None
    primary_method: str  # "mann_kendall_sen_slope" | "ols_regression"

    def to_dict(self) -> dict:
        return asdict(self)


def compute_trend(years: list[int], values: list[float]) -> TrendResult:
    """Compute OLS regression AND Mann-Kendall/Sen's-slope trend statistics.

    Mann-Kendall + Sen's slope is the primary reported method because it is
    non-parametric (robust to non-normal, autocorrelated environmental data)
    and is the standard method used in IPCC/USGS trend-detection literature.
    OLS is computed alongside for interpretability/comparison.
    """
    if len(years) < 4:
        raise ValueError("At least 4 annual data points are required to compute a trend.")

    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)

    ols = stats.linregress(x, y)

    mk_result = mk.original_test(y)

    n_years = int(years[-1] - years[0])
    total_change_sen = mk_result.slope * n_years
    mean_value = float(np.mean(y))
    percent_change = (total_change_sen / abs(mean_value) * 100) if mean_value != 0 else None

    primary_method = "mann_kendall_sen_slope"

    return TrendResult(
        n_years=len(years),
        start_year=int(years[0]),
        end_year=int(years[-1]),
        mean_value=mean_value,
        std_dev=float(np.std(y, ddof=1)) if len(y) > 1 else 0.0,
        ols_slope_per_year=float(ols.slope),
        ols_intercept=float(ols.intercept),
        ols_r_squared=float(ols.rvalue ** 2),
        ols_p_value=float(ols.pvalue),
        ols_std_err=float(ols.stderr),
        mk_trend=mk_result.trend,
        mk_p_value=float(mk_result.p),
        mk_z=float(mk_result.z),
        mk_tau=float(mk_result.Tau),
        sen_slope_per_year=float(mk_result.slope),
        sen_intercept=float(mk_result.intercept),
        total_change=float(total_change_sen),
        percent_change=percent_change,
        primary_method=primary_method,
    )


def sen_slope_confidence_interval(years: list[int], values: list[float], alpha: float = 0.05) -> dict:
    """95% confidence interval for Sen's slope via pymannkendall's built-in estimator."""
    y = np.asarray(values, dtype=float)
    result = mk.original_test(y, alpha=alpha)
    # pymannkendall does not expose the CI directly on original_test; derive it
    # from the Kendall/Theil-Sen pairwise-slope distribution.
    n = len(y)
    x = np.asarray(years, dtype=float)
    slopes = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            if x[j] != x[i]:
                slopes.append((y[j] - y[i]) / (x[j] - x[i]))
    slopes = np.sort(np.asarray(slopes))
    if len(slopes) == 0:
        return {"lower": result.slope, "upper": result.slope, "confidence": 1 - alpha}
    z = stats.norm.ppf(1 - alpha / 2)
    var_s = result.var_s
    c_alpha = z * np.sqrt(var_s)
    m1 = int(round((len(slopes) - c_alpha) / 2))
    m2 = int(round((len(slopes) + c_alpha) / 2)) + 1
    m1 = max(0, min(m1, len(slopes) - 1))
    m2 = max(0, min(m2, len(slopes) - 1))
    return {
        "lower": float(slopes[m1]),
        "upper": float(slopes[m2]),
        "confidence": 1 - alpha,
    }


def bootstrap_trend_band(
    years: list[int], values: list[float], trend: TrendResult, n_boot: int = 500, alpha: float = 0.05, seed: int = 42
) -> list[dict]:
    """Residual bootstrap confidence band around the Sen's-slope trend line.

    Resamples residuals (observed minus the already-fitted trend, holding
    year fixed) with replacement, refits Sen's slope on each synthetic
    series, and takes the alpha/2 and 1-alpha/2 percentile of the fitted
    line at each year across replicates. A fixed seed makes the band
    reproducible between runs of the same investigation rather than
    silently changing on every request.
    """
    y = np.asarray(values, dtype=float)
    n = len(y)
    fitted = np.array([trend.sen_intercept + trend.sen_slope_per_year * i for i in range(n)])
    residuals = y - fitted

    rng = np.random.default_rng(seed)
    fitted_lines = np.empty((n_boot, n))
    for b in range(n_boot):
        resampled_resid = rng.choice(residuals, size=n, replace=True)
        synthetic = fitted + resampled_resid
        boot_result = mk.original_test(synthetic)
        boot_slope = boot_result.slope if not np.isnan(boot_result.slope) else 0.0
        boot_intercept = boot_result.intercept if not np.isnan(boot_result.intercept) else float(np.mean(synthetic))
        fitted_lines[b] = boot_intercept + boot_slope * np.arange(n)

    lower = np.percentile(fitted_lines, 100 * alpha / 2, axis=0)
    upper = np.percentile(fitted_lines, 100 * (1 - alpha / 2), axis=0)

    return [
        {"year": year, "lower": float(lo), "upper": float(hi)}
        for year, lo, hi in zip(years, lower, upper)
    ]


def first_half_second_half_persistence(years: list[int], values: list[float]) -> dict:
    """Robustness check used by the Investigation Agent: does the trend hold
    up if we split the period in half and re-estimate it on each half?
    """
    n = len(years)
    if n < 8:
        return {"applicable": False, "reason": "Fewer than 8 annual points; split not meaningful."}

    mid = n // 2
    first = compute_trend(years[:mid], values[:mid])
    second = compute_trend(years[mid:], values[mid:])

    same_sign = (first.sen_slope_per_year >= 0) == (second.sen_slope_per_year >= 0)
    return {
        "applicable": True,
        "first_half": {"years": f"{first.start_year}-{first.end_year}", "slope_per_year": first.sen_slope_per_year, "p_value": first.mk_p_value},
        "second_half": {"years": f"{second.start_year}-{second.end_year}", "slope_per_year": second.sen_slope_per_year, "p_value": second.mk_p_value},
        "consistent_direction": same_sign,
    }
