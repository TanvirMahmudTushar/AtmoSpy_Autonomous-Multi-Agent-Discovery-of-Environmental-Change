"""Known-answer tests for the monthly-first preparation in analysis/timeseries.py."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analysis import timeseries
from app.analysis.trend import compute_trend


def _monthly_dates(start_year: int, n_years: int) -> list[date]:
    return [date(y, m, 15) for y in range(start_year, start_year + n_years) for m in range(1, 13)]


def test_to_monthly_drops_months_below_coverage():
    # January complete (31 days of 2.0); February only 10 of 28 days observed.
    jan = [date(2020, 1, 1) + timedelta(days=i) for i in range(31)]
    feb = [date(2020, 2, 1) + timedelta(days=i) for i in range(10)]
    monthly = timeseries.to_monthly(jan + feb, [2.0] * 31 + [5.0] * 10)

    assert monthly.loc["2020-01-01"] == pytest.approx(2.0)
    assert np.isnan(monthly.loc["2020-02-01"])


def test_to_monthly_passes_monthly_input_through():
    dates = _monthly_dates(2010, 2)
    monthly = timeseries.to_monthly(dates, list(range(24)))
    assert len(monthly) == 24
    assert monthly.iloc[5] == 5


def test_infer_cadence():
    assert timeseries.infer_cadence([date(2020, 1, 1) + timedelta(days=i) for i in range(30)]) == "daily"
    assert timeseries.infer_cadence(_monthly_dates(2010, 1)) == "monthly"
    assert timeseries.infer_cadence([date(y, 1, 1) for y in range(2000, 2010)]) == "annual"


def test_anomalies_remove_seasonal_cycle_and_keep_the_trend():
    years = 25
    dates = _monthly_dates(2000, years)
    t = np.arange(len(dates)) / 12.0
    seasonal = 8.0 * np.sin(2 * np.pi * (np.arange(len(dates)) % 12) / 12)
    values = 15.0 + seasonal + 0.03 * t  # 0.03 units/year under a big seasonal cycle

    bundle = timeseries.prepare(dates, list(values))
    anom = bundle.anomalies.dropna()

    # the climatology captures the seasonal shape
    assert bundle.climatology.max() - bundle.climatology.min() == pytest.approx(16.0, rel=0.05)
    # anomalies are tiny compared with the raw seasonal swing
    assert anom.std() < 0.3
    result = compute_trend(timeseries.decimal_year(anom.index), anom.values, basis="monthly_anomaly")
    assert result.sen_slope_per_year == pytest.approx(0.03, rel=0.02)


def test_to_annual_is_not_biased_by_a_missing_seasonal_extreme():
    dates = _monthly_dates(2000, 10)
    seasonal = 10.0 * np.cos(2 * np.pi * (np.arange(len(dates)) % 12 - 6) / 12)  # peaks in July
    values = 20.0 + seasonal
    values[6 + 12 * 3] = np.nan  # July 2003 missing

    monthly = timeseries.to_monthly(dates, list(values))
    clim = timeseries.climatology(monthly)
    annual = timeseries.to_annual(monthly, clim)

    naive_2003 = monthly[monthly.index.year == 2003].mean()
    assert naive_2003 < 19.5  # the plain mean is dragged down by the missing July
    assert annual.loc[2003] == pytest.approx(20.0, abs=1e-9)  # the robust mean is not


def test_to_annual_requires_ten_months():
    dates = _monthly_dates(2000, 2)
    values = [1.0] * 24
    for i in (0, 1, 2):  # 2000 keeps only 9 months
        values[i] = np.nan
    annual = timeseries.to_annual(timeseries.to_monthly(dates, values), np.ones(12))
    assert list(annual.index) == [2001]


def test_djf_season_assigns_december_to_the_following_year():
    idx = pd.date_range("2000-12-01", "2001-02-01", freq="MS")
    anom = pd.Series([1.0, 2.0, 3.0], index=idx)
    djf = timeseries.seasonal_means(anom, "DJF")
    assert list(djf.index) == [2001]
    assert djf.loc[2001] == pytest.approx(2.0)


def test_decimal_year_is_mid_month():
    x = timeseries.decimal_year(pd.DatetimeIndex(["2000-01-01", "2000-12-01"]))
    assert x[0] == pytest.approx(2000 + 0.5 / 12)
    assert x[1] == pytest.approx(2000 + 11.5 / 12)
