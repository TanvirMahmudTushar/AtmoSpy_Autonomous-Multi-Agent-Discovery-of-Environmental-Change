"""Adapter for SMAP (Soil Moisture Active Passive) L3 radiometer global daily
soil moisture, via NSIDC DAAC.

Architecturally different from GRACE-FO (app/nasa/grace.py) in two ways,
both confirmed empirically before writing this, not assumed:

1. **One HDF5 file per day**, not one file for the whole record. Fetching
   every day over a multi-year investigation isn't practical, so this
   adapter samples roughly monthly (one granule near the 1st of each month,
   searching a few days forward via CMR if that exact day's granule is
   missing) — the same "monthly effective resolution" as GRACE-FO,
   reflected the same way (`DatasetInfo.temporal_resolution_days`), just as
   a deliberate access-pattern choice here rather than the instrument's own
   native cadence.
2. **Full download, not lazy remote reads.** GRACE-FO's single ~44GB file
   is read lazily over HTTP range requests. Tried the identical approach
   here first — it hung indefinitely (confirmed: killed after minutes with
   zero progress) rather than just being slow, apparently because SMAP's
   internal HDF5 chunk/metadata layout doesn't suit fsspec's range-request
   pattern the way GRACE-FO's did. Each SMAP granule is only ~33MB and
   downloads in ~9s via a plain `httpx` GET, so this adapter downloads the
   whole granule and parses it in memory with `h5py` instead.

Also unlike GRACE-FO's simple 1D lat/lon coordinate arrays, SMAP uses the
EASE-Grid 2.0 projection: `latitude`/`longitude` are 2D arrays (406, 964)
where the SAME (row, col) index is the same physical grid cell in every
granule (it's a fixed grid) — nearest-point lookup is a 2D distance
argmin, and grid queries reuse one granule's (row, col) selection across
every other month's file rather than re-matching by lat/lon each time.

Collection, fill value, valid range, and quality-flag convention (all
below) were read directly off a real downloaded granule, not guessed —
see the values used here against `Soil_Moisture_Retrieval_Data_AM` in any
recent SPL3SMP V009 file to re-verify after an upstream version bump.
"""

import asyncio
from datetime import date, timedelta

import httpx
import numpy as np

from app.core.config import get_settings
from app.nasa.base import (
    DatasetInfo,
    GridCell,
    GridSeries,
    NASAAdapterError,
    NASADataAdapter,
    PointSeries,
    VariableInfo,
)

CMR_GRANULE_SEARCH_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
COLLECTION_SHORT_NAME = "SPL3SMP"
COLLECTION_VERSION = "009"
GROUP = "Soil_Moisture_Retrieval_Data_AM"  # the AM overpass is the primary/canonical retrieval
FILL_VALUE = -9999.0
RECOMMENDED_BIT = 1  # retrieval_qual_flag & 1 == 0 means "retrieval recommended"

SOIL_MOISTURE = VariableInfo(
    "soil_moisture", "SMAP Soil Moisture (satellite retrieval)", "cm^3/cm^3",
    "Volumetric surface soil moisture from SMAP's L-band radiometer, a direct satellite "
    "retrieval (unlike NASA POWER's GLDAS model-based GWETROOT/GWETTOP). 36km EASE-Grid 2.0 "
    "resolution.",
    0.02, 0.5,
)

SMAP_DATASET_INFO = DatasetInfo(
    code="SMAP_L3",
    name="SMAP L3 Radiometer Global Soil Moisture",
    provider="NASA JPL / NSIDC DAAC",
    description=(
        "Daily global soil moisture from the Soil Moisture Active Passive mission's L-band "
        "radiometer (36km EASE-Grid 2.0, SPL3SMP V009). Requires a NASA Earthdata Login bearer "
        "token (NASA_EARTHDATA_TOKEN) authorized for NSIDC DAAC."
    ),
    base_url="https://cmr.earthdata.nasa.gov/search/",
    status="requires_credentials",
    requires_credentials=True,
    version=COLLECTION_VERSION,
    variables=[SOIL_MOISTURE],
    # Fetched roughly monthly, not daily — see the module docstring for why.
    temporal_resolution_days=30.44,
    retry_floor_year=2016,  # real record starts March 2015
)


def _month_starts(start: date, end: date) -> list[date]:
    months = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        months.append(cur)
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return months


