"""Shared SSE streaming helper for both /investigations/{id}/events and
/discover/{id}/events — both are just an investigation_id under the hood.

Deliberately opens its own short-lived DB session for the initial replay
read and closes it before entering the long-lived streaming loop, rather
than holding a request-scoped connection-pool slot for up to 10 minutes.
"""

import asyncio
import json
import uuid

from sqlalchemy import select
from starlette.responses import StreamingResponse

from app.db.session import AsyncSessionLocal
from app.models import Investigation, InvestigationStep
from app.services.events import DONE_SENTINEL, EVENT_BUS

STREAM_TIMEOUT_SECONDS = 600


async def event_stream(investigation_id: uuid.UUID):
    async with AsyncSessionLocal() as session:
        investigation = (
            await session.execute(select(Investigation).where(Investigation.id == investigation_id))
        ).scalar_one_or_none()
        if investigation is None:
            yield f"event: error\ndata: {json.dumps({'message': 'investigation not found'})}\n\n"
            return

        past_steps = (
            (
                await session.execute(
                    select(InvestigationStep)
                    .where(InvestigationStep.investigation_id == investigation_id)
                    .order_by(InvestigationStep.seq)
                )
            )
            .scalars()
            .all()
        )
        for step in past_steps:
            payload = {
                "agent": step.agent, "status": step.status, "message": step.message,
                "detail": step.detail, "seq": step.seq, "ts": step.created_at.isoformat(),
            }
            yield f"data: {json.dumps(payload)}\n\n"

        terminal = investigation.status in ("completed", "failed", "insufficient_data")

    if terminal:
        yield f"event: done\ndata: {json.dumps({'status': investigation.status})}\n\n"
        return

    queue = EVENT_BUS.subscribe(investigation_id)
    try:
        elapsed = 0
        while elapsed < STREAM_TIMEOUT_SECONDS:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                elapsed += 15
                yield ": keep-alive\n\n"
                continue
            if event is DONE_SENTINEL or event.get("status") == "stream_complete":
                yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"
                return
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        EVENT_BUS.unsubscribe(investigation_id, queue)


def sse_response(investigation_id: uuid.UUID) -> StreamingResponse:
    return StreamingResponse(
        event_stream(investigation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
