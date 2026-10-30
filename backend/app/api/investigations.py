import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import run_investigation
from app.api.deps import get_current_user_optional
from app.api.sse import sse_response
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.llm.planner import structured_plan
from app.models import Investigation, User
from app.schemas.api import CreateInvestigationRequest, CreateInvestigationResponse, InvestigationOut

router = APIRouter(prefix="/investigations", tags=["investigations"])

# Keep strong references to background tasks so they aren't garbage-collected
# mid-flight (a well-known asyncio.create_task footgun).
_background_tasks: set[asyncio.Task] = set()


@router.post("", response_model=CreateInvestigationResponse, status_code=201, dependencies=[Depends(rate_limit(30, 60))])
async def create_investigation(
    body: CreateInvestigationRequest,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    plan = None
    question = body.question
    if body.variable_code is not None:
        try:
            plan = structured_plan(
                body.variable_code,
                region_code=body.region_code,
                bbox=(body.bbox.min_lat, body.bbox.max_lat, body.bbox.min_lon, body.bbox.max_lon) if body.bbox else None,
                start_year=body.start_year,
                end_year=body.end_year,
                compare_region_code=body.compare_region_code,
                run_relationship_analysis=body.run_relationship_analysis,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        # kept for history lists, which show the question
        question = question or plan.reasoning.removeprefix("Chosen directly: ")

    # Investigating never requires an account — user_id is attached only
    # when a valid token was sent, so anonymous usage keeps working exactly
    # as before.
    investigation = Investigation(
        mode="guided" if plan else "nlp", question=question, status="pending", user_id=user.id if user else None
    )
    session.add(investigation)
    await session.commit()
    await session.refresh(investigation)

    task = asyncio.create_task(run_investigation(investigation.id, question, plan))
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
