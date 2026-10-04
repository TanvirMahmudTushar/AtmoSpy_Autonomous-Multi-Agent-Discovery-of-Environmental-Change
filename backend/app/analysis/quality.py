"""Data Quality Agent's deterministic checks.

The system must never silently analyze bad data (spec section 5, Agent 3) —
`assess_quality` returns a `passed: bool` the orchestrator is required to
respect before running any trend/statistics step.
"""

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np

MIN_YEARS_FOR_TREND = 5
MIN_COMPLETENESS = 0.5


@dataclass
class QualityReport:
    period_start: str
    period_end: str
    requested_days: int
    observed_days: int
    completeness: float
    max_gap_days: int
    n_outliers: int
    outlier_dates: list[str]
    range_violations: int
    coverage_years: float
    passed: bool
    issues: list[str]


def assess_quality(
    dates: list[date],
    values: list[float],
    missing_dates: list[date],
    requested_start: date,
    requested_end: date,
    valid_min: float | None = None,
    valid_max: float | None = None,
    expected_interval_days: float = 1.0,
) -> QualityReport:
    """expected_interval_days is the source's real observation cadence (1.0
    for daily sources like POWER, ~30.44 for monthly sources like GRACE-FO)
    — completeness/coverage are judged against how many observations *should*
    exist at that cadence, not against a raw day-count that implicitly
    assumes daily data."""
    issues: list[str] = []
    requested_days = (requested_end - requested_start).days + 1
    expected_observations = requested_days / expected_interval_days if requested_days > 0 else 0.0
    observed_days = len(dates)
    completeness = observed_days / expected_observations if expected_observations > 0 else 0.0
    coverage_years = (observed_days * expected_interval_days) / 365.25

    all_dates = sorted(dates + missing_dates)
    max_gap = 0
    if len(all_dates) > 1:
        diffs = [(all_dates[i + 1] - all_dates[i]).days for i in range(len(all_dates) - 1)]
        max_gap = max(diffs) if diffs else 0

    n_outliers = 0
    outlier_dates: list[str] = []
    range_violations = 0
    if len(values) >= 8:
        arr = np.asarray(values)
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        lower_fence, upper_fence = q1 - 3 * iqr, q3 + 3 * iqr
        for d, v in zip(dates, values):
            if v < lower_fence or v > upper_fence:
                n_outliers += 1
                if len(outlier_dates) < 20:
                    outlier_dates.append(d.isoformat())

    if valid_min is not None and valid_max is not None:
        range_violations = sum(1 for v in values if v < valid_min or v > valid_max)

    if completeness < MIN_COMPLETENESS:
        issues.append(
            f"Only {completeness:.0%} of the requested period has data (minimum required: "
            f"{MIN_COMPLETENESS:.0%})."
        )
    if coverage_years < MIN_YEARS_FOR_TREND:
        issues.append(
            f"Only {coverage_years:.1f} years of data available; at least {MIN_YEARS_FOR_TREND} "
            "years are required for a defensible trend estimate."
        )
    if max_gap > 365:
        issues.append(f"Largest data gap is {max_gap} days (over one year).")
    if range_violations > 0:
        issues.append(f"{range_violations} values fell outside the physically valid range.")

    passed = completeness >= MIN_COMPLETENESS and coverage_years >= MIN_YEARS_FOR_TREND

    return QualityReport(
        period_start=requested_start.isoformat(),
        period_end=requested_end.isoformat(),
        requested_days=requested_days,
        observed_days=observed_days,
        completeness=round(completeness, 4),
        max_gap_days=max_gap,
        n_outliers=n_outliers,
        outlier_dates=outlier_dates,
        range_violations=range_violations,
        coverage_years=round(coverage_years, 2),
        passed=passed,
        issues=issues,
    )
