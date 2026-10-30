"""A reproducible Jupyter notebook for one finding.

The notebook embeds the exact series the app analyzed and recomputes the
headline statistics with a short, standalone re-implementation (NumPy,
SciPy, pymannkendall), then checks them against the app's numbers. Anyone
can audit a finding without trusting or installing this app. For NASA POWER
findings it also includes a cell that re-downloads the raw data from NASA.
"""

import json

from app.models import Finding

STATS_CODE = '''import numpy as np
import pymannkendall as mk
from scipy import stats

def trend_stats(x, y, alpha=0.05):
    """Sen's slope + lag-1 variance-corrected Mann-Kendall + n_eff t-test,
    as described in the app's method notes."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    n = len(x)
    ols = stats.linregress(x, y)
    resid = y - (ols.intercept + ols.slope * x)
    r1 = 0.0 if np.std(resid) <= 1e-10 * max(np.abs(y).max(), 1) else float(np.corrcoef(resid[:-1], resid[1:])[0, 1])
    r1c = min(max(r1, 0.0), 0.95)
    n_eff = n * (1 - r1c) / (1 + r1c)
    se = ols.stderr * np.sqrt((n - 2) / (n_eff - 2))
    t_p = 2 * stats.t.sf(abs(ols.slope / se), n_eff - 2)
    m = mk.original_test(y)
    var_s = m.var_s * (1 + r1c) / (1 - r1c)
    z = (m.s - np.sign(m.s)) / np.sqrt(var_s) if m.s != 0 else 0.0
    mk_p = 2 * stats.norm.sf(abs(z))
    i, j = np.triu_indices(n, 1)
    slopes = np.sort((y[j] - y[i]) / (x[j] - x[i]))
    sen = float(np.median(slopes))
    c = stats.norm.ppf(1 - alpha / 2) * np.sqrt(var_s)
    lo = slopes[max(0, int(np.floor((len(slopes) - c) / 2)) - 1)]
    hi = slopes[min(len(slopes) - 1, int(np.ceil((len(slopes) + c) / 2)))]
    return {"sen_slope_per_year": sen, "sen_ci": (lo, hi), "mk_p": mk_p, "t_test_p": t_p,
            "lag1": r1, "n_eff": n_eff, "n": n}
'''


def _md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def _code(src: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src}


def build_notebook(finding: Finding, variable_code: str, region_name: str, visualizations: dict,
                   provenance: dict | None) -> dict:
    t = finding.trend_details or {}
    ts = visualizations.get("timeseries") or {}
    basis = t.get("basis", "annual")
    if basis == "monthly_anomaly" and ts.get("monthly"):
        m = ts["monthly"]
        pairs = [(d, a) for d, a in zip(m["dates"], m["anomaly"]) if a is not None]
        data = {"dates": [d for d, _ in pairs], "values": [a for _, a in pairs]}
        load = (
            "import numpy as np\n"
            f"data = {json.dumps(data)}\n"
            "# mid-month decimal years, as in the app\n"
            "x = [int(d[:4]) + (int(d[5:7]) - 0.5) / 12 for d in data['dates']]\n"
            "y = data['values']  # monthly anomalies (seasonal cycle removed)\n"
        )
        what = "monthly anomalies (each month minus its average for that calendar month)"
    else:
        pts = ts.get("points", [])
        data = {"years": [p["year"] for p in pts], "values": [p["value"] for p in pts]}
        load = f"data = {json.dumps(data)}\nx, y = data['years'], data['values']  # yearly averages\n"
        what = "yearly averages"

    expected = {
        "sen_slope_per_year": finding.trend_per_year,
        "mk_p": finding.p_value,
        "t_test_p": t.get("ols_p_value"),
    }
    cells = [
        _md(
            f"# {finding.title}\n\n"
            f"Reproduces the headline statistics of an AtmoSpy finding from the data it analyzed: {what} "
            f"of **{variable_code}** over **{region_name}**.\n\n"
            f"**Method (from the app):** {finding.statistical_method}\n\n"
            + (f"**Processing:** {provenance['processing_method']}\n\n" if provenance else "")
            + "Requires: `pip install numpy scipy pymannkendall`."
        ),
        _code(STATS_CODE),
        _md("## The data the app analyzed"),
        _code(load + "print(len(y), 'values')"),
        _md("## Recompute and compare with the app"),
        _code(
            "r = trend_stats(x, y)\n"
            f"app = {json.dumps(expected)}\n"
            "for k in ('sen_slope_per_year', 'mk_p', 't_test_p'):\n"
            "    if app[k] is None:\n"
            "        continue\n"
            "    ok = np.isclose(r[k], app[k], rtol=1e-3, atol=1e-12)\n"
            "    print(f\"{k:20s} notebook={r[k]:.6g}  app={app[k]:.6g}  {'match' if ok else 'DIFFERENT'}\")\n"
            "print('Sen 95% CI per decade:', [round(float(v) * 10, 4) for v in r['sen_ci']])\n"
            "print('lag-1 autocorrelation:', round(r['lag1'], 3), ' effective sample size:', round(r['n_eff']))"
        ),
    ]
    if provenance and "power.larc.nasa.gov" in (provenance.get("url") or ""):
        cells += [
            _md(
                "## Optional: fetch the raw data from NASA POWER yourself\n\n"
                "This is the exact query the app made (monthly values on every grid cell in the region). "
                "Averaging the cells with cos(latitude) weights and removing the monthly climatology gives "
                "the series above."
            ),
            _code(
                "import requests\n"
                f"url = {json.dumps(provenance['url'])}\n"
                "raw = requests.get(url, timeout=120).json()\n"
                "print(len(raw.get('features', [])), 'grid cells')"
            ),
        ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "atmospy": {"finding_id": str(finding.id), "analysis_version": finding.analysis_version},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
