"""Monte Carlo check that the significance tests keep their promise.

Monthly climate anomalies are autocorrelated: this month resembles last
month. The plain Mann-Kendall test assumes independent samples and, on
AR(1) noise with phi = 0.6 and no trend at all, calls ~28% of series
'significant' at alpha = 0.05. The lag-1 corrected tests used by
analysis/trend.py must stay close to the nominal 5%.

This study is also how the MK variant was chosen. On the same noise,
pymannkendall's Hamed-Rao test rejected 14-18% and its Yue-Wang test ~50%
(seeded runs, n = 240 and 480), so neither was used.
"""

import numpy as np

from app.analysis.trend import compute_trend

SIMS = 200
N = 240  # 20 years of monthly anomalies
PHI = 0.6


def _ar1(n, phi, rng):
    e = rng.normal(size=n)
    x = np.empty(n)
    x[0] = e[0] / np.sqrt(1 - phi ** 2)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def test_false_positive_rate_on_autocorrelated_noise():
    rng = np.random.default_rng(2026)
    x = 2000 + np.arange(N) / 12
    corrected = uncorrected = t_test = covered = 0
    for _ in range(SIMS):
        r = compute_trend(x, _ar1(N, PHI, rng), basis="monthly_anomaly")
        corrected += r.mk_p_value < 0.05
        uncorrected += r.mk_p_value_original < 0.05
        t_test += r.ols_p_value < 0.05
        covered += r.sen_ci_lower <= 0 <= r.sen_ci_upper

    assert uncorrected / SIMS > 0.15, "sanity: the uncorrected test should be badly over-confident"
    assert corrected / SIMS <= 0.09
    assert t_test / SIMS <= 0.09
    assert covered / SIMS >= 0.90  # 95% CI should contain the true slope (0) ~95% of the time


def test_power_on_a_real_trend():
    rng = np.random.default_rng(7)
    x = 2000 + np.arange(N) / 12
    noise_sd = 1 / np.sqrt(1 - PHI ** 2)
    slope = 1.5 * noise_sd / (N / 12)  # total change = 1.5 noise SDs over the record
    detected = sum(
        compute_trend(x, _ar1(N, PHI, rng) + slope * (x - x[0]), basis="monthly_anomaly").mk_p_value < 0.05
        for _ in range(100)
    )
    assert detected / 100 >= 0.7
