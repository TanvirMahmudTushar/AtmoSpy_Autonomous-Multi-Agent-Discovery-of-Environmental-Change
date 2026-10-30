"""Guided exploration: variable suggestions for a place, and the region scan."""

import asyncio
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scan import run_scan
from app.api.deps import get_current_user_optional
from app.api.sse import sse_response
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.llm.suggest import suggest_variables
from app.models import Investigation, User
from app.nasa.regions import REGIONS_BY_CODE, RegionDef, custom_region
from app.schemas.api import BBox

router = APIRouter(tags=["explore"])
_background_tasks: set[asyncio.Task] = set()


def _region(region_code: str | None, bbox: BBox | None) -> RegionDef | None:
    if bbox is not None:
        return custom_region(bbox.min_lat, bbox.max_lat, bbox.min_lon, bbox.max_lon)
    if region_code is None:
        return None
    if region_code not in REGIONS_BY_CODE:
        raise HTTPException(422, f"Unknown region {region_code!r}")
    return REGIONS_BY_CODE[region_code]


@router.get("/suggest", dependencies=[Depends(rate_limit(60, 60))])
async def suggest(
    place: list[str] = Query(default=[], description="place types, e.g. city, desert"),
    region_code: str | None = None,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    limit: int = Query(6, ge=1, le=12),
):
    """Variables worth investigating for the chosen place types and region,
    each with a plain one-sentence reason."""
    corners = (min_lat, max_lat, min_lon, max_lon)
    bbox = BBox(min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon) if None not in corners else None
    return await suggest_variables(place, _region(region_code, bbox), limit=limit)


class ScanRequest(BaseModel):
    region_code: str | None = None
    bbox: BBox | None = None
    start_year: int = Field(1990, ge=1940)
    end_year: int = Field(date.today().year - 1, le=2100)


class ScanResponse(BaseModel):
    investigation_id: uuid.UUID


@router.post("/scan", response_model=ScanResponse, status_code=201, dependencies=[Depends(rate_limit(10, 600))])
async def start_scan(
    body: ScanRequest,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    region = _region(body.region_code, body.bbox)
    if region is None:
        raise HTTPException(422, "Send a region_code or a bbox.")
    end = min(body.end_year, date.today().year - 1)
    if end - body.start_year < 7:
        raise HTTPException(422, "Scan at least 8 years.")
    investigation = Investigation(
        mode="scan", question=f"What is changing over {region.name}?", status="pending",
        user_id=user.id if user else None,
        plan={"region_code": region.code, "region_name": region.name, "start_year": body.start_year, "end_year": end,
              "bbox": [region.min_lat, region.max_lat, region.min_lon, region.max_lon]},
    )
    session.add(investigation)
    await session.commit()
    await session.refresh(investigation)

    task = asyncio.create_task(run_scan(investigation.id, region, body.start_year, end))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return ScanResponse(investigation_id=investigation.id)


@router.get("/scan/{investigation_id}/events")
async def stream_scan_events(investigation_id: uuid.UUID):
    return sse_response(investigation_id)
