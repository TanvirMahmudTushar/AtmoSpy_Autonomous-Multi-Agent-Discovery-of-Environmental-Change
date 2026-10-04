"""Agent 6 — Statistics Agent. Consolidates significance testing and draws
the explicit line between "statistically significant" and "scientifically
important" (spec section 11)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.services.events import StepRecorder
from app.tools import analysis_tools


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    await recorder.emit("STATISTICS_AGENT", "running", "Testing statistical significance (Mann-Kendall)...")

    trend_result = state.trend_result
    significance = analysis_tools.calculate_statistical_significance(trend_result)
    ci = analysis_tools.calculate_confidence_interval(state.years, state.values)
    importance = analysis_tools.calculate_importance_note(trend_result)

    state.significance = significance
    state.confidence_interval = ci
    state.importance_note = importance

    verdict = "statistically significant" if significance["classification"] == "statistically_significant" else "not statistically significant"
    await recorder.emit(
        "STATISTICS_AGENT", "done",
        f"Mann-Kendall p = {trend_result.mk_p_value:.4f} — the trend is {verdict} at alpha=0.05. "
        f"Sen's slope 95% CI: [{ci['lower']:.4g}, {ci['upper']:.4g}].",
        {"significance": significance, "confidence_interval": ci, "importance_note": importance},
    )
    return state
