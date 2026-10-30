"""Offline tests for scripts/build_cube.py: DMR parsing, field extraction for
the three on-disk layouts we meet (MERRA-2 time/lat/lon, IMERG grouped and
lon-major, pressure levels), fill masking, and monthly assembly including
the daily-to-monthly valid-day rule. Responses are synthetic netCDF-4 files
shaped like real DAP4 output, so no Earthdata access is needed."""

import io
import json
from datetime import date

import h5netcdf
import numpy as np
import pytest
import xarray as xr

from app.nasa.catalog_yaml import cube_variable_specs
from scripts import build_cube as bc

MERRA_DMR = """<?xml version="1.0" encoding="ISO-8859-1"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="MERRA2_400.tavgM_2d_slv_Nx.202509.nc4">
  <Dimension name="time" size="1"/><Dimension name="lat" size="361"/><Dimension name="lon" size="576"/>
  <Float64 name="lat"><Dim name="/lat"/></Float64>
  <Float64 name="lon"><Dim name="/lon"/></Float64>
  <Float32 name="T2M"><Dim name="/time"/><Dim name="/lat"/><Dim name="/lon"/></Float32>
  <Float32 name="TQV"><Dim name="/time"/><Dim name="/lat"/><Dim name="/lon"/></Float32>
</Dataset>"""

IMERG_DMR = """<?xml version="1.0" encoding="ISO-8859-1"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="3B-MO.MS.MRG.3IMERG.HDF5">
  <Group name="Grid">
    <Dimension name="time" size="1"/><Dimension name="lon" size="3600"/><Dimension name="lat" size="1800"/>
    <Float32 name="lat"><Dim name="/Grid/lat"/></Float32>
    <Float32 name="lon"><Dim name="/Grid/lon"/></Float32>
    <Float32 name="precipitation"><Dim name="/Grid/time"/><Dim name="/Grid/lon"/><Dim name="/Grid/lat"/></Float32>
  </Group>
</Dataset>"""


def test_parse_dmr_flat_and_grouped():
    m = bc.parse_dmr(MERRA_DMR, ("T2M",))
    assert m.var_paths == ["/T2M"] and m.lat_path == "/lat" and m.lon_path == "/lon"
    g = bc.parse_dmr(IMERG_DMR, ("precipitation",))
    assert g.var_paths == ["/Grid/precipitation"]
    assert g.lat_path == "/Grid/lat" and g.var_dims == ["/Grid/time", "/Grid/lon", "/Grid/lat"]
    with pytest.raises(SystemExit, match="not in this product"):
        bc.parse_dmr(MERRA_DMR, ("NOPE",))


def _nc(build) -> bytes:
    buf = io.BytesIO()
    with h5netcdf.File(buf, "w") as f:
        build(f)
    return buf.getvalue()


def test_extract_field_masks_fill_and_reduces_time():
    def build(f):
        f.dimensions = {"time": 1, "lat": 3, "lon": 4}
        f.create_variable("lat", ("lat",), "f8", data=[-1.0, 0.0, 1.0])
        f.create_variable("lon", ("lon",), "f8", data=[0.0, 1.0, 2.0, 3.0])
        v = f.create_variable("T2M", ("time", "lat", "lon"), "f4", data=np.arange(12, dtype="f4").reshape(1, 3, 4))
        v.attrs["_FillValue"] = np.float32(5.0)
    layout = bc.parse_dmr(MERRA_DMR, ("T2M",))
    field, lat, lon = bc.extract_field(_nc(build), layout, cube_variable_specs()["M2_T2M"], None)
    assert field.shape == (3, 4) and np.isnan(field[1, 1]) and field[2, 3] == 11
    assert list(lat) == [-1.0, 0.0, 1.0]


