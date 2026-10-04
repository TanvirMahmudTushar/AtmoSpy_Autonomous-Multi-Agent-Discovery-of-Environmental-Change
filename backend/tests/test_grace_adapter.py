"""Real (unmocked) GRACE-FO integration test — skipped unless a real
NASA_EARTHDATA_TOKEN is configured, since it hits the live PO.DAAC archive.
This is deliberately NOT respx-mocked like test_power_adapter.py: the whole
point of this adapter was verifying it against the real file structure
(scripts/inspect_grace_dataset.py), and a mock would silently stop proving
that once the shape of the real data ever changes."""

import pytest

from app.core.config import get_settings
from app.nasa.grace import GraceAdapter

pytestmark = pytest.mark.skipif(
    not get_settings().NASA_EARTHDATA_TOKEN,
    reason="requires a real NASA_EARTHDATA_TOKEN",
)


@pytest.mark.asyncio
async def test_query_point_series_returns_plausible_greenland_mass_loss():
    adapter = GraceAdapter()
    from datetime import date

    series = await adapter.query_point_series("lwe_thickness", 72.0, -42.0, date(2003, 1, 1), date(2023, 12, 31))

    assert len(series.values) > 100
    assert series.units == "cm"
    # Southern Greenland has lost ice mass steadily since 2003 — this isn't
    # an arbitrary assertion, it's the well-documented real-world signal;
    # if this ever flips it means something upstream (units, sign
    # convention, wrong region) broke, not that the science changed.
    assert series.values[-1] < series.values[0]


@pytest.mark.asyncio
async def test_query_grid_series_returns_a_full_grid():
    from datetime import date

    adapter = GraceAdapter()
    grid = await adapter.query_grid_series("lwe_thickness", 67.0, 77.0, -47.0, -37.0, date(2003, 1, 1), date(2023, 12, 31))

    assert len(grid.cells) > 100  # ~400 expected at 0.5deg resolution over a 10x10 region
    assert all(-180 <= c.lon <= 180 for c in grid.cells)  # converted back from the file's native 0-360
