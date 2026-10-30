"""Deterministic trend statistics. No LLM involvement anywhere in this file —
every number returned here is produced by NumPy/SciPy/pymannkendall.

Method (analysis_version 2):
- Sen's slope on real time (decimal years), so gaps don't distort the rate.
- Mann-Kendall with a lag-1 variance correction: Var(S) is inflated by
  (1 + r1) / (1 - r1), where r1 is the lag-1 autocorrelation of the
  detrended series. The same corrected variance gives Sen's CI. Chosen by a
  Monte Carlo study on AR(1) noise (tests/test_trend_mc.py): it holds the
  false-positive rate near 5%, where the uncorrected test reaches 28-33%
  at r1 = 0.6 and pymannkendall's Hamed-Rao / Yue-Wang variants 14-50%.
- OLS with a t-test whose standard error uses the effective sample size
  n_eff = n (1 - r1) / (1 + r1) (Santer et al. 2000).
- Pre-whitened MK (von Storch 1995) and, for monthly data, the seasonal MK
  (Hirsch et al. 1982) are recorded as cross-checks.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats

from app.analysis import timeseries
from app.analysis.timeseries import MonthlyBundle

ANALYSIS_VERSION = 2  # stored on each Finding; bump when the method changes

ALPHA = 0.05
MAX_LAG1 = 0.95  # caps the variance inflation at ~39x for near-random-walk series
LOW_N_EFF = 10

PRIMARY_METHOD = "mann_kendall_lag1_corrected_sen_slope"


@dataclass
class TrendResult:
    n_years: int  # distinct calendar years with data
    start_year: int
    end_year: int
    mean_value: float  # mean of the variable itself (baseline for % change)
    std_dev: float  # year-to-year variability: SD of the detrended annual values

    ols_slope_per_year: float
    ols_intercept: float
    ols_r_squared: float
    ols_p_value: float  # t-test with n_eff degrees of freedom
    ols_std_err: float  # inflated for autocorrelation

    mk_trend: str  # "increasing" | "decreasing" | "no trend"
    mk_p_value: float  # lag-1 corrected; this is the headline p-value
    mk_z: float
    mk_tau: float
    sen_slope_per_year: float
    sen_intercept: float  # in calendar time: fitted = intercept + slope * x

    total_change: float
    percent_change: float | None
    primary_method: str

    basis: str = "annual"  # "annual" | "monthly_anomaly"
    basis_reason: str = ""
    seasonal_sd_ratio: float | None = None
    n_points: int = 0
    lag1: float = 0.0
    n_eff: float = 0.0
    low_n_eff: bool = False
    residual_std: float = 0.0
    sen_ci_lower: float = 0.0
    sen_ci_upper: float = 0.0
    ols_t: float = 0.0
    ols_ci_lower: float = 0.0
    ols_ci_upper: float = 0.0
    ols_p_value_naive: float = 1.0
    mk_variant: str = "lag1_variance_corrected"
    mk_p_value_original: float = 1.0
    mk_p_value_prewhitened: float | None = None
    seasonal_mk_p_value: float | None = None
    slope_per_decade: float = 0.0
    median_x: float = 0.0
    median_y: float = 0.0

    def to_dict(self) -> dict:
        """JSON-safe: Postgres JSONB rejects NaN/Infinity, so those become None."""
        return {
            k: (None if isinstance(v, float) and not np.isfinite(v) else v)
            for k, v in asdict(self).items()
        }


def _lag1(resid: np.ndarray, scale: float) -> float:
    # A (near-)perfect fit leaves only floating-point noise in the residuals;
    # its "autocorrelation" is meaningless and would wrongly gut n_eff.
    if len(resid) < 3 or np.std(resid) <= 1e-10 * max(scale, 1.0):
        return 0.0
    r1 = float(np.corrcoef(resid[:-1], resid[1:])[0, 1])
    return 0.0 if np.isnan(r1) else r1


def _pairwise(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Sorted pairwise slopes (for Sen's slope and its CI) and the
    Mann-Kendall S statistic with its tie-corrected variance, from one pass
    over all pairs i < j. Same formulas as pymannkendall's original_test
    (Kendall 1975), vectorized: its Python loops were most of the cost of a
    per-cell spatial map (tested equal in tests/test_trend_v2.py)."""
    n = len(y)
    i, j = np.triu_indices(n, 1)
    dy = y[j] - y[i]
    dx = x[j] - x[i]
    s = float(np.sign(dy).sum())
    _, ties = np.unique(y, return_counts=True)
    ties = ties[ties > 1].astype(float)
    var_s = (n * (n - 1) * (2 * n + 5) - float(np.sum(ties * (ties - 1) * (2 * ties + 5)))) / 18.0
    keep = dx != 0
    return np.sort(dy[keep] / dx[keep]), s, var_s


