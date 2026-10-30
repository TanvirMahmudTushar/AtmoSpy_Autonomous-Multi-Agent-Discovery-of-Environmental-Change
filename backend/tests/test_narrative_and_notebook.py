"""The narrative guardrail's fallback, the sampling-aware reanalysis note,
and the reproducibility notebook (executed here to prove it recomputes the
app's own numbers)."""

import contextlib
import io
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.analysis import timeseries
from app.analysis.trend import ANALYSIS_VERSION, primary_trend
from app.knowledge.insight import build_insight
from app.llm.narrator import generate_narrative
from app.models import Finding
from app.services.notebook import build_notebook
from app.services.visualization import build_timeseries_chart

FACTS = {
    "variable_name": "Temperature", "region_name": "Testland", "trend_units": "degC",
    "trend_per_year": 0.03, "trend_per_decade": 0.3, "trend_basis": "monthly_anomaly",
    "p_value": 0.002, "t_test_p_value": 0.01, "significance_classification": "statistically_significant",
    "start_year": 1990, "end_year": 2020, "percent_change": None, "coverage_years": 31, "completeness": 1.0,
    "dataset_name": "Test data",
}


def _llm(reply: dict):
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.complete_json = AsyncMock(return_value=reply)
    return llm


@pytest.mark.asyncio
async def test_llm_text_with_untraceable_numbers_is_replaced_by_the_template():
    reply = {"interpretation": "Temperature rose 4.7 degC per decade.", "limitations": "None."}
    with patch("app.llm.narrator.get_llm_client", return_value=_llm(reply)):
        out = await generate_narrative(FACTS)
    assert out["source"] == "template"
    assert "4.7" in out["guardrail_flags"]
    assert "+0.3 degC per decade" in out["interpretation"]
    assert "4.7" not in out["interpretation"]


@pytest.mark.asyncio
async def test_clean_llm_text_is_kept():
    reply = {"interpretation": "Temperature rose by about 0.3 degC per decade (p = 0.002).", "limitations": "Short."}
    with patch("app.llm.narrator.get_llm_client", return_value=_llm(reply)):
        out = await generate_narrative(FACTS)
    assert out["source"] == "llm" and out["guardrail_flags"] == []


def _insight_texts(sampling):
    insight = build_insight(
        variable_code="T2M", region_code="tibetan_plateau", region_kind="plateau", total_change=1.0,
        effect_size=1.0, significant=True, trend_units="degC/year", robustness=None, skeptic=None,
        spatial_summary=None, change_points=None, related_variables=None, sampling=sampling,
    )
    return " ".join(e["text"] for e in insight["evidence"])


def test_reanalysis_note_matches_how_the_region_was_sampled():
    assert "averaged over the region" in _insight_texts({"method": "area_mean"})
    assert "centre point" in _insight_texts({"method": "centroid_point"})
    assert "centre point" in _insight_texts(None)  # findings from before regional averaging


@pytest.mark.parametrize("seasonal_amplitude, basis", [(5.0, "monthly_anomaly"), (0.0, "annual")])
def test_notebook_recomputes_the_apps_numbers(seasonal_amplitude, basis):
    rng = np.random.default_rng(1)
    dates = [date(y, m, 15) for y in range(1995, 2021) for m in range(1, 13)]
    if basis == "annual":
        # a dry season (all-zero months) forces the annual basis
        values = [(3 + 0.05 * (d.year - 1995) + rng.normal(0, 0.5)) if d.month in (6, 7, 8) else 0.0 for d in dates]
    else:
        values = [seasonal_amplitude * np.sin(d.month) + 0.02 * (d.year - 1995) + rng.normal(0, 0.4) for d in dates]
    bundle = timeseries.prepare(dates, values)
    t = primary_trend(bundle)
    assert t.basis == basis
    chart = build_timeseries_chart(
        [int(y) for y in bundle.annual.index], list(bundle.annual.values), t, [], "Test", "u", monthly=bundle
    )
    finding = Finding(
        id=uuid.uuid4(), title="Test finding", trend_per_year=t.sen_slope_per_year, p_value=t.mk_p_value,
        statistical_method="test", analysis_version=ANALYSIS_VERSION, trend_details=t.to_dict(),
    )
    nb = build_notebook(finding, "TEST", "Testland", {"timeseries": chart}, None)

    ns: dict = {}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                exec(cell["source"], ns)
    printed = out.getvalue()
    assert "DIFFERENT" not in printed
    assert printed.count("match") == 3
