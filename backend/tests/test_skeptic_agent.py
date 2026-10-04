"""Unit tests for the Skeptic Agent's deterministic objection logic — every
point it raises must trace to a real computed number, and it must NOT raise
objections that don't apply (e.g. a long, clean, high-confidence series
should get zero objections)."""

from app.agents.skeptic_agent import _build_skeptic_points
from app.agents.state import InvestigationState
from app.analysis.quality import QualityReport
from app.analysis.trend import compute_trend
from app.llm.planner import InvestigationPlan
from app.nasa.regions import REGIONS_BY_CODE


def _base_state(years, values) -> InvestigationState:
    plan = InvestigationPlan(variable_code="T2M", region_code="bangladesh", start_year=years[0], end_year=years[-1])
    state = InvestigationState(
        investigation_id=None, question=None, mode="nlp", plan=plan, region=REGIONS_BY_CODE["bangladesh"]
    )
    state.years, state.values = years, values
    state.trend_result = compute_trend(years, values)
    state.change_points = []
    state.quality_report = QualityReport(
        period_start="x", period_end="y", requested_days=1, observed_days=1, completeness=1.0,
        max_gap_days=0, n_outliers=0, outlier_dates=[], range_violations=0,
        coverage_years=float(len(years)), passed=True, issues=[],
    )
    return state


def test_clean_long_series_raises_no_objections():
    years = list(range(1990, 2026))  # 36 years
    values = [10 + 0.5 * i for i in range(len(years))]  # strong, clean, linear
    state = _base_state(years, values)
    points = _build_skeptic_points(state)
    assert points == []


def test_short_series_raises_sample_size_objection():
    years = list(range(2015, 2026))  # 11 years — under the 15-year bar
    values = [10 + 0.5 * i for i in range(len(years))]
    state = _base_state(years, values)
    points = _build_skeptic_points(state)
    assert any("annual points" in p for p in points)


def test_low_completeness_raises_objection():
    years = list(range(1990, 2026))
    values = [10 + 0.5 * i for i in range(len(years))]
    state = _base_state(years, values)
    state.quality_report.completeness = 0.6
    points = _build_skeptic_points(state)
    assert any("60%" in p for p in points)


def test_strong_related_variable_raises_confound_objection():
    years = list(range(1990, 2026))
    values = [10 + 0.5 * i for i in range(len(years))]
    state = _base_state(years, values)
    state.related_variables = [{"variable_name": "Minimum Temperature", "r": 0.91, "p_value": 0.0001}]
    points = _build_skeptic_points(state)
    assert any("Minimum Temperature" in p and "0.91" in p for p in points)
