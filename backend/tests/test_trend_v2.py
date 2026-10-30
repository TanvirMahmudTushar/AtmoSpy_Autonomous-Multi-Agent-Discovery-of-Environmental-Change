"""Known-answer tests for the v2 trend statistics. Values marked "by hand"
are worked out in the comments so they can be checked without software."""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.stats.multitest import multipletests

from app.analysis import detectability, timeseries
from app.analysis.spatial import benjamini_hochberg, compute_cell_trends
from app.analysis.trend import compute_trend, primary_trend
from app.nasa.base import GridCell

# y = [1, 3, 2, 5, 4] at x = 0..4
#   Pairs (i<j) with y_j > y_i: 8, with y_j < y_i: 2  ->  S = 6
#   Var(S) = n(n-1)(2n+5)/18 = 5*4*15/18 = 16.667   (no ties)
#   z = (S - 1)/sqrt(Var) = 5/4.0825 = 1.2247       ->  p = 0.2207
#   Pairwise slopes sorted: -1,-1,1/3,0.5,0.75,1,1,4/3,2,3  ->  Sen = (0.75+1)/2 = 0.875
#   OLS residuals alternate in sign, so lag-1 autocorrelation < 0 and no
#   variance correction applies: corrected p equals the original p.
#   Gilbert CI: C = 1.96*sqrt(16.667) = 8.0, M1 = (10-8)/2 ~ 1, M2 = (10+8)/2+1 ~ 10
#   -> [slope_1, slope_10] = [-1, 3]
SMALL_X = [0, 1, 2, 3, 4]
SMALL_Y = [1, 3, 2, 5, 4]


def test_mann_kendall_and_sen_match_hand_calculation():
    r = compute_trend(SMALL_X, SMALL_Y)
    assert r.sen_slope_per_year == pytest.approx(0.875)
    assert r.mk_p_value_original == pytest.approx(2 * stats.norm.sf(5 / np.sqrt(16.6667)), abs=1e-4)
    assert r.mk_p_value_original == pytest.approx(0.2207, abs=1e-4)
    assert r.lag1 < 0
    assert r.mk_p_value == pytest.approx(r.mk_p_value_original)
    assert (r.sen_ci_lower, r.sen_ci_upper) == (pytest.approx(-1.0), pytest.approx(3.0))
    assert r.ols_slope_per_year == pytest.approx(0.8)  # Sxy/Sxx = 8/10


@pytest.mark.parametrize("seed, ties", [(1, False), (2, True), (3, True)])
def test_vectorized_mann_kendall_equals_pymannkendall(seed, ties):
    import pymannkendall as mk

    rng = np.random.default_rng(seed)
    y = rng.normal(size=300) + 0.002 * np.arange(300)
    if ties:
        y = np.round(y, 1)  # many tied values, exercising the variance correction
    x = 2000 + np.arange(300) / 12
    ref = mk.original_test(y)
    r = compute_trend(x, y)
    assert r.mk_p_value_original == pytest.approx(ref.p, rel=1e-9, abs=1e-15)
    assert r.mk_tau == pytest.approx(ref.Tau, rel=1e-12)
    assert r.sen_slope_per_year * (1 / 12) == pytest.approx(ref.slope, rel=1e-9)  # pymannkendall's slope is per step


def test_sen_slope_is_per_year_even_with_gaps():
    # The v1 code took Sen's slope per array step; with gaps in the years the
    # per-step slope overstates the per-year rate.
    years = [2000, 2001, 2002, 2006, 2010, 2011, 2015, 2020]
    values = [3.0 + 0.5 * (y - 2000) for y in years]
    r = compute_trend(years, values)
    assert r.sen_slope_per_year == pytest.approx(0.5)
    assert r.total_change == pytest.approx(10.0)  # 0.5/yr over 20 years
    assert r.slope_per_decade == pytest.approx(5.0)


def test_requires_four_points():
    with pytest.raises(ValueError):
        compute_trend([2000, 2001, 2002], [1.0, 2.0, 3.0])


def test_nan_values_are_dropped():
    r = compute_trend([2000, 2001, 2002, 2003, 2004, 2005], [1.0, 2.0, np.nan, 4.0, 5.0, 6.0])
    assert r.n_points == 5
    assert r.sen_slope_per_year == pytest.approx(1.0)


def test_autocorrelation_widens_the_t_test():
    rng = np.random.default_rng(11)
    n, phi = 240, 0.7
    e = rng.normal(size=n)
    y = np.empty(n)
    y[0] = e[0]
    for i in range(1, n):
        y[i] = phi * y[i - 1] + e[i]
    x = 2000 + np.arange(n) / 12
    r = compute_trend(x, y)

    assert 0.5 < r.lag1 < 0.85
    assert r.n_eff < n / 3
    assert r.ols_p_value > r.ols_p_value_naive
    assert r.ols_ci_lower < r.ols_slope_per_year < r.ols_ci_upper


def test_anomaly_basis_uses_reference_mean_for_percent_change():
    x = 2000 + np.arange(120) / 12
    anom = 0.1 * (x - 2005)
    r = compute_trend(x, anom, basis="monthly_anomaly", reference_mean=50.0)
    assert r.mean_value == 50.0
    assert r.percent_change == pytest.approx(r.total_change / 50.0 * 100)


