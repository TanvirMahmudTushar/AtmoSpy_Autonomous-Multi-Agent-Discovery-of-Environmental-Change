"""Adapter for GRACE-FO (Gravity Recovery and Climate Experiment Follow-On)
mass-anomaly / terrestrial water storage data, via PO.DAAC.

Unlike NASA POWER, this is not a simple REST API — the real product is one
~44GB global NetCDF file (not per-region/per-month granules) covering the
whole 2002-present record, distributed from PO.DAAC's protected (Earthdata
Login-gated) Cumulus archive. Confirmed via NASA's public CMR API
(https://cmr.earthdata.nasa.gov/search/) against the real collection:

    short_name: TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4
    (JPL GRACE/GRACE-FO Mascon, Coastal Resolution Improvement filtered,
    0.5-degree grid — the "ready to use" gridded product, not the raw
    unfiltered mascon solution that needs a separate scale-factor grid.)

We never download that file — h5netcdf reads it lazily over HTTP range
requests via fsspec, so a point/region query only pulls the bytes it
actually needs. The granule's exact filename changes as new months are
appended, so the current URL is resolved via a live CMR granule search
rather than hardcoded.

Variable/dimension names (lwe_thickness, lat, lon, time) follow JPL's
long-standing, unchanged-across-releases mascon NetCDF convention. Inspect
the live file once real credentials are configured before trusting it in
production.
"""

import asyncio
from datetime import date, timedelta

import httpx
import numpy as np  # already a core dependency (app/analysis/*); safe to import eagerly

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
COLLECTION_SHORT_NAME = "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4"

LWE_THICKNESS = VariableInfo(
    "lwe_thickness", "Liquid Water Equivalent Thickness (groundwater / ice mass anomaly)", "cm",
    "Terrestrial water storage / mass anomaly relative to a 2004-2009 baseline "
    "mean, from GRACE/GRACE-FO gravity measurements. Positive = mass gain "
    "(e.g. wetter soil, more groundwater, ice accumulation); negative = mass "
    "loss (drought, groundwater depletion, ice sheet melt).",
    -200, 200,
)

GRACE_FO_DATASET_INFO = DatasetInfo(
    code="GRACE_FO",
    name="GRACE-FO Mascon Terrestrial Water Storage Anomaly",
    provider="NASA JPL / PO.DAAC",
    description=(
        "Monthly terrestrial water storage / mass anomaly from the GRACE and GRACE-FO "
        "gravity-recovery satellite missions (JPL RL06.3 mascon solution, coastal-resolution "
        "filtered). Requires a NASA Earthdata Login bearer token (NASA_EARTHDATA_TOKEN)."
    ),
    base_url="https://cmr.earthdata.nasa.gov/search/",
    status="requires_credentials",
    requires_credentials=True,
    version="RL06.3Mv04",
    variables=[LWE_THICKNESS],
    temporal_resolution_days=30.44,
    retry_floor_year=2003,  # real record starts April 2002
)


