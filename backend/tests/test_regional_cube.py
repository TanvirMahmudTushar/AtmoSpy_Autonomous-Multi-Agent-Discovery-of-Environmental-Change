"""Regional area means, map coarsening, box-average regridding and the cube
adapter — all on synthetic data with known answers, no network."""

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from app.analysis.spatial import coarsen_cells, regional_mean
from app.core.config import get_settings
from app.nasa import cube
from app.nasa.base import GridCell
from app.nasa.catalog_yaml import cube_variable_specs, dataset_specs


def _months(n, start="2000-01-01"):
    return [d.date() for d in pd.date_range(start, periods=n, freq="MS")]


def test_regional_mean_weights_by_area():
    # Equator cell weight 1, 60N cell weight cos(60) = 0.5.
    dates = _months(3)
    cells = [GridCell(0.0, 0.0, dates, [10.0] * 3), GridCell(60.0, 0.0, dates, [40.0] * 3)]
    mean = regional_mean(cells)
    assert mean.values == pytest.approx([(10 * 1 + 40 * 0.5) / 1.5] * 3)
    assert mean.mean_valid_area_fraction == pytest.approx(1.0)


def test_regional_mean_drops_months_with_too_little_area():
    dates = _months(2)
    cells = [
        GridCell(0.0, 0.0, dates, [1.0, 1.0]),
        GridCell(0.0, 1.0, dates[:1], [3.0]),  # missing in month 2
        GridCell(0.0, 2.0, dates[:1], [5.0]),  # missing in month 2
    ]
    mean = regional_mean(cells, min_valid_area=0.7)
    assert mean.dates == [dates[0]]  # month 2 has only 1/3 of the area
    assert mean.missing_dates == [dates[1]]
    assert mean.values == pytest.approx([3.0])


def test_coarsen_cells_caps_count_and_preserves_the_mean():
    dates = _months(2)
    cells = [GridCell(float(la), float(lo), dates, [float(la), float(la)]) for la in range(20) for lo in range(20)]
    out = coarsen_cells(cells, max_cells=100)
    assert len(out) <= 100
    full = regional_mean(cells).values[0]
    coarse = regional_mean(out).values[0]
    assert coarse == pytest.approx(full, rel=0.01)


def test_bin_average_onto_one_degree():
    # 0.5-degree source with a value equal to its latitude: each 1-degree
    # cell averages two latitude rows (weighted by cos lat).
    lat = np.arange(-89.75, 90, 0.5)
    lon = np.arange(-179.75, 180, 0.5)
    field = np.repeat(lat[:, None], len(lon), axis=1)
    out = cube.bin_average(field, lat, lon, 1.0)
    lat_t, lon_t = cube.target_axes(1.0)
    assert out.shape == (180, 360)
    i = int(np.argmin(np.abs(lat_t - 10.5)))
    w = np.cos(np.radians([10.25, 10.75]))
    assert out[i, 0] == pytest.approx((10.25 * w[0] + 10.75 * w[1]) / w.sum())


def test_bin_average_wraps_0_360_longitudes_and_ignores_nan():
    lat = np.array([0.25, 0.75])
    lon = np.array([359.25, 359.75])  # = -0.75, -0.25
    field = np.array([[1.0, np.nan], [3.0, 5.0]])
    out = cube.bin_average(field, lat, lon, 1.0)
    lat_t, lon_t = cube.target_axes(1.0)
    i, j = int(np.argmin(np.abs(lat_t - 0.5))), int(np.argmin(np.abs(lon_t + 0.5)))
    assert out[i, j] == pytest.approx(3.0, rel=1e-3)  # mean of 1, 3, 5 (near-equal weights)
    assert np.isnan(out[0, 0])


def test_bin_average_accepts_2d_coordinate_grids():
    # AIRS3STM stores 180x360 Latitude/Longitude arrays (north to south);
    # the result must match the 1-D-axis path without building a huge meshgrid.
    lat = np.arange(89.5, -90, -1.0)
    lon = np.arange(-179.5, 180, 1.0)
    field = np.add.outer(lat, lon / 1000)
    lat2, lon2 = np.meshgrid(lat, lon, indexing="ij")
    out = cube.bin_average(field, lat2, lon2, 1.0)
    np.testing.assert_allclose(out, cube.bin_average(field, lat, lon, 1.0))
    assert out[0, 0] == pytest.approx(-89.5 - 0.1795)  # flipped to south-to-north


