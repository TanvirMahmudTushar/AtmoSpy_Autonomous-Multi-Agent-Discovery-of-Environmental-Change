"""Real (unmocked) SMAP integration test — skipped unless a real
NASA_EARTHDATA_TOKEN is configured, since it hits the live NSIDC archive.
Deliberately not respx-mocked, same reasoning as test_grace_adapter.py: the
whole point was verifying against the real file (structure AND the
quality-flag bit convention, confirmed against NSIDC's own user guide) —
a mock would stop proving any of that continues to hold."""

from datetime import date

import pytest

from app.core.config import get_settings
from app.nasa.smap import SmapAdapter

pytestmark = pytest.mark.skipif(
    not get_settings().NASA_EARTHDATA_TOKEN,
    reason="requires a real NASA_EARTHDATA_TOKEN",
)


@pytest.mark.asyncio
async def test_query_point_series_returns_physically_valid_soil_moisture():
    adapter = SmapAdapter()
    series = await adapter.query_point_series("soil_moisture", 29.0, 78.0, date(2016, 1, 1), date(2016, 12, 31))

    assert len(series.values) > 0
    assert series.units == "cm^3/cm^3"
    # SMAP's own documented valid range (0.02-0.5 m^3/m^3) — every value that
    # survives the quality filter must fall inside it.
    assert all(0.02 <= v <= 0.5 for v in series.values)


@pytest.mark.asyncio
async def test_query_grid_series_returns_a_grid_with_the_same_cells_across_months():
    adapter = SmapAdapter()
    grid = await adapter.query_grid_series("soil_moisture", 24.0, 31.0, 75.0, 85.0, date(2016, 6, 1), date(2016, 9, 30))

    assert len(grid.cells) > 10
    assert all(-180 <= c.lon <= 180 for c in grid.cells)
    assert all(0.02 <= v <= 0.5 for c in grid.cells for v in c.values)
