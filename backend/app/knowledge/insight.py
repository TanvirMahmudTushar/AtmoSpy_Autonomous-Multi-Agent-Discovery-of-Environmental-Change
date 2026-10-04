"""Turns a finding's own computed numbers into the "cause / impact / action"
view — without inventing anything.

Two separate things are combined here and kept apart in the output:

* Judgement from *this finding's data*: is the change clear and large enough
  to matter (significance + effect size), how much do we trust it (the
  robustness and skeptic verdicts already computed), and what does its own
  data say (an abrupt step, a co-moving variable, opposite trends across the
  region). Every number in `evidence` comes from the finding.
* General context for *this kind of change* from app/knowledge/content.py:
  commonly cited drivers, typical impacts, and what reduces or copes with
  them. This is labelled as general, hedged, and never presented as the
  attributed cause of this particular trend.

Nothing is shown as "bad" unless the change is statistically clear, not
small next to normal year-to-year swings, and in a direction that is
generally harmful for that variable; and a finding the pipeline itself
doubts is downgraded rather than dressed up.
"""

from app.knowledge.content import (
    ENTRIES,
    GENERIC_ENTRY,
    KIND_EXTRAS,
    REGION_CONTEXT,
    REGION_EXTRAS,
    VARIABLE_FAMILY,
    Entry,
    references_for,
)

EFFECT_SMALL = 0.2  # same cut-offs as analysis/significance.py::importance_note
EFFECT_LARGE = 0.8

CONCERN_LEVELS = ("none", "watch", "concerning", "serious")

DISCLAIMER = (
    "General scientific context for this kind of change, drawn from the cited assessments. "
    "It is not derived from this finding's data and does not attribute this specific trend "
    "to any one cause. Every number elsewhere on this page comes from the computed analysis."
)

REANALYSIS_NOTE = (
    "The underlying data is reanalysis (model-assimilated) sampled at the region's centre point, "
    "so a trend can partly reflect changes in the observing system rather than the climate."
)


def family_of(variable_code: str) -> str:
    return VARIABLE_FAMILY.get(variable_code, "generic")


def direction_of(total_change: float) -> str:
    if total_change > 0:
        return "up"
    if total_change < 0:
        return "down"
    return "flat"


def _entry(family: str, direction: str) -> Entry:
    return ENTRIES.get((family, direction), GENERIC_ENTRY)


def confidence_of(robustness: dict | None, skeptic: dict | None) -> tuple[str, list[str]]:
    """Trust in the *finding* (not in any explanation of it), from verdicts the
    pipeline already computed.

    Low is reserved for a negative verdict — the trend "is not robust" or the
    skeptic says to treat it "cautiously". Ordinary caveats mean it held up but
    has things worth knowing, so they give medium; only a clean pass is high.
    (Most findings carry some caveat, so treating caveats as doubt would label
    the majority "low" and stop the label meaning anything.)
    """
    reasons: list[str] = []
    low = medium = False

    rob = (robustness or {}).get("verdict")
    if rob == "not robust":
        low = True
        reasons.append("The robustness check says the trend does not hold up across both halves of the record.")
    elif rob == "robust with caveats":
        medium = True
        reasons.append("The trend held up in both halves of the record, with caveats (for example an abrupt step).")

    skep = (skeptic or {}).get("verdict")
    if skep == "should be treated cautiously":
        low = True
        reasons.append("The skeptic review raised several objections.")
    elif skep == "held up under scrutiny, with caveats":
        medium = True
        reasons.append("The skeptic review found it held up, with objections worth keeping in mind.")

    level = "low" if low else "medium" if medium else "high"
    return level, reasons


def concern_of(
    family: str,
    total_change: float,
    effect_size: float | None,
    significant: bool,
    confidence: str,
) -> tuple[str, list[str]]:
    """none | watch | concerning | serious, with the reasons that produced it."""
    direction = direction_of(total_change)
    reasons: list[str] = []
    if direction == "flat" or not significant:
        return "none", ["The trend is not statistically clear, so no judgement is made."]
    if effect_size is None:
        return "none", ["The size of the change relative to normal swings is unavailable."]
    if effect_size < EFFECT_SMALL:
        return "none", ["The change is statistically detectable but small next to normal year-to-year swings."]

    reasons.append(
        f"Statistically clear and {'large' if effect_size >= EFFECT_LARGE else 'moderate'} "
        f"next to normal swings (effect size {effect_size:.2f})."
    )
    polarity = _entry(family, direction).polarity
    if polarity == "concerning":
        level = 3 if effect_size >= EFFECT_LARGE else 2
        reasons.append("A change in this direction is generally harmful for this variable.")
    elif polarity == "mixed":
        level = 1
        reasons.append("A change in this direction helps some things and harms others.")
    else:
        level = 1 if effect_size >= EFFECT_LARGE else 0
        reasons.append("There is no general judgement for a change in this direction.")

    if confidence == "low" and level >= 2:
        level -= 1
        reasons.append("Lowered one level because the pipeline itself doubts this finding.")
    return CONCERN_LEVELS[level], reasons


