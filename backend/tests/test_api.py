"""API-level smoke tests. Investigation creation mocks out the background
orchestrator (real NASA calls are exercised separately by
scripts/demo_investigation.py and the adapter unit tests) so this suite
stays network-free and fast."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # These drive the frontend's live status strip — must be real booleans,
    # not hardcoded/fabricated.
    assert isinstance(body["database"], bool)
    assert isinstance(body["llm_available"], bool)


@pytest.mark.asyncio
async def test_get_datasets_lists_power_as_active():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/datasets")
    assert resp.status_code == 200
    codes = {d["code"]: d["status"] for d in resp.json()}
    # Always active, no credentials required.
    assert codes["NASA_POWER"] == "active"
    # MODIS_NDVI has no adapter at all yet, regardless of environment — the
    # one dataset code guaranteed to still be a stub everywhere.
    assert codes["MODIS_NDVI"] == "requires_credentials"
    # GRACE_FO/SMAP_L3 legitimately flip to "active" once NASA_EARTHDATA_TOKEN
    # is configured (see test_registry.py for that behavior under explicit
    # control) — asserting a fixed value here would just encode whatever
    # happens to be in this environment's .env, not a real invariant.
    assert codes["GRACE_FO"] in ("active", "requires_credentials")
    assert codes["SMAP_L3"] in ("active", "requires_credentials")


@pytest.mark.asyncio
async def test_get_regions_returns_seeded_gazetteer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/regions")
    assert resp.status_code == 200
    codes = {r["code"] for r in resp.json()}
    assert "bangladesh" in codes


@pytest.mark.asyncio
async def test_create_investigation_returns_id_and_schedules_background_run():
    with patch("app.api.investigations.run_investigation", new=AsyncMock()) as mocked:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/investigations", json={"question": "Is temperature rising in Bangladesh?"})
        assert resp.status_code == 201
        body = resp.json()
        assert "investigation_id" in body
        mocked.assert_called_once()
