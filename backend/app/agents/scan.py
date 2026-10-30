"""Region scan — "what is changing here?".

Screens every available variable that suits one region with the same
autocorrelation-corrected trend test the full pipeline uses, on the same
area-mean series, then corrects for testing many variables at once
(Benjamini-Hochberg: with 15 variables at p < 0.05, about one would look
significant by chance alone). It produces a ranked shortlist, not Findings;
clicking a row runs the full investigation on that variable.
"""

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone

import numpy as np
from sqlalchemy import select

from app.analysis.spatial import benjamini_hochberg
from app.analysis.trend import primary_trend
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Investigation
from app.nasa.base import NASAAdapterError
from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable, earliest_year
from app.nasa.regions import RegionDef
from app.nasa.registry import get_adapter
from app.services.events import StepRecorder
from app.tools import analysis_tools, nasa_tools

logger = logging.getLogger(__name__)

FDR_ALPHA = 0.05
MIN_YEARS = 8


def scan_variables(region: RegionDef) -> tuple[list[str], list[str]]:
    """(to scan, skipped as too slow). Over open ocean only ocean-tagged
    variables make sense. Sources that download whole files on demand take
    minutes per region, too slow for a quick screen; they can still be
    investigated one at a time."""
    codes, slow = [], []
    for code, v in VARIABLES_BY_CODE.items():
        if region.kind == "ocean" and "ocean" not in v.place_tags:
            continue
        (slow if get_adapter(dataset_code_for_variable(code)).slow else codes).append(code)
    return codes, slow


async def _screen_one(session, region: RegionDef, code: str, start_year: int, end_year: int) -> dict | None:
    v = VARIABLES_BY_CODE[code]
    start = max(start_year, earliest_year(code))
    regional = await nasa_tools.query_region_series(
        session, dataset_code_for_variable(code), code, region, date(start, 1, 1), date(end_year, 12, 31)
    )
    # CPU work off the event loop; the quick screen needs only the headline test.
    bundle = await asyncio.to_thread(analysis_tools.prepare_monthly, regional.series)
    if bundle.coverage_years < MIN_YEARS or len(bundle.annual) < 5:
        return None
    t = await asyncio.to_thread(primary_trend, bundle, False)
    return {
        "variable_code": code,
        "name": v.name,
        "units": v.units,
        "definition": v.definition,
        "start_year": t.start_year,
        "end_year": t.end_year,
        "slope_per_decade": t.slope_per_decade,
        "sen_ci_per_decade": [t.sen_ci_lower * 10, t.sen_ci_upper * 10],
        "total_change": t.total_change,
        "effect_size": abs(t.total_change) / t.std_dev if t.std_dev else 0.0,
        "p_value": t.mk_p_value,
        "z": t.mk_z,
        "basis": t.basis,
        "sampling": regional.sampling.get("method"),
    }


async def run_scan(investigation_id: uuid.UUID, region: RegionDef, start_year: int, end_year: int) -> None:
    codes, slow = scan_variables(region)
    sem = asyncio.Semaphore(get_settings().DISCOVERY_MAX_CONCURRENCY)

    async with AsyncSessionLocal() as session:
        recorder = StepRecorder(investigation_id, session)
        investigation = (await session.execute(select(Investigation).where(Investigation.id == investigation_id))).scalar_one()
        investigation.status = "running"
        await session.commit()
        msg = f"Scanning {len(codes)} variables over {region.name}, {start_year}-{end_year}, for trends..."
        if slow:
            names = ", ".join(VARIABLES_BY_CODE[c].name for c in slow)
            msg += f" Not in this quick scan (their data downloads take minutes): {names}. Investigate them directly."
        await recorder.emit("ORCHESTRATOR", "running", msg)

    async def one(code: str):
        async with sem, AsyncSessionLocal() as s:
            rec = StepRecorder(investigation_id, s)
            name = VARIABLES_BY_CODE[code].name
            try:
                result = await _screen_one(s, region, code, start_year, end_year)
            except NASAAdapterError as exc:
                await rec.emit("NASA_DATA_AGENT", "skipped", f"{name}: data unavailable ({exc}).")
                return None
            except Exception:  # noqa: BLE001 - one variable failing must not end the scan
                logger.exception("Scan of %s failed", code)
                await rec.emit("NASA_DATA_AGENT", "skipped", f"{name}: failed unexpectedly; skipped.")
                return None
            if result is None:
                await rec.emit("TREND_AGENT", "skipped", f"{name}: too short a record here to test.")
            else:
                await rec.emit(
                    "TREND_AGENT", "done",
                    f"{name}: {result['slope_per_decade']:+.3g} {result['units']} per decade (p = {result['p_value']:.3g}).",
                )
            return result

    results = [r for r in await asyncio.gather(*(one(c) for c in codes)) if r]
    q = benjamini_hochberg([r["p_value"] for r in results])
    for r, qv in zip(results, q):
        r["q_value"] = float(qv)
        r["significant"] = bool(qv < FDR_ALPHA)
        r["score"] = float(abs(r["z"]) * r["effect_size"])
    results.sort(key=lambda r: (not r["significant"], -r["score"]))

    async with AsyncSessionLocal() as session:
        recorder = StepRecorder(investigation_id, session)
        n_sig = sum(r["significant"] for r in results)
        await recorder.emit(
            "REPORT_AGENT", "done",
            f"Scan complete: {len(results)} variables tested over {region.name}; {n_sig} show a significant trend "
            f"after correcting for testing {len(results)} variables at once.",
            {"scan_results": _json_safe(results), "region": region.name},
        )
        investigation = (await session.execute(select(Investigation).where(Investigation.id == investigation_id))).scalar_one()
        investigation.status = "completed"
        investigation.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await recorder.close()


def _json_safe(rows: list[dict]) -> list[dict]:
    def clean(v):
        if isinstance(v, float) and not np.isfinite(v):
            return None
        if isinstance(v, list):
            return [clean(x) for x in v]
        return v

    return [{k: clean(v) for k, v in r.items()} for r in rows]
