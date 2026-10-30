"""Analysis-ready monthly cubes: one Zarr store per variable on a regular
latitude/longitude grid, built offline by scripts/build_cube.py from NASA
Level-3 products, plus a manifest.json recording each cube's provenance.

At request time the app reads only the chunks a region touches — no NASA
service is called — so any box answers in about a second and demos don't
depend on a DAAC being up.

Regridding is a box average: every source pixel falls into the target cell
containing its centre, weighted by cos(latitude) (its area). For coarse
source grids this is close to conservative regridding; the residual error
is checked against Giovanni's native-resolution area averages by
tests/test_giovanni_validation.py whenever its fixtures are present.
"""

import dataclasses
import json
import logging
from datetime import date
from functools import lru_cache
from pathlib import Path

import fsspec
import numpy as np
import xarray as xr

from app.core.config import get_settings
from app.nasa.base import DatasetInfo, GridCell, GridSeries, NASAAdapterError, NASADataAdapter, PointSeries
from app.nasa.catalog_yaml import CubeVariableSpec, DatasetSpec

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CUBE_DIR = REPO_ROOT / "data" / "cubes"
MANIFEST = "manifest.json"


# ---------------------------------------------------------------- grid math

def target_axes(res: float) -> tuple[np.ndarray, np.ndarray]:
    """Cell-centre latitudes (south to north) and longitudes (-180 to 180)."""
    lat = np.arange(-90 + res / 2, 90, res)
    lon = np.arange(-180 + res / 2, 180, res)
    return lat, lon


