import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class BBox(BaseModel):
    min_lat: float = Field(..., ge=-90, le=90)
    max_lat: float = Field(..., ge=-90, le=90)
    min_lon: float = Field(..., ge=-180, le=180)
    max_lon: float = Field(..., ge=-180, le=180)

    @model_validator(mode="after")
    def _ordered(self):
        if self.min_lat >= self.max_lat or self.min_lon >= self.max_lon:
            raise ValueError("bbox needs min_lat < max_lat and min_lon < max_lon")
        return self


class CreateInvestigationRequest(BaseModel):
    """Either a plain-language `question`, or a structured choice (from the
    guided wizard): `variable_code` plus a preset `region_code` or a drawn
    `bbox`. Structured requests skip question parsing entirely."""

    question: str | None = Field(None, min_length=3, max_length=500)
    variable_code: str | None = None
    region_code: str | None = None
    bbox: BBox | None = None
    start_year: int | None = Field(None, ge=1940, le=2100)
    end_year: int | None = Field(None, ge=1940, le=2100)
    compare_region_code: str | None = None
    run_relationship_analysis: bool = False

    @model_validator(mode="after")
    def _question_or_choice(self):
        structured = self.variable_code is not None
        if not structured and not self.question:
            raise ValueError("Send a question, or a variable_code with a region_code or bbox.")
        if structured and (self.region_code is None) == (self.bbox is None):
            raise ValueError("A structured request needs exactly one of region_code or bbox.")
        return self


class CreateInvestigationResponse(BaseModel):
    investigation_id: uuid.UUID


class DiscoverRequest(BaseModel):
    pass


class DiscoverResponse(BaseModel):
    investigation_id: uuid.UUID


class WatchCreateRequest(BaseModel):
    region_code: str
    variable_code: str
    frequency_days: int = Field(30, ge=1, le=365)


class WatchOut(BaseModel):
    id: uuid.UUID
    region_code: str
    variable_code: str
    frequency_days: int
    is_active: bool
    created_at: datetime
    last_checked_at: datetime | None
    next_check_at: datetime
    last_investigation_id: uuid.UUID | None
    last_finding_id: uuid.UUID | None
    last_trend_per_year: float | None
    last_significance: str | None
    prev_trend_per_year: float | None = None
    prev_significance: str | None = None
    last_check_note: str | None

    model_config = {"from_attributes": True}


class WatchCheckNowResponse(BaseModel):
    investigation_id: uuid.UUID


class InvestigationStepOut(BaseModel):
    seq: int
    agent: str
    status: str
    message: str
    detail: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestigationOut(BaseModel):
    id: uuid.UUID
    mode: str
    question: str | None
    status: str
    plan: dict | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    steps: list[InvestigationStepOut] = []

    model_config = {"from_attributes": True}


class FindingSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    variable_code: str
    variable_name: str
    region_code: str
    region_name: str
    # [min_lat, max_lat, min_lon, max_lon]; lets maps place drawn-box regions,
    # which aren't in the preset list
    region_bbox: list[float] | None = None
    period_start: date
    period_end: date
    trend_per_year: float
    trend_units: str
    total_change: float
    percent_change: float | None
    # |total_change| / std. dev.; None for findings saved before it existed
    # and not yet backfilled.
    effect_size: float | None = None
    p_value: float
    significance_classification: str
    # none | watch | concerning | serious — see app/knowledge/insight.py
    concern: str = "none"
    discovery_score: dict | None
    created_at: datetime


class FindingDetailOut(FindingSummaryOut):
    what: str
    where: str
    statistical_method: str
    confidence_interval: dict | None
    importance_note: str
    data_quality: dict
    spatial_summary: dict | None
    related_variables: list | None
    robustness: dict | None
    skeptic_review: dict | None
    interpretation: str
    limitations: str
    narrative_source: str
    visualizations: dict
    provenance: dict | None
    insight: dict | None = None
    # Version 1 findings (annual means, uncorrected tests) leave these empty.
    analysis_version: int = 1
    temporal_basis: str = "annual"
    trend_details: dict | None = None
    detectability: dict | None = None
    seasonal_trends: list | None = None


class DatasetOut(BaseModel):
    code: str
    name: str
    provider: str
    description: str
    status: str
    requires_credentials: bool
    version: str | None
    variables: list[dict]


class VariableOut(BaseModel):
    code: str
    name: str
    units: str
    description: str
    dataset_code: str
    # learning metadata (app/nasa/variables.yaml)
    dataset_name: str = ""
    available: bool = True  # False: listed, but its data isn't connected/built yet
    definition: str = ""
    why_it_matters: str = ""
    scale: str = "ratio"
    domain: str = "land"
    place_tags: list[str] = []
    source_label: str = ""
    coverage_start: int | None = None
    level_hpa: int | None = None
    known_breaks: list[dict] = []


class RegionOut(BaseModel):
    code: str
    name: str
    kind: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    centroid_lat: float
    centroid_lon: float
    place_tags: list[str] = []
    notes: str = ""
