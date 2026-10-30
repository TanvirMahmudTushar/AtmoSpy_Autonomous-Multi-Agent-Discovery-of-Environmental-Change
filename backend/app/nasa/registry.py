"""Registry of all NASA data adapters — active and planned.

`/api/datasets` reflects this list honestly: only NASA_POWER is `active`
today. The others are real, named, documented extension points (not fake
rows) that raise a clear "not yet connected" error if ever called, so the
UI can show what a fuller build would add without pretending it's there.
"""

import dataclasses

from app.core.config import get_settings
from app.nasa.catalog_yaml import cube_variable_specs, dataset_specs, overlay
from app.nasa.cube import CubeAdapter, load_manifest
from app.nasa.base import DatasetInfo, NASADataAdapter, UnavailableAdapter, VariableInfo
from app.nasa.grace import GRACE_FO_DATASET_INFO, GraceAdapter
from app.nasa.power import PowerAdapter
from app.nasa.smap import SMAP_DATASET_INFO, SmapAdapter

_PLANNED: list[DatasetInfo] = [
    DatasetInfo(
        code="MODIS_NDVI",
        name="MODIS Vegetation Indices (MOD13)",
        provider="NASA LP DAAC",
        description=(
            "16-day composite NDVI/EVI vegetation index at 250m-1km resolution. Requires "
            "Earthdata Login and tiled HDF/NetCDF retrieval; not yet wired up."
        ),
        base_url="https://lpdaac.usgs.gov",
        status="requires_credentials",
        requires_credentials=True,
        version=None,
        variables=[VariableInfo("NDVI", "Normalized Difference Vegetation Index", "index (-1 to 1)", "Vegetation greenness index")],
    ),
]


def build_registry() -> dict[str, NASADataAdapter]:
    """GRACE_FO and SMAP_L3 are conditionally-active: a real adapter if
    NASA_EARTHDATA_TOKEN is configured, otherwise the same honest
    UnavailableAdapter stub every other unconnected dataset uses. Both use
    the same token (one Earthdata Login covers every DAAC once each is
    authorized on the account) — if NSIDC specifically isn't authorized,
    SMAP queries fail with a real NASAAdapterError at query time rather
    than at registration time, same as any other real API failure. Nothing
    else in the app needs to know which case it is — catalog.py only ever
    sees whatever this function actually returns."""
    settings = get_settings()
    registry: dict[str, NASADataAdapter] = {"NASA_POWER": PowerAdapter()}
    registry["GRACE_FO"] = GraceAdapter() if settings.NASA_EARTHDATA_TOKEN else UnavailableAdapter(GRACE_FO_DATASET_INFO)
    registry["SMAP_L3"] = SmapAdapter() if settings.NASA_EARTHDATA_TOKEN else UnavailableAdapter(SMAP_DATASET_INFO)
    for info in _PLANNED:
        registry[info.code] = UnavailableAdapter(info)
    registry.update(_cube_adapters())
    return registry


def _cube_adapters() -> dict[str, NASADataAdapter]:
    """One adapter per cube dataset (MERRA-2, GPM IMERG, ...). Active only
    for variables whose cube is actually built (listed in manifest.json);
    a dataset with none built yet is listed as planned, never faked."""
    manifest = load_manifest()
    by_dataset: dict[str, list] = {}
    for spec in cube_variable_specs().values():
        by_dataset.setdefault(spec.dataset, []).append(spec)

    adapters: dict[str, NASADataAdapter] = {}
    for code, dataset in dataset_specs().items():
        specs = by_dataset.get(code, [])
        built = [s for s in specs if s.info.code in manifest]
        if built:
            adapters[code] = CubeAdapter(dataset, built, manifest)
        else:
            adapters[code] = UnavailableAdapter(DatasetInfo(
                code=code, name=dataset.name, provider=dataset.provider,
                description=dataset.description + " Analysis-ready cubes for it have not been built yet.",
                base_url="https://disc.gsfc.nasa.gov", status="planned", requires_credentials=True,
                version=dataset.version, variables=[s.info for s in specs],
                temporal_resolution_days=30.44, retry_floor_year=dataset.retry_floor_year,
            ))
    return adapters


ADAPTER_REGISTRY = build_registry()


def get_adapter(code: str) -> NASADataAdapter:
    if code not in ADAPTER_REGISTRY:
        raise KeyError(f"Unknown dataset code: {code}")
    return ADAPTER_REGISTRY[code]


def list_dataset_metadata() -> list[DatasetInfo]:
    """Every dataset, with each variable's learning metadata (plain
    definition, scale, place tags, known breaks) overlaid from variables.yaml."""
    return [
        dataclasses.replace(info, variables=[overlay(v) for v in info.variables])
        for info in (adapter.get_metadata() for adapter in ADAPTER_REGISTRY.values())
    ]
