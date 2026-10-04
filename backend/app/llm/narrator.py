"""Report Agent's narrative writer.

The LLM (or, without a key, a deterministic template) is given the already-
computed structured numbers and asked only to phrase an interpretation —
never to produce new numbers. `_numeric_guardrail` scans whatever text comes
back and flags any number that doesn't trace to the supplied data, so a
fabrication is caught and surfaced rather than silently trusted.
"""

import re

from app.llm.client import get_llm_client

NUMBER_PATTERN = re.compile(r"-?\d+\.?\d*")


def _allowed_numbers(finding_facts: dict) -> set[str]:
    allowed: set[str] = set()

    def add(value):
        if value is None:
            return
        try:
            f = float(value)
        except (TypeError, ValueError):
            return
        for nd in (0, 1, 2):
            allowed.add(f"{f:.{nd}f}")
            allowed.add(f"{abs(f):.{nd}f}")
        # Fields like confidence (0.95) and completeness (0.83) are fractions
        # in the data but conventionally written as percentages ("95%
        # confidence interval") in prose — allow both scales so a correct
        # restatement doesn't get flagged as a fabrication.
        if 0 <= abs(f) <= 1:
            pct = f * 100
            for nd in (0, 1):
                allowed.add(f"{pct:.{nd}f}")

    def walk(v):
        if isinstance(v, (int, float)):
            add(v)
        elif isinstance(v, str):
            for m in NUMBER_PATTERN.findall(v):
                add(m)
        elif isinstance(v, dict):
            for item in v.values():
                walk(item)
        elif isinstance(v, (list, tuple)):
            for item in v:
                walk(item)

    for v in finding_facts.values():
        walk(v)
    # small integers (years, counts) are always fine to restate
    for y in range(1981, 2036):
        allowed.add(str(y))
    return allowed


def numeric_guardrail(text: str, finding_facts: dict) -> list[str]:
    """Returns a list of numeric tokens present in `text` that don't match
    any number in `finding_facts` (within simple rounding tolerance).
    Percent signs / units adjacent to the number are ignored for matching.
    """
    allowed = _allowed_numbers(finding_facts)
    flagged = []
    for token in NUMBER_PATTERN.findall(text):
        try:
            f = float(token)
        except ValueError:
            continue
        if abs(f) < 3 and f == int(f):
            continue  # small integers ("2" datasets, "3 regions") are narrative, not data
        candidates = {f"{f:.0f}", f"{f:.1f}", f"{f:.2f}", f"{abs(f):.0f}", f"{abs(f):.1f}", f"{abs(f):.2f}"}
        if not candidates & allowed:
            flagged.append(token)
    return flagged


REPORT_SYSTEM_PROMPT = """You are the Report Agent of a NASA Earth-science investigation system.
You will be given ALREADY-COMPUTED structured results (trend, significance, data quality, related
variables). Write a short scientific interpretation (3-5 sentences) and a short limitations note
(1-3 sentences).

Rules you MUST follow:
1. Do NOT introduce any number that is not present in the data given to you.
2. Never claim correlation implies causation. If related variables are mentioned, use language like
   "coincides with" or "is associated with", and explicitly say further investigation would be
   needed to establish causation.
3. Clearly distinguish statistical significance from practical/scientific importance if both are
   relevant.
4. Be precise and measured — this is a scientific report, not marketing copy.
5. Output ONLY a JSON object: {"interpretation": "...", "limitations": "..."}
"""


def template_narrative(facts: dict) -> dict:
    """Deterministic fallback narrative used when no LLM key is configured."""
    direction = "increasing" if facts.get("trend_per_year", 0) > 0 else "decreasing"
    sig = facts.get("significance_classification")
    sig_txt = (
        "statistically significant (p = {:.4f})".format(facts["p_value"])
        if sig == "statistically_significant"
        else "not statistically significant (p = {:.4f})".format(facts.get("p_value", 1.0))
    )
    pct = facts.get("percent_change")
    pct_txt = f", a total change of {pct:+.1f}% over the period" if pct is not None else ""

    interpretation = (
        f"{facts.get('variable_name', 'The variable')} in {facts.get('region_name', 'the selected region')} "
        f"shows a {direction} trend of {facts.get('trend_per_year', 0):+.4g} {facts.get('trend_units', '')} "
        f"per year between {facts.get('start_year')} and {facts.get('end_year')}{pct_txt}. "
        f"This trend is {sig_txt} under the Mann-Kendall test. "
    )
    related = facts.get("related_variables") or []
    if related:
        top = related[0]
        interpretation += (
            f"The trend coincides with a {top.get('method')} correlation of r={top.get('r'):.2f} "
            f"with {top.get('variable_name')} (p={top.get('p_value'):.4f}) over the same period, "
            "which suggests a relationship worth further investigation — this is not evidence of "
            "causation."
        )

    limitations = (
        f"Based on {facts.get('coverage_years', 'the available')} years of "
        f"{facts.get('dataset_name', 'NASA')} data with {facts.get('completeness', 0):.0%} temporal "
        "completeness. Reanalysis/model-derived and gravity-derived data each carry their own "
        "uncertainty distinct from direct instrument retrievals, and a regional average can mask "
        "sub-regional variability."
    )
    return {"interpretation": interpretation, "limitations": limitations}


async def generate_narrative(facts: dict) -> dict:
    """Returns {"interpretation": str, "limitations": str, "source": "llm"|"template",
    "guardrail_flags": list[str]}."""
    llm = get_llm_client()
    if llm.is_available():
        result = await llm.complete_json(REPORT_SYSTEM_PROMPT, f"DATA:\n{facts}")
        if result and "interpretation" in result:
            combined_text = f"{result.get('interpretation', '')} {result.get('limitations', '')}"
            flags = numeric_guardrail(combined_text, facts)
            return {
                "interpretation": result["interpretation"],
                "limitations": result.get("limitations", ""),
                "source": "llm",
                "guardrail_flags": flags,
            }

    fallback = template_narrative(facts)
    return {**fallback, "source": "template", "guardrail_flags": []}
