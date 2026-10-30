"""Warm the NASA data cache so the first investigation of a region is fast.

    cd backend
    python -m scripts.prewarm                 # Discover pairs + demo regions
    python -m scripts.prewarm --all-presets   # every preset region x its suggested variables
    python -m scripts.prewarm --start 1990

A cold NASA POWER regional request takes 5-10 s; a cached one about 0.2 s.
This fetches each region's grid once through the same code path an
investigation uses (app.tools.nasa_tools.query_region_series), so the cache
entries are exactly the ones investigations will look up. Cached entries
live for NASA_POWER_CACHE_TTL_HOURS (7 days by default); run it again after
that, e.g. from a scheduled job.
"""

import argparse
import asyncio
import sys
import time
from datetime import date

from app.db.session import AsyncSessionLocal
from app.llm.suggest import rule_based
from app.nasa.base import NASAAdapterError
from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable, earliest_year
from app.nasa.regions import DISCOVERY_CANDIDATES, REGIONS, REGIONS_BY_CODE
from app.nasa.registry import get_adapter
from app.tools import nasa_tools

DEMO_PAIRS = [
    ("arctic_alaska_north_slope", "T2M"),
    ("tibetan_plateau", "T2M"),
    ("indo_gangetic_plain", "lwe_thickness"),
]


def pairs(all_presets: bool) -> list[tuple[str, str]]:
    out = list(DISCOVERY_CANDIDATES) + DEMO_PAIRS
    if all_presets:
        for region in REGIONS:
            out += [(region.code, s["variable_code"]) for s in rule_based(list(region.place_tags), region, limit=6)]
    seen, unique = set(), []
    for p in out:
        region, var = p
        # skip unavailable variables and whole-file-download sources (minutes each)
        if p in seen or var not in VARIABLES_BY_CODE or get_adapter(dataset_code_for_variable(var)).slow:
            continue
        seen.add(p)
        unique.append(p)
    return unique


async def warm(todo: list[tuple[str, str]], start_year: int, end_year: int, concurrency: int) -> int:
    sem = asyncio.Semaphore(concurrency)
    failures = 0

    async def one(i: int, region_code: str, var: str):
        nonlocal failures
        region = REGIONS_BY_CODE[region_code]
        first = max(start_year, earliest_year(var))
        async with sem, AsyncSessionLocal() as session:
            t = time.perf_counter()
            try:
                r = await nasa_tools.query_region_series(
                    session, dataset_code_for_variable(var), var, region, date(first, 1, 1), date(end_year, 12, 31)
                )
                how = f"{r.sampling['method']}"
            except NASAAdapterError as exc:
                failures += 1
                how = f"FAILED: {exc}"
            print(f"[{i}/{len(todo)}] {region_code:28s} {var:18s} {time.perf_counter() - t:5.1f}s {how}", flush=True)

    await asyncio.gather(*(one(i + 1, r, v) for i, (r, v) in enumerate(todo)))
    return failures


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--all-presets", action="store_true")
    p.add_argument("--start", type=int, default=1990)
    p.add_argument("--end", type=int, default=date.today().year - 1)
    p.add_argument("--concurrency", type=int, default=3, help="simultaneous NASA requests (be polite)")
    args = p.parse_args(argv)
    todo = pairs(args.all_presets)
    print(f"Warming {len(todo)} region/variable pairs, {args.start}-{args.end}")
    failures = asyncio.run(warm(todo, args.start, args.end, args.concurrency))
    print(f"done, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
