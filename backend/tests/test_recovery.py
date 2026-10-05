"""Investigations left running by a dead process are failed at startup."""

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import Investigation
from app.services.recovery import fail_orphaned_investigations


@pytest.mark.asyncio
async def test_unfinished_investigations_are_marked_failed():
    async with AsyncSessionLocal() as session:
        running = Investigation(mode="discover", question=None, status="running")
        pending = Investigation(mode="nlp", question="q", status="pending")
        done = Investigation(mode="nlp", question="q", status="completed")
        session.add_all([running, pending, done])
        await session.commit()
        ids = (running.id, pending.id, done.id)

    assert await fail_orphaned_investigations() >= 2

    async with AsyncSessionLocal() as session:
        rows = {
            r.id: r.status
            for r in (await session.execute(select(Investigation).where(Investigation.id.in_(ids)))).scalars()
        }
    assert rows[ids[0]] == "failed"
    assert rows[ids[1]] == "failed"
    assert rows[ids[2]] == "completed"
