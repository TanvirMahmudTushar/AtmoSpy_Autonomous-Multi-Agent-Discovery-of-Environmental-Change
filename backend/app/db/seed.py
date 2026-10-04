"""Seeds datasets, variables, and the region gazetteer. Idempotent — safe to
re-run (upserts by unique code).
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import Dataset, Region, Variable
from app.nasa.regions import REGIONS
from app.nasa.registry import list_dataset_metadata


async def seed_datasets_and_variables(session: AsyncSession) -> dict[str, dict[str, object]]:
    code_to_ids: dict[str, dict[str, object]] = {}
    for ds_info in list_dataset_metadata():
        existing = (
            await session.execute(select(Dataset).where(Dataset.code == ds_info.code))
        ).scalar_one_or_none()
        if existing is None:
            existing = Dataset(
                code=ds_info.code,
                name=ds_info.name,
                provider=ds_info.provider,
                description=ds_info.description,
                base_url=ds_info.base_url,
                version=ds_info.version,
                status=ds_info.status,
                requires_credentials=ds_info.requires_credentials,
            )
            session.add(existing)
            await session.flush()
        else:
            existing.name = ds_info.name
            existing.description = ds_info.description
            existing.status = ds_info.status
            existing.version = ds_info.version
            existing.requires_credentials = ds_info.requires_credentials

        var_ids: dict[str, object] = {}
        for var_info in ds_info.variables:
            existing_var = (
                await session.execute(
                    select(Variable).where(
                        Variable.dataset_id == existing.id, Variable.code == var_info.code
                    )
                )
            ).scalar_one_or_none()
            if existing_var is None:
                existing_var = Variable(
                    dataset_id=existing.id,
                    code=var_info.code,
                    name=var_info.name,
                    units=var_info.units,
                    description=var_info.description,
                    valid_min=var_info.valid_min,
                    valid_max=var_info.valid_max,
                )
                session.add(existing_var)
                await session.flush()
            var_ids[var_info.code] = existing_var.id

        code_to_ids[ds_info.code] = {"dataset_id": existing.id, "variables": var_ids}
    return code_to_ids


async def seed_regions(session: AsyncSession) -> None:
    for r in REGIONS:
        existing = (
            await session.execute(select(Region).where(Region.code == r.code))
        ).scalar_one_or_none()
        wkt = (
            f"POLYGON(({r.min_lon} {r.min_lat}, {r.max_lon} {r.min_lat}, "
            f"{r.max_lon} {r.max_lat}, {r.min_lon} {r.max_lat}, {r.min_lon} {r.min_lat}))"
        )
        if existing is None:
            session.add(
                Region(
                    code=r.code,
                    name=r.name,
                    kind=r.kind,
                    min_lat=r.min_lat,
                    max_lat=r.max_lat,
                    min_lon=r.min_lon,
                    max_lon=r.max_lon,
                    centroid_lat=r.centroid_lat,
                    centroid_lon=r.centroid_lon,
                    geom=f"SRID=4326;{wkt}",
                )
            )
        else:
            existing.name = r.name
            existing.min_lat, existing.max_lat = r.min_lat, r.max_lat
            existing.min_lon, existing.max_lon = r.min_lon, r.max_lon
            existing.centroid_lat, existing.centroid_lon = r.centroid_lat, r.centroid_lon


async def run_seed() -> None:
    async with AsyncSessionLocal() as session:
        await seed_datasets_and_variables(session)
        await seed_regions(session)
        await session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(run_seed())
