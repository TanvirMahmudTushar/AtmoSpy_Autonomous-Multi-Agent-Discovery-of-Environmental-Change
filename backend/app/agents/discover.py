"""Autonomous "Discover Changes" mode.

Scans a curated set of (region, variable) candidates end-to-end through the
same full pipeline used by /investigate (data -> quality -> trend ->
significance -> spatial -> relationship -> robustness -> report), each
producing a real Finding if the data supports one. Afterwards, all resulting
Findings are ranked by explicit, displayed criteria — never a single opaque
AI "interestingness" score.
"""

import asyncio
import logging
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.agents.orchestrator import run_pipeline
from app.agents.state import InvestigationState
from app.analysis.spatial import benjamini_hochberg
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.llm.planner import InvestigationPlan
from app.models import Finding, Investigation
from app.nasa.catalog import VARIABLES_BY_CODE
from app.nasa.regions import DISCOVERY_CANDIDATES, REGIONS_BY_CODE
from app.services.events import StepRecorder

logger = logging.getLogger(__name__)

# Ranking weights are fixed and documented here — not learned, not hidden.
# Each criterion is normalized to roughly [0, 1] before weighting.
CRITERIA_WEIGHTS = {
    "trend_magnitude_pct": 0.30,
    "significance_strength": 0.30,
    "data_completeness": 0.15,
    "persistence_score": 0.15,
    "spatial_extent_fraction": 0.10,
}


async def _run_candidate(investigation_id: uuid.UUID, region_code: str, variable_code: str, semaphore: asyncio.Semaphore) -> str | None:
    async with semaphore:
        async with AsyncSessionLocal() as session:
            recorder = StepRecorder(investigation_id, session)
            region = REGIONS_BY_CODE[region_code]
            var_name = VARIABLES_BY_CODE[variable_code].name
            label = f"{region.name} / {var_name}"

            plan = InvestigationPlan(
                variable_code=variable_code,
                region_code=region_code,
                start_year=1990,
                end_year=datetime.now(timezone.utc).year - 1,
                run_spatial_analysis=True,
                run_relationship_analysis=True,
                reasoning=f"Discovery candidate: {label}",
                source="discovery_candidate",
            )
            state = InvestigationState(investigation_id=investigation_id, question=None, mode="discover", plan=plan, region=region)

            try:
                await recorder.emit("NASA_DATA_AGENT", "running", f"[{label}] Retrieving NASA data...")
                state = await run_pipeline(session, recorder, state, allow_retry=False)
                return str(state.finding_id) if state.finding_id else None
            except Exception:
                logger.exception("Discovery candidate %s failed", label)
                await recorder.emit("SYSTEM", "error", f"[{label}] Candidate failed unexpectedly; skipped.")
                return None


def _criteria(finding: Finding, q_value: float) -> dict:
    """q_value is the finding's p-value after Benjamini-Hochberg adjustment
    across every finding in this scan: screening 16 candidates at p < 0.05
    would otherwise expect ~1 'significant' trend by chance alone."""
    magnitude = min(abs(finding.percent_change or 0.0) / 50.0, 1.0)  # 50% change treated as "maxed out"
    sig_strength = min(-math.log10(max(q_value, 1e-10)) / 5.0, 1.0)  # q=1e-5 -> 1.0
    completeness = (finding.data_quality or {}).get("completeness", 0.0)
    verdict = (finding.robustness or {}).get("verdict")
    persistence_score = 1.0 if verdict == "robust" else 0.5 if verdict == "robust with caveats" else 0.0
    spatial_extent = 0.0
    if finding.spatial_summary and finding.spatial_summary.get("total_cells"):
        spatial_extent = (finding.spatial_summary.get("significant_cells") or 0) / finding.spatial_summary["total_cells"]

    raw = {
        "trend_magnitude_pct": round(magnitude, 4),
        "significance_strength": round(sig_strength, 4),
        "data_completeness": round(completeness, 4),
        "persistence_score": round(persistence_score, 4),
        "spatial_extent_fraction": round(spatial_extent, 4),
    }
    weighted_total = sum(raw[k] * w for k, w in CRITERIA_WEIGHTS.items())
    return {
        **raw,
        "q_value_across_scan": round(float(q_value), 6),
        "significant_across_scan": bool(q_value < 0.05),
        "weights": CRITERIA_WEIGHTS,
        "weighted_total": round(weighted_total, 4),
    }


async def run_discovery(investigation_id: uuid.UUID) -> None:
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.DISCOVERY_MAX_CONCURRENCY)

    async with AsyncSessionLocal() as session:
        investigation = (
            await session.execute(select(Investigation).where(Investigation.id == investigation_id))
        ).scalar_one()
        recorder = StepRecorder(investigation_id, session)
        await recorder.emit(
            "ORCHESTRATOR", "running",
            f"Scanning {len(DISCOVERY_CANDIDATES)} region/variable candidates for significant trends...",
        )
        investigation.status = "running"
        await session.commit()

    tasks = [
        _run_candidate(investigation_id, region_code, variable_code, semaphore)
        for region_code, variable_code in DISCOVERY_CANDIDATES
    ]
    await asyncio.gather(*tasks)

    async with AsyncSessionLocal() as session:
        recorder = StepRecorder(investigation_id, session)
        findings = (
            await session.execute(select(Finding).where(Finding.investigation_id == investigation_id))
        ).scalars().all()

        q_values = benjamini_hochberg([f.p_value for f in findings])
        scored = []
        for f, q in zip(findings, q_values):
            criteria = _criteria(f, q)
            f.discovery_score = criteria
            scored.append((criteria["weighted_total"], f))
        scored.sort(key=lambda t: t[0], reverse=True)
        for rank, (_, f) in enumerate(scored, start=1):
            f.discovery_score = {**f.discovery_score, "rank": rank}

        await session.commit()

        investigation = (
            await session.execute(select(Investigation).where(Investigation.id == investigation_id))
        ).scalar_one()
        investigation.status = "completed"
        investigation.completed_at = datetime.now(timezone.utc)
        await session.commit()

        n_significant = sum(1 for f in findings if f.significance_classification == "statistically_significant")
        n_after_fdr = sum(1 for q in q_values if q < 0.05)
        await recorder.emit(
            "REPORT_AGENT", "done",
            f"Discovery complete: {len(findings)} findings produced from {len(DISCOVERY_CANDIDATES)} candidates "
            f"screened, {n_significant} statistically significant on their own and {n_after_fdr} after correcting "
            f"for testing {len(findings)} candidates at once (Benjamini-Hochberg).",
            {"n_findings": len(findings), "n_significant": n_significant, "n_significant_after_fdr": n_after_fdr},
        )
        await recorder.close()
