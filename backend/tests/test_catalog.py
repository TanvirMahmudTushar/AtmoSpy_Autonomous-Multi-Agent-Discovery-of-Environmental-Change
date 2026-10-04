"""app.nasa.catalog is what lets agents route to the right dataset for a
given variable instead of hardcoding "NASA_POWER" — this locks in the
contract every agent now depends on. See test_registry.py for the
conditional-registration behavior (GRACE_FO active vs. stubbed) — that's
tested against an explicitly controlled registry build, not this module's
ambient (import-time) state, which depends on whatever NASA_EARTHDATA_TOKEN
happens to be set in the environment running the tests."""

import pytest

from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable


def test_active_power_variables_are_all_resolvable():
    assert "T2M" in VARIABLES_BY_CODE
    assert dataset_code_for_variable("T2M") == "NASA_POWER"


def test_unknown_variable_raises():
    with pytest.raises(KeyError):
        dataset_code_for_variable("not_a_real_variable")
