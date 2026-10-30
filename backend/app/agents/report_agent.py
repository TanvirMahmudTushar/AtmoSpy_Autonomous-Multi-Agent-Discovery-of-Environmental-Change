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
from app.analysis.trend import ANALYSIS_VERSION, TrendResult
from app.db.seed import seed_datasets_and_variables, upsert_region
from app.models import Dataset, Finding, Provenance, Region, Report, Variable, Visualization
from app.nasa.catalog import VARIABLES_BY_CODE, dataset_code_for_variable
from app.nasa.registry import get_adapter
from app.services.events import StepRecorder
from app.tools import report_tools


async def _dataset_and_variable_rows(session: AsyncSession, dataset_code: str, variable_code: str):
    """The Dataset and Variable rows for this finding, seeding them on demand
    (a cube built after the last seed run adds new variables)."""
    for attempt in range(2):
        dataset_row = (await session.execute(select(Dataset).where(Dataset.code == dataset_code))).scalar_one_or_none()
        variable_row = None
        if dataset_row is not None:
            variable_row = (
                await session.execute(
                    select(Variable).where(Variable.dataset_id == dataset_row.id, Variable.code == variable_code)
                )
            ).scalar_one_or_none()
        if variable_row is not None:
            return dataset_row, variable_row
        if attempt == 0:
            await seed_datasets_and_variables(session)
    raise RuntimeError(f"Variable {variable_code} of {dataset_code} could not be registered.")


def _method_description(trend: TrendResult) -> str:
    basis = (
        "monthly anomalies (seasonal cycle removed)" if trend.basis == "monthly_anomaly" else "annual means"
    )
    return (
        f"Sen's slope with a Mann-Kendall test on {basis}, both corrected for lag-1 autocorrelation "
        f"(r1 = {trend.lag1:.2f}); OLS t-test with effective sample size n_eff = {trend.n_eff:.0f} as a second check"
    )


def _processing_description(daily: bool, dataset_name: str, trend: TrendResult, sampling: dict) -> str:
    if sampling.get("method") == "area_mean":
        steps = (
            f"Monthly {dataset_name} values on {sampling['n_cells']} grid cells averaged over the region with "
            f"cos(latitude) area weights (a month counts only when at least 70% of the region's area has data)"
        )
    else:
        steps = f"{'Daily' if daily else 'Monthly'} {dataset_name} values at the region's centre point"
        if sampling.get("reason"):
            steps += f" (no regional grid: {sampling['reason']})"
        if daily:
            steps += ", averaged to monthly means (months with under 70% of days observed are dropped)"
    if trend.basis == "monthly_anomaly":
        steps += (
            ", the average seasonal cycle (monthly climatology over the record) subtracted to give anomalies, "
            "then trend-tested; annual means are shown for reference."
        )
    else:
        steps += ", aggregated to annual means, then trend-tested."
    return steps


def _slim_related(related: list[dict]) -> list[dict]:
    return [
        {k: v for k, v in r.items() if k not in ("target_years", "seed_anomalies", "target_anomalies")}
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
        "trend_per_decade": trend_result.slope_per_decade,
        "trend_basis": trend_result.basis,
        "t_test_p_value": trend_result.ols_p_value,
        "effective_sample_size": round(trend_result.n_eff),
        "years_needed_to_detect": (state.detectability or {}).get("years_needed"),
        "seasonal_trends": state.seasonal_trends,
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
    dataset_row, variable_row = await _dataset_and_variable_rows(session, dataset_code, state.plan.variable_code)
    region_row = await upsert_region(session, state.region)

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
        statistical_method=_method_description(trend_result),
        p_value=trend_result.mk_p_value,
        analysis_version=ANALYSIS_VERSION,
        temporal_basis=trend_result.basis,
        trend_details=trend_result.to_dict(),
        detectability=state.detectability,
        seasonal_trends=state.seasonal_trends,
        confidence_interval=state.confidence_interval,
        significance_classification=state.significance["classification"],
        importance_note=state.importance_note or "",
        # sampling: how the series represents the region (area mean or centre point)
        data_quality={**(state.quality_report.__dict__ if state.quality_report else {}), "sampling": state.sampling},
        spatial_summary=state.opposite_trends,
        related_variables=_slim_related(state.related_variables),
        robustness={"verdict": state.robustness_verdict, "caveats": state.robustness_caveats},
        skeptic_review={"verdict": state.skeptic_verdict, "points": state.skeptic_points},
        interpretation=narrative["interpretation"],
        limitations=narrative["limitations"],
        narrative_source=narrative["source"],
    )
    if narrative.get("guardrail_flags"):
        await recorder.emit(
            "REPORT_AGENT", "running",
            f"The AI-written summary quoted {len(narrative['guardrail_flags'])} number(s) that don't trace back to "
            f"the analysis ({', '.join(narrative['guardrail_flags'][:5])}), so it was discarded and the plain "
            "template summary was used instead.",
        )
    session.add(finding)
    await session.flush()
    state.finding_id = finding.id

    ts_chart = report_tools.generate_time_series_chart(
        state.years, state.values, trend_result, state.change_points, var_info.name, var_info.units,
        monthly=state.monthly,
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
        if top["target_years"]:
            # Plot what was correlated: each variable's anomaly with its trend removed.
            scatter = report_tools.generate_relationship_scatter(
                top["target_years"], top["seed_anomalies"], top["target_anomalies"],
                f"{var_info.name} (detrended anomaly)", f"{top['variable_name']} (detrended anomaly)",
                {"method": top["method"], "r": top["r"], "p_value": top["p_value"], "q_value": top["q_value"]},
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
            processing_method=_processing_description(
                get_adapter(dataset_code).get_metadata().temporal_resolution_days <= 1.0, dataset_row.name,
                trend_result, state.sampling,
            ),
            statistical_method=finding.statistical_method,
            url=state.point_series.source_url,
        )
    )

    await session.commit()

    change = (
        f"{finding.percent_change:+.1f}% change"
        if finding.percent_change is not None
        else f"total change {finding.total_change:+.3g} {var_info.units}"
    )
    await recorder.emit(
        "REPORT_AGENT", "done",
        f"Finding saved: {finding.title} — {finding.significance_classification}, {change}.",
        {"finding_id": str(finding.id)},
    )

    state.status = "completed"
    return state
