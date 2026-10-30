"""Agent 6 — Statistics Agent. Consolidates significance testing and draws
the explicit line between "statistically significant" and "scientifically
important" (spec section 11)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.services.events import StepRecorder
from app.tools import analysis_tools


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    await recorder.emit(
        "STATISTICS_AGENT", "running",
        "Testing significance (Mann-Kendall and t-test, both corrected for autocorrelation)...",
    )

    trend_result = state.trend_result
    significance = analysis_tools.calculate_statistical_significance(trend_result)
    ci = analysis_tools.calculate_confidence_interval(trend_result)
    importance = analysis_tools.calculate_importance_note(trend_result)
    detect = analysis_tools.calculate_detectability(trend_result)

    state.significance = significance
    state.confidence_interval = ci
    state.importance_note = importance
    state.detectability = detect

    verdict = "statistically significant" if significance["classification"] == "statistically_significant" else "not statistically significant"
    msg = (
        f"Mann-Kendall p = {trend_result.mk_p_value:.4f} — the trend is {verdict} at alpha=0.05. "
        f"Sen's slope 95% CI: [{ci['lower']:.4g}, {ci['upper']:.4g}] per year. "
        f"t-test p = {trend_result.ols_p_value:.4f} with an effective sample size of {trend_result.n_eff:.0f} "
        f"(lag-1 autocorrelation {trend_result.lag1:.2f})."
    )
    # Weatherhead's horizon is the expected wait for a typical record, so a
    # record can already be significant before it; only explain it when the
    # trend has not (yet) reached significance.
    if significance["classification"] != "statistically_significant" and detect["years_needed"] is not None:
        msg += (
            f" Not significant yet: a trend this size typically needs about {detect['years_needed']:.0f} years "
            f"of data to be detected; this record has {detect['years_available']}."
        )
    await recorder.emit(
        "STATISTICS_AGENT", "done", msg,
        {"significance": significance, "confidence_interval": ci, "importance_note": importance, "detectability": detect},
    )
    return state
