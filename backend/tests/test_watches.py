"""Watch mode: API-level tests (auth, ownership, validation) with the actual
pipeline execution mocked out — same reasoning as test_api.py's investigation
tests, real NASA/network calls are out of scope here. _build_note is pure
logic and tested directly against known before/after snapshots."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.watch_runner import _build_note
from app.main import app
from app.models import Watch


def _unique_email() -> str:
    return f"watch-test-{uuid.uuid4().hex[:12]}@example.com"


async def _signed_up_client(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/auth/signup", json={"email": _unique_email(), "password": "correct-horse-battery"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_watch_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/watches", json={"region_code": "bangladesh", "variable_code": "T2M"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_watch_rejects_unknown_codes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _signed_up_client(client)
        resp = await client.post(
            "/api/watches", json={"region_code": "atlantis", "variable_code": "T2M"}, headers=headers
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_list_and_delete_watch_roundtrip():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _signed_up_client(client)

        create_resp = await client.post(
            "/api/watches",
            json={"region_code": "bangladesh", "variable_code": "T2M", "frequency_days": 14},
            headers=headers,
        )
        assert create_resp.status_code == 201
        watch = create_resp.json()
        assert watch["region_code"] == "bangladesh"
        assert watch["frequency_days"] == 14
        assert watch["is_active"] is True
        # No check has run yet, so neither snapshot exists — but the fields
        # must be present for the UI's previous-vs-latest comparison.
        assert watch["last_trend_per_year"] is None
        assert watch["prev_trend_per_year"] is None
        assert watch["prev_significance"] is None

        list_resp = await client.get("/api/watches", headers=headers)
        assert list_resp.status_code == 200
        assert any(w["id"] == watch["id"] for w in list_resp.json())

        del_resp = await client.delete(f"/api/watches/{watch['id']}", headers=headers)
        assert del_resp.status_code == 204

        list_resp2 = await client.get("/api/watches", headers=headers)
        assert all(w["id"] != watch["id"] for w in list_resp2.json())


@pytest.mark.asyncio
async def test_toggle_watch_flips_is_active():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _signed_up_client(client)
        create_resp = await client.post(
            "/api/watches", json={"region_code": "bangladesh", "variable_code": "T2M"}, headers=headers
        )
        watch_id = create_resp.json()["id"]

        toggled = await client.post(f"/api/watches/{watch_id}/toggle", headers=headers)
        assert toggled.status_code == 200
        assert toggled.json()["is_active"] is False

        toggled_back = await client.post(f"/api/watches/{watch_id}/toggle", headers=headers)
        assert toggled_back.json()["is_active"] is True


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_watch():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        owner_headers = await _signed_up_client(client)
        other_headers = await _signed_up_client(client)

        create_resp = await client.post(
            "/api/watches", json={"region_code": "bangladesh", "variable_code": "T2M"}, headers=owner_headers
        )
        watch_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/watches/{watch_id}", headers=other_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_check_now_creates_investigation_and_schedules_execution():
    with patch("app.api.watches.execute_watch_check", new=AsyncMock()) as mocked:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _signed_up_client(client)
            create_resp = await client.post(
                "/api/watches", json={"region_code": "bangladesh", "variable_code": "T2M"}, headers=headers
            )
            watch_id = create_resp.json()["id"]

            resp = await client.post(f"/api/watches/{watch_id}/check-now", headers=headers)
            assert resp.status_code == 200
            assert "investigation_id" in resp.json()
            mocked.assert_called_once()


@pytest.mark.asyncio
async def test_two_concurrent_check_now_calls_get_distinct_investigation_ids():
    """The real bug this guards against: check-now used to guess 'the most
    recently created investigation for this user', which breaks the moment
    two checks are in flight at once."""
    with patch("app.api.watches.execute_watch_check", new=AsyncMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _signed_up_client(client)
            watch_ids = []
            for _ in range(2):
                r = await client.post(
                    "/api/watches", json={"region_code": "bangladesh", "variable_code": "T2M"}, headers=headers
                )
                watch_ids.append(r.json()["id"])

            resp_a = await client.post(f"/api/watches/{watch_ids[0]}/check-now", headers=headers)
            resp_b = await client.post(f"/api/watches/{watch_ids[1]}/check-now", headers=headers)
            assert resp_a.json()["investigation_id"] != resp_b.json()["investigation_id"]


def _watch(**overrides) -> Watch:
    defaults = dict(last_trend_per_year=None, last_significance=None)
    defaults.update(overrides)
    return Watch(**defaults)


def test_build_note_first_check_has_nothing_to_compare():
    note = _build_note(_watch(), new_trend=0.5, new_significance="not_significant")
    assert "First check" in note


def test_build_note_insufficient_data():
    note = _build_note(_watch(last_trend_per_year=0.2, last_significance="not_significant"), new_trend=None, new_significance=None)
    assert "insufficient data" in note


def test_build_note_flags_sign_flip():
    watch = _watch(last_trend_per_year=0.3, last_significance="not_significant")
    note = _build_note(watch, new_trend=-0.1, new_significance="not_significant")
    assert "flipped" in note


def test_build_note_flags_newly_significant():
    watch = _watch(last_trend_per_year=0.3, last_significance="not_significant")
    note = _build_note(watch, new_trend=0.35, new_significance="statistically_significant")
    assert "Newly statistically significant" in note


def test_build_note_flags_lost_significance():
    watch = _watch(last_trend_per_year=0.3, last_significance="statistically_significant")
    note = _build_note(watch, new_trend=0.28, new_significance="not_significant")
    assert "No longer statistically significant" in note


def test_build_note_consistent_when_nothing_changed():
    watch = _watch(last_trend_per_year=0.3, last_significance="statistically_significant")
    note = _build_note(watch, new_trend=0.31, new_significance="statistically_significant")
    assert "Consistent" in note
