"""Skeptic Agent — a deliberately adversarial pass between the robustness
check and the final report. Its job is to argue AGAINST over-trusting the
finding, using only numbers already computed by earlier agents (quality
report, persistence check, change points, effect size, related-variable
correlations). It never invents a statistic; it only reframes existing ones
critically. This is what keeps "statistically significant" from silently
becoming "definitely true" in the final write-up.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.services.events import StepRecorder

STRICT_ALPHA = 0.01
SHORT_SERIES_YEARS = 15
SMALL_EFFECT_SIZE = 0.3
STRONG_CORRELATION = 0.7
LOW_COMPLETENESS = 0.85


def _build_skeptic_points(state: InvestigationState) -> list[str]:
    points: list[str] = []
    trend = state.trend_result
    if trend is None:
        return points

    # 1. Is a chunk of the "trend" really just one abrupt step?
    span = max(trend.end_year - trend.start_year, 1)
    for cp in state.change_points:
        distance_from_edge = min(cp["year"] - trend.start_year, trend.end_year - cp["year"])
        if distance_from_edge > span * 0.15:
            points.append(
                f"A change point in {cp['year']} shifted the mean by {cp['shift']:+.4g} {state.point_series.units if state.point_series else ''} — "
                "part of the reported trend may reflect a step change rather than a gradual process, which a "
                "single monotonic-trend statistic cannot distinguish from steady change."
            )
            break

    # 2. Short series are prone to multi-year natural cycles masquerading as trends.
    if trend.n_years < SHORT_SERIES_YEARS:
        points.append(
            f"Only {trend.n_years} years of data were available. Short climate series are susceptible to "
            "multi-year natural oscillations producing an apparently significant trend that would not hold "
            "over a longer record."
        )

    # 3. Significant at 0.05 but not at a stricter bar often used for exploratory/multi-candidate scans.
    if STRICT_ALPHA <= trend.mk_p_value < 0.05:
        points.append(
            f"p = {trend.mk_p_value:.4f} clears the conventional 0.05 threshold but not a stricter "
            f"{STRICT_ALPHA} bar — worth keeping in mind if this result came from scanning many candidates, "
            "where some 'significant' findings are expected by chance alone."
        )

    # 4. Statistically significant but practically small.
    if trend.std_dev > 0:
        effect_size = abs(trend.total_change) / trend.std_dev
        if effect_size < SMALL_EFFECT_SIZE:
            points.append(
                f"The effect size ({effect_size:.2f}, from the importance-note calculation) is small relative "
                "to year-to-year variability — statistically detectable is not the same as practically large."
            )

    # 5. A strong correlation could reflect a shared external driver or reversed influence, not this
    #    variable being the cause of anything.
    if state.related_variables:
        top = state.related_variables[0]
        if abs(top["r"]) > STRONG_CORRELATION:
            points.append(
                f"{top['variable_name']} correlates strongly (r={top['r']:.2f}) with this variable here — "
                "the two could share a common external driver, or the apparent direction of influence could be "
                "reversed. Correlation alone cannot distinguish these possibilities."
            )

    # 6. Data completeness, surfaced explicitly rather than left in a nested quality report.
    if state.quality_report and state.quality_report.completeness < LOW_COMPLETENESS:
        points.append(
            f"Only {state.quality_report.completeness:.0%} of the requested period had data — gaps "
            "concentrated in a particular season or year could bias the estimated trend."
        )

    # 7. Persistence: consecutive values that resemble each other carry less independent information.
    if trend.low_n_eff:
        points.append(
            f"Consecutive values are strongly correlated (lag-1 autocorrelation {trend.lag1:.2f}), so the "
            f"{trend.n_points} data points carry only about {trend.n_eff:.0f} independent pieces of information. "
            "Slow natural swings can look like trends in records like this."
        )

    # 8. The two independent significance tests disagree.
    mk_sig = trend.mk_p_value < 0.05
    t_sig = trend.ols_p_value < 0.05
    if mk_sig != t_sig:
        points.append(
            f"The two significance tests disagree: Mann-Kendall gives p = {trend.mk_p_value:.4f} but the "
            f"t-test gives p = {trend.ols_p_value:.4f}. The trend is borderline; outliers or a non-linear "
            "shape can pull the two tests apart."
        )
    if trend.seasonal_mk_p_value is not None and mk_sig and trend.seasonal_mk_p_value >= 0.05:
        points.append(
            f"Testing each calendar month separately (seasonal Mann-Kendall, p = {trend.seasonal_mk_p_value:.4f}) "
            "does not confirm the trend — it may be concentrated in a few months rather than year-round."
        )

    return points


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    await recorder.emit("SKEPTIC_AGENT", "running", "Arguing against the finding before it's finalized...")

    points = _build_skeptic_points(state)
    if not points:
        verdict = "no major objections raised"
    elif len(points) <= 2:
        verdict = "held up under scrutiny, with caveats"
    else:
        verdict = "should be treated cautiously"

    state.skeptic_points = points
    state.skeptic_verdict = verdict

    summary = f"Adversarial review: {verdict}."
    if points:
        summary += f" {len(points)} objection(s) raised."
    await recorder.emit("SKEPTIC_AGENT", "done", summary, {"skeptic_points": points, "verdict": verdict})
    return state
