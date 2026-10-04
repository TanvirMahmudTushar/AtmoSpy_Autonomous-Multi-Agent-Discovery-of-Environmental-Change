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
from app.nasa.registry import list_dataset_metadata


def _build_variables_by_code() -> dict[str, VariableInfo]:
    result: dict[str, VariableInfo] = {}
    for info in list_dataset_metadata():
        if info.status != "active":
            continue
        for v in info.variables:
            result[v.code] = v
    return result


VARIABLES_BY_CODE: dict[str, VariableInfo] = _build_variables_by_code()


def dataset_code_for_variable(variable_code: str) -> str:
    for info in list_dataset_metadata():
        if info.status != "active":
            continue
        if any(v.code == variable_code for v in info.variables):
            return info.code
    raise KeyError(f"No active dataset provides variable: {variable_code}")