def test_extract_field_transposes_lon_major_groups():
    def build(f):
        g = f.create_group("Grid")
        g.dimensions = {"time": 1, "lon": 2, "lat": 3}
        g.create_variable("lat", ("lat",), "f4", data=[10.0, 11.0, 12.0])
        g.create_variable("lon", ("lon",), "f4", data=[50.0, 51.0])
        data = np.array([[[1, 2, 3], [4, 5, 6]]], dtype="f4")  # (time, lon, lat)
        g.create_variable("precipitation", ("time", "lon", "lat"), "f4", data=data)
    layout = bc.parse_dmr(IMERG_DMR, ("precipitation",))
    field, lat, lon = bc.extract_field(_nc(build), layout, cube_variable_specs()["GPM_PRECIP"], None)
    assert field.shape == (3, 2)  # (lat, lon)
    assert field[0, 1] == 4 and field[2, 0] == 3


def test_extract_field_sums_multipart_variables():
    def build(f):
        f.dimensions = {"time": 1, "lat": 1, "lon": 2}
        f.create_variable("lat", ("lat",), "f8", data=[0.0])
        f.create_variable("lon", ("lon",), "f8", data=[0.0, 1.0])
        f.create_variable("Qs_acc", ("time", "lat", "lon"), "f4", data=np.array([[[1.0, 2.0]]], dtype="f4"))
        f.create_variable("Qsb_acc", ("time", "lat", "lon"), "f4", data=np.array([[[0.5, 0.25]]], dtype="f4"))
    dmr = MERRA_DMR.replace('name="T2M"', 'name="Qs_acc"').replace('name="TQV"', 'name="Qsb_acc"')
    spec = cube_variable_specs()["GLDAS_RUNOFF"]
    field, _, _ = bc.extract_field(_nc(build), bc.parse_dmr(dmr, spec.source_vars), spec, None)
    assert field.tolist() == [[1.5, 2.25]]


def test_level_constraint_selects_one_pressure_level():
    dmr = """<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#">
      <Dimension name="time" size="1"/><Dimension name="lev" size="42"/><Dimension name="lat" size="361"/><Dimension name="lon" size="576"/>
      <Float64 name="lev"><Dim name="/lev"/></Float64><Float64 name="lat"><Dim name="/lat"/></Float64><Float64 name="lon"><Dim name="/lon"/></Float64>
      <Float32 name="T"><Dim name="/time"/><Dim name="/lev"/><Dim name="/lat"/><Dim name="/lon"/></Float32></Dataset>"""
    layout = bc.parse_dmr(dmr, ("T",))
    ce = bc.constraint(layout, 6, bc.dmr_dim_sizes(dmr))
    assert ce.startswith("/T[0:1:0][6:1:6][0:1:360][0:1:575]")
    assert ce.endswith(";/lat;/lon")


def test_assemble_daily_to_monthly_with_valid_day_rule(tmp_path):
    spec = cube_variable_specs()["OMI_NO2"]  # min_valid_days = 5, 0.5-degree grid
    work = tmp_path / "_work" / spec.info.code
    work.mkdir(parents=True)
    shape = (360, 720)
    granules = []
    for day in range(1, 8):  # 7 January days: a cell seen on only 3 days must be dropped
        d = date(2010, 1, day)
        f = np.full(shape, 2e15, dtype="float32")
        if day > 3:
            f[0, 0] = np.nan
        np.save(work / f"{d:%Y%m%d}.npy", f)
        granules.append(bc.Granule(month=d.replace(day=1), day=d, url=""))
    coll = {"concept_id": "C-TEST", "doi": "10.0000/test", "title": "test"}
    entry = bc.assemble(spec, granules, True, coll, work, tmp_path, 2010, 2010)

    ds = xr.open_zarr(tmp_path / "OMI_NO2.zarr")
    assert ds["OMI_NO2"].shape == (1, 360, 720)
    assert float(ds["OMI_NO2"][0, 5, 5]) == pytest.approx(2.0)  # converted to 1e15 molecules/cm2
    assert np.isnan(float(ds["OMI_NO2"][0, 0, 0]))  # only 3 valid days
    assert int(ds["valid_days"][0, 0, 0]) == 3
    assert entry["doi"] == "10.0000/test" and entry["first_full_year"] is None
    assert json.loads((tmp_path / "manifest.json").read_text())["OMI_NO2"]["concept_id"] == "C-TEST"
