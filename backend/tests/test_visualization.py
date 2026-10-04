"""Regression test for a real bug caught via a live screenshot: the fitted
trend line was being evaluated at the calendar year instead of the 0-based
sample index pymannkendall's Sen's-slope intercept is fit against, which
made the chart's trend line render far outside the data's range.
"""

from app.analysis.trend import compute_trend
from app.services.visualization import build_timeseries_chart


def test_fitted_trend_line_stays_within_observed_value_range():
    years = list(range(1990, 2026))
    values = [1.0 + 0.05 * i for i in range(len(years))]  # slope 0.05/yr, near-zero noise
    trend = compute_trend(years, values)

    chart = build_timeseries_chart(years, values, trend, [], "Test Variable", "units")

    obs_min, obs_max = min(values), max(values)
    margin = (obs_max - obs_min) * 0.5 + 0.5
    for point in chart["trend_line"]:
        assert obs_min - margin <= point["fitted"] <= obs_max + margin, (
            f"Fitted value {point['fitted']} at year {point['year']} is far outside the observed "
            f"range [{obs_min}, {obs_max}] — the trend line would render off-chart."
        )

    # the fitted line should track the observed line closely for a clean synthetic series
    first_fitted = chart["trend_line"][0]["fitted"]
    last_fitted = chart["trend_line"][-1]["fitted"]
    assert abs(first_fitted - values[0]) < 0.5
    assert abs(last_fitted - values[-1]) < 0.5
