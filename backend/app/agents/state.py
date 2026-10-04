"""Shared mutable state threaded through the agent pipeline. Each agent
function reads what it needs and writes its own results back onto this
object — this is what gives the orchestrator real branching power (e.g.
skip spatial/relationship agents, or abort after quality failure).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date

from app.analysis.quality import QualityReport
from app.analysis.spatial import CellTrend
from app.analysis.trend import TrendResult
from app.llm.planner import InvestigationPlan
from app.nasa.base import GridSeries, PointSeries
from app.nasa.regions import RegionDef


@dataclass
class InvestigationState:
    investigation_id: uuid.UUID
    question: str | None
    mode: str  # "nlp" | "discover"
    plan: InvestigationPlan
    region: RegionDef

    point_series: PointSeries | None = None
    quality_report: QualityReport | None = None
    years: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)

    trend_result: TrendResult | None = None
    change_points: list[dict] = field(default_factory=list)
    trend_band: list[dict] = field(default_factory=list)
    significance: dict | None = None
    confidence_interval: dict | None = None
    importance_note: str | None = None
    persistence: dict | None = None
    robustness_verdict: str | None = None
    robustness_caveats: list[str] = field(default_factory=list)
    skeptic_points: list[str] = field(default_factory=list)
    skeptic_verdict: str | None = None

    grid_series: GridSeries | None = None
    cell_trends: list[CellTrend] = field(default_factory=list)
    opposite_trends: dict | None = None
    compare_result: dict | None = None
    timelapse: dict | None = None

    related_variables: list[dict] = field(default_factory=list)

    narrative: dict | None = None
    visualizations: dict = field(default_factory=dict)
    finding_id: uuid.UUID | None = None

    status: str = "running"  # running | completed | failed | insufficient_data
    error: str | None = None

    @property
    def start_date(self) -> date:
        return date(self.plan.start_year, 1, 1)

    @property
    def end_date(self) -> date:
        return date(self.plan.end_year, 12, 31)
