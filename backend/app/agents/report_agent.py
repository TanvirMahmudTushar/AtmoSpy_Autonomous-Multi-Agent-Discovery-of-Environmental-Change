"""Agent 9 — Report Agent. Assembles the structured Finding (WHAT/WHERE/WHEN/
HOW MUCH/SIGNIFICANCE/SOURCE/METHOD/LIMITATIONS/RELATED/INTERPRETATION),
persists it with full provenance, and is the only place an LLM call is made
to phrase (never compute) the interpretation.
"""

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import InvestigationState
from app.analysis.significance import classify_significance, effect_size
from app.models import Dataset, Finding, Provenance, Region, Report, Variable, Visualization
from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable
from app.nasa.registry import get_adapter
from app.services.events import StepRecorder
from app.tools import report_tools


async def _get_or_create_region(session: AsyncSession, region_def) -> Region:
    row = (await session.execute(select(Region).where(Region.code == region_def.code))).scalar_one_or_none()
    if row is None:
        raise RuntimeError(f"Region {region_def.code} not seeded — run app.db.seed first.")
    return row


def _slim_related(related: list[dict]) -> list[dict]:
    return [
        {k: v for k, v in r.items() if k not in ("target_years", "target_values")}
        for r in related
    ]


def _build_facts(state: InvestigationState, var_info, dataset_row: Dataset, region_row: Region) -> dict:
    trend_result = state.trend_result
    return {
        "variable_code": state.plan.variable_code,
        "variable_name": var_info.name,
        "trend_units": var_info.units,
        "region_name": region_row.name,
        "start_year": trend_result.start_year,
        "end_year": trend_result.end_year,
        "trend_per_year": trend_result.sen_slope_per_year,
        "total_change": trend_result.total_change,
        "percent_change": trend_result.percent_change,
        "p_value": trend_result.mk_p_value,
        "significance_classification": state.significance["classification"],
        "confidence_interval": state.confidence_interval,
        "coverage_years": state.quality_report.coverage_years if state.quality_report else None,
        "completeness": state.quality_report.completeness if state.quality_report else None,
        "importance_note": state.importance_note,
        "related_variables": _slim_related(state.related_variables),
        "spatial_summary": state.opposite_trends,
        "robustness_verdict": state.robustness_verdict,
        "skeptic_verdict": state.skeptic_verdict,
        "skeptic_points": state.skeptic_points,
        "dataset_name": dataset_row.name,
    }


