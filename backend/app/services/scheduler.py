"""In-process background scheduler for Watch mode.

Deliberately not Celery/cron — consistent with the project's existing "no
Redis, no Celery" scope decision (running more than one backend instance would need a real job queue: the
`next_check_at <= now()` query below is what a real job queue's scheduling
table would do too, this is just that same idea running as one asyncio loop
instead of a separate worker process).
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.agents.watch_runner import run_watch_check
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Watch

logger = logging.getLogger(__name__)


async def _run_due_watches() -> None:
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.WATCH_MAX_CONCURRENCY)

    async with AsyncSessionLocal() as session:
        due = (
            await session.execute(
                select(Watch.id).where(Watch.is_active.is_(True), Watch.next_check_at <= datetime.now(timezone.utc))
            )
        ).scalars().all()

    if not due:
        return
    logger.info("Scheduler: %d watch(es) due for a check", len(due))

    async def _guarded(watch_id):
        async with semaphore:
            try:
                await run_watch_check(watch_id)
            except Exception:  # noqa: BLE001 - one watch's failure must not kill the scheduler loop
                logger.exception("Scheduled check for watch %s raised unexpectedly", watch_id)

    await asyncio.gather(*(_guarded(watch_id) for watch_id in due))


async def scheduler_loop() -> None:
    settings = get_settings()
    interval = settings.WATCH_SCHEDULER_INTERVAL_SECONDS
    logger.info("Watch scheduler started (checking every %ds)", interval)
    try:
        while True:
            try:
                await _run_due_watches()
            except Exception:  # noqa: BLE001 - a bad query/DB hiccup must not kill the whole loop
                logger.exception("Watch scheduler tick failed")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Watch scheduler stopped")
        raise
