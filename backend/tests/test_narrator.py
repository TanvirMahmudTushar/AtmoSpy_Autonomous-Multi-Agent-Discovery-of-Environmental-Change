"""Regression test for a real false-positive caught in live testing: the LLM
correctly restated a 95% confidence interval (stored as confidence=0.95, a
fraction) as "95% confidence interval" (a percentage), and the guardrail
flagged "95" as an unverified/fabricated number.
"""

from app.llm.narrator import numeric_guardrail


def test_guardrail_accepts_percent_form_of_stored_fraction():
    facts = {
        "confidence_interval": {"lower": 0.0018, "upper": 0.0399, "confidence": 0.95},
        "p_value": 0.041,
        "trend_per_year": 0.0195,
    }
    text = "The trend has a 95% confidence interval of 0.0018-0.0399 degC/yr."
    flags = numeric_guardrail(text, facts)
    assert flags == []


def test_guardrail_still_flags_a_genuinely_fabricated_number():
    facts = {"p_value": 0.041, "trend_per_year": 0.0195, "percent_change": 12.3}
    text = "The trend increased by 47.9% over the period."
    flags = numeric_guardrail(text, facts)
    assert "47.9" in flags
