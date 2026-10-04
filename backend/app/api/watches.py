import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.watch_runner import create_watch_check_investigation, execute_watch_check
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, Watch
from app.nasa.catalog import VARIABLES_BY_CODE
from app.nasa.regions import REGIONS_BY_CODE
from app.schemas.api import WatchCheckNowResponse, WatchCreateRequest, WatchOut

router = APIRouter(prefix="/watches", tags=["watches"])

# Same "keep a strong reference so it isn't GC'd mid-flight" pattern used by
# /investigations and /discover for their own background tasks.
_background_tasks: set[asyncio.Task] = set()


async def _get_owned_watch(session: AsyncSession, watch_id: uuid.UUID, user: User) -> Watch:
    watch = (await session.execute(select(Watch).where(Watch.id == watch_id))).scalar_one_or_none()
    if watch is None or watch.user_id != user.id:
        raise HTTPException(404, "Watch not found")
    return watch


@router.post("", response_model=WatchOut, status_code=201)
async def create_watch(
    body: WatchCreateRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.region_code not in REGIONS_BY_CODE:
        raise HTTPException(422, f"Unknown region_code: {body.region_code}")
    if body.variable_code not in VARIABLES_BY_CODE:
        raise HTTPException(422, f"Unknown variable_code: {body.variable_code}")

    watch = Watch(
        user_id=user.id,
        region_code=body.region_code,
        variable_code=body.variable_code,
        frequency_days=body.frequency_days,
    )
    session.add(watch)
    await session.commit()
    await session.refresh(watch)
    return watch


@router.get("", response_model=list[WatchOut])
async def list_watches(session: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        (await session.execute(select(Watch).where(Watch.user_id == user.id).order_by(Watch.created_at.desc())))
        .scalars()
        .all()
    )
    return rows


@router.delete("/{watch_id}", status_code=204)
async def delete_watch(
    watch_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    watch = await _get_owned_watch(session, watch_id, user)
    await session.delete(watch)
    await session.commit()


@router.post("/{watch_id}/toggle", response_model=WatchOut)
async def toggle_watch(
    watch_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    watch = await _get_owned_watch(session, watch_id, user)
    watch.is_active = not watch.is_active
    await session.commit()
    await session.refresh(watch)
    return watch


@router.post("/{watch_id}/check-now", response_model=WatchCheckNowResponse)
async def check_watch_now(
    watch_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    watch = await _get_owned_watch(session, watch_id, user)

    # Create the Investigation row synchronously so its id can be returned
    # immediately — the frontend needs it right away to start streaming SSE
    # events, and guessing "the most recent investigation" from a background
    # task would race against any other check in flight for this user.
    investigation = await create_watch_check_investigation(session, watch)

    task = asyncio.create_task(execute_watch_check(watch.id, investigation.id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return WatchCheckNowResponse(investigation_id=investigation.id)