@pytest.fixture
def tiny_cube(tmp_path, monkeypatch):
    """A 2-degree-wide cube around (10N, 20E) with a known trend, written
    exactly the way scripts/build_cube.py writes real ones."""
    times = pd.date_range("2000-01-01", periods=12 * 15, freq="MS")
    lat = np.array([9.5, 10.5])
    lon = np.array([19.5, 20.5])
    t = np.arange(len(times)) / 12
    data = (0.1 * t)[:, None, None] + np.zeros((len(times), 2, 2))
    data[:, 0, 0] = np.nan  # an all-missing (e.g. ocean) cell
    ds = xr.Dataset({"M2_T2M": (("time", "lat", "lon"), data.astype("float32"))},
                    coords={"time": times, "lat": lat, "lon": lon})
    ds.to_zarr(tmp_path / "M2_T2M.zarr", consolidated=True)
    (tmp_path / "manifest.json").write_text(json.dumps({"M2_T2M": {"first_full_year": 2000, "source": "test"}}))

    monkeypatch.setenv("CUBE_BASE_URL", str(tmp_path))
    get_settings.cache_clear()
    cube.load_manifest.cache_clear()
    cube.open_cube.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
    cube.load_manifest.cache_clear()
    cube.open_cube.cache_clear()


@pytest.mark.asyncio
async def test_cube_adapter_reads_only_the_box(tiny_cube):
    spec = cube_variable_specs()["M2_T2M"]
    adapter = cube.CubeAdapter(dataset_specs()["MERRA2"], [spec], cube.load_manifest())
    grid = await adapter.query_grid_series("M2_T2M", 9.0, 11.0, 19.0, 21.0, date(2005, 1, 1), date(2009, 12, 31))

    assert len(grid.cells) == 3  # the all-NaN cell is skipped
    assert all(len(c.dates) == 60 for c in grid.cells)
    assert grid.cells[0].dates[0] == date(2005, 1, 1)
    assert adapter.get_metadata().status == "active"

    # a box smaller than one cell falls back to the cell containing its centre
    point = await adapter.query_grid_series("M2_T2M", 10.6, 10.7, 20.6, 20.7, date(2000, 1, 1), date(2000, 12, 31))
    assert [(c.lat, c.lon) for c in point.cells] == [(10.5, 20.5)]


@pytest.mark.asyncio
async def test_cube_adapter_rejects_continent_plus_boxes(tiny_cube):
    adapter = cube.CubeAdapter(dataset_specs()["MERRA2"], [cube_variable_specs()["M2_T2M"]], cube.load_manifest())
    with pytest.raises(Exception, match="degrees"):
        await adapter.query_grid_series("M2_T2M", -50, 40, 0, 10, date(2000, 1, 1), date(2001, 1, 1))


@pytest.mark.asyncio
async def test_packed_zip_cube_reads_the_same_values(tiny_cube, monkeypatch):
    # scripts/pack_cubes.py zips each store for single-file hosting (e.g. a
    # GitHub release); the app must read the zip exactly like the directory.
    from scripts.pack_cubes import pack

    spec = cube_variable_specs()["M2_T2M"]
    args = ("M2_T2M", 9.0, 11.0, 19.0, 21.0, date(2005, 1, 1), date(2009, 12, 31))
    direct = await cube.CubeAdapter(dataset_specs()["MERRA2"], [spec], cube.load_manifest()).query_grid_series(*args)

    out = tiny_cube / "release"
    pack(tiny_cube, out)
    assert json.loads((out / "manifest.json").read_text())["M2_T2M"]["store"] == "M2_T2M.zarr.zip"
    get_settings.cache_clear()
    cube.load_manifest.cache_clear()
    cube.open_cube.cache_clear()
    monkeypatch.setenv("CUBE_BASE_URL", str(out))
    zipped = await cube.CubeAdapter(dataset_specs()["MERRA2"], [spec], cube.load_manifest()).query_grid_series(*args)

    assert [(c.lat, c.lon, c.values) for c in zipped.cells] == [(c.lat, c.lon, c.values) for c in direct.cells]
