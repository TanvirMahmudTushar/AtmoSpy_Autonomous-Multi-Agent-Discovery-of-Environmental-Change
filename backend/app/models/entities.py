"""ORM models — one table per spec section 15 entity, plus a NASA response cache.

Kept in a single module deliberately: this schema is small enough (12 tables)
that splitting it across files would cost more in cross-import ceremony than
it buys in organization.
"""

import uuid
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPk


class User(Base, UUIDPk, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Dataset(Base, UUIDPk, TimestampMixin):
    __tablename__ = "datasets"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    base_url: Mapped[str] = mapped_column(String(512))
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    # active | planned | requires_credentials
    requires_credentials: Mapped[bool] = mapped_column(Boolean, default=False)

    variables: Mapped[list["Variable"]] = relationship(back_populates="dataset")


class Variable(Base, UUIDPk, TimestampMixin):
    __tablename__ = "variables"

    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"))
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    units: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    valid_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="variables")

    __table_args__ = (UniqueConstraint("dataset_id", "code", name="uq_dataset_variable"),)


class Region(Base, UUIDPk, TimestampMixin):
    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))  # country | basin | continent | custom
    min_lat: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    min_lon: Mapped[float] = mapped_column(Float)
    max_lon: Mapped[float] = mapped_column(Float)
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)
    geom = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)


class Investigation(Base, UUIDPk, TimestampMixin):
    __tablename__ = "investigations"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(32))  # nlp | discover
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | running | completed | failed | insufficient_data
    plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["InvestigationStep"]] = relationship(
        back_populates="investigation", order_by="InvestigationStep.seq"
    )


class InvestigationStep(Base, UUIDPk, TimestampMixin):
    __tablename__ = "investigation_steps"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE")
    )
    seq: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))  # running | done | error | skipped
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    investigation: Mapped[Investigation] = relationship(back_populates="steps")

    __table_args__ = (Index("ix_steps_investigation_seq", "investigation_id", "seq"),)


class Observation(Base, UUIDPk, TimestampMixin):
    """Aggregated (annual) time-series points that fed a given analysis.

    We deliberately store the aggregated series used for trend analysis
    (not raw daily values) to keep this table small while preserving full
    reproducibility of every chart and statistic.
    """

    __tablename__ = "observations"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE")
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"))
    variable_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("variables.id"))
    region_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    period: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    n_samples: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        Index("ix_observations_investigation", "investigation_id"),
    )


class AnalysisResult(Base, UUIDPk, TimestampMixin):
    __tablename__ = "analysis_results"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(32))
    # quality | trend | spatial | correlation | change_point | robustness
    variable_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("variables.id"), nullable=True)
    region_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(128))
    result: Mapped[dict] = mapped_column(JSONB)


class Finding(Base, UUIDPk, TimestampMixin):
    __tablename__ = "findings"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(512))
    variable_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("variables.id"))
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regions.id"))

    what: Mapped[str] = mapped_column(Text)
    where: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    trend_per_year: Mapped[float] = mapped_column(Float)
    trend_units: Mapped[str] = mapped_column(String(64))
    total_change: Mapped[float] = mapped_column(Float)
    percent_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    # |total_change| / std. dev. of the annual series — how big the change is
    # against the variable's own year-to-year swings (see analysis/significance.py).
    effect_size: Mapped[float | None] = mapped_column(Float, nullable=True)

    statistical_method: Mapped[str] = mapped_column(String(128))
    p_value: Mapped[float] = mapped_column(Float)
    confidence_interval: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    significance_classification: Mapped[str] = mapped_column(String(32))
    # not_significant | statistically_significant
    importance_note: Mapped[str] = mapped_column(Text)

    data_quality: Mapped[dict] = mapped_column(JSONB)
    spatial_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    related_variables: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    robustness: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    skeptic_review: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # a deliberately adversarial pass — points raised against over-trusting this finding

    interpretation: Mapped[str] = mapped_column(Text)
    limitations: Mapped[str] = mapped_column(Text)
    narrative_source: Mapped[str] = mapped_column(String(32))  # llm | template

    discovery_score: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # explicit, displayed ranking criteria — never an opaque single number

    __table_args__ = (Index("ix_findings_variable_region", "variable_id", "region_id"),)


class Visualization(Base, UUIDPk, TimestampMixin):
    __tablename__ = "visualizations"

    finding_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=True)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32))  # timeseries | spatial_map | scatter
    data: Mapped[dict] = mapped_column(JSONB)


class Report(Base, UUIDPk, TimestampMixin):
    __tablename__ = "reports"

    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"))
    content: Mapped[dict] = mapped_column(JSONB)
    generated_by: Mapped[str] = mapped_column(String(32))  # llm | template


class Provenance(Base, UUIDPk, TimestampMixin):
    __tablename__ = "provenance"

    finding_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=True)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"))
    variable_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("variables.id"), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255))
    dataset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processing_method: Mapped[str] = mapped_column(Text)
    statistical_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1024))


class NasaQueryCache(Base, UUIDPk, TimestampMixin):
    __tablename__ = "nasa_query_cache"

    cache_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    dataset_code: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict] = mapped_column(JSONB)
    response: Mapped[dict] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Watch(Base, UUIDPk, TimestampMixin):
    """A user's standing subscription to a (region, variable) pair — the
    in-process scheduler (app/services/scheduler.py) periodically re-runs the
    same pipeline /investigate uses and snapshots whether the result changed
    since last time. region_code/variable_code are plain codes (matching
    InvestigationPlan/DISCOVERY_CANDIDATES), not FKs, since they're always
    resolved through REGIONS_BY_CODE/VARIABLES_BY_CODE, the same as every
    other pipeline entry point."""

    __tablename__ = "watches"
    __table_args__ = (
        # The scheduler's every-tick query is exactly this predicate.
        Index("ix_watches_due", "is_active", "next_check_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    region_code: Mapped[str] = mapped_column(String(64))
    variable_code: Mapped[str] = mapped_column(String(64))
    frequency_days: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigations.id", ondelete="SET NULL"), nullable=True
    )
    last_finding_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    # Snapshot of the previous check's own results — compared against the
    # newest check to decide whether anything meaningfully changed, without
    # re-deriving it from history each time.
    last_trend_per_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_significance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # The check before last_* — kept so the UI can draw "previous vs latest".
    prev_trend_per_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    prev_significance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_check_note: Mapped[str | None] = mapped_column(Text, nullable=True)
