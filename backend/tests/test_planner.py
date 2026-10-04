"""Fallback (no-LLM) planner tests — specifically the routing logic for
variables whose dataset isn't active yet (GRACE_FO's lwe_thickness, unless
NASA_EARTHDATA_TOKEN is configured in this environment). This is the exact
path that used to be a static UNSUPPORTED_HINTS lookup and is now dynamic
against app.nasa.catalog — worth locking in given how easy it'd be to
silently break the "never claim data works when it doesn't" guarantee."""

from app.llm.planner import fallback_plan
from app.nasa.catalog import VARIABLES_BY_CODE


def test_groundwater_question_falls_back_to_proxy_when_grace_not_active():
    plan = fallback_plan("Is groundwater depleting in the Indo-Gangetic Plain?")
    if "lwe_thickness" in VARIABLES_BY_CODE:
        # this environment has GRACE_FO wired up (a real token is configured)
        assert plan.variable_code == "lwe_thickness"
        assert plan.unsupported_variable_note is None
    else:
        assert plan.variable_code == "GWETROOT"
        assert plan.unsupported_variable_note is not None
        assert "groundwater" in plan.unsupported_variable_note.lower()


def test_temperature_question_routes_directly_no_note():
    plan = fallback_plan("Has temperature changed significantly in Bangladesh?")
    assert plan.variable_code == "T2M"
    assert plan.unsupported_variable_note is None


def test_vegetation_question_still_uses_static_unsupported_hint():
    plan = fallback_plan("Has vegetation greenness changed in the Amazon?")
    assert plan.variable_code == "GWETROOT"
    assert plan.unsupported_variable_note is not None
    assert "MODIS" in plan.unsupported_variable_note
