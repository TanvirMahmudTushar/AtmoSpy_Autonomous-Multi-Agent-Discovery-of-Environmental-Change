"""Turns raw numbers into the three-way distinction spec section 11 requires:
visually noticeable vs. statistically significant vs. scientifically
important. All rule-based on computed quantities — no LLM judgment call.
"""

ALPHA = 0.05


def classify_significance(p_value: float, alpha: float = ALPHA) -> str:
    return "statistically_significant" if p_value < alpha else "not_significant"


def effect_size(total_change: float, std_dev: float) -> float:
    """|total change| / std. dev. of the annual series (a Cohen's-d-style ratio).
    Persisted on each Finding so views without the full series (Discover cards,
    the globe) can still size a visual to the change.
    """
    if std_dev == 0:
        return 0.0
    return abs(total_change) / std_dev


def importance_note(total_change: float, std_dev: float, percent_change: float | None) -> str:
    """Effect-size heuristic: how large is the total change relative to the
    variable's own year-to-year variability (a Cohen's-d-style ratio)? This
    is shown as a transparent computed number, not a hidden AI score, and is
    explicitly framed as separate from statistical significance.
    """
    effect = effect_size(total_change, std_dev)

    if effect < 0.2:
        bucket = "small relative to natural year-to-year variability"
    elif effect < 0.8:
        bucket = "moderate relative to natural year-to-year variability"
    else:
        bucket = "large relative to natural year-to-year variability"

    pct_txt = f" ({percent_change:+.1f}% over the period)" if percent_change is not None else ""
    return (
        f"Effect size = |total change| / std. dev. = {effect:.2f} — the observed change is "
        f"{bucket}{pct_txt}. A statistically significant trend can still have a small effect size; "
        "significance and scientific/practical importance are evaluated separately here."
    )
