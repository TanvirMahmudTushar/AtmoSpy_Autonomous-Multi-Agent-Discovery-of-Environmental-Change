"""Adapter for NASA POWER (Prediction Of Worldwide Energy Resources).

Public REST API, no authentication. Backed by MERRA-2 reanalysis and
GLDAS-derived land-surface fields, daily since 1981. We use the
"Agroclimatology" community, which conveniently exposes meteorological
variables (temperature, precipitation, humidity, radiation, wind) *and*
GLDAS Noah root-zone/surface soil wetness in the same API — giving us a
genuinely interconnected variable set without needing SMAP/GRACE auth.

Docs: https://power.larc.nasa.gov/docs/services/api/
"""

from datetime import date, datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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

FILL_VALUE = -999.0

POWER_VARIABLES = [
    VariableInfo("T2M", "Temperature at 2 Meters", "degC",
                 "Average air temperature at 2 meters above the surface.", -90, 60),
    VariableInfo("T2M_MAX", "Maximum Temperature at 2 Meters", "degC",
                 "Daily/monthly maximum air temperature at 2 meters.", -90, 60),
    VariableInfo("T2M_MIN", "Minimum Temperature at 2 Meters", "degC",
                 "Daily/monthly minimum air temperature at 2 meters.", -90, 60),
    VariableInfo("PRECTOTCORR", "Precipitation Corrected", "mm/day",
                 "Bias-corrected total precipitation.", 0, 2000),
    VariableInfo("RH2M", "Relative Humidity at 2 Meters", "%",
                 "Relative humidity at 2 meters above the surface.", 0, 100),
    VariableInfo("GWETROOT", "Root Zone Soil Wetness", "fraction",
                 "GLDAS Noah root-zone soil wetness, 0 (dry) to 1 (saturated).", 0, 1),
    VariableInfo("GWETTOP", "Surface Soil Wetness", "fraction",
                 "GLDAS Noah surface-layer soil wetness, 0 (dry) to 1 (saturated).", 0, 1),
    VariableInfo("GWETPROF", "Profile Soil Wetness", "fraction",
                 "GLDAS Noah whole-column soil wetness, 0 (dry) to 1 (saturated).", 0, 1),
    VariableInfo("ALLSKY_SFC_SW_DWN", "All Sky Surface Shortwave Downward Irradiance",
                 "kW-hr/m^2/day", "All-sky insolation incident on a horizontal surface.", 0, 40),
    VariableInfo("WS2M", "Wind Speed at 2 Meters", "m/s",
                 "Average wind speed at 2 meters above the surface.", 0, 50),
    VariableInfo("TS", "Earth Skin Temperature", "degC",
                 "Land/ocean surface (skin) temperature.", -90, 60),
]

VARIABLES_BY_CODE = {v.code: v for v in POWER_VARIABLES}


