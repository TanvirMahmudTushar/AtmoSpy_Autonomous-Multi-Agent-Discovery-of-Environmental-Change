"""Known-answer tests for the deterministic analysis core, using synthetic
series with mathematically known properties — these must pass without any
network access or database, since correctness here doesn't depend on NASA
POWER being reachable.
"""

from datetime import date

import numpy as np
import pytest

from app.analysis.changepoint import detect_change_points
from app.analysis.correlation import align_annual, correlate
from app.analysis.quality import assess_quality
from app.analysis.significance import classify_significance, effect_size, importance_note
from app.analysis.spatial import build_timelapse_frames, compare_regions
from app.nasa.base import GridCell
from app.analysis.trend import bootstrap_trend_band, compute_trend, first_half_second_half_persistence


def test_compute_trend_detects_known_linear_increase():
    years = list(range(2000, 2024))
    values = [10 + 0.5 * (y - 2000) for y in years]  # exact slope = 0.5/yr
    result = compute_trend(years, values)

    assert result.sen_slope_per_year == pytest.approx(0.5, abs=1e-6)
    assert result.ols_slope_per_year == pytest.approx(0.5, abs=1e-6)
    assert result.mk_p_value < 0.001
    assert result.mk_trend == "increasing"
    assert result.total_change == pytest.approx(0.5 * (years[-1] - years[0]), abs=1e-6)


def test_compute_trend_flat_noise_is_not_significant():
    rng = np.random.default_rng(42)
    years = list(range(2000, 2024))
    values = list(10 + rng.normal(0, 0.05, len(years)))  # tiny noise, no trend
    result = compute_trend(years, values)

    assert result.mk_p_value > 0.05
    assert classify_significance(result.mk_p_value) == "not_significant"


def test_compute_trend_requires_minimum_points():
    with pytest.raises(ValueError):
        compute_trend([2020, 2021], [1.0, 2.0])


def test_persistence_check_flags_inconsistent_trend():
    years = list(range(2000, 2020))
    # increasing then decreasing -> should NOT be consistent
    values = [10 + 0.5 * i for i in range(10)] + [15 - 0.5 * i for i in range(10)]
    result = first_half_second_half_persistence(years, values)
    assert result["applicable"] is True
    assert result["consistent_direction"] is False


def test_detect_change_points_finds_step_shift():
    years = list(range(2000, 2020))
    values = [10.0] * 10 + [20.0] * 10
    points = detect_change_points(years, values, penalty=1.0)
    assert len(points) >= 1
    assert abs(points[0]["shift"] - 10.0) < 1.0


def test_correlate_perfectly_correlated_series():
    dates_a = [date(y, 7, 1) for y in range(2000, 2020)]
    dates_b = dates_a
    values_a = [float(i) for i in range(20)]
    values_b = [2.0 * i + 1.0 for i in range(20)]

    years, xa, xb = align_annual(dates_a, values_a, dates_b, values_b)
    result = correlate(xa, xb, years)

    assert result is not None
    assert result.r == pytest.approx(1.0, abs=1e-6)
    assert result.p_value < 0.001


def test_assess_quality_treats_complete_monthly_data_as_complete():
    # 22 years of one observation per month — genuinely complete for a
    # monthly source (GRACE-FO), but would look like ~3% "complete" if
    # judged against a day-count basis meant for daily sources (POWER).
    dates = []
    d = date(2002, 1, 15)
    while d < date(2024, 1, 1):
        dates.append(d)
        d = date(d.year + 1, 1, 15) if d.month == 12 else date(d.year, d.month + 1, 15)
    report = assess_quality(
        dates=dates,
        values=[1.0] * len(dates),
        missing_dates=[],
        requested_start=date(2002, 1, 1),
        requested_end=date(2023, 12, 31),
        expected_interval_days=30.44,
    )
    assert report.completeness > 0.9
    assert report.coverage_years == pytest.approx(22, abs=1)
    assert report.passed is True


