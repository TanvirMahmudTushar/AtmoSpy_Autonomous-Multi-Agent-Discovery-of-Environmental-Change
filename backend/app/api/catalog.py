from fastapi import APIRouter

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
    out = []
    for d in list_dataset_metadata():
        for v in d.variables:
            out.append(VariableOut(code=v.code, name=v.name, units=v.units, description=v.description, dataset_code=d.code))
    return out


@router.get("/regions", response_model=list[RegionOut])
async def get_regions():
    return [
        RegionOut(
            code=r.code, name=r.name, kind=r.kind, min_lat=r.min_lat, max_lat=r.max_lat,
            min_lon=r.min_lon, max_lon=r.max_lon, centroid_lat=r.centroid_lat, centroid_lon=r.centroid_lon,
        )
        for r in REGIONS
    ]