def concern_for_summary(
    variable_code: str,
    total_change: float,
    effect_size: float | None,
    significant: bool,
    robustness: dict | None,
    skeptic: dict | None,
) -> str:
    """The same concern level as the full insight, from summary-row fields only —
    lets the list endpoint tag cards without building the whole insight."""
    confidence, _ = confidence_of(robustness, skeptic)
    level, _ = concern_of(family_of(variable_code), total_change, effect_size, significant, confidence)
    return level


def _base_units(trend_units: str) -> str:
    return trend_units[: -len("/year")] if trend_units.endswith("/year") else trend_units


# Satellite-retrieved, not model reanalysis — the standing data caveat does not apply.
_NON_REANALYSIS = {"lwe_thickness", "soil_moisture"}


def _evidence(
    total_change: float,
    trend_units: str,
    change_points: list[dict] | None,
    related_variables: list[dict] | None,
    spatial_summary: dict | None,
    reanalysis: bool,
) -> list[dict]:
    """What this finding's own data says that bears on cause — all from computed fields."""
    out: list[dict] = []
    units = _base_units(trend_units)

    steps = [cp for cp in (change_points or []) if cp.get("shift") is not None and cp.get("year") is not None]
    if len(steps) >= 3:
        # Many steps: one steady trend is a poor description; list years, not each shift.
        years = ", ".join(str(cp["year"]) for cp in steps)
        out.append({
            "kind": "step",
            "text": (
                f"{len(steps)} abrupt steps were detected ({years}), so a single steady trend is a poor "
                "description of this record. Repeated steps often reflect regime changes or "
                "data-source discontinuities rather than gradual driving."
            ),
        })
    else:
        for cp in steps:
            shift, year = cp["shift"], cp["year"]
            # A step only "explains" the change if it points the same way and is big next to it.
            same_direction = total_change != 0 and (shift > 0) == (total_change > 0)
            if same_direction and abs(shift) >= 0.5 * abs(total_change):
                out.append({
                    "kind": "step",
                    "text": (
                        f"An abrupt shift of {shift:+.2f} {units} around {year} accounts for much of the "
                        "overall change. Sudden steps often point to a regime change or a data-source "
                        "discontinuity rather than gradual driving."
                    ),
                })
            else:
                out.append({"kind": "step", "text": f"A step of {shift:+.2f} {units} was detected around {year}."})

    for rv in (related_variables or [])[:2]:
        out.append({
            "kind": "related",
            "text": (
                f"Moves together with {rv['variable_name']} "
                f"({rv['method']} r = {rv['r']:+.2f}) — an association only, not proof of cause."
            ),
        })

    if spatial_summary and spatial_summary.get("has_opposite_regional_trends"):
        out.append({
            "kind": "spatial",
            "text": (
                f"Parts of the region move in opposite directions "
                f"({spatial_summary.get('increasing_cells', 0)} grid cells rising, "
                f"{spatial_summary.get('decreasing_cells', 0)} falling), so one regional story is too simple."
            ),
        })

    if reanalysis:
        out.append({"kind": "data", "text": REANALYSIS_NOTE})
    return out


def build_insight(
    *,
    variable_code: str,
    region_code: str,
    region_kind: str,
    total_change: float,
    effect_size: float | None,
    significant: bool,
    trend_units: str,
    robustness: dict | None,
    skeptic: dict | None,
    spatial_summary: dict | None,
    change_points: list[dict] | None,
    related_variables: list[dict] | None,
) -> dict:
    family = family_of(variable_code)
    reanalysis = variable_code not in _NON_REANALYSIS
    evidence = _evidence(total_change, trend_units, change_points, related_variables, spatial_summary, reanalysis)
    direction = direction_of(total_change)
    confidence, confidence_reasons = confidence_of(robustness, skeptic)
    concern, concern_reasons = concern_of(family, total_change, effect_size, significant, confidence)
    refs = [{"label": r.label, "url": r.url} for r in references_for(family)]

    base = {
        "concern": concern,
        "concern_reasons": concern_reasons,
        "confidence": confidence,
        "confidence_reasons": confidence_reasons,
        "family": family,
        "direction": direction,
        "disclaimer": DISCLAIMER,
        "references": refs,
    }

    # No clear change: say so, and do not tell a causal story about noise.
    if concern == "none":
        return {
            **base,
            "applicable": False,
            "headline": "No clear change to explain.",
            "evidence": evidence,
            "drivers": [], "impacts": [], "mitigate": [], "adapt": [], "region_context": None,
        }

    entry = _entry(family, direction)
    impacts = [{"sector": s, "text": t} for s, t in entry.impacts]
    mitigate = list(entry.mitigate)
    adapt = list(entry.adapt)
    for extra in (
        KIND_EXTRAS.get((family, direction, region_kind)),
        REGION_EXTRAS.get((family, direction, region_code)),
    ):
        if extra:
            impacts += [{"sector": s, "text": t} for s, t in extra.impacts]
            mitigate += list(extra.mitigate)
            adapt += list(extra.adapt)

    return {
        **base,
        "applicable": True,
        "headline": entry.headline,
        "evidence": evidence,
        "drivers": [{"title": t, "text": x} for t, x in entry.drivers],
        "impacts": impacts,
        "mitigate": mitigate,
        "adapt": adapt,
        "region_context": REGION_CONTEXT.get(region_code),
    }