def test_assess_quality_flags_sparse_data():
    dates = [date(2020, 1, d) for d in range(1, 10)]
    report = assess_quality(
        dates=dates,
        values=[1.0] * len(dates),
        missing_dates=[],
        requested_start=date(2000, 1, 1),
        requested_end=date(2020, 12, 31),
    )
    assert report.passed is False
    assert report.completeness < 0.5


def test_compare_regions_detects_opposite_signs():
    years = list(range(2000, 2020))
    inc = compute_trend(years, [10 + 0.3 * i for i in range(20)])
    dec = compute_trend(years, [10 - 0.3 * i for i in range(20)])
    cmp = compare_regions(inc, dec, "Region A", "Region B")
    assert cmp["opposite_signs"] is True


def test_effect_size_known_answers():
    assert effect_size(total_change=3.0, std_dev=2.0) == pytest.approx(1.5)
    assert effect_size(total_change=-3.0, std_dev=2.0) == pytest.approx(1.5)  # magnitude only
    assert effect_size(total_change=1.0, std_dev=0.0) == 0.0  # flat series: no divide-by-zero


def test_effect_size_matches_importance_note():
    result = compute_trend(list(range(2000, 2020)), [10 + 0.3 * i for i in range(20)])
    expected = effect_size(result.total_change, result.std_dev)
    assert f"= {expected:.2f}" in importance_note(result.total_change, result.std_dev, result.percent_change)


def test_importance_note_distinguishes_significance_from_effect_size():
    note = importance_note(total_change=0.1, std_dev=5.0, percent_change=1.0)
    assert "small" in note
    assert "significance" in note.lower()


def test_bootstrap_trend_band_contains_fitted_line():
    years = list(range(2000, 2024))
    rng = np.random.default_rng(7)
    values = [10 + 0.5 * (y - 2000) + rng.normal(0, 1.0) for y in years]
    trend_result = compute_trend(years, values)
    band = bootstrap_trend_band(years, values, trend_result, n_boot=200)

    assert len(band) == len(years)
    for i, point in enumerate(band):
        assert point["year"] == years[i]
        assert point["lower"] <= point["upper"]
        fitted = trend_result.sen_intercept + trend_result.sen_slope_per_year * i
        # the band should bracket the fitted line itself, since it's built
        # from residual-resampled refits of that same trend
        assert point["lower"] <= fitted + 1e-6
        assert point["upper"] >= fitted - 1e-6


def test_build_timelapse_frames_one_frame_per_year_with_consistent_range():
    dates = [date(y, 6, 15) for y in range(2000, 2010)]
    cell_a = GridCell(lat=10.0, lon=20.0, dates=dates, values=[1.0 + 0.1 * i for i in range(10)])
    cell_b = GridCell(lat=11.0, lon=21.0, dates=dates, values=[5.0 - 0.2 * i for i in range(10)])

    result = build_timelapse_frames([cell_a, cell_b], min_years=5)

    assert result["years"] == list(range(2000, 2010))
    assert result["value_min"] == pytest.approx(min(cell_a.values + cell_b.values), abs=1e-6)
    assert result["value_max"] == pytest.approx(max(cell_a.values + cell_b.values), abs=1e-6)
    # every year's frame has one point per cell that had data that year
    assert len(result["frames"]["2000"]) == 2
    assert {p["lat"] for p in result["frames"]["2000"]} == {10.0, 11.0}


def test_build_timelapse_frames_excludes_cells_below_min_years():
    dates = [date(y, 6, 15) for y in range(2000, 2003)]  # only 3 years
    cell = GridCell(lat=10.0, lon=20.0, dates=dates, values=[1.0, 2.0, 3.0])
    result = build_timelapse_frames([cell], min_years=5)
    assert result["years"] == []
    assert result["frames"] == {}


def test_bootstrap_trend_band_is_reproducible_with_fixed_seed():
    years = list(range(2000, 2020))
    values = [10 + 0.2 * i for i in range(len(years))]
    trend_result = compute_trend(years, values)
    band_a = bootstrap_trend_band(years, values, trend_result, n_boot=100, seed=42)
    band_b = bootstrap_trend_band(years, values, trend_result, n_boot=100, seed=42)
    assert band_a == band_b
