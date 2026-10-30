"""Loads app/nasa/variables.yaml: learning metadata for every variable, and
product definitions for the gridded cube variables.

Adapters keep defining the variables they serve; `overlay()` adds the plain
definitions, scale, place tags and known breaks on top, so there is one place
to edit what students read.
"""

import dataclasses
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.nasa.base import VariableInfo

CATALOG_PATH = Path(__file__).with_name("variables.yaml")

_LEARNING_FIELDS = (
    "definition", "why_it_matters", "scale", "domain", "place_tags",
    "source_label", "coverage_start", "level_hpa", "known_breaks", "family",
)


@dataclass(frozen=True)
class DatasetSpec:
    code: str
    name: str
    provider: str
    description: str
    version: str
    retry_floor_year: int


@dataclass(frozen=True)
class CubeVariableSpec:
    """How to build and read one cube variable."""

    info: VariableInfo
    dataset: str
    short_name: str
    version: str
    source_vars: tuple[str, ...]  # summed when more than one (e.g. surface + subsurface runoff)
    level_hpa: int | None = None
    scale: float = 1.0
    offset: float = 0.0
    min_valid_days: int | None = None  # daily products: days needed for a valid month
    grid_res: float = 1.0  # cube resolution, degrees
    # Fallback source grid for products whose OPeNDAP view has no lat/lon
    # arrays (some HDF-EOS grids): {lat0, dlat, nlat, lon0, dlon, nlon}.
    source_grid: dict = field(default_factory=dict)


@lru_cache
def _raw() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def place_tags() -> list[str]:
    return list(_raw()["place_tags"])


def _learning(entry: dict) -> dict:
    out = {k: entry[k] for k in _LEARNING_FIELDS if k in entry}
    if "place_tags" in out:
        out["place_tags"] = tuple(out["place_tags"])
    if "known_breaks" in out:
        out["known_breaks"] = tuple((int(y), str(note)) for y, note in out["known_breaks"])
    return out


def overlay(v: VariableInfo) -> VariableInfo:
    entry = _raw()["variables"].get(v.code)
    return dataclasses.replace(v, **_learning(entry)) if entry else v


@lru_cache
def dataset_specs() -> dict[str, DatasetSpec]:
    return {
        code: DatasetSpec(
            code=code, name=d["name"], provider=d["provider"], description=d["description"].strip(),
            version=str(d["version"]), retry_floor_year=int(d["retry_floor_year"]),
        )
        for code, d in _raw()["datasets"].items()
    }


@lru_cache
def cube_variable_specs() -> dict[str, CubeVariableSpec]:
    specs = {}
    for code, e in _raw()["variables"].items():
        product = e.get("product")
        if not product:
            continue
        src = product["variable"]
        lo, hi = e.get("valid_range", [None, None])
        info = VariableInfo(
            code=code, name=e["name"], units=e["units"], description=e.get("definition", ""),
            valid_min=lo, valid_max=hi, **_learning(e),
        )
        convert = e.get("convert", {})
        specs[code] = CubeVariableSpec(
            info=info,
            dataset=e["dataset"],
            short_name=product["short_name"],
            version=str(product["version"]),
            source_vars=tuple(src) if isinstance(src, list) else (src,),
            level_hpa=product.get("level_hpa"),
            scale=float(convert.get("scale", 1.0)),
            offset=float(convert.get("offset", 0.0)),
            min_valid_days=e.get("min_valid_days"),
            grid_res=float(e.get("grid_res", 1.0)),
            source_grid=dict(e.get("source_grid", {})),
        )
    return specs
