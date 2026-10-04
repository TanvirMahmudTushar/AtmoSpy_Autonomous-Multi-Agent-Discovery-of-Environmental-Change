import asyncio
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.discover import run_discovery
from app.api.sse import sse_response
from app.db.session import get_db
from app.models import Investigation
from app.schemas.api import DiscoverResponse

router = APIRouter(prefix="/discover", tags=["discover"])

_background_tasks: set[asyncio.Task] = set()


@router.post("", response_model=DiscoverResponse, status_code=201)
async def start_discovery(session: AsyncSession = Depends(get_db)):
    investigation = Investigation(mode="discover", question=None, status="pending")
    session.add(investigation)
    await session.commit()
    await session.refresh(investigation)

    task = asyncio.create_task(run_discovery(investigation.id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return DiscoverResponse(investigation_id=investigation.id)


@router.get("/{investigation_id}/events")
async def stream_discovery_events(investigation_id: uuid.UUID):
    return sse_response(investigation_id)