class SmapAdapter(NASADataAdapter):
    code = "SMAP_L3"

    def __init__(self):
        self._token = get_settings().NASA_EARTHDATA_TOKEN
        self._semaphore = asyncio.Semaphore(4)

    def get_metadata(self) -> DatasetInfo:
        info = SMAP_DATASET_INFO
        return DatasetInfo(
            code=info.code, name=info.name, provider=info.provider, description=info.description,
            base_url=info.base_url, status="active", requires_credentials=True, version=info.version,
            variables=info.variables, temporal_resolution_days=info.temporal_resolution_days,
            retry_floor_year=info.retry_floor_year,
        )

    async def _find_granule_url(self, client: httpx.AsyncClient, target: date, search_window_days: int = 6) -> str | None:
        window_end = target + timedelta(days=search_window_days)
        resp = await client.get(
            CMR_GRANULE_SEARCH_URL,
            params={
                "short_name": COLLECTION_SHORT_NAME,
                "version": COLLECTION_VERSION,
                "temporal": f"{target.isoformat()}T00:00:00Z,{window_end.isoformat()}T00:00:00Z",
                "page_size": 1,
                "sort_key": "start_date",
            },
        )
        resp.raise_for_status()
        entries = resp.json().get("feed", {}).get("entry", [])
        if not entries:
            return None
        links = entries[0].get("links", [])
        for link in links:
            href = link.get("href", "")
            if href.startswith("https://") and href.endswith(".h5"):
                return href
        return None

    async def _download_granule(self, client: httpx.AsyncClient, url: str):
        import io

        import h5py

        resp = await client.get(url, headers={"Authorization": f"Bearer {self._token}"})
        resp.raise_for_status()
        return await asyncio.to_thread(lambda: h5py.File(io.BytesIO(resp.content), "r"))

    async def query_point_series(
        self, variable: str, lat: float, lon: float, start: date, end: date, temporal: str = "monthly"
    ) -> PointSeries:
        if variable != SOIL_MOISTURE.code:
            raise NASAAdapterError(f"Unknown SMAP variable: {variable}")
        if not self._token:
            raise NASAAdapterError("NASA_EARTHDATA_TOKEN is not configured")

        months = _month_starts(start, end)
        dates: list[date] = []
        values: list[float] = []
        missing: list[date] = []
        source_url = ""

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async def fetch_one(month_start: date):
                async with self._semaphore:  # bounds CMR search + download together, not just the download
                    try:
                        url = await self._find_granule_url(client, month_start)
                        if url is None:
                            return month_start, None, None
                        h5 = await self._download_granule(client, url)
                        return month_start, url, h5
                    except (httpx.HTTPError, OSError) as exc:
                        return month_start, None, exc

            results = await asyncio.gather(*(fetch_one(m) for m in months))

        def _extract(h5) -> float | None:
            grp = h5[GROUP]
            lat_grid = grp["latitude"][:]
            lon_grid = grp["longitude"][:]
            dist2 = (lat_grid - lat) ** 2 + (lon_grid - lon) ** 2
            row, col = np.unravel_index(np.argmin(dist2), dist2.shape)
            sm = float(grp["soil_moisture"][row, col])
            qf = int(grp["retrieval_qual_flag"][row, col])
            if sm == FILL_VALUE or sm != sm or (qf & RECOMMENDED_BIT):
                return None
            return sm

        for month_start, url, result in results:
            if isinstance(result, Exception) or result is None:
                missing.append(month_start)
                continue
            source_url = url
            value = await asyncio.to_thread(_extract, result)
            result.close()
            if value is None:
                missing.append(month_start)
            else:
                dates.append(month_start)
                values.append(value)

        return PointSeries(
            variable=variable, units=SOIL_MOISTURE.units, lat=lat, lon=lon,
            dates=dates, values=values, missing_dates=missing,
            source_url=source_url or CMR_GRANULE_SEARCH_URL, retrieved_at=date.today(),
        )

    async def query_grid_series(
        self, variable: str, min_lat: float, max_lat: float, min_lon: float, max_lon: float, start: date, end: date
    ) -> GridSeries:
        if variable != SOIL_MOISTURE.code:
            raise NASAAdapterError(f"Unknown SMAP variable: {variable}")
        if not self._token:
            raise NASAAdapterError("NASA_EARTHDATA_TOKEN is not configured")

        months = _month_starts(start, end)
        source_url = ""
        cell_coords: list[tuple[int, int, float, float]] | None = None  # (row, col, lat, lon), fixed grid
        cell_series: dict[tuple[int, int], tuple[list[date], list[float]]] = {}

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            for month_start in months:
                try:
                    url = await self._find_granule_url(client, month_start)
                    if url is None:
                        continue
                    h5 = await self._download_granule(client, url)
                except (httpx.HTTPError, OSError):
                    continue
                source_url = url

                def _extract(h5=h5):
                    grp = h5[GROUP]
                    lat_grid = grp["latitude"][:]
                    lon_grid = grp["longitude"][:]
                    sm_grid = grp["soil_moisture"][:]
                    qf_grid = grp["retrieval_qual_flag"][:]
                    nonlocal cell_coords
                    if cell_coords is None:
                        mask = (
                            (lat_grid >= min_lat) & (lat_grid <= max_lat)
                            & (lon_grid >= min_lon) & (lon_grid <= max_lon)
                            & (lat_grid != FILL_VALUE)
                        )
                        rows, cols = np.nonzero(mask)
                        cell_coords = [(int(r), int(c), float(lat_grid[r, c]), float(lon_grid[r, c])) for r, c in zip(rows, cols)]
                    out = {}
                    for row, col, _, _ in cell_coords:
                        sm, qf = float(sm_grid[row, col]), int(qf_grid[row, col])
                        if sm != FILL_VALUE and sm == sm and not (qf & RECOMMENDED_BIT):
                            out[(row, col)] = sm
                    return out

                values_by_cell = await asyncio.to_thread(_extract)
                h5.close()
                for key, value in values_by_cell.items():
                    series = cell_series.setdefault(key, ([], []))
                    series[0].append(month_start)
                    series[1].append(value)

        if cell_coords is None:
            cell_coords = []
        coord_by_key = {(r, c): (lat_v, lon_v) for r, c, lat_v, lon_v in cell_coords}
        cells = [
            GridCell(lat=coord_by_key[key][0], lon=coord_by_key[key][1], dates=dates, values=values)
            for key, (dates, values) in cell_series.items()
            if dates
        ]

        return GridSeries(
            variable=variable, units=SOIL_MOISTURE.units, cells=cells,
            source_url=source_url or CMR_GRANULE_SEARCH_URL, retrieved_at=date.today(),
        )
