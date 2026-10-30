"""Measure how much regridding to cubes changes regional averages.

    cd backend
    python -m scripts.validate_cubes                 # every built cube, default regions
    python -m scripts.validate_cubes --var M2_T2M --months 36

For each built cube and each test region, this fetches the product's
native-resolution field for a sample of months straight from NASA's cloud
OPeNDAP (exactly what Giovanni averages), computes the area-weighted
(cos latitude) mean over the native pixels whose centres fall in the box,
and compares it with the regional mean this app computes from its cube.
Results (correlation, mean bias, bias as a fraction of the month-to-month
standard deviation) are printed and saved to <cubes>/validation.json, which
the About page and README reference.
"""

import argparse
import asyncio
import io
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import h5netcdf
import httpx
import numpy as np

from app.analysis.spatial import regional_mean
from app.core.config import get_settings
from app.nasa import cube
from app.nasa.catalog_yaml import cube_variable_specs, dataset_specs
from app.nasa.regions import REGIONS_BY_CODE
from scripts.build_cube import (
    cmr_collection, cmr_granules, constraint, dmr_dim_sizes, extract_field, fetch, parse_dmr, _read,
)

# Regions of different size, latitude and surface (box edges need not align with cube cells).
DEFAULT_REGIONS = ["tibetan_plateau", "sahel_west_africa", "great_plains_us", "indo_gangetic_plain", "delhi"]


def native_mean(field: np.ndarray, lat: np.ndarray, lon: np.ndarray, box) -> float:
    lon = ((np.asarray(lon, float) + 180) % 360) - 180
    # Half-open [min, max), the same rule the cube's box-averaging uses to
    # assign a pixel on a cell edge, so both sides average the same area.
    la = (lat >= box.min_lat) & (lat < box.max_lat)
    lo = (lon >= box.min_lon) & (lon < box.max_lon)
    sub = field[np.ix_(la, lo)]
    w = np.cos(np.radians(lat[la]))[:, None] * np.ones((1, lo.sum()))
    ok = np.isfinite(sub)
    return float((sub[ok] * w[ok]).sum() / w[ok].sum()) if ok.any() else float("nan")


async def validate(code: str, regions: list[str], n_months: int) -> list[dict]:
    spec = cube_variable_specs()[code]
    manifest = cube.load_manifest()
    adapter = cube.CubeAdapter(dataset_specs()[spec.dataset], [spec], manifest)
    with httpx.Client(timeout=60) as c:
        coll = cmr_collection(c, spec.short_name, spec.version)
        first = int(manifest[code]["first_month"][:4])
        last = int(manifest[code]["last_month"][:4])
        granules = cmr_granules(c, coll["concept_id"], first, last)
    monthly = len({g.month for g in granules}) == len(granules)
    if not monthly:
        print(f"{code}: daily product, skipped (would need a whole month of daily files per sample)")
        return []
    # Every 25th month: spread over the record AND through all calendar months
    # (an even spacing of 24 would sample the same month every time).
    pick = sorted({(k * 25) % len(granules) for k in range(min(n_months, len(granules)))})
    sample = [granules[i] for i in pick]

    headers = {"Authorization": f"Bearer {get_settings().NASA_EARTHDATA_TOKEN}"}
    native: dict[str, list[float]] = {r: [] for r in regions}
    months = []
    async with httpx.AsyncClient(timeout=180, follow_redirects=True, headers=headers) as client:
        dmr = (await fetch(client, sample[0].url + ".dmr.xml")).text
        layout = parse_dmr(dmr, spec.source_vars)
        lev_index = None
        if spec.level_hpa is not None:
            r = await fetch(client, sample[0].url + ".dap.nc4", {"dap4.ce": layout.lev_path})
            with h5netcdf.File(io.BytesIO(r.content), "r") as f:
                levels = np.asarray(_read(f, layout.lev_path)[...], float)
            lev_index = int(np.argmin(np.abs(levels - spec.level_hpa)))
        ce = constraint(layout, lev_index, dmr_dim_sizes(dmr))
        sem = asyncio.Semaphore(4)

        async def one(g):
            async with sem:
                r = await fetch(client, g.url + ".dap.nc4", {"dap4.ce": ce})
            return g.month, extract_field(r.content, layout, spec, lev_index)

        for month, (field, lat, lon) in sorted(await asyncio.gather(*(one(g) for g in sample)), key=lambda t: t[0]):
            months.append(month)
            for rc in regions:
                v = native_mean(field, lat, lon, REGIONS_BY_CODE[rc])
                native[rc].append(v * spec.scale + spec.offset)

    out = []
    for rc in regions:
        box = REGIONS_BY_CODE[rc]
        grid = await adapter.query_grid_series(code, box.min_lat, box.max_lat, box.min_lon, box.max_lon,
                                               date(months[0].year, 1, 1), date(months[-1].year, 12, 31))
        mean = regional_mean(grid.cells)
        by_month = dict(zip(mean.dates, mean.values))
        pairs = [(by_month.get(m), n) for m, n in zip(months, native[rc]) if by_month.get(m) is not None and np.isfinite(n)]
        if len(pairs) < 6:
            continue
        ours, theirs = np.array(pairs).T
        bias = float((ours - theirs).mean())
        sd = float(theirs.std(ddof=1))
        # A constant series (no snow in the Sahel) has no correlation or SD to compare against.
        r = float(np.corrcoef(ours, theirs)[0, 1]) if sd > 0 and ours.std() > 0 else None
        row = {"variable": code, "region": rc, "months": len(pairs), "r": round(r, 5) if r is not None else None,
               "bias": round(bias, 5), "bias_over_sd": round(abs(bias) / sd, 4) if sd > 0 else None,
               "units": spec.info.units}
        r_txt = f"{r:.4f}" if r is not None else "n/a (constant)"
        sd_txt = f"{row['bias_over_sd']:.1%} of SD" if row["bias_over_sd"] is not None else "no variability"
        print(f"{code:12s} {rc:22s} n={len(pairs):3d} r={r_txt} bias={bias:+.4g} {spec.info.units} ({sd_txt})")
        out.append(row)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--var", action="append", default=[])
    p.add_argument("--region", action="append", default=[])
    p.add_argument("--months", type=int, default=24)
    args = p.parse_args(argv)
    manifest = cube.load_manifest()
    codes = args.var or sorted(manifest)
    regions = args.region or DEFAULT_REGIONS
    rows = []
    for code in codes:
        if code not in manifest:
            print(f"{code}: no cube, skipped")
            continue
        rows += asyncio.run(validate(code, regions, args.months))
    path = Path(cube.cube_base()) / "validation.json"
    existing = json.loads(path.read_text()) if path.exists() else {}
    for row in rows:
        existing.setdefault("results", {})[f"{row['variable']}|{row['region']}"] = row
    existing["method"] = (
        "Regional area-weighted (cos latitude) means of each cube compared with the same means computed from the "
        "product's native-resolution files over the same box and months."
    )
    existing["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(json.dumps(existing, indent=2))
    print(f"saved {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
