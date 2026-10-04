import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import run_investigation
from app.api.deps import get_current_user_optional
from app.api.sse import sse_response
from app.db.session import get_db
from app.models import Investigation, User
from app.schemas.api import CreateInvestigationRequest, CreateInvestigationResponse, InvestigationOut

router = APIRouter(prefix="/investigations", tags=["investigations"])

# Keep strong references to background tasks so they aren't garbage-collected
# mid-flight (a well-known asyncio.create_task footgun).
_background_tasks: set[asyncio.Task] = set()


@router.post("", response_model=CreateInvestigationResponse, status_code=201)
async def create_investigation(
    body: CreateInvestigationRequest,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    # Investigating never requires an account — user_id is attached only
    # when a valid token was sent, so anonymous usage keeps working exactly
    # as before.
    investigation = Investigation(
        mode="nlp", question=body.question, status="pending", user_id=user.id if user else None
    )
    session.add(investigation)
    await session.commit()
    await session.refresh(investigation)

    task = asyncio.create_task(run_investigation(investigation.id, body.question))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return CreateInvestigationResponse(investigation_id=investigation.id)


@router.get("", response_model=list[InvestigationOut])
async def list_my_investigations(
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    limit: int = Query(20, le=100),
):
    if user is None:
        return []
    rows = (
        (
            await session.execute(
                select(Investigation)
                .options(selectinload(Investigation.steps))
                .where(Investigation.user_id == user.id)
                .order_by(Investigation.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/{investigation_id}", response_model=InvestigationOut)
async def get_investigation(investigation_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    investigation = (
        await session.execute(
            select(Investigation)
            .options(selectinload(Investigation.steps))
            .where(Investigation.id == investigation_id)
        )
    ).scalar_one_or_none()
    if investigation is None:
        raise HTTPException(404, "Investigation not found")
    return investigation


@router.get("/{investigation_id}/events")
async def stream_investigation_events(investigation_id: uuid.UUID):
    return sse_response(investigation_id)
