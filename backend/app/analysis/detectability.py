"""How many years of data would this trend need before it is detectable?

Weatherhead et al. (1998, JGR 103:17149): for monthly data with noise
standard deviation sigma_N and lag-1 autocorrelation phi, a trend of
omega per year is detectable (|trend| > 2 sigma, with 90% probability) after

    n* = [ (3.3 sigma_N / |omega|) * sqrt((1 + phi) / (1 - phi)) ]^(2/3)  years.

The formula assumes 12 samples per year. For other sampling rates the noise
is rescaled to its monthly equivalent: the OLS slope variance with s samples
per year over n years is 12 sigma^2 / (s n^3), so sigma_eq = sigma sqrt(12 / s).
"""

import math

from app.analysis.trend import MAX_LAG1, TrendResult


def years_to_detect(slope_per_year: float, noise_std: float, phi: float, samples_per_year: int = 12) -> float | None:
    if slope_per_year == 0 or noise_std <= 0:
        return None
    phi = min(max(phi, 0.0), MAX_LAG1)
    sigma_eq = noise_std * math.sqrt(12 / samples_per_year)
    return ((3.3 * sigma_eq / abs(slope_per_year)) * math.sqrt((1 + phi) / (1 - phi))) ** (2 / 3)


def assess(trend: TrendResult) -> dict:
    samples_per_year = 12 if trend.basis == "monthly_anomaly" else 1
    needed = years_to_detect(trend.sen_slope_per_year, trend.residual_std, trend.lag1, samples_per_year)
    available = trend.end_year - trend.start_year + 1
    if needed is None:
        return {
            "method": "weatherhead_1998",
            "years_needed": None,
            "years_available": available,
            "detectable_now": False,
            "projected_year": None,
            "note": "No measurable trend, so no detection horizon can be estimated.",
        }
    years_needed = round(needed, 1)
    detectable_now = needed <= available
    projected_year = None if detectable_now else trend.start_year + math.ceil(needed) - 1
    return {
        "method": "weatherhead_1998",
        "years_needed": years_needed,
        "years_available": available,
        "detectable_now": detectable_now,
        "projected_year": projected_year,
        "noise_std": trend.residual_std,
        "lag1": trend.lag1,
        "samples_per_year": samples_per_year,
    }
