"""In-process event bus for streaming agent progress over SSE, plus durable
persistence to `investigation_steps` so a client can reconnect mid-run or
replay history for a completed investigation.

Single-process in-memory queues are the right scope here: this is a
hackathon-scale deployment (one backend instance), and every event is also
written to Postgres, so nothing is lost if a subscriber isn't connected yet.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InvestigationStep

DONE_SENTINEL = {"agent": "SYSTEM", "status": "stream_complete", "message": "", "detail": None}


@dataclass
class StepEvent:
    agent: str
    status: str  # running | done | error | skipped
    message: str
    detail: dict | None = None
    seq: int = 0
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "status": self.status,
            "message": self.message,
            "detail": self.detail,
            "seq": self.seq,
            "ts": self.ts,
        }


class EventBus:
    def __init__(self):
        self._queues: dict[uuid.UUID, list[asyncio.Queue]] = {}

    def _subscribers(self, investigation_id: uuid.UUID) -> list[asyncio.Queue]:
        return self._queues.setdefault(investigation_id, [])

    async def publish(self, investigation_id: uuid.UUID, event: dict) -> None:
        for q in self._subscribers(investigation_id):
            await q.put(event)

    def subscribe(self, investigation_id: uuid.UUID) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers(investigation_id).append(q)
        return q

    def unsubscribe(self, investigation_id: uuid.UUID, q: asyncio.Queue) -> None:
        subs = self._queues.get(investigation_id)
        if subs and q in subs:
            subs.remove(q)


EVENT_BUS = EventBus()


class StepRecorder:
    """Used by the orchestrator/agents to emit one event per meaningful
    action. Every call both durably persists the step and pushes it to any
    live SSE subscribers."""

    def __init__(self, investigation_id: uuid.UUID, session: AsyncSession):
        self.investigation_id = investigation_id
        self.session = session
        self._seq = 0

    async def emit(self, agent: str, status: str, message: str, detail: dict | None = None) -> StepEvent:
        self._seq += 1
        event = StepEvent(agent=agent, status=status, message=message, detail=detail, seq=self._seq)

        row = InvestigationStep(
            investigation_id=self.investigation_id,
            seq=event.seq,
            agent=event.agent,
            status=event.status,
            message=event.message,
            detail=event.detail,
        )
        self.session.add(row)
        await self.session.commit()

        await EVENT_BUS.publish(self.investigation_id, event.to_dict())
        return event

    async def close(self) -> None:
        await EVENT_BUS.publish(self.investigation_id, DONE_SENTINEL)
