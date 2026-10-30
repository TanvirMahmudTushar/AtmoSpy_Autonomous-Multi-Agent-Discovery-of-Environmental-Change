"""Build analysis-ready monthly cubes from NASA Level-3 products.

    cd backend
    python -m scripts.build_cube --var M2_T2M --var GPM_PRECIP
    python -m scripts.build_cube --dataset MERRA2 --start 1980 --end 2025
    python -m scripts.build_cube --list

For each catalog variable (app/nasa/variables.yaml) this:
  1. looks up the collection in CMR (concept id and DOI are recorded from
     CMR, never typed by hand) and lists its granules;
  2. reads the first granule's DAP4 metadata (DMR) to find the variable's
     full path, dimensions and coordinate arrays;
  3. for every granule, requests only the needed variable (and pressure
     level) through NASA's cloud OPeNDAP, masks fill values, applies
     scale/offset attributes, sums multi-part variables, and box-averages
     the field onto a regular grid with cos(latitude) weights;
  4. for daily products, averages days into months, keeping a month only
     when a cell has at least `min_valid_days` valid days;
  5. converts units, writes a compressed Zarr store chunked for regional
     time series (all months x 10x10 cells), and records provenance in
     manifest.json.

Per-granule results are cached under <out>/_work so an interrupted build
(OMI has ~7,000 daily granules) resumes where it stopped.

Needs NASA_EARTHDATA_TOKEN, with the DAAC's EULA accepted on that Earthdata
account (GES DISC answers 403 "EULA Acceptance Failure" otherwise).
"""

import argparse
import asyncio
import io
import json
import logging
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import h5netcdf
import httpx
import numpy as np
import pandas as pd
import xarray as xr
from numcodecs import Blosc
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.nasa.catalog_yaml import CubeVariableSpec, cube_variable_specs
from app.nasa.cube import DEFAULT_CUBE_DIR, MANIFEST, bin_average, target_axes

log = logging.getLogger("build_cube")

CMR = "https://cmr.earthdata.nasa.gov/search"
DAP4_NS = "{http://xml.opendap.org/ns/DAP/4.0#}"
NUMERIC = {"Float32", "Float64", "Int8", "Int16", "Int32", "Int64", "UInt8", "UInt16", "UInt32", "UInt64", "Byte"}
LAT_NAMES = ("lat", "latitude", "Latitude", "YDim", "lat_0")
LON_NAMES = ("lon", "longitude", "Longitude", "XDim", "lon_0")
LEV_NAMES = ("lev", "level", "StdPressureLev", "TempPrsLvls", "plev")


def _is_dim(name: str, names: tuple[str, ...]) -> bool:
    """Dimension-name match that also accepts HDF-EOS group suffixes
    (AIRS3STM names its axes YDim_ascending, XDim_location, ...)."""
    return name in names or name.split("_", 1)[0] in names


class EulaNotAccepted(RuntimeError):
    pass


# ------------------------------------------------------------------ CMR

def cmr_collection(client: httpx.Client, short_name: str, version: str) -> dict:
    r = client.get(f"{CMR}/collections.umm_json", params={"short_name": short_name, "version": version})
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise SystemExit(f"CMR has no collection {short_name} v{version}")
    meta, umm = items[0]["meta"], items[0]["umm"]
    doi = (umm.get("DOI") or {}).get("DOI")
    return {"concept_id": meta["concept-id"], "doi": doi, "title": umm.get("EntryTitle", short_name)}


@dataclass
class Granule:
    month: date  # first day of the granule's month
    day: date  # granule start date
    url: str  # cloud OPeNDAP endpoint


