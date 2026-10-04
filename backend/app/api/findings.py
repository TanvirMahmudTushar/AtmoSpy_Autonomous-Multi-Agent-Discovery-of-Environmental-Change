import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.db.session import get_db
from app.knowledge.insight import build_insight, concern_for_summary
from app.models import Finding, Investigation, Provenance, Region, User, Variable, Visualization
from app.schemas.api import FindingDetailOut, FindingSummaryOut

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=list[FindingSummaryOut])
async def list_findings(
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    variable_code: str | None = None,
    region_code: str | None = None,
    significance: str | None = Query(None, pattern="^(statistically_significant|not_significant)$"),
    investigation_id: uuid.UUID | None = None,
    mine: bool = False,
    limit: int = Query(50, le=200),
):
    stmt = (
        select(Finding, Variable, Region)
        .join(Variable, Finding.variable_id == Variable.id)
        .join(Region, Finding.region_id == Region.id)
        .order_by(Finding.created_at.desc())
        .limit(limit)
    )
    if variable_code:
        stmt = stmt.where(Variable.code == variable_code)
    if region_code:
        stmt = stmt.where(Region.code == region_code)
    if significance:
        stmt = stmt.where(Finding.significance_classification == significance)
    if investigation_id:
        stmt = stmt.where(Finding.investigation_id == investigation_id)
    if mine:
        if user is None:
            return []
        stmt = stmt.join(Investigation, Finding.investigation_id == Investigation.id).where(
            Investigation.user_id == user.id
        )

    rows = (await session.execute(stmt)).all()
    return [
        FindingSummaryOut(
            id=f.id, title=f.title, variable_code=v.code, variable_name=v.name,
            region_code=r.code, region_name=r.name, period_start=f.period_start, period_end=f.period_end,
            trend_per_year=f.trend_per_year, trend_units=f.trend_units, total_change=f.total_change,
            percent_change=f.percent_change, effect_size=f.effect_size,
            p_value=f.p_value, significance_classification=f.significance_classification,
            concern=concern_for_summary(
                v.code, f.total_change, f.effect_size,
                f.significance_classification == "statistically_significant",
                f.robustness, f.skeptic_review,
            ),
            discovery_score=f.discovery_score, created_at=f.created_at,
        )
        for f, v, r in rows
    ]


@router.get("/{finding_id}", response_model=FindingDetailOut)
async def get_finding(finding_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    row = (
        await session.execute(
            select(Finding, Variable, Region)
            .join(Variable, Finding.variable_id == Variable.id)
            .join(Region, Finding.region_id == Region.id)
            .where(Finding.id == finding_id)
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Finding not found")
    f, v, r = row

    viz_rows = (
        await session.execute(select(Visualization).where(Visualization.finding_id == finding_id))
    ).scalars().all()
    visualizations = {viz.kind: viz.data for viz in viz_rows}

    prov = (
        await session.execute(select(Provenance).where(Provenance.finding_id == finding_id))
    ).scalar_one_or_none()
    provenance = (
        {
            "source_name": prov.source_name, "dataset_version": prov.dataset_version,
            "retrieval_time": prov.retrieval_time.isoformat(), "processing_method": prov.processing_method,
            "statistical_method": prov.statistical_method, "url": prov.url,
        }
        if prov
        else None
    )

    significant = f.significance_classification == "statistically_significant"
    insight = build_insight(
        variable_code=v.code, region_code=r.code, region_kind=r.kind,
        total_change=f.total_change, effect_size=f.effect_size, significant=significant,
        trend_units=f.trend_units, robustness=f.robustness, skeptic=f.skeptic_review,
        spatial_summary=f.spatial_summary,
        change_points=(visualizations.get("timeseries") or {}).get("change_points"),
        related_variables=f.related_variables,
    )

    return FindingDetailOut(
        id=f.id, title=f.title, variable_code=v.code, variable_name=v.name,
        region_code=r.code, region_name=r.name, period_start=f.period_start, period_end=f.period_end,
        trend_per_year=f.trend_per_year, trend_units=f.trend_units, total_change=f.total_change,
        percent_change=f.percent_change, effect_size=f.effect_size,
        p_value=f.p_value, significance_classification=f.significance_classification,
        concern=insight["concern"], insight=insight,
        discovery_score=f.discovery_score, created_at=f.created_at,
        what=f.what, where=f.where, statistical_method=f.statistical_method,
        confidence_interval=f.confidence_interval, importance_note=f.importance_note,
        data_quality=f.data_quality, spatial_summary=f.spatial_summary, related_variables=f.related_variables,
        robustness=f.robustness, skeptic_review=f.skeptic_review, interpretation=f.interpretation,
        limitations=f.limitations, narrative_source=f.narrative_source, visualizations=visualizations,
        provenance=provenance,
    )
