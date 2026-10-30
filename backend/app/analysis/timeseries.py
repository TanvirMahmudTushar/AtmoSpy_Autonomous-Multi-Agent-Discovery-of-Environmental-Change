"""Monthly-first time-series preparation. Deterministic pandas/NumPy only.

Pipeline: native samples -> monthly means (with a coverage rule) -> monthly
climatology (the average seasonal cycle) -> anomalies (each month minus its
climatological mean, i.e. the series with the seasonal cycle removed).
Trends are estimated on the anomalies; annual means are kept as a
cross-check and for display.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}


@dataclass
class MonthlyBundle:
    """Everything derived from one series, all indexed by month start."""

    monthly: pd.Series  # raw monthly means, NaN where coverage failed
    climatology: np.ndarray  # shape (12,), NaN for a calendar month never observed
    anomalies: pd.Series  # monthly - climatology
    annual: pd.Series  # indexed by int year

    @property
    def valid_months(self) -> int:
        return int(self.monthly.notna().sum())

    @property
    def coverage_years(self) -> float:
        valid = self.monthly.dropna()
        if valid.empty:
            return 0.0
        return (valid.index[-1] - valid.index[0]).days / 365.25 + 1 / 12


def _median_step_days(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 30.0
    return float(np.median(np.diff(index.values).astype("timedelta64[D]").astype(float)))


def _is_monthly(index: pd.DatetimeIndex) -> bool:
    return _median_step_days(index) >= 25


def infer_cadence(dates: list[date]) -> str:
    """"daily" | "monthly" | "annual", from the median sampling interval."""
    step = _median_step_days(pd.to_datetime(sorted(dates)))
    if step >= 300:
        return "annual"
    return "monthly" if step >= 25 else "daily"


def to_monthly(dates: list[date], values: list[float], min_coverage: float = 0.7) -> pd.Series:
    """Monthly means indexed by month start. A month built from daily samples
    is kept only if at least `min_coverage` of its days are present, so a
    month with three observed days can't masquerade as a monthly mean.
    Already-monthly input (GRACE, SMAP, gridded L3) is passed through.
    """
    if not dates:
        return pd.Series(dtype=float)
    s = pd.Series(np.asarray(values, dtype=float), index=pd.to_datetime(dates)).sort_index()
    s = s[~s.index.duplicated(keep="first")]

    if _is_monthly(s.index):
        monthly = s.groupby(s.index.to_period("M")).mean()
    else:
        grouped = s.dropna().groupby(s.dropna().index.to_period("M"))
        means, counts = grouped.mean(), grouped.count()
        days_in_month = means.index.days_in_month
        means[counts.values < np.ceil(min_coverage * days_in_month)] = np.nan
        monthly = means

    full = pd.period_range(monthly.index.min(), monthly.index.max(), freq="M")
    monthly = monthly.reindex(full)
    monthly.index = monthly.index.to_timestamp()
    return monthly


def climatology(monthly: pd.Series, baseline: tuple[int, int] | None = None) -> np.ndarray:
    """Average value for each calendar month over the baseline years
    (default: the full record). This is the 'normal' seasonal cycle."""
    s = monthly
    if baseline is not None:
        s = s[(s.index.year >= baseline[0]) & (s.index.year <= baseline[1])]
    by_month = s.groupby(s.index.month).mean()
    return np.array([by_month.get(m, np.nan) for m in range(1, 13)], dtype=float)


def anomalies(monthly: pd.Series, clim: np.ndarray) -> pd.Series:
    return monthly - clim[monthly.index.month - 1]


def to_annual(monthly: pd.Series, clim: np.ndarray, min_months: int = 10) -> pd.Series:
    """Annual means that are robust to a missing month: mean of the
    climatology plus the mean anomaly of the months that were observed.
    A plain mean of the observed months would be biased whenever the
    missing month is a seasonally warm/wet/cold one.
    """
    anom = anomalies(monthly, clim)
    grouped = anom.groupby(anom.index.year)
    counts = grouped.count()
    annual = grouped.mean() + float(np.nanmean(clim))
    annual = annual[counts >= min_months]
    annual.index = annual.index.astype(int)
    return annual


def seasonal_means(anom: pd.Series, season: str) -> pd.Series:
    """Per-year mean anomaly for one season. December is counted with the
    following January/February (DJF 2001 = Dec 2000 + Jan/Feb 2001).
    All three months must be present."""
    months = SEASONS[season]
    s = anom[anom.index.month.isin(months)]
    season_year = s.index.year + (s.index.month == 12).astype(int) if season == "DJF" else s.index.year
    grouped = s.groupby(season_year)
    out = grouped.mean()[grouped.count() == 3]
    out.index = out.index.astype(int)
    return out


def seasonal_sd_ratio(anom: pd.Series, min_count: int = 3) -> float:
    """Largest / smallest standard deviation of the anomalies across calendar
    months. Near 1 for temperature-like variables; huge for rainfall in a
    region with a dry season (dry-month anomalies are always ~0)."""
    a = anom.dropna()
    grouped = a.groupby(a.index.month)
    sd = grouped.std()[grouped.count() >= min_count]
    if len(sd) < 2:
        return float("nan")
    return float("inf") if sd.min() == 0 else float(sd.max() / sd.min())


def decimal_year(index: pd.DatetimeIndex) -> np.ndarray:
    """Mid-month decimal years (Jan 2000 -> 2000.0417)."""
    return index.year.values + (index.month.values - 0.5) / 12.0


def prepare(dates: list[date], values: list[float], baseline: tuple[int, int] | None = None) -> MonthlyBundle:
    monthly = to_monthly(dates, values)
    clim = climatology(monthly, baseline)
    return MonthlyBundle(
        monthly=monthly,
        climatology=clim,
        anomalies=anomalies(monthly, clim),
        annual=to_annual(monthly, clim),
    )