class PowerAdapter(NASADataAdapter):
    code = "NASA_POWER"

    def __init__(self, client: httpx.AsyncClient | None = None):
        settings = get_settings()
        self._base_url = settings.NASA_POWER_BASE_URL
        self._client = client
        self._community = "AG"

    def get_metadata(self) -> DatasetInfo:
        return DatasetInfo(
            code=self.code,
            name="NASA POWER (Prediction Of Worldwide Energy Resources)",
            provider="NASA Langley Research Center",
            description=(
                "Global, gap-free daily meteorological and land-surface data derived from "
                "MERRA-2 reanalysis and GLDAS Noah land-surface model output, available from "
                "1981 to near-present with no authentication required."
            ),
            base_url=self._base_url,
            status="active",
            requires_credentials=False,
            version="v2.10.0",
            variables=POWER_VARIABLES,
        )

    async def _client_or_new(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=30.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _get(self, path: str, params: dict) -> dict:
        client = self._client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=30.0)
        try:
            resp = await client.get(f"{self._base_url}{path}", params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise NASAAdapterError(
                f"NASA POWER returned HTTP {exc.response.status_code} for {path}"
            ) from exc
        except httpx.TransportError as exc:
            raise NASAAdapterError(f"Could not reach NASA POWER: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

        messages = data.get("messages") or []
        if messages:
            raise NASAAdapterError(f"NASA POWER error: {'; '.join(messages)}")
        return data

    async def query_point_series(
        self,
        variable: str,
        lat: float,
        lon: float,
        start: date,
        end: date,
        temporal: str = "daily",
    ) -> PointSeries:
        if variable not in VARIABLES_BY_CODE:
            raise NASAAdapterError(f"Unknown NASA POWER variable: {variable}")

        if temporal == "daily":
            path = "/temporal/daily/point"
            params = {
                "parameters": variable,
                "community": self._community,
                "longitude": lon,
                "latitude": lat,
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "format": "JSON",
            }
        elif temporal in ("monthly", "annual"):
            path = "/temporal/monthly/point"
            params = {
                "parameters": variable,
                "community": self._community,
                "longitude": lon,
                "latitude": lat,
                "start": str(start.year),
                "end": str(end.year),
                "format": "JSON",
            }
        else:
            raise NASAAdapterError(f"Unsupported temporal resolution: {temporal}")

        data = await self._get(path, params)
        raw = data["properties"]["parameter"][variable]

        dates: list[date] = []
        values: list[float] = []
        missing: list[date] = []

        for key in sorted(raw.keys()):
            val = raw[key]
            if temporal == "daily":
                d = datetime.strptime(key, "%Y%m%d").date()
            elif temporal == "annual":
                if not key.endswith("13"):
                    continue
                d = date(int(key[:4]), 7, 1)
            else:  # monthly
                if key.endswith("13"):
                    continue
                d = date(int(key[:4]), int(key[4:6]), 1)

            if val == FILL_VALUE:
                missing.append(d)
                continue
            dates.append(d)
            values.append(float(val))

        var_info = VARIABLES_BY_CODE[variable]
        req = httpx.Request("GET", f"{self._base_url}{path}", params=params)
        return PointSeries(
            variable=variable,
            units=var_info.units,
            lat=lat,
            lon=lon,
            dates=dates,
            values=values,
            missing_dates=missing,
            source_url=str(req.url),
            retrieved_at=date.today(),
        )

    async def query_grid_series(
        self,
        variable: str,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        start: date,
        end: date,
    ) -> GridSeries:
        if variable not in VARIABLES_BY_CODE:
            raise NASAAdapterError(f"Unknown NASA POWER variable: {variable}")

        settings = get_settings()
        if (max_lat - min_lat) > settings.MAX_REGION_SPAN_DEGREES or (
            max_lon - min_lon
        ) > settings.MAX_REGION_SPAN_DEGREES:
            raise NASAAdapterError(
                f"Requested region spans more than {settings.MAX_REGION_SPAN_DEGREES} degrees; "
                "narrow the bounding box for a spatial-grid query."
            )

        path = "/temporal/monthly/regional"
        params = {
            "parameters": variable,
            "community": self._community,
            "longitude-min": min_lon,
            "longitude-max": max_lon,
            "latitude-min": min_lat,
            "latitude-max": max_lat,
            "start": str(start.year),
            "end": str(end.year),
            "format": "JSON",
        }
        data = await self._get(path, params)
        features = data.get("features", [])

        cells: list[GridCell] = []
        for feature in features:
            lon, lat = feature["geometry"]["coordinates"][:2]
            raw = feature["properties"]["parameter"].get(variable, {})
            dates: list[date] = []
            values: list[float] = []
            for key in sorted(raw.keys()):
                if not key.endswith("13"):
                    continue
                val = raw[key]
                if val == FILL_VALUE:
                    continue
                dates.append(date(int(key[:4]), 7, 1))
                values.append(float(val))
            if dates:
                cells.append(GridCell(lat=lat, lon=lon, dates=dates, values=values))

        req = httpx.Request("GET", f"{self._base_url}{path}", params=params)
        var_info = VARIABLES_BY_CODE[variable]
        return GridSeries(
            variable=variable,
            units=var_info.units,
            cells=cells,
            source_url=str(req.url),
            retrieved_at=date.today(),
        )