def cmr_granules(client: httpx.Client, concept_id: str, start: int, end: int) -> list[Granule]:
    out, search_after = [], None
    while True:
        headers = {"CMR-Search-After": search_after} if search_after else {}
        r = client.get(
            f"{CMR}/granules.umm_json",
            params={
                "collection_concept_id": concept_id, "page_size": 2000, "sort_key": "start_date",
                "temporal": f"{start}-01-01T00:00:00Z,{end}-12-31T23:59:59Z",
            },
            headers=headers,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        for it in items:
            umm = it["umm"]
            begin = umm["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][:10]
            day = date.fromisoformat(begin)
            url = next(
                (u["URL"] for u in umm.get("RelatedUrls", []) if u.get("Subtype") == "OPENDAP DATA"
                 and "opendap.earthdata.nasa.gov" in u["URL"]),
                None,
            )
            if url:
                out.append(Granule(month=day.replace(day=1), day=day, url=url))
        search_after = r.headers.get("CMR-Search-After")
        if not items or not search_after:
            return out


# ------------------------------------------------------------------ DMR

@dataclass
class Layout:
    """Where the variable and its coordinates live inside a granule."""

    var_paths: list[str]
    var_dims: list[str]  # dimension names of the (first) variable, e.g. /time /lat /lon
    lat_path: str | None
    lon_path: str | None
    lev_path: str | None


def parse_dmr(xml_text: str, source_vars: tuple[str, ...]) -> Layout:
    root = ET.fromstring(xml_text)
    variables: dict[str, list[str]] = {}

    def walk(node, prefix):
        for child in node:
            tag = child.tag.replace(DAP4_NS, "")
            if tag == "Group":
                walk(child, f"{prefix}/{child.get('name')}")
            elif tag in NUMERIC:
                dims = [d.get("name") for d in child.findall(f"{DAP4_NS}Dim")]
                variables[f"{prefix}/{child.get('name')}"] = dims

    walk(root, "")

    def find(leaf_names) -> str | None:
        for name in leaf_names:
            for path in variables:
                if path.rsplit("/", 1)[-1] == name:
                    return path
        return None

    var_paths = []
    for v in source_vars:
        path = find((v,))
        if path is None:
            raise SystemExit(f"Variable {v!r} not in this product. Available: {sorted(variables)[:60]}")
        var_paths.append(path)
    return Layout(
        var_paths=var_paths,
        var_dims=variables[var_paths[0]],
        lat_path=find(LAT_NAMES),
        lon_path=find(LON_NAMES),
        lev_path=find(LEV_NAMES),
    )


# ------------------------------------------------------------------ fetch + extract

def _read(f: h5netcdf.File, path: str):
    node = f
    parts = [p for p in path.split("/") if p]
    for g in parts[:-1]:
        node = node.groups[g]
    return node.variables[parts[-1]]


def _masked(var) -> np.ndarray:
    """Values with fill masked to NaN and CF scale/offset applied."""
    a = np.asarray(var[...], dtype="float64")
    for key in ("_FillValue", "missing_value"):
        if key in var.attrs:
            fill = np.atleast_1d(var.attrs[key]).astype("float64")
            a[np.isin(a, fill)] = np.nan
    if "scale_factor" in var.attrs:
        a = a * float(np.atleast_1d(var.attrs["scale_factor"])[0])
    if "add_offset" in var.attrs:
        a = a + float(np.atleast_1d(var.attrs["add_offset"])[0])
    a[np.abs(a) > 1e29] = np.nan  # some products use huge sentinels without declaring them
    return a


def extract_field(content: bytes, layout: Layout, spec: CubeVariableSpec, lev_index: int | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(field[lat, lon], lat, lon) from one DAP4 netCDF-4 response."""
    with h5netcdf.File(io.BytesIO(content), "r") as f:
        total = None
        for path in layout.var_paths:
            var = _read(f, path)
            a = _masked(var)
            dims = [d.rsplit("/", 1)[-1] for d in var.dimensions]
            # reduce to (lat, lon): drop time/level axes, transposing lon-major layouts
            for axis in reversed(range(a.ndim)):
                name = dims[axis]
                if _is_dim(name, LAT_NAMES) or _is_dim(name, LON_NAMES):
                    continue
                if _is_dim(name, LEV_NAMES) and lev_index is not None and a.shape[axis] > 1:
                    a = np.take(a, lev_index, axis=axis)
                else:
                    a = np.take(a, 0, axis=axis)
                del dims[axis]
            if dims and _is_dim(dims[0], LON_NAMES):
                a = a.T
            total = a if total is None else total + a
        if layout.lat_path and layout.lon_path:
            lat = np.asarray(_read(f, layout.lat_path)[...], dtype="float64")
            lon = np.asarray(_read(f, layout.lon_path)[...], dtype="float64")
            # Some L3 products (AIRS3STM) store full 2-D coordinate grids; a
            # regular grid collapses to its 1-D axes.
            if lat.ndim == 2 and np.allclose(lat, lat[:, :1]) and np.allclose(lon, lon[:1, :]):
                lat, lon = lat[:, 0], lon[0, :]
        else:
            g = spec.source_grid
            if not g:
                raise SystemExit(f"{spec.info.code}: no lat/lon arrays and no source_grid in variables.yaml")
            lat = g["lat0"] + g["dlat"] * np.arange(g["nlat"])
            lon = g["lon0"] + g["dlon"] * np.arange(g["nlon"])
    return total, lat, lon


class Retryable(RuntimeError):
    pass


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type((httpx.TransportError, Retryable)),
    reraise=True,
)
async def fetch(client: httpx.AsyncClient, url: str, params: dict | None = None) -> httpx.Response:
    """GET with retries for network errors, throttling (429) and server
    errors (5xx) only. Auth failures stop the build at once: retrying
    cannot fix an unaccepted EULA."""
    r = await client.get(url, params=params)
    if r.status_code in (401, 403):
        raise EulaNotAccepted(
            f"HTTP {r.status_code} from {url.split('/granules/')[0]}: accept this DAAC's EULA and authorize its "
            f"application in your Earthdata Login profile, then rerun. Server said: {r.text[:160]!r}"
        )
    if r.status_code == 429 or r.status_code >= 500:
        raise Retryable(f"HTTP {r.status_code} from {url}")
    r.raise_for_status()
    return r


# ------------------------------------------------------------------ build

def constraint(layout: Layout, lev_index: int | None, dim_sizes: dict[str, int]) -> str:
    parts = []
    for path in layout.var_paths:
        if lev_index is None:
            parts.append(path)
            continue
        idx = []
        for d in layout.var_dims:
            leaf = d.rsplit("/", 1)[-1]
            n = dim_sizes.get(d) or dim_sizes.get(leaf)
            idx.append(f"[{lev_index}:1:{lev_index}]" if _is_dim(leaf, LEV_NAMES) else f"[0:1:{n - 1}]")
        parts.append(path + "".join(idx))
    for p in (layout.lat_path, layout.lon_path):
        if p:
            parts.append(p)
    return ";".join(parts)


def dmr_dim_sizes(xml_text: str) -> dict[str, int]:
    root = ET.fromstring(xml_text)
    sizes = {}

    def walk(node, prefix):
        for child in node:
            tag = child.tag.replace(DAP4_NS, "")
            if tag == "Group":
                walk(child, f"{prefix}/{child.get('name')}")
            elif tag == "Dimension":
                sizes[f"{prefix}/{child.get('name')}"] = int(child.get("size"))
                sizes[child.get("name")] = int(child.get("size"))

    walk(root, "")
    return sizes


async def build_variable(spec: CubeVariableSpec, start: int, end: int, out_dir: Path, workers: int) -> dict:
    token = get_settings().NASA_EARTHDATA_TOKEN
    if not token:
        raise SystemExit("NASA_EARTHDATA_TOKEN is not set")
    code = spec.info.code
    work = out_dir / "_work" / code
    work.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=60) as c:
        coll = cmr_collection(c, spec.short_name, spec.version)
        granules = cmr_granules(c, coll["concept_id"], start, end)
    if not granules:
        raise SystemExit(f"No granules for {spec.short_name} v{spec.version} in {start}-{end}")
    daily = len({g.month for g in granules}) < len(granules)
    log.info("%s: %s (%s), %d granules, %s", code, coll["title"], coll["concept_id"], len(granules),
             "daily -> monthly" if daily else "monthly")

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=180, follow_redirects=True, headers=headers) as client:
        dmr = (await fetch(client, granules[0].url + ".dmr.xml")).text
        layout = parse_dmr(dmr, spec.source_vars)
        sizes = dmr_dim_sizes(dmr)
        lev_index = None
        if spec.level_hpa is not None:
            if not layout.lev_path:
                raise SystemExit(f"{code}: product has no pressure-level axis")
            r = await fetch(client, granules[0].url + ".dap.nc4", {"dap4.ce": layout.lev_path})
            with h5netcdf.File(io.BytesIO(r.content), "r") as f:
                levels = np.asarray(_read(f, layout.lev_path)[...], dtype=float)
            lev_index = int(np.argmin(np.abs(levels - spec.level_hpa)))
            if abs(levels[lev_index] - spec.level_hpa) > 0.5:
                raise SystemExit(f"{code}: level {spec.level_hpa} hPa not in {levels.tolist()}")
        ce = constraint(layout, lev_index, sizes)
        log.info("%s: DAP4 constraint %s", code, ce)

        sem = asyncio.Semaphore(workers)
        done = 0

        async def one(g: Granule):
            nonlocal done
            path = work / f"{g.day:%Y%m%d}.npy"
            if path.exists():
                done += 1
                return
            async with sem:
                r = await fetch(client, g.url + ".dap.nc4", {"dap4.ce": ce})
            field, lat, lon = extract_field(r.content, layout, spec, lev_index)
            np.save(path, bin_average(field, lat, lon, spec.grid_res).astype("float32"))
            done += 1
            if done % 25 == 0 or done == len(granules):
                log.info("%s: %d/%d granules", code, done, len(granules))

        await asyncio.gather(*(one(g) for g in granules))

    return assemble(spec, granules, daily, coll, work, out_dir, start, end)


def replace_dir(tmp: Path, final: Path, attempts: int = 8) -> None:
    """Swap the freshly written store into place. On Windows a rename can
    briefly fail with "Access is denied" while antivirus or the search
    indexer still has a just-written file open, so retry with backoff, then
    fall back to copying."""
    for i in range(attempts):
        try:
            shutil.rmtree(final, ignore_errors=True)
            tmp.rename(final)
            return
        except PermissionError:
            time.sleep(0.5 * 2**i)
    shutil.copytree(tmp, final, dirs_exist_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)


def assemble(spec, granules, daily, coll, work, out_dir, start, end) -> dict:
    code = spec.info.code
    lat, lon = target_axes(spec.grid_res)
    by_month: dict[date, list[Path]] = {}
    for g in granules:
        by_month.setdefault(g.month, []).append(work / f"{g.day:%Y%m%d}.npy")
    months = sorted(by_month)

    data = np.full((len(months), len(lat), len(lon)), np.nan, dtype="float32")
    valid_days = np.zeros((len(months), len(lat), len(lon)), dtype="int16") if daily else None
    for t, m in enumerate(months):
        fields = [np.load(p) for p in by_month[m]]
        if daily:
            stack = np.stack(fields)
            count = np.isfinite(stack).sum(axis=0)
            with np.errstate(invalid="ignore"):
                mean = np.nanmean(stack, axis=0)
            mean[count < (spec.min_valid_days or 1)] = np.nan
            data[t], valid_days[t] = mean, count
        else:
            data[t] = fields[0]
    data = data * spec.scale + spec.offset

    times = pd.DatetimeIndex([pd.Timestamp(m) for m in months])
    chunk = max(1, int(round(10 / spec.grid_res)))
    ds = xr.Dataset(
        {code: (("time", "lat", "lon"), data.astype("float32"))},
        coords={"time": times, "lat": lat.astype("float32"), "lon": lon.astype("float32")},
        attrs={"title": f"{spec.info.name}, monthly, {spec.grid_res} degree", "source": coll["title"]},
    )
    ds[code].attrs.update({"units": spec.info.units, "long_name": spec.info.name})
    if valid_days is not None:
        ds["valid_days"] = (("time", "lat", "lon"), valid_days)
    compressor = Blosc(cname="zstd", clevel=5, shuffle=Blosc.BITSHUFFLE)
    encoding = {v: {"chunks": (len(months), chunk, chunk), "compressor": compressor} for v in ds.data_vars}

    final = out_dir / f"{code}.zarr"
    tmp = out_dir / f"{code}.zarr.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    ds.to_zarr(tmp, encoding=encoding, consolidated=True, mode="w")
    replace_dir(tmp, final)

    full_years = [y for y in range(months[0].year, months[-1].year + 1)
                  if sum(1 for m in months if m.year == y) == 12]
    entry = {
        "variable": code,
        "name": spec.info.name,
        "units": spec.info.units,
        "product": spec.short_name,
        "version": spec.version,
        "concept_id": coll["concept_id"],
        "doi": coll["doi"],
        "source": f"{CMR}/concepts/{coll['concept_id']}.html",
        "source_variables": list(spec.source_vars),
        "level_hpa": spec.level_hpa,
        "resolution_deg": spec.grid_res,
        "regrid": "cos(latitude)-weighted box average of native pixels",
        "conversion": {"scale": spec.scale, "offset": spec.offset},
        "daily_to_monthly": {"min_valid_days": spec.min_valid_days} if daily else None,
        "n_granules": len(granules),
        "first_month": months[0].isoformat(),
        "last_month": months[-1].isoformat(),
        "first_full_year": full_years[0] if full_years else None,
        "requested_years": [start, end],
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    manifest_path = out_dir / MANIFEST
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest[code] = entry
    manifest_path.write_text(json.dumps(manifest, indent=2))
    log.info("%s: wrote %s (%d months, %s)", code, final, len(months), entry["doi"])
    return entry


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--var", action="append", default=[], help="catalog variable id (repeatable)")
    p.add_argument("--dataset", help="build every variable of one dataset, e.g. MERRA2")
    p.add_argument("--start", type=int, default=1980)
    p.add_argument("--end", type=int, default=date.today().year - 1)
    p.add_argument("--out", type=Path, default=DEFAULT_CUBE_DIR)
    p.add_argument("--workers", type=int, default=6, help="concurrent OPeNDAP requests (be polite)")
    p.add_argument("--list", action="store_true", help="list buildable variables and exit")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request is noise here

    specs = cube_variable_specs()
    if args.list:
        for code, s in specs.items():
            level = f" @{s.level_hpa} hPa" if s.level_hpa else ""
            print(f"{code:14s} {s.dataset:10s} {s.short_name} v{s.version} {'+'.join(s.source_vars)}{level}")
        return 0
    chosen = list(args.var) + [c for c, s in specs.items() if args.dataset and s.dataset == args.dataset]
    unknown = [c for c in chosen if c not in specs]
    if unknown or not chosen:
        p.error(f"choose --var or --dataset; unknown: {unknown}. Use --list.")

    args.out.mkdir(parents=True, exist_ok=True)
    for code in dict.fromkeys(chosen):
        spec = specs[code]
        start = max(args.start, spec.info.coverage_start or args.start)
        try:
            asyncio.run(build_variable(spec, start, args.end, args.out, args.workers))
        except EulaNotAccepted as exc:
            log.error("%s", exc)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
