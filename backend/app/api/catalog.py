from fastapi import APIRouter

from app.nasa.catalog_yaml import place_tags
from app.nasa.regions import REGIONS
from app.nasa.registry import list_dataset_metadata
from app.schemas.api import DatasetOut, RegionOut, VariableOut

router = APIRouter(tags=["catalog"])


@router.get("/datasets", response_model=list[DatasetOut])
async def get_datasets():
    return [
        DatasetOut(
            code=d.code, name=d.name, provider=d.provider, description=d.description,
            status=d.status, requires_credentials=d.requires_credentials, version=d.version,
            variables=[{"code": v.code, "name": v.name, "units": v.units} for v in d.variables],
        )
        for d in list_dataset_metadata()
    ]


@router.get("/variables", response_model=list[VariableOut])
async def get_variables():
    """Every variable with its plain-language definition, whether it can be
    analyzed right now (`available`), and the place types it suits."""
    out = []
    for d in list_dataset_metadata():
        for v in d.variables:
            out.append(VariableOut(
                code=v.code, name=v.name, units=v.units, description=v.description, dataset_code=d.code,
                dataset_name=d.name, available=d.status == "active",
                definition=v.definition, why_it_matters=v.why_it_matters, scale=v.scale, domain=v.domain,
                place_tags=list(v.place_tags), source_label=v.source_label, coverage_start=v.coverage_start,
                level_hpa=v.level_hpa, known_breaks=[{"year": y, "note": n} for y, n in v.known_breaks],
            ))
    return out


@router.get("/regions", response_model=list[RegionOut])
async def get_regions():
    return [
        RegionOut(
            code=r.code, name=r.name, kind=r.kind, min_lat=r.min_lat, max_lat=r.max_lat,
            min_lon=r.min_lon, max_lon=r.max_lon, centroid_lat=r.centroid_lat, centroid_lon=r.centroid_lon,
            place_tags=list(r.place_tags), notes=r.notes,
        )
        for r in REGIONS
    ]


@router.get("/place-types", response_model=list[str])
async def get_place_types():
    return place_tags()
