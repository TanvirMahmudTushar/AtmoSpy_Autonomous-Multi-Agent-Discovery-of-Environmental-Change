"""Conditional adapter registration: GRACE_FO and SMAP_L3 must be real
adapters when NASA_EARTHDATA_TOKEN is configured and honest
UnavailableAdapter stubs otherwise — tested against an explicitly
controlled settings object rather than whatever happens to be in the
ambient environment/.env, so this stays correct regardless of who runs it
or where."""

from unittest.mock import patch

from app.core.config import Settings
from app.nasa.base import UnavailableAdapter
from app.nasa.grace import GraceAdapter
from app.nasa.registry import build_registry
from app.nasa.smap import SmapAdapter


def test_grace_fo_is_stubbed_without_a_token():
    with patch("app.nasa.registry.get_settings", return_value=Settings(NASA_EARTHDATA_TOKEN="")):
        registry = build_registry()
    assert isinstance(registry["GRACE_FO"], UnavailableAdapter)
    assert registry["GRACE_FO"].get_metadata().status == "requires_credentials"


def test_grace_fo_is_active_with_a_token():
    with patch("app.nasa.registry.get_settings", return_value=Settings(NASA_EARTHDATA_TOKEN="fake-token-for-test")):
        registry = build_registry()
    assert isinstance(registry["GRACE_FO"], GraceAdapter)
    assert registry["GRACE_FO"].get_metadata().status == "active"


def test_smap_is_stubbed_without_a_token():
    with patch("app.nasa.registry.get_settings", return_value=Settings(NASA_EARTHDATA_TOKEN="")):
        registry = build_registry()
    assert isinstance(registry["SMAP_L3"], UnavailableAdapter)
    assert registry["SMAP_L3"].get_metadata().status == "requires_credentials"


def test_smap_is_active_with_a_token():
    with patch("app.nasa.registry.get_settings", return_value=Settings(NASA_EARTHDATA_TOKEN="fake-token-for-test")):
        registry = build_registry()
    assert isinstance(registry["SMAP_L3"], SmapAdapter)
    assert registry["SMAP_L3"].get_metadata().status == "active"
