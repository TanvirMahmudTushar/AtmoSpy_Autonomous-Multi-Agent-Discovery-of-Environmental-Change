"""Cross-validation against NASA Giovanni.

Giovanni's "Time Series, Area-Averaged" is NASA's own reference tool for
regional means at native resolution. For each case in
fixtures/giovanni/cases.json this compares Giovanni's CSV with the area mean
this app computes from its 1-degree cube for the same box and months: the
two must correlate almost perfectly with a small bias, which bounds the error
from regridding to cubes.

A case is skipped (not passed) until both its Giovanni CSV and its cube
exist — see the "_how_to" note in cases.json.
"""

import csv
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analysis.spatial import regional_mean
from app.nasa import cube
from app.nasa.catalog_yaml import cube_variable_specs, dataset_specs

FIXTURES = Path(__file__).parent / "fixtures" / "giovanni"
CASES = json.loads((FIXTURES / "cases.json").read_text())["cases"]


def read_giovanni_csv(path: Path) -> pd.Series:
    """Monthly series from a Giovanni area-averaged CSV (metadata lines, then
    a 'time,mean_<var>' header, then rows). Fill values become NaN."""
    rows = list(csv.reader(path.read_text(encoding="utf-8", errors="replace").splitlines()))
    fill = None
    for r in rows:
        if r and r[0].lower().startswith("fill value") and len(r) > 1:
            fill = float(r[1])
    start = next(i for i, r in enumerate(rows) if r and r[0].strip().lower() == "time")
    times, values = [], []
    for r in rows[start + 1:]:
        if len(r) < 2 or not r[0].strip():
            continue
        v = float(r[1])
        times.append(pd.Timestamp(r[0].strip()[:10]).to_period("M").to_timestamp())
        values.append(np.nan if fill is not None and v == fill else v)
    return pd.Series(values, index=pd.DatetimeIndex(times)).sort_index()


async def compare_with_giovanni(case: dict, csv_path: Path, manifest: dict) -> dict:
    """Correlation, mean bias and Giovanni's SD over the overlapping months."""
    spec = cube_variable_specs()[case["variable"]]
    adapter = cube.CubeAdapter(dataset_specs()[spec.dataset], [spec], manifest)
    lat0, lat1, lon0, lon1 = case["bbox"]
    y0, y1 = case["years"]
    grid = await adapter.query_grid_series(spec.info.code, lat0, lat1, lon0, lon1, date(y0, 1, 1), date(y1, 12, 31))
    mean = regional_mean(grid.cells)
    ours = pd.Series(mean.values, index=pd.DatetimeIndex(pd.to_datetime(mean.dates)))
    theirs = read_giovanni_csv(csv_path) * case["unit_scale"] + case["unit_offset"]
    joined = pd.concat({"ours": ours, "giovanni": theirs}, axis=1).dropna()
    return {
        "n": len(joined),
        "r": float(np.corrcoef(joined["ours"], joined["giovanni"])[0, 1]),
        "bias": float((joined["ours"] - joined["giovanni"]).mean()),
        "sd": float(joined["giovanni"].std()),
    }


@pytest.mark.parametrize("case", CASES, ids=[c["file"] for c in CASES])
@pytest.mark.asyncio
async def test_cube_area_mean_matches_giovanni(case):
    csv_path = FIXTURES / case["file"]
    if not csv_path.exists():
        pytest.skip(f"Giovanni fixture {case['file']} not downloaded yet (see cases.json)")
    manifest = cube.load_manifest()
    if case["variable"] not in manifest:
        pytest.skip(f"cube {case['variable']} not built yet")
    m = await compare_with_giovanni(case, csv_path, manifest)
    print(f"{case['variable']}: r={m['r']:.4f}, bias={m['bias']:.4g} ({abs(m['bias']) / m['sd']:.1%} of SD), n={m['n']}")
    assert m["n"] >= 24, "too few overlapping months to compare"
    assert m["r"] >= case["min_r"]
    assert abs(m["bias"]) <= case["max_bias_sd"] * m["sd"]


@pytest.mark.asyncio
async def test_comparison_on_a_synthetic_cube_and_csv(tmp_path, monkeypatch):
    """The comparison itself, end to end: a cube and a 'Giovanni' CSV made
    from the same field must agree, and in Giovanni's (Kelvin) units."""
    import xarray as xr
    from app.core.config import get_settings

    times = pd.date_range("2000-01-01", periods=60, freq="MS")
    lat, lon = np.array([10.5, 11.5]), np.array([20.5, 21.5])
    rng = np.random.default_rng(0)
    field = 15 + 5 * np.sin(np.arange(60) * np.pi / 6)[:, None, None] + rng.normal(0, 0.2, (60, 2, 2))
    xr.Dataset({"M2_T2M": (("time", "lat", "lon"), field.astype("float32"))},
               coords={"time": times, "lat": lat, "lon": lon}).to_zarr(tmp_path / "M2_T2M.zarr", consolidated=True)
    (tmp_path / "manifest.json").write_text(json.dumps({"M2_T2M": {}}))
    w = np.cos(np.radians(lat))[None, :, None] * np.ones((1, 1, 2))
    kelvin = (field * w).sum(axis=(1, 2)) / w.sum() + 273.15
    csv_lines = ["Title:,synthetic", "", "time,mean_T2M"] + [f"{t:%Y-%m-%d} 00:00:00,{v}" for t, v in zip(times, kelvin)]
    (tmp_path / "g.csv").write_text("\n".join(csv_lines))

    monkeypatch.setenv("CUBE_BASE_URL", str(tmp_path))
    for f in (get_settings, cube.load_manifest, cube.open_cube):
        f.cache_clear()
    try:
        case = {"variable": "M2_T2M", "bbox": [10, 12, 20, 22], "years": [2000, 2004],
                "unit_scale": 1.0, "unit_offset": -273.15}
        m = await compare_with_giovanni(case, tmp_path / "g.csv", cube.load_manifest())
    finally:
        for f in (get_settings, cube.load_manifest, cube.open_cube):
            f.cache_clear()
    assert m["n"] == 60 and m["r"] > 0.9999 and abs(m["bias"]) < 1e-4


def test_giovanni_csv_parser(tmp_path):
    sample = (
        "Title:,Time Series Area-Averaged of Precipitation monthly\n"
        "User Start Date:,2001-01-01T00:00:00Z\n"
        "Fill Value (mean_GPM_3IMERGM_07_precipitation):,-9999.9\n"
        "\n"
        "time,mean_GPM_3IMERGM_07_precipitation\n"
        "2001-01-01 00:00:00,0.0123\n"
        "2001-02-01 00:00:00,-9999.9\n"
        "2001-03-01 00:00:00,0.05\n"
    )
    p = tmp_path / "g.csv"
    p.write_text(sample)
    s = read_giovanni_csv(p)
    assert list(s.index.month) == [1, 2, 3]
    assert s.iloc[0] == pytest.approx(0.0123) and np.isnan(s.iloc[1])