def bin_average(field: np.ndarray, src_lat: np.ndarray, src_lon: np.ndarray, res: float) -> np.ndarray:
    """Area-weighted box average of a (lat, lon) field onto the regular
    `res`-degree grid. NaN pixels are ignored; target cells with no valid
    pixel are NaN. Longitudes in 0..360 are wrapped to -180..180. The source
    coordinates may be 1-D axes or 2-D arrays shaped like the field."""
    lat_t, lon_t = target_axes(res)
    values = np.asarray(field, dtype=float)
    src_lat = np.asarray(src_lat, dtype=float)
    src_lon = ((np.asarray(src_lon, dtype=float) + 180) % 360) - 180
    if src_lat.ndim == 2 and src_lon.ndim == 2:
        lat2, lon2 = src_lat, src_lon
    else:
        lat2, lon2 = np.meshgrid(src_lat, src_lon, indexing="ij")
    ok = np.isfinite(values)

    i = np.clip(((lat2 + 90) // res).astype(int), 0, len(lat_t) - 1)
    j = np.clip(((lon2 + 180) // res).astype(int), 0, len(lon_t) - 1)
    flat = (i * len(lon_t) + j)[ok]
    w = np.cos(np.radians(lat2))[ok]
    n = len(lat_t) * len(lon_t)
    num = np.bincount(flat, weights=w * values[ok], minlength=n)
    den = np.bincount(flat, weights=w, minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(den > 0, num / den, np.nan)
    return out.reshape(len(lat_t), len(lon_t))


# ---------------------------------------------------------------- the store

def cube_base() -> str:
    base = get_settings().CUBE_BASE_URL.strip()
    return base.rstrip("/") if base else str(DEFAULT_CUBE_DIR)


@lru_cache
def load_manifest() -> dict:
    """{variable_id: {...provenance...}} for every built cube; {} if none."""
    base = cube_base()
    try:
        with fsspec.open(f"{base}/{MANIFEST}", "r", timeout=10) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:  # noqa: BLE001 - an unreachable cube host must not stop the app booting
        logger.warning("Could not read cube manifest at %s", base, exc_info=True)
        return {}


@lru_cache(maxsize=64)
def open_cube(variable: str) -> xr.Dataset:
    return xr.open_zarr(fsspec.get_mapper(f"{cube_base()}/{variable}.zarr"), consolidated=True)


class CubeAdapter(NASADataAdapter):
    """Serves the built cubes of one dataset (e.g. MERRA-2)."""

    cacheable = False  # chunk reads are already fast; don't copy grids into the DB cache

    def __init__(self, dataset: DatasetSpec, specs: list[CubeVariableSpec], manifest: dict):
        self.code = dataset.code
        self._dataset = dataset
        self._specs = {s.info.code: s for s in specs}
        self._manifest = manifest

    def get_metadata(self) -> DatasetInfo:
        variables = []
        for code, spec in self._specs.items():
            entry = self._manifest[code]
            # the cube's real first full year beats the catalog's nominal one
            variables.append(_with_coverage(spec.info, entry.get("first_full_year")))
        doi = sorted({self._manifest[c].get("doi") for c in self._specs if self._manifest[c].get("doi")})
        return DatasetInfo(
            code=self.code,
            name=self._dataset.name,
            provider=self._dataset.provider,
            description=self._dataset.description + (f" DOI: {', '.join(doi)}." if doi else ""),
            base_url=cube_base(),
            status="active",
            requires_credentials=False,
            version=self._dataset.version,
            variables=variables,
            temporal_resolution_days=30.44,
            retry_floor_year=self._dataset.retry_floor_year,
        )

    def _check(self, variable: str) -> None:
        if variable not in self._specs:
            raise NASAAdapterError(f"{variable} is not a built {self.code} cube")

    async def query_grid_series(self, variable, min_lat, max_lat, min_lon, max_lon, start: date, end: date) -> GridSeries:
        self._check(variable)
        span = get_settings().MAX_CUBE_REGION_SPAN_DEGREES
        if (max_lat - min_lat) > span or (max_lon - min_lon) > span:
            raise NASAAdapterError(f"Region spans more than {span} degrees; draw a smaller box.")
        ds = open_cube(variable)
        da = ds[variable].sel(time=slice(np.datetime64(start), np.datetime64(end)))
        sub = da.sel(lat=slice(min_lat, max_lat), lon=slice(min_lon, max_lon))
        if sub.sizes["lat"] == 0 or sub.sizes["lon"] == 0:
            # box smaller than one cell: use the cell containing its centre
            sub = da.sel(lat=[(min_lat + max_lat) / 2], lon=[(min_lon + max_lon) / 2], method="nearest")
        values = sub.values  # (time, lat, lon); reads only the touched chunks
        dates = [date(int(str(t)[:4]), int(str(t)[5:7]), 1) for t in sub["time"].values]

        cells = []
        for a, la in enumerate(sub["lat"].values):
            for b, lo in enumerate(sub["lon"].values):
                col = values[:, a, b]
                ok = np.isfinite(col)
                if ok.any():
                    cells.append(GridCell(
                        lat=float(la), lon=float(lo),
                        dates=[d for d, k in zip(dates, ok) if k],
                        values=[float(v) for v in col[ok]],
                    ))
        return GridSeries(
            variable=variable,
            units=self._specs[variable].info.units,
            cells=cells,
            source_url=self._manifest[variable].get("source", cube_base()),
            retrieved_at=date.today(),
        )

    async def query_point_series(self, variable, lat, lon, start: date, end: date, temporal: str = "monthly") -> PointSeries:
        grid = await self.query_grid_series(variable, lat, lat, lon, lon, start, end)
        if not grid.cells:
            raise NASAAdapterError(f"No {variable} data at {lat:.2f}, {lon:.2f}")
        cell = grid.cells[0]
        return PointSeries(
            variable=variable, units=grid.units, lat=lat, lon=lon, dates=cell.dates, values=cell.values,
            missing_dates=[], source_url=grid.source_url, retrieved_at=grid.retrieved_at,
        )


def _with_coverage(info, first_full_year):
    return dataclasses.replace(info, coverage_start=first_full_year) if first_full_year else info