def test_seasonal_mann_kendall_runs_on_monthly_series():
    idx = pd.date_range("2000-01-01", periods=15 * 12, freq="MS")
    monthly = pd.Series(10 + 5 * np.sin(np.arange(len(idx)) * np.pi / 6) + 0.05 * np.arange(len(idx)) / 12, index=idx)
    bundle_anom = monthly - monthly.groupby(idx.month).transform("mean")
    r = compute_trend(timeseries.decimal_year(idx), bundle_anom.values, basis="monthly_anomaly", seasonal_series=monthly)
    assert r.seasonal_mk_p_value is not None
    assert r.seasonal_mk_p_value < 0.001


def test_dry_season_rainfall_is_tested_on_annual_means():
    # Rain only Jun-Sep, growing 0.4 mm/day per year in those months: the
    # annual mean grows 4/12 * 0.4 = 0.1333 mm/day per year. Pooled monthly
    # anomalies would be ~0 in the 8 dry months and drag Sen's median to ~0.
    rng = np.random.default_rng(4)
    dates = [date(y, m, 15) for y in range(1990, 2025) for m in range(1, 13)]
    vals = [
        (5.0 + 0.4 * (d.year - 1990) + rng.normal(0, 1.5)) if 6 <= d.month <= 9 else 0.0
        for d in dates
    ]
    result = primary_trend(timeseries.prepare(dates, vals))
    assert result.basis == "annual"
    assert result.seasonal_sd_ratio is None  # dry months have zero spread
    assert "wet season" in result.basis_reason
    assert result.sen_slope_per_year == pytest.approx(0.4 * 4 / 12, rel=0.15)


def test_homoscedastic_series_uses_monthly_anomalies():
    rng = np.random.default_rng(8)
    dates = [date(y, m, 15) for y in range(1990, 2025) for m in range(1, 13)]
    vals = [10 * np.sin(2 * np.pi * d.month / 12) + 0.03 * (d.year - 1990) + rng.normal(0, 1) for d in dates]
    result = primary_trend(timeseries.prepare(dates, vals))
    assert result.basis == "monthly_anomaly"
    assert result.seasonal_sd_ratio < 3
    assert result.sen_slope_per_year == pytest.approx(0.03, abs=0.01)


def test_weatherhead_by_hand():
    # monthly: n* = (3.3 * 1 / 0.1)^(2/3) = 33^(2/3) = 10.29 years
    assert detectability.years_to_detect(0.1, 1.0, 0.0, 12) == pytest.approx(33 ** (2 / 3))
    # annual sampling: noise rescaled by sqrt(12) -> (3.3*sqrt(12)/0.1)^(2/3)
    assert detectability.years_to_detect(0.1, 1.0, 0.0, 1) == pytest.approx((33 * np.sqrt(12)) ** (2 / 3))
    # autocorrelation lengthens the wait: phi=0.5 multiplies the base by sqrt(3)
    assert detectability.years_to_detect(0.1, 1.0, 0.5, 12) == pytest.approx((33 * np.sqrt(3)) ** (2 / 3))
    assert detectability.years_to_detect(0.0, 1.0, 0.0) is None


def test_detectability_assess_projects_a_year_for_a_short_record():
    rng = np.random.default_rng(5)
    x = 2015 + np.arange(96) / 12  # 8 years
    y = 0.02 * (x - 2015) + rng.normal(0, 1.0, len(x))
    r = compute_trend(x, y, basis="monthly_anomaly")
    d = detectability.assess(r)
    assert d["years_needed"] > d["years_available"]
    assert d["detectable_now"] is False
    assert d["projected_year"] > 2022


def test_benjamini_hochberg_matches_statsmodels():
    p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
    ours = benjamini_hochberg(p)
    reference = multipletests(p, method="fdr_bh")[1]
    np.testing.assert_allclose(ours, reference)


def _monthly_cell(lat, lon, slope, rng, years=20, noise=0.3):
    dates = [date(y, m, 15) for y in range(2003, 2003 + years) for m in range(1, 13)]
    t = np.arange(len(dates)) / 12
    vals = 5 * np.sin(2 * np.pi * np.arange(len(dates)) / 12) + slope * t + rng.normal(0, noise, len(dates))
    return GridCell(lat=lat, lon=lon, dates=dates, values=list(vals))


def test_monthly_cells_get_per_year_slopes_and_opposite_signs():
    # v1 treated each monthly value as an annual sample of its calendar year.
    rng = np.random.default_rng(3)
    cells = [_monthly_cell(10.0, 20.0, 0.2, rng), _monthly_cell(10.5, 20.5, -0.2, rng)]
    trends = compute_cell_trends(cells)
    assert len(trends) == 2
    assert trends[0].slope_per_year == pytest.approx(0.2, abs=0.03)
    assert trends[1].slope_per_year == pytest.approx(-0.2, abs=0.03)
    assert all(t.significant for t in trends)


def test_fdr_keeps_pure_noise_cells_insignificant():
    rng = np.random.default_rng(9)
    cells = [_monthly_cell(float(i), 0.0, 0.0, rng, years=12, noise=1.0) for i in range(40)]
    trends = compute_cell_trends(cells)
    assert sum(t.significant for t in trends) <= 1
