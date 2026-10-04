"""Adapter interface every NASA data source must implement.

Only `PowerAdapter` is functional today (no auth required). Additional
sources (SMAP, GRACE-FO, MODIS via Earthdata/GES DISC) are registered as
stubs with status=REQUIRES_CREDENTIALS so `/api/datasets` can list them
honestly instead of faking data for them.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class VariableInfo:
    code: str
    name: str
    units: str
    description: str
    valid_min: float | None = None
    valid_max: float | None = None


@dataclass(frozen=True)
class DatasetInfo:
    code: str
    name: str
    provider: str
    description: str
    base_url: str
    status: str  # active | planned | requires_credentials
    requires_credentials: bool
    version: str | None
    variables: list[VariableInfo] = field(default_factory=list)
    # Real observation cadence of the source — assess_quality() uses this to
    # judge completeness/coverage correctly. A monthly source (GRACE-FO) that
    # returns ~1 observation/month must not be judged against the same
    # observed/requested-days ratio a daily source (POWER) is; without this,
    # every monthly investigation would fail quality with ~3% "completeness"
    # even on a perfectly complete series.
    temporal_resolution_days: float = 1.0
    # The floor year the orchestrator's retry-widen branch should use for
    # THIS dataset specifically (app/agents/orchestrator.py) — not the
    # literal mission-start date, a few years after it, since a dataset's
    # very first year(s) tend to be sparser. A single global floor (POWER's
    # 1985) is wrong for GRACE-FO (2002+) or SMAP (2015+): widening a
    # SMAP-only investigation's request back to 1985 doesn't add real data
    # (SMAP didn't exist yet), it just dilutes completeness against a mostly-
    # empty 40-year window and turns a marginal-but-fixable case into a hard
    # failure — confirmed by actually hitting this for a real SMAP question
    # before this field existed.
    retry_floor_year: int = 1985


@dataclass(frozen=True)
class PointSeries:
    variable: str
    units: str
    lat: float
    lon: float
    dates: list[date]
    values: list[float]
    missing_dates: list[date]
    source_url: str
    retrieved_at: date


@dataclass(frozen=True)
class GridCell:
    lat: float
    lon: float
    dates: list[date]
    values: list[float]


@dataclass(frozen=True)
class GridSeries:
    variable: str
    units: str
    cells: list[GridCell]
    source_url: str
    retrieved_at: date


class NASAAdapterError(RuntimeError):
    """Raised when a NASA source cannot fulfil a request (network, no data, etc.)."""


class NASADataAdapter(ABC):
    code: str

    @abstractmethod
    def get_metadata(self) -> DatasetInfo: ...

    @abstractmethod
    async def query_point_series(
        self,
        variable: str,
        lat: float,
        lon: float,
        start: date,
        end: date,
        temporal: str = "daily",
    ) -> PointSeries: ...

    @abstractmethod
    async def query_grid_series(
        self,
        variable: str,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        start: date,
        end: date,
    ) -> GridSeries: ...


class UnavailableAdapter(NASADataAdapter):
    """Placeholder for a dataset that is architecturally supported but not
    yet wired up because it requires Earthdata credentials or further
    integration work. Never returns fabricated data — always raises.
    """

    def __init__(self, info: DatasetInfo):
        self.code = info.code
        self._info = info

    def get_metadata(self) -> DatasetInfo:
        return self._info

    async def query_point_series(self, *args, **kwargs) -> PointSeries:
        raise NASAAdapterError(
            f"{self.code} is not yet connected (status={self._info.status}). "
            "Set NASA_EARTHDATA_TOKEN to enable it."
        )

    async def query_grid_series(self, *args, **kwargs) -> GridSeries:
        raise NASAAdapterError(
            f"{self.code} is not yet connected (status={self._info.status})."
        )
