import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class CreateInvestigationRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


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