class GraceAdapter(NASADataAdapter):
    code = "GRACE_FO"

    def __init__(self):
        self._token = get_settings().NASA_EARTHDATA_TOKEN
        self._granule_url: str | None = None
        self._dataset = None  # lazily-opened xarray.Dataset, cached for the process lifetime
        self._open_lock = asyncio.Lock()

    def get_metadata(self) -> DatasetInfo:
        info = GRACE_FO_DATASET_INFO
        # Reported as active here (unlike the module-level constant used for
        # the UnavailableAdapter fallback) — this class only ever exists when
        # registry.py already confirmed a token is configured.
        return DatasetInfo(
            code=info.code, name=info.name, provider=info.provider, description=info.description,
            base_url=info.base_url, status="active", requires_credentials=True, version=info.version,
            variables=info.variables, temporal_resolution_days=info.temporal_resolution_days,
            retry_floor_year=info.retry_floor_year,
        )

    async def _resolve_granule_url(self) -> str:
        if self._granule_url:
            return self._granule_url
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                CMR_GRANULE_SEARCH_URL,
                params={"short_name": COLLECTION_SHORT_NAME, "page_size": 1},
            )
            resp.raise_for_status()
            entries = resp.json().get("feed", {}).get("entry", [])
        if not entries:
            raise NASAAdapterError(f"CMR returned no granules for {COLLECTION_SHORT_NAME}")
        links = entries[0].get("links", [])
        https_links = [
            link["href"] for link in links
            if link.get("href", "").startswith("https://") and link["href"].endswith(".nc")
        ]
        if not https_links:
            raise NASAAdapterError("CMR granule metadata had no direct HTTPS .nc download link")
        self._granule_url = https_links[0]
        return self._granule_url

    async def _get_dataset(self):
        if self._dataset is not None:
            return self._dataset
        async with self._open_lock:
            if self._dataset is not None:  # re-check after acquiring the lock
                return self._dataset
            if not self._token:
                raise NASAAdapterError("NASA_EARTHDATA_TOKEN is not configured")
            url = await self._resolve_granule_url()

            def _open():
                import fsspec
                import xarray as xr

                fs = fsspec.filesystem("https", headers={"Authorization": f"Bearer {self._token}"})
                try:
                    f = fs.open(url, "rb")
                    return xr.open_dataset(f, engine="h5netcdf")
                except Exception as exc:  # noqa: BLE001 - reraised as NASAAdapterError below
                    raise RuntimeError(str(exc)) from exc

            try:
                self._dataset = await asyncio.to_thread(_open)
            except RuntimeError as exc:
                raise NASAAdapterError(f"Could not open GRACE-FO dataset: {exc}") from exc
            return self._dataset

    @staticmethod
    def _to_lon_0_360(lon: float) -> float:
        return lon % 360

    async def query_point_series(
        self, variable: str, lat: float, lon: float, start: date, end: date, temporal: str = "monthly"
    ) -> PointSeries:
        if variable != LWE_THICKNESS.code:
            raise NASAAdapterError(f"Unknown GRACE-FO variable: {variable}")
        ds = await self._get_dataset()
        url = self._granule_url or ""

        def _extract():
            point = ds[variable].sel(lat=lat, lon=self._to_lon_0_360(lon), method="nearest")
            point = point.sel(time=slice(str(start), str(end)))
            times = point["time"].values
            values = point.values

            dates: list[date] = []
            out_values: list[float] = []
            missing: list[date] = []
            for t, v in zip(times, values):
                d = _to_python_date(t)
                if v is None or v != v:  # NaN check without importing numpy just for this
                    missing.append(d)
                    continue
                dates.append(d)
                out_values.append(float(v))
            return dates, out_values, missing

        try:
            dates, values, missing = await asyncio.to_thread(_extract)
        except Exception as exc:  # noqa: BLE001
            raise NASAAdapterError(f"GRACE-FO point extraction failed: {exc}") from exc

        return PointSeries(
            variable=variable, units=LWE_THICKNESS.units, lat=lat, lon=lon,
            dates=dates, values=values, missing_dates=missing,
            source_url=url, retrieved_at=date.today(),
        )

    async def query_grid_series(
        self, variable: str, min_lat: float, max_lat: float, min_lon: float, max_lon: float, start: date, end: date
    ) -> GridSeries:
        if variable != LWE_THICKNESS.code:
            raise NASAAdapterError(f"Unknown GRACE-FO variable: {variable}")
        ds = await self._get_dataset()
        url = self._granule_url or ""
        lon_min_360, lon_max_360 = self._to_lon_0_360(min_lon), self._to_lon_0_360(max_lon)

        def _extract():
            lat_mask = (ds["lat"] >= min_lat) & (ds["lat"] <= max_lat)
            lon_mask = (ds["lon"] >= lon_min_360) & (ds["lon"] <= lon_max_360)
            subset = ds[variable].where(lat_mask & lon_mask, drop=True)
            subset = subset.sel(time=slice(str(start), str(end)))

            cells: list[GridCell] = []
            for lat_val in subset["lat"].values:
                for lon_val in subset["lon"].values:
                    series = subset.sel(lat=lat_val, lon=lon_val)
                    times = series["time"].values
                    values = series.values
                    dates: list[date] = []
                    out_values: list[float] = []
                    for t, v in zip(times, values):
                        if v is None or v != v:
                            continue
                        dates.append(_to_python_date(t))
                        out_values.append(float(v))
                    if dates:
                        # store lon back in -180..180 for consistency with every
                        # other adapter/region definition in this codebase
                        lon_out = float(lon_val) - 360 if float(lon_val) > 180 else float(lon_val)
                        cells.append(GridCell(lat=float(lat_val), lon=lon_out, dates=dates, values=out_values))
            return cells

        try:
            cells = await asyncio.to_thread(_extract)
        except Exception as exc:  # noqa: BLE001
            raise NASAAdapterError(f"GRACE-FO grid extraction failed: {exc}") from exc

        return GridSeries(variable=variable, units=LWE_THICKNESS.units, cells=cells, source_url=url, retrieved_at=date.today())


_EPOCH = np.datetime64("1970-01-01")
_ONE_DAY = np.timedelta64(1, "D")


def _to_python_date(np_datetime) -> date:
    """xarray/numpy datetime64 -> stdlib date."""
    days_since_epoch = (np.datetime64(np_datetime, "D") - _EPOCH) / _ONE_DAY
    return date(1970, 1, 1) + timedelta(days=int(days_since_epoch))
