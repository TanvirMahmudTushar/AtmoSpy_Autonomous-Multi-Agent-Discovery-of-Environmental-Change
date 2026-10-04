"""Verifies the in-memory rate limiter actually blocks excessive requests to
the login endpoint — the concrete threat this guards against is credential
stuffing / brute force against real user accounts."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import reset_for_tests
from app.main import app


@pytest.mark.asyncio
async def test_login_is_rate_limited_after_threshold():
    reset_for_tests()
    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/signup", json={"email": email, "password": "correct-horse-battery"})

        statuses = []
        for _ in range(25):
            resp = await client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
            statuses.append(resp.status_code)

        assert 429 in statuses, "expected the limiter to kick in within 25 rapid requests"
        assert statuses[:20].count(401) == 20, "the first 20 attempts should be normal 401s, not blocked"