async def run(session: AsyncSession, recorder: StepRecorder, state: InvestigationState) -> InvestigationState:
    await recorder.emit("REPORT_AGENT", "running", "Assembling the scientific finding...")

    var_info = VARIABLES_BY_CODE[state.plan.variable_code]
    dataset_code = dataset_code_for_variable(state.plan.variable_code)
    dataset_row = (await session.execute(select(Dataset).where(Dataset.code == dataset_code))).scalar_one()
    variable_row = (
        await session.execute(
            select(Variable).where(Variable.dataset_id == dataset_row.id, Variable.code == state.plan.variable_code)
        )
    ).scalar_one()
    region_row = await _get_or_create_region(session, state.region)

    facts = _build_facts(state, var_info, dataset_row, region_row)
    narrative = await report_tools.create_investigation_report(facts)
    state.narrative = narrative

    trend_result = state.trend_result
    finding = Finding(
        investigation_id=state.investigation_id,
        title=f"{var_info.name} in {region_row.name}, {trend_result.start_year}-{trend_result.end_year}",
        variable_id=variable_row.id,
        region_id=region_row.id,
        what=f"{var_info.name} ({var_info.units})",
        where=region_row.name,
        period_start=date(trend_result.start_year, 1, 1),
        period_end=date(trend_result.end_year, 12, 31),
        trend_per_year=trend_result.sen_slope_per_year,
        trend_units=f"{var_info.units}/year",
        total_change=trend_result.total_change,
        percent_change=trend_result.percent_change,
        effect_size=effect_size(trend_result.total_change, trend_result.std_dev),
        statistical_method="Mann-Kendall trend test with Sen's slope estimator (OLS regression computed for comparison)",
        p_value=trend_result.mk_p_value,
        confidence_interval=state.confidence_interval,
        significance_classification=state.significance["classification"],
        importance_note=state.importance_note or "",
        data_quality=state.quality_report.__dict__ if state.quality_report else {},
        spatial_summary=state.opposite_trends,
        related_variables=_slim_related(state.related_variables),
        robustness={"verdict": state.robustness_verdict, "caveats": state.robustness_caveats},
        skeptic_review={"verdict": state.skeptic_verdict, "points": state.skeptic_points},
        interpretation=narrative["interpretation"],
        limitations=narrative["limitations"] + (
            f" [NOTE: narrative contained {len(narrative['guardrail_flags'])} number(s) not traced to computed "
            f"data and was flagged for review: {narrative['guardrail_flags']}]"
            if narrative.get("guardrail_flags") else ""
        ),
        narrative_source=narrative["source"],
    )
    session.add(finding)
    await session.flush()
    state.finding_id = finding.id

    ts_chart = report_tools.generate_time_series_chart(
        state.years, state.values, trend_result, state.change_points, var_info.name, var_info.units,
        trend_band=state.trend_band,
    )
    session.add(Visualization(finding_id=finding.id, investigation_id=state.investigation_id, kind="timeseries", data=ts_chart))
    state.visualizations["timeseries"] = ts_chart

    if state.cell_trends:
        spatial_map = report_tools.generate_spatial_map(state.cell_trends, var_info.name, var_info.units)
        session.add(Visualization(finding_id=finding.id, investigation_id=state.investigation_id, kind="spatial_map", data=spatial_map))
        state.visualizations["spatial_map"] = spatial_map

        if state.timelapse and state.timelapse.get("years"):
            timelapse_viz = report_tools.generate_spatial_timelapse(state.timelapse, var_info.name, var_info.units)
            session.add(Visualization(finding_id=finding.id, investigation_id=state.investigation_id, kind="spatial_timelapse", data=timelapse_viz))
            state.visualizations["spatial_timelapse"] = timelapse_viz

    if state.related_variables:
        top = state.related_variables[0]
        common = sorted(set(state.years) & set(top["target_years"]))
        if common:
            y_map, t_map = dict(zip(state.years, state.values)), dict(zip(top["target_years"], top["target_values"]))
            scatter = report_tools.generate_relationship_scatter(
                common, [y_map[y] for y in common], [t_map[y] for y in common],
                var_info.name, top["variable_name"],
                {"method": top["method"], "r": top["r"], "p_value": top["p_value"]},
            )
            session.add(Visualization(finding_id=finding.id, investigation_id=state.investigation_id, kind="scatter", data=scatter))
            state.visualizations["scatter"] = scatter

    session.add(
        Report(
            finding_id=finding.id,
            content={
                "what": finding.what, "where": finding.where,
                "when": f"{finding.period_start.isoformat()} to {finding.period_end.isoformat()}",
                "how_much": {"trend_per_year": finding.trend_per_year, "total_change": finding.total_change, "percent_change": finding.percent_change},
                "significance": finding.significance_classification, "p_value": finding.p_value,
                "data_source": dataset_row.name, "method": finding.statistical_method,
                "limitations": finding.limitations, "related_variables": finding.related_variables,
                "interpretation": finding.interpretation,
            },
            generated_by=narrative["source"],
        )
    )

    session.add(
        Provenance(
            finding_id=finding.id,
            investigation_id=state.investigation_id,
            dataset_id=dataset_row.id,
            variable_id=variable_row.id,
            source_name=dataset_row.name,
            dataset_version=dataset_row.version,
            retrieval_time=datetime.now(timezone.utc),
            processing_method=(
                f"{'Daily' if get_adapter(dataset_code).get_metadata().temporal_resolution_days <= 1.0 else 'Monthly'} "
                f"{dataset_row.name} values aggregated to annual means (pandas), then trend-tested."
            ),
            statistical_method=finding.statistical_method,
            url=state.point_series.source_url,
        )
    )

    await session.commit()

    await recorder.emit(
        "REPORT_AGENT", "done",
        f"Finding saved: {finding.title} — {finding.significance_classification}, "
        f"{finding.percent_change:+.1f}% change." if finding.percent_change is not None else "Finding saved.",
        {"finding_id": str(finding.id)},
    )

    state.status = "completed"
    return state
