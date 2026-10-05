"""Startup recovery for work that died with the previous process.

Investigations and discovery scans run as in-process asyncio tasks, so a
restart (a deploy, or the host recycling the instance) kills them and leaves
their rows 'pending' or 'running' forever. Clients then wait on an event
stream that never finishes. Marking them failed at boot lets the UI show the
real outcome instead of an endless spinner.
"""

import logging

from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models import Investigation

logger = logging.getLogger("app.recovery")

UNFINISHED = ("pending", "running")


async def fail_orphaned_investigations() -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(Investigation).where(Investigation.status.in_(UNFINISHED)).values(status="failed")
        )
        await session.commit()
    count = result.rowcount or 0
    if count:
        logger.warning("Marked %d unfinished investigation(s) as failed after restart", count)
    return count
