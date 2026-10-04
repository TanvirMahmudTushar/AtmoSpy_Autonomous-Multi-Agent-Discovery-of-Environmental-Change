"""The cause / impact / action layer: known-answer tests for the gating rules,
plus integrity checks on the curated content (a typo'd sector or region code
should fail here, not silently render nothing)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.knowledge.content import (
    ENTRIES,
    FAMILY_REFERENCES,
    KIND_EXTRAS,
    REFERENCES,
    REGION_CONTEXT,
    REGION_EXTRAS,
    SECTORS,
    VARIABLE_FAMILY,
)
from app.knowledge.insight import (
    build_insight,
    concern_for_summary,
    concern_of,
    confidence_of,
    family_of,
)
from app.main import app
from app.nasa.regions import REGIONS_BY_CODE

ROBUST = {"verdict": "robust", "caveats": []}
CLEAN = {"verdict": "no major objections raised", "points": []}


def _insight(**overrides):
    args = dict(
        variable_code="PRECTOTCORR", region_code="sahel_west_africa", region_kind="region",
        total_change=-2.0, effect_size=1.5, significant=True, trend_units="mm/day/year",
        robustness=ROBUST, skeptic=CLEAN, spatial_summary=None, change_points=None, related_variables=None,
    )
    args.update(overrides)
    return build_insight(**args)


# ------------------------------------------------------------------ confidence

def test_confidence_high_when_nothing_doubts_the_finding():
    assert confidence_of(ROBUST, CLEAN)[0] == "high"


def test_confidence_medium_with_a_single_doubt():
    assert confidence_of({"verdict": "robust with caveats", "caveats": ["x"]}, CLEAN)[0] == "medium"
    assert confidence_of(ROBUST, {"verdict": "held up under scrutiny, with caveats", "points": ["x"]})[0] == "medium"


def test_ordinary_caveats_never_add_up_to_low():
    # Most findings carry some caveat; that must not be read as "the analysis doubts this".
    both = confidence_of(
        {"verdict": "robust with caveats", "caveats": []},
        {"verdict": "held up under scrutiny, with caveats", "points": []},
    )
    assert both[0] == "medium"


def test_confidence_low_only_on_a_negative_verdict():
    assert confidence_of({"verdict": "not robust", "caveats": []}, CLEAN)[0] == "low"
    assert confidence_of(ROBUST, {"verdict": "should be treated cautiously", "points": []})[0] == "low"
    # a negative verdict wins over a clean one from the other reviewer
    assert confidence_of({"verdict": "not robust", "caveats": []}, {"verdict": "no major objections raised", "points": []})[0] == "low"


def test_confidence_handles_missing_reviews():
    assert confidence_of(None, None)[0] == "high"


# --------------------------------------------------------------------- concern

def test_no_concern_when_not_significant_or_small():
    assert concern_of("precipitation", -2.0, 1.5, False, "high")[0] == "none"
    assert concern_of("precipitation", -2.0, 0.1, True, "high")[0] == "none"
    assert concern_of("precipitation", -2.0, None, True, "high")[0] == "none"
    assert concern_of("precipitation", 0.0, 1.5, True, "high")[0] == "none"


def test_harmful_direction_is_concerning_or_serious_by_effect_size():
    assert concern_of("precipitation", -1.0, 0.5, True, "high")[0] == "concerning"
    assert concern_of("precipitation", -1.0, 1.5, True, "high")[0] == "serious"
    assert concern_of("temperature", +1.0, 1.5, True, "high")[0] == "serious"
    assert concern_of("soil", -0.05, 0.9, True, "high")[0] == "serious"


def test_mixed_direction_is_only_ever_worth_watching():
    # More rain helps and harms — never labelled "bad" on its own.
    assert concern_of("precipitation", +5.0, 2.3, True, "high")[0] == "watch"
    assert concern_of("wind", -0.14, 1.5, True, "high")[0] == "watch"


def test_unexpected_cooling_is_not_called_bad():
    assert concern_of("temperature", -0.8, 1.6, True, "high")[0] == "watch"
    assert concern_of("temperature", -0.8, 0.5, True, "high")[0] == "none"


def test_low_confidence_lowers_the_level_one_step():
    assert concern_of("precipitation", -1.0, 1.5, True, "low")[0] == "concerning"
    assert concern_of("precipitation", -1.0, 0.5, True, "low")[0] == "watch"
    # a mixed finding is already at "watch" and is not pushed to "none"
    assert concern_of("precipitation", +1.0, 1.5, True, "low")[0] == "watch"


def test_summary_concern_matches_the_full_insight():
    for variable, change, effect in [("PRECTOTCORR", -2.0, 1.5), ("T2M", 1.0, 0.5), ("T2M", -0.8, 1.6), ("WS2M", -0.1, 1.4)]:
        full = build_insight(
            variable_code=variable, region_code="bangladesh", region_kind="country",
            total_change=change, effect_size=effect, significant=True, trend_units="u/year",
            robustness=ROBUST, skeptic=CLEAN, spatial_summary=None, change_points=None, related_variables=None,
        )
        assert full["concern"] == concern_for_summary(variable, change, effect, True, ROBUST, CLEAN)


# --------------------------------------------------------------------- insight

def test_no_clear_change_gives_no_causal_story():
    out = _insight(significant=False)
    assert out["applicable"] is False
    assert out["concern"] == "none"
    assert out["drivers"] == out["impacts"] == out["mitigate"] == out["adapt"] == []
    assert out["region_context"] is None
    assert "No clear change" in out["headline"]


def test_harmful_change_has_drivers_impacts_and_both_kinds_of_action():
    out = _insight()
    assert out["applicable"] is True
    assert out["concern"] == "serious"
    assert out["drivers"] and out["impacts"] and out["mitigate"] and out["adapt"]
    assert "drought" in out["region_context"].lower()
    assert out["disclaimer"]
    assert all(r["url"].startswith("https://") for r in out["references"])


def test_place_type_adds_extra_context():
    warm_ice = _insight(variable_code="T2M", total_change=1.7, region_code="greenland_south", region_kind="ice")
    assert any(i["sector"] == "cryosphere" for i in warm_ice["impacts"])
    warm_city = _insight(variable_code="T2M", total_change=1.7, region_code="bangladesh", region_kind="country")
    assert not any(i["sector"] == "cryosphere" for i in warm_city["impacts"])


def test_delta_flood_context_reaches_the_regions_it_is_meant_for():
    wetter = _insight(variable_code="PRECTOTCORR", total_change=+5.0, region_code="bangladesh", region_kind="country")
    assert any("salt-intrusion" in i["text"] for i in wetter["impacts"])
    assert any("cyclone shelters" in a for a in wetter["adapt"])
    elsewhere = _insight(variable_code="PRECTOTCORR", total_change=+5.0, region_code="sahel_west_africa", region_kind="region")
    assert not any("salt-intrusion" in i["text"] for i in elsewhere["impacts"])


def test_an_abrupt_step_is_called_out_as_a_possible_artifact():
    out = _insight(
        variable_code="T2M", total_change=-0.76, region_code="bangladesh", region_kind="country",
        change_points=[{"year": 1997, "shift": -0.96}],
    )
    steps = [e for e in out["evidence"] if e["kind"] == "step"]
    assert steps and "1997" in steps[0]["text"] and "data-source discontinuity" in steps[0]["text"]


def test_a_step_against_the_trend_is_not_said_to_explain_it():
    out = _insight(total_change=-2.0, change_points=[{"year": 2018, "shift": +2.04}])
    steps = [e for e in out["evidence"] if e["kind"] == "step"]
    assert steps and "accounts for much" not in steps[0]["text"]


def test_many_steps_are_summarised_as_an_unstable_record():
    out = _insight(change_points=[{"year": 1997, "shift": -2.2}, {"year": 2015, "shift": -0.9}, {"year": 2018, "shift": 2.0}])
    steps = [e for e in out["evidence"] if e["kind"] == "step"]
    assert len(steps) == 1
    assert "3 abrupt steps" in steps[0]["text"] and "1997" in steps[0]["text"] and "2018" in steps[0]["text"]
    assert "poor description" in steps[0]["text"]


def test_a_small_step_is_reported_without_the_artifact_warning():
    out = _insight(change_points=[{"year": 2004, "shift": -0.1}], total_change=-2.0)
    steps = [e for e in out["evidence"] if e["kind"] == "step"]
    assert steps and "discontinuity" not in steps[0]["text"]


def test_related_variables_are_framed_as_association_only():
    out = _insight(related_variables=[{"variable_name": "Root Zone Soil Wetness", "method": "pearson", "r": 0.6}])
    related = [e for e in out["evidence"] if e["kind"] == "related"]
    assert related and "association only" in related[0]["text"]


def test_opposite_regional_trends_are_surfaced():
    out = _insight(spatial_summary={"has_opposite_regional_trends": True, "increasing_cells": 27, "decreasing_cells": 45})
    assert any(e["kind"] == "spatial" and "27" in e["text"] and "45" in e["text"] for e in out["evidence"])


def test_reanalysis_caveat_only_applies_to_reanalysis_variables():
    assert any(e["kind"] == "data" for e in _insight()["evidence"])
    grace = _insight(variable_code="lwe_thickness", total_change=-8.0, trend_units="cm/year")
    assert not any(e["kind"] == "data" for e in grace["evidence"])


def test_unknown_variable_falls_back_honestly_instead_of_inventing():
    out = _insight(variable_code="MYSTERY", total_change=3.0, effect_size=2.0)
    assert family_of("MYSTERY") == "generic"
    assert out["concern"] == "watch"
    assert out["drivers"] == [] and out["adapt"] == []
    assert "does not have a curated" in out["headline"]


# ------------------------------------------------------------ content integrity

def test_every_sector_used_has_a_ui_icon():
    for (family, direction), entry in ENTRIES.items():
        for sector, text in entry.impacts:
            assert sector in SECTORS, f"{family}/{direction}: unknown sector {sector!r}"
            assert text.strip()
    for extra in KIND_EXTRAS.values():
        for sector, _ in extra.impacts:
            assert sector in SECTORS


def test_polarity_values_are_valid_and_directions_are_up_or_down():
    for (family, direction), entry in ENTRIES.items():
        assert direction in ("up", "down")
        assert entry.polarity in ("concerning", "mixed", "neutral")
        assert entry.headline.strip()


def test_every_harmful_entry_offers_a_way_to_cope():
    for (family, direction), entry in ENTRIES.items():
        if entry.polarity == "concerning":
            assert entry.drivers and entry.impacts and entry.adapt and entry.mitigate, (family, direction)


def test_region_context_and_extras_point_at_real_regions_and_kinds():
    for code in REGION_CONTEXT:
        assert code in REGIONS_BY_CODE, f"REGION_CONTEXT has unknown region {code!r}"
    kinds = {r.kind for r in REGIONS_BY_CODE.values()}
    for (_, _, kind) in KIND_EXTRAS:
        assert kind in kinds, f"KIND_EXTRAS uses kind {kind!r} that no region has"
    for (_, _, code) in REGION_EXTRAS:
        assert code in REGIONS_BY_CODE, f"REGION_EXTRAS has unknown region {code!r}"


def test_every_family_has_valid_references():
    for family in set(VARIABLE_FAMILY.values()) | {"generic"}:
        keys = FAMILY_REFERENCES[family]
        assert keys and all(k in REFERENCES for k in keys)


def test_curated_text_hedges_rather_than_attributes():
    """Guard the tone: general context must not read as a verdict on this finding."""
    banned = ("this trend is caused by", "this finding is caused by", "is definitely", "proves that")
    for entry in ENTRIES.values():
        blob = " ".join([entry.headline] + [t for _, t in entry.drivers] + [t for _, t in entry.impacts]).lower()
        assert not any(b in blob for b in banned)


# ------------------------------------------------------------------------- API

@pytest.mark.asyncio
async def test_api_exposes_concern_on_list_and_insight_on_detail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listing = (await client.get("/api/findings?limit=5")).json()
        if not listing:
            pytest.skip("no findings in the database to inspect")
        assert all(f["concern"] in ("none", "watch", "concerning", "serious") for f in listing)
        detail = (await client.get(f"/api/findings/{listing[0]['id']}")).json()
        assert detail["concern"] == listing[0]["concern"]
        ins = detail["insight"]
        assert ins["disclaimer"] and ins["references"]
        assert ins["confidence"] in ("low", "medium", "high")
        if not ins["applicable"]:
            assert ins["drivers"] == [] and ins["adapt"] == []
