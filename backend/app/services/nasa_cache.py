"""Database-backed cache in front of NASA adapter calls.

Past-year NASA POWER data doesn't change, so a 24h TTL keyed by the exact
query parameters is enough to make repeated investigations (and Discover
mode's concurrent scan) fast and avoid hammering the public API.
"""

import asyncio
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import NasaQueryCache
from app.nasa.base import GridCell, GridSeries, NASADataAdapter, PointSeries
from app.nasa.registry import get_adapter

_semaphore = asyncio.Semaphore(get_settings().NASA_POWER_MAX_CONCURRENCY)


def _cache_key(**params) -> str:
    blob = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _point_series_to_json(ps: PointSeries) -> dict:
    return {
        "variable": ps.variable,
        "units": ps.units,
        "lat": ps.lat,
        "lon": ps.lon,
        "dates": [d.isoformat() for d in ps.dates],
        "values": ps.values,
        "missing_dates": [d.isoformat() for d in ps.missing_dates],
        "source_url": ps.source_url,
        "retrieved_at": ps.retrieved_at.isoformat(),
    }


def _json_to_point_series(data: dict) -> PointSeries:
    return PointSeries(
        variable=data["variable"],
        units=data["units"],
        lat=data["lat"],
        lon=data["lon"],
        dates=[date.fromisoformat(d) for d in data["dates"]],
        values=data["values"],
        missing_dates=[date.fromisoformat(d) for d in data["missing_dates"]],
        source_url=data["source_url"],
        retrieved_at=date.fromisoformat(data["retrieved_at"]),
    )


def _grid_series_to_json(gs: GridSeries) -> dict:
    return {
        "variable": gs.variable,
        "units": gs.units,
        "cells": [
            {"lat": c.lat, "lon": c.lon, "dates": [d.isoformat() for d in c.dates], "values": c.values}
            for c in gs.cells
        ],
        "source_url": gs.source_url,
        "retrieved_at": gs.retrieved_at.isoformat(),
    }


def _json_to_grid_series(data: dict) -> GridSeries:
    return GridSeries(
        variable=data["variable"],
        units=data["units"],
        cells=[
            GridCell(lat=c["lat"], lon=c["lon"], dates=[date.fromisoformat(d) for d in c["dates"]], values=c["values"])
            for c in data["cells"]
        ],
        source_url=data["source_url"],
        retrieved_at=date.fromisoformat(data["retrieved_at"]),
    )


async def _get_cached(session: AsyncSession, key: str) -> dict | None:
    row = (
        await session.execute(select(NasaQueryCache).where(NasaQueryCache.cache_key == key))
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    return row.response


async def _store_cache(session: AsyncSession, key: str, dataset_code: str, params: dict, response: dict) -> None:
    settings = get_settings()
    existing = (
        await session.execute(select(NasaQueryCache).where(NasaQueryCache.cache_key == key))
    ).scalar_one_or_none()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.NASA_POWER_CACHE_TTL_HOURS)
    if existing:
        existing.response = response
        existing.expires_at = expires_at
    else:
        session.add(
            NasaQueryCache(
                cache_key=key, dataset_code=dataset_code, params=params, response=response, expires_at=expires_at
            )
        )
    await session.commit()


async def get_point_series(
    session: AsyncSession,
    dataset_code: str,
    variable: str,
    lat: float,
    lon: float,
    start: date,
    end: date,
    temporal: str = "annual",
) -> PointSeries:
    params = {
        "dataset": dataset_code, "kind": "point", "variable": variable, "lat": round(lat, 3),
        "lon": round(lon, 3), "start": start.isoformat(), "end": end.isoformat(), "temporal": temporal,
    }
    key = _cache_key(**params)
    cached = await _get_cached(session, key)
    if cached is not None:
        return _json_to_point_series(cached)

    adapter: NASADataAdapter = get_adapter(dataset_code)
    async with _semaphore:
        result = await adapter.query_point_series(variable, lat, lon, start, end, temporal)

    await _store_cache(session, key, dataset_code, params, _point_series_to_json(result))
    return result


async def get_grid_series(
    session: AsyncSession,
    dataset_code: str,
    variable: str,
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    start: date,
    end: date,
) -> GridSeries:
    params = {
        "dataset": dataset_code, "kind": "grid", "variable": variable,
        "min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon,
        "start": start.isoformat(), "end": end.isoformat(),
    }
    key = _cache_key(**params)
    cached = await _get_cached(session, key)
    if cached is not None:
        return _json_to_grid_series(cached)

    adapter: NASADataAdapter = get_adapter(dataset_code)
    async with _semaphore:
        result = await adapter.query_grid_series(variable, min_lat, max_lat, min_lon, max_lon, start, end)

    await _store_cache(session, key, dataset_code, params, _grid_series_to_json(result))
    return result
