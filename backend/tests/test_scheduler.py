"""Verifies the scheduler's due-watch query — the actual "recurring" part of
Watch mode. Uses the real database directly (not the API) since creating a
watch with a specific next_check_at in the past/future isn't something the
API exposes (it always defaults to now() on creation)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models import User, Watch
from app.services.scheduler import _run_due_watches


async def _make_user(session) -> User:
    user = User(email=f"sched-{uuid.uuid4().hex[:12]}@example.com", password_hash=hash_password("x"))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_run_due_watches_only_checks_watches_that_are_actually_due():
    async with AsyncSessionLocal() as session:
        user = await _make_user(session)
        now = datetime.now(timezone.utc)

        due = Watch(
            user_id=user.id, region_code="bangladesh", variable_code="T2M",
            next_check_at=now - timedelta(hours=1), is_active=True,
        )
        not_due = Watch(
            user_id=user.id, region_code="bangladesh", variable_code="T2M",
            next_check_at=now + timedelta(days=10), is_active=True,
        )
        paused_but_due = Watch(
            user_id=user.id, region_code="bangladesh", variable_code="T2M",
            next_check_at=now - timedelta(hours=1), is_active=False,
        )
        session.add_all([due, not_due, paused_but_due])
        await session.commit()
        await session.refresh(due)
        await session.refresh(not_due)
        await session.refresh(paused_but_due)

    with patch("app.services.scheduler.run_watch_check", new=AsyncMock()) as mocked:
        await _run_due_watches()
        checked_ids = {call.args[0] for call in mocked.call_args_list}

    assert due.id in checked_ids
    assert not_due.id not in checked_ids
    assert paused_but_due.id not in checked_ids