def _pairwise_slopes(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return _pairwise(x, y)[0]


def _seasonal_mk_p(monthly: pd.Series) -> float | None:
    """Seasonal MK on the raw monthly series, padded to whole years from January."""
    if monthly is None or monthly.notna().sum() < 36:
        return None
    start = pd.Timestamp(monthly.index[0].year, 1, 1)
    end = pd.Timestamp(monthly.index[-1].year, 12, 1)
    padded = monthly.reindex(pd.date_range(start, end, freq="MS"))
    try:
        return float(mk.seasonal_test(padded.values, period=12).p)
    except Exception:  # degenerate input (e.g. a calendar month with no data at all)
        return None


def compute_trend(
    x,
    values,
    *,
    basis: str = "annual",
    reference_mean: float | None = None,
    variability_std: float | None = None,
    seasonal_series: pd.Series | None = None,
    alpha: float = ALPHA,
    cross_checks: bool = True,
) -> TrendResult:
    """Trend statistics for values sampled at times x (calendar years or
    decimal years). For basis="monthly_anomaly", pass the raw series'
    mean as `reference_mean` (anomalies average ~0, so % change needs the
    real level) and the annual detrended SD as `variability_std`.
    `cross_checks=False` skips the pre-whitened MK cross-check (used for the
    many cells of a spatial map, where only the headline test is shown).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(values, dtype=float)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    order = np.argsort(x)
    x, y = x[order], y[order]
    n = len(x)
    if n < 4:
        raise ValueError("At least 4 data points are required to compute a trend.")

    # OLS + residual autocorrelation
    ols = stats.linregress(x, y)
    resid = y - (ols.intercept + ols.slope * x)
    r1 = _lag1(resid, float(np.max(np.abs(y))))
    r1_used = min(max(r1, 0.0), MAX_LAG1)
    n_eff = n * (1 - r1_used) / (1 + r1_used)
    vif = (1 + r1_used) / (1 - r1_used)

    if n_eff > 2:
        se_adj = float(ols.stderr) * np.sqrt((n - 2) / (n_eff - 2))
        df = n_eff - 2
    else:
        se_adj, df = float("inf"), 1.0
    if se_adj == 0:  # exact fit: any nonzero slope is certain
        t_stat = float("inf") if ols.slope != 0 else 0.0
        p_adj = 0.0 if ols.slope != 0 else 1.0
    elif np.isfinite(se_adj):
        t_stat = float(ols.slope / se_adj)
        p_adj = float(2 * stats.t.sf(abs(t_stat), df))
    else:
        t_stat, p_adj = 0.0, 1.0
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    ols_ci = (float(ols.slope - t_crit * se_adj), float(ols.slope + t_crit * se_adj))

    # Mann-Kendall with lag-1 variance correction, and Sen's slope + CI
    slopes, s, var_s0 = _pairwise(x, y)
    z0 = (s - np.sign(s)) / np.sqrt(var_s0) if (s != 0 and var_s0 > 0) else 0.0
    p_mk_original = float(2 * stats.norm.sf(abs(z0)))
    tau = s / (0.5 * n * (n - 1))
    var_s = var_s0 * vif
    z = (s - np.sign(s)) / np.sqrt(var_s) if (s != 0 and var_s > 0) else 0.0
    p_mk = float(2 * stats.norm.sf(abs(z)))
    if p_mk < alpha:
        mk_trend = "increasing" if z > 0 else "decreasing"
    else:
        mk_trend = "no trend"

    sen_slope = float(np.median(slopes))
    med_x, med_y = float(np.median(x)), float(np.median(y))
    sen_intercept = med_y - sen_slope * med_x
    big_n = len(slopes)
    c_alpha = stats.norm.ppf(1 - alpha / 2) * np.sqrt(var_s)
    # Gilbert (1987): 1-based ranks M1 = (N - C)/2 and M2 = (N + C)/2 + 1.
    m1 = int(np.floor((big_n - c_alpha) / 2)) - 1
    m2 = int(np.ceil((big_n + c_alpha) / 2))
    sen_ci = (float(slopes[max(0, m1)]), float(slopes[min(big_n - 1, m2)]))

    p_pw = None
    if cross_checks:
        try:
            p_pw = float(mk.pre_whitening_modification_test(y, alpha=alpha).p)
        except Exception:
            p_pw = None

    span = float(x[-1] - x[0])
    total_change = sen_slope * span
    mean_value = float(reference_mean) if reference_mean is not None else float(np.mean(y))
    percent_change = (total_change / abs(mean_value) * 100) if mean_value != 0 else None
    if variability_std is None:
        variability_std = float(np.std(resid, ddof=1)) if n > 2 else 0.0

    years_int = np.floor(x).astype(int)
    return TrendResult(
        n_years=int(len(np.unique(years_int))),
        start_year=int(years_int[0]),
        end_year=int(years_int[-1]),
        mean_value=mean_value,
        std_dev=float(variability_std),
        ols_slope_per_year=float(ols.slope),
        ols_intercept=float(ols.intercept),
        ols_r_squared=float(ols.rvalue ** 2),
        ols_p_value=p_adj,
        ols_std_err=float(se_adj),
        mk_trend=mk_trend,
        mk_p_value=p_mk,
        mk_z=float(z),
        mk_tau=float(tau),
        sen_slope_per_year=sen_slope,
        sen_intercept=float(sen_intercept),
        total_change=float(total_change),
        percent_change=percent_change,
        primary_method=PRIMARY_METHOD,
        basis=basis,
        n_points=n,
        lag1=float(r1),
        n_eff=float(n_eff),
        low_n_eff=bool(n_eff < LOW_N_EFF),
        residual_std=float(np.std(resid, ddof=1)) if n > 2 else 0.0,
        sen_ci_lower=sen_ci[0],
        sen_ci_upper=sen_ci[1],
        ols_t=t_stat,
        ols_ci_lower=ols_ci[0],
        ols_ci_upper=ols_ci[1],
        ols_p_value_naive=float(ols.pvalue),
        mk_p_value_original=p_mk_original,
        mk_p_value_prewhitened=p_pw,
        seasonal_mk_p_value=_seasonal_mk_p(seasonal_series) if seasonal_series is not None else None,
        slope_per_decade=sen_slope * 10,
        median_x=med_x,
        median_y=med_y,
    )


MIN_MONTHS_FOR_ANOMALY_TREND = 36
# Pool monthly anomalies only when calendar months vary comparably. Beyond
# this ratio Sen's median slope is dominated by the quiet months: on NASA
# POWER rainfall for the West Sahel (ratio ~160) it came out ~10x smaller
# than the annual-mean and OLS slopes, which agreed with each other. Up to
# ~3 all three estimators agreed on the real series checked (temperature,
# rainfall and soil wetness in 8 regions).
MAX_SEASONAL_SD_RATIO = 3.0


def _detrended_std(years: list[int], values: list[float]) -> float | None:
    if len(years) < 3:
        return None
    x, y = np.asarray(years, dtype=float), np.asarray(values, dtype=float)
    coef = np.polyfit(x, y, 1)
    return float(np.std(y - np.polyval(coef, x), ddof=2))


def primary_trend(bundle: MonthlyBundle, cross_checks: bool = True) -> TrendResult:
    """Headline trend. Uses monthly anomalies (seasonal cycle removed; every
    month of data, so the most statistical power) when there are enough
    months and the calendar months vary comparably; otherwise annual means.
    Slope, CI and p-value always come from the same series, so a CI that
    includes zero never sits next to 'significant'. cross_checks=False skips
    the seasonal and pre-whitened Mann-Kendall cross-checks (map cells)."""
    years = [int(y) for y in bundle.annual.index]
    values = [float(v) for v in bundle.annual.values]
    variability = _detrended_std(years, values)
    seasonal = bundle.monthly if cross_checks else None
    anom = bundle.anomalies.dropna()
    ratio = timeseries.seasonal_sd_ratio(anom)
    ratio_out = ratio if np.isfinite(ratio) else None

    if len(anom) < MIN_MONTHS_FOR_ANOMALY_TREND:
        reason = "Too few monthly values to remove the seasonal cycle reliably, so annual means were tested."
    elif not ratio <= MAX_SEASONAL_SD_RATIO:  # also catches NaN/inf
        reason = (
            "Some months vary far more than others here (for example a wet season and a dry season), so "
            "pooling monthly values would let the quiet months hide the trend. Annual means were tested instead."
        )
    else:
        result = compute_trend(
            timeseries.decimal_year(anom.index),
            anom.values,
            basis="monthly_anomaly",
            reference_mean=float(np.nanmean(bundle.climatology)),
            variability_std=variability,
            seasonal_series=seasonal,
            cross_checks=cross_checks,
        )
        result.basis_reason = "Monthly values with the average seasonal cycle removed were tested, using every month of data."
        result.seasonal_sd_ratio = ratio_out
        return result

    result = compute_trend(
        years, values, variability_std=variability, seasonal_series=seasonal, cross_checks=cross_checks
    )
    result.basis_reason = reason
    result.seasonal_sd_ratio = ratio_out
    return result


def fitted(trend: TrendResult, x) -> np.ndarray:
    """Sen's trend line at times x, in the units of the series it was fit on."""
    return trend.sen_intercept + trend.sen_slope_per_year * np.asarray(x, dtype=float)


def ci_band(trend: TrendResult, x) -> tuple[np.ndarray, np.ndarray]:
    """95% band for the trend line: the lines with the lower and upper Sen
    CI slopes, pivoting on the data's median point (where Sen's line is
    anchored). Narrowest at the middle of the record, widest at the ends.
    """
    x = np.asarray(x, dtype=float)
    a = trend.median_y + trend.sen_ci_lower * (x - trend.median_x)
    b = trend.median_y + trend.sen_ci_upper * (x - trend.median_x)
    return np.minimum(a, b), np.maximum(a, b)


def annual_display_offset(trend: TrendResult) -> tuple[float, float]:
    """(level, x_shift) that maps an anomaly-basis trend onto annual means:
    annual mean of year Y ~ level + fitted(Y + x_shift)."""
    if trend.basis == "monthly_anomaly":
        return trend.mean_value, 0.5
    return 0.0, 0.0


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
