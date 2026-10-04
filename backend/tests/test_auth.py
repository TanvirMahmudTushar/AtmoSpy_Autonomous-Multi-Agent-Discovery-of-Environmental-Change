"""Auth endpoint tests. Uses the real database (via the shared engine) since
password hashing/verification and uniqueness constraints are worth testing
against the actual schema, not mocks. Each test uses a unique email so runs
don't collide with leftover rows from previous runs."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


@pytest.mark.asyncio
async def test_signup_then_me_roundtrip():
    email = _unique_email()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        signup_resp = await client.post(
            "/api/auth/signup", json={"email": email, "password": "correct-horse-battery", "display_name": "Ada"}
        )
        assert signup_resp.status_code == 201
        body = signup_resp.json()
        assert body["user"]["email"] == email
        assert body["user"]["display_name"] == "Ada"
        assert "access_token" in body
        # the hash must never be echoed back to the client
        assert "password" not in body["user"]
        assert "password_hash" not in body["user"]

        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == email


@pytest.mark.asyncio
async def test_signup_duplicate_email_rejected():
    email = _unique_email()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/auth/signup", json={"email": email, "password": "correct-horse-battery"})
        assert first.status_code == 201
        second = await client.post("/api/auth/signup", json={"email": email, "password": "another-password-1"})
        assert second.status_code == 409


@pytest.mark.asyncio
async def test_login_with_wrong_password_rejected():
    email = _unique_email()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/signup", json={"email": email, "password": "correct-horse-battery"})
        resp = await client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_correct_password_returns_token():
    email = _unique_email()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/signup", json={"email": email, "password": "correct-horse-battery"})
        resp = await client.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery"})
        assert resp.status_code == 200
        assert resp.json()["user"]["email"] == email


@pytest.mark.asyncio
async def test_me_without_token_is_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_garbage_token_is_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_guest_login_returns_a_usable_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/guest")
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["user"]["email"].startswith("guest-")
        assert body["user"]["display_name"].startswith("Guest-")

        # the token must actually authenticate, same as a real signup's would
        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["id"] == body["user"]["id"]


@pytest.mark.asyncio
async def test_two_guest_logins_get_distinct_accounts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = (await client.post("/api/auth/guest")).json()
        second = (await client.post("/api/auth/guest")).json()
        assert first["user"]["id"] != second["user"]["id"]
        assert first["user"]["email"] != second["user"]["email"]


@pytest.mark.asyncio
async def test_create_investigation_without_auth_still_works():
    """Anonymous usage must keep working exactly as before — auth is
    additive, never required."""
    from unittest.mock import AsyncMock, patch

    with patch("app.api.investigations.run_investigation", new=AsyncMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/investigations", json={"question": "Is temperature rising anywhere?"})
            assert resp.status_code == 201
