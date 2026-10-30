"""Unified variable -> dataset lookup across every *active* registered
adapter, so agents don't need to hardcode which dataset owns a variable
(historically every agent imported app.nasa.power's VARIABLES_BY_CODE
directly and hardcoded the "NASA_POWER" dataset code — fine when there was
exactly one active source, wrong the moment a second one is wired up).

A variable owned by a still-"requires_credentials" adapter is deliberately
excluded from VARIABLES_BY_CODE here — querying it should route through the
"not connected yet" fallback messaging (see app/llm/planner.py), not appear
selectable as if it already worked.
"""

from app.nasa.base import VariableInfo
from app.nasa.registry import get_adapter, list_dataset_metadata


def _build_variables_by_code() -> dict[str, VariableInfo]:
    result: dict[str, VariableInfo] = {}
    for info in list_dataset_metadata():
        if info.status != "active":
            continue
        for v in info.variables:
            result[v.code] = v
    return result


VARIABLES_BY_CODE: dict[str, VariableInfo] = _build_variables_by_code()


def related_candidates(variable_code: str, limit: int = 5) -> list[str]:
    """Other active variables worth correlating with this one: ranked by
    shared place tags, preferring a different domain (temperature vs soil
    moisture is a more informative pairing than temperature vs maximum
    temperature). Near-duplicates (same domain and units) are skipped, and so
    are slow sources (whole-file downloads), which would add minutes to every
    investigation that asks about relationships."""
    seed = VARIABLES_BY_CODE.get(variable_code)
    if seed is None:
        return []
    scored = []
    for code, v in VARIABLES_BY_CODE.items():
        if code == variable_code or (v.domain == seed.domain and v.units == seed.units):
            continue
        if get_adapter(dataset_code_for_variable(code)).slow:
            continue
        shared = len(set(v.place_tags) & set(seed.place_tags))
        scored.append((shared + (0.5 if v.domain != seed.domain else 0.0), code))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [code for _, code in scored[:limit]]


def earliest_year(variable_code: str, default: int = 1981) -> int:
    v = VARIABLES_BY_CODE.get(variable_code)
    return v.coverage_start if v and v.coverage_start else default


def dataset_code_for_variable(variable_code: str) -> str:
    for info in list_dataset_metadata():
        if info.status != "active":
            continue
        if any(v.code == variable_code for v in info.variables):
            return info.code
    raise KeyError(f"No active dataset provides variable: {variable_code}")
