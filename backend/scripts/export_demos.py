"""Run the demo cases through the real API and freeze them as static JSON.

    # with the API running (uvicorn app.main:app --port 8000)
    cd backend
    python -m scripts.export_demos
    python -m scripts.export_demos --only not-significant-yet

Each demo is executed exactly as a user would run it (structured
investigation or region scan), then its agent steps and results are written
to frontend/public/demos/<id>.json, plus an index.json of what's available.
The demo player replays these files, so demos work even when the backend is
asleep, and every number in them came from the real pipeline.

Demos whose variables aren't available yet (e.g. MERRA-2 pressure levels
before their cubes are built) are skipped and left out of the index.
"""

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demos"
LAST = date.today().year - 1
INDIA_BOX = {"min_lat": 5, "max_lat": 35, "min_lon": 60, "max_lon": 100}

DEMOS = [
    {
        "id": "hidden-by-seasons",
        "kind": "investigation",
        "title": "Hidden by the seasons",
        "summary": "Arctic Alaska swings about 30 °C between winter and summer every year. Remove that cycle and a steady warming appears.",
        "requests": [{"variable_code": "T2M", "region_code": "arctic_alaska_north_slope", "start_year": 1981, "end_year": LAST}],
    },
    {
        "id": "not-significant-yet",
        "kind": "investigation",
        "title": "Real, but not significant yet",
        "summary": "Averaged over the whole Tibetan Plateau, temperature is rising, but natural ups and downs are large. How many more years until we can be sure?",
        "requests": [{"variable_code": "T2M", "region_code": "tibetan_plateau", "start_year": 1990, "end_year": LAST}],
    },
    {
        "id": "vanishing-water",
        "kind": "investigation",
        "title": "Water disappearing underground",
        "summary": "Satellites that weigh water by its gravity see northern India's stored water falling, a sign of groundwater pumping.",
        "requests": [{"variable_code": "lwe_thickness", "region_code": "indo_gangetic_plain", "start_year": 2003,
                      "end_year": LAST, "run_relationship_analysis": True}],
    },
    {
        "id": "whats-changing-sahel",
        "kind": "scan",
        "title": "What is changing in the Sahel?",
        "summary": "Test every variable over the West Sahel at once, and correct for testing so many, to see what has really changed since 1990.",
        "requests": [{"region_code": "sahel_west_africa", "start_year": 1990, "end_year": LAST}],
    },
    {
        "id": "opposite-heights",
        "kind": "pair",
        "title": "Same cause, opposite directions",
        "summary": "Over South Asia and its seas (5 to 35 N, 60 to 100 E), the air 5 km up has warmed while the stratosphere 24 km up has cooled. Extra carbon dioxide does both: two heights, one cause, opposite trends.",
        # A large box gives a clean signal at both heights (checked against
        # other candidates; the North Atlantic "warming hole" is noisier).
        "requests": [
            {"variable_code": "M2_T500", "bbox": INDIA_BOX, "start_year": 1981, "end_year": LAST},
            {"variable_code": "M2_T30", "bbox": INDIA_BOX, "start_year": 1981, "end_year": LAST},
        ],
    },
    {
        "id": "city-air",
        "kind": "pair",
        "title": "City air: cleaner in one place, dirtier in another",
        "summary": "Over the same 21 years (2005 to 2025), nitrogen dioxide from traffic and industry fell over Los Angeles and rose over fast-growing Dhaka.",
        "requests": [
            {"variable_code": "OMI_NO2", "region_code": "los_angeles", "start_year": 2005, "end_year": LAST},
            {"variable_code": "OMI_NO2", "region_code": "dhaka", "start_year": 2005, "end_year": LAST},
        ],
    },
]


def wait(client: httpx.Client, inv_id: str, timeout_s: int) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        inv = client.get(f"/api/investigations/{inv_id}").json()
        if inv["status"] not in ("pending", "running"):
            return inv
        time.sleep(3)
    raise SystemExit(f"Investigation {inv_id} did not finish within {timeout_s}s")


def run_investigation(client: httpx.Client, req: dict, timeout_s: int) -> dict:
    inv_id = client.post("/api/investigations", json=req).raise_for_status().json()["investigation_id"]
    inv = wait(client, inv_id, timeout_s)
    findings = client.get("/api/findings", params={"investigation_id": inv_id, "limit": 1}).json()
    if not findings:
        raise SystemExit(f"{req}: no finding ({inv['status']}: {inv.get('error')})")
    return {"steps": inv["steps"], "finding": client.get(f"/api/findings/{findings[0]['id']}").json()}


def run_scan(client: httpx.Client, req: dict, timeout_s: int) -> dict:
    inv_id = client.post("/api/scan", json=req).raise_for_status().json()["investigation_id"]
    inv = wait(client, inv_id, timeout_s)
    final = next((s for s in reversed(inv["steps"]) if (s.get("detail") or {}).get("scan_results") is not None), None)
    if final is None:
        raise SystemExit(f"Scan {inv_id} produced no results ({inv['status']})")
    return {"steps": inv["steps"], "scan_results": final["detail"]["scan_results"], "region": final["detail"]["region"]}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--only", action="append", default=[], help="demo id (repeatable)")
    p.add_argument("--timeout", type=int, default=900, help="seconds per investigation")
    args = p.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=args.api, timeout=60) as client:
        available = {v["code"] for v in client.get("/api/variables").json() if v.get("available", True)}
        exported = []
        for demo in DEMOS:
            if args.only and demo["id"] not in args.only:
                continue
            needed = {r["variable_code"] for r in demo["requests"] if "variable_code" in r}
            missing = needed - available
            if missing:
                print(f"skip {demo['id']}: not available yet: {', '.join(sorted(missing))}")
                continue
            print(f"run  {demo['id']} ...", flush=True)
            if demo["kind"] == "scan":
                parts = [run_scan(client, demo["requests"][0], args.timeout)]
            else:
                parts = [run_investigation(client, r, args.timeout) for r in demo["requests"]]
            record = {
                "id": demo["id"],
                "kind": demo["kind"],
                "title": demo["title"],
                "summary": demo["summary"],
                "requests": demo["requests"],
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "parts": parts,
            }
            (OUT / f"{demo['id']}.json").write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
            exported.append(demo["id"])
            print(f"  wrote {demo['id']}.json")

    # The index lists every demo file present (including ones from earlier runs).
    index = []
    for demo in DEMOS:
        path = OUT / f"{demo['id']}.json"
        if path.exists():
            rec = json.loads(path.read_text(encoding="utf-8"))
            index.append({k: rec[k] for k in ("id", "kind", "title", "summary", "generated_at")})
    (OUT / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"index: {[d['id'] for d in index]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
