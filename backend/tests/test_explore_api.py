"""API tests for the guided-exploration surface: learning metadata on
/api/variables, place-tagged regions, structured (wizard) investigations,
variable suggestions and region-scan validation. Background work is mocked,
so no NASA calls are made."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.llm.suggest import rule_based
from app.main import app
from app.nasa.regions import REGIONS_BY_CODE, custom_region


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_variables_carry_plain_definitions_and_availability():
    async with await _client() as c:
        rows = (await c.get("/api/variables")).json()
    t2m = next(r for r in rows if r["code"] == "T2M")
    assert t2m["available"] is True and t2m["scale"] == "interval"
    assert "metres" in t2m["definition"] and "city" in t2m["place_tags"]
    # cube variables are listed honestly even before their cube is built
    no2 = next(r for r in rows if r["code"] == "OMI_NO2")
    assert no2["dataset_code"] == "OMI" and no2["known_breaks"][0]["year"] == 2007


@pytest.mark.asyncio
async def test_regions_and_place_types():
    async with await _client() as c:
        regions = (await c.get("/api/regions")).json()
        places = (await c.get("/api/place-types")).json()
    delhi = next(r for r in regions if r["code"] == "delhi")
    assert delhi["kind"] == "city" and "city" in delhi["place_tags"]
    assert {"city", "desert", "ocean", "ice"} <= set(places)


@pytest.mark.asyncio
async def test_structured_investigation_with_a_drawn_box():
    body = {"variable_code": "T2M", "bbox": {"min_lat": 10, "max_lat": 14, "min_lon": 0, "max_lon": 5},
            "start_year": 1995, "end_year": 2020}
    with patch("app.api.investigations.run_investigation", new=AsyncMock()) as run:
        async with await _client() as c:
            resp = await c.post("/api/investigations", json=body)
    assert resp.status_code == 201
    question, plan = run.call_args.args[1], run.call_args.args[2]
    assert plan.source == "structured" and plan.bbox == (10, 14, 0, 5)
    assert plan.region_code.startswith("bbox_") and plan.start_year == 1995
    assert "Custom area" in question


@pytest.mark.asyncio
@pytest.mark.parametrize("body, fragment", [
    ({"variable_code": "T2M"}, "exactly one of region_code or bbox"),
    ({"variable_code": "T2M", "region_code": "atlantis"}, "Unknown region"),
    ({"variable_code": "NOT_A_VAR", "region_code": "delhi"}, "isn't available"),
    ({"variable_code": "T2M", "bbox": {"min_lat": 14, "max_lat": 10, "min_lon": 0, "max_lon": 5}}, "min_lat < max_lat"),
    ({}, "Send a question"),
])
async def test_structured_investigation_validation(body, fragment):
    with patch("app.api.investigations.run_investigation", new=AsyncMock()):
        async with await _client() as c:
            resp = await c.post("/api/investigations", json=body)
    assert resp.status_code == 422
    assert fragment in resp.text


@pytest.mark.asyncio
async def test_suggest_returns_city_variables_with_reasons():
    async with await _client() as c:
        body = (await c.get("/api/suggest", params={"place": "city", "region_code": "delhi"})).json()
    assert body["source"] in ("rules", "llm")
    codes = [s["variable_code"] for s in body["suggestions"]]
    assert codes and all(s["reason"] for s in body["suggestions"])
    # the LLM (when configured) may only reorder the rule-based candidates
    allowed = {s["variable_code"] for s in rule_based(["city"], REGIONS_BY_CODE["delhi"], limit=10)}
    assert set(codes) <= allowed
    if body["source"] == "rules":
        from app.nasa.catalog import VARIABLES_BY_CODE
        assert VARIABLES_BY_CODE[codes[0]].family == "air_temperature"  # most matching tags, longest record
    assert not any(ch.isdigit() for s in body["suggestions"] for ch in s["reason"]) or body["source"] == "rules"


def test_rule_based_suggestions_follow_place_tags():
    from app.nasa.catalog import VARIABLES_BY_CODE

    ice = [s["variable_code"] for s in rule_based(["ice"], REGIONS_BY_CODE["greenland_south"])]
    families = [VARIABLES_BY_CODE[c].family for c in ice]
    assert "air_temperature" in families and "PRECTOTCORR" not in ice  # rainfall isn't tagged for ice
    # one product per quantity before any repeats (several datasets measure air temperature)
    n_families = len({v.family for v in VARIABLES_BY_CODE.values() if "ice" in v.place_tags})
    assert len(set(families)) == min(len(ice), n_families)
    assert rule_based(["ocean"], None) == [] or all(
        "ocean" in s["reason"] or s["reason"] for s in rule_based(["ocean"], None)
    )


@pytest.mark.asyncio
async def test_scan_validation_and_start():
    with patch("app.api.explore.run_scan", new=AsyncMock()) as run:
        async with await _client() as c:
            short = await c.post("/api/scan", json={"region_code": "delhi", "start_year": 2018, "end_year": 2020})
            none = await c.post("/api/scan", json={"start_year": 1990})
            ok = await c.post("/api/scan", json={"region_code": "sahel_west_africa"})
    assert short.status_code == 422 and "8 years" in short.text
    assert none.status_code == 422
    assert ok.status_code == 201 and run.call_args.args[1].code == "sahel_west_africa"


def test_custom_region_is_stable_and_validated():
    a = custom_region(10, 14, 0, 5)
    b = custom_region(10.001, 14.0, 0.0, 5.0)
    assert a.code == b.code  # rounded to 0.01 degree
    with pytest.raises(ValueError):
        custom_region(14, 10, 0, 5)


@pytest.mark.asyncio
async def test_scan_is_rate_limited():
    with patch("app.api.explore.run_scan", new=AsyncMock()):
        async with await _client() as c:
            codes = [(await c.post("/api/scan", json={"region_code": "sahel_west_africa"})).status_code for _ in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


@pytest.mark.asyncio
async def test_related_prefetch_is_keyed_by_period_and_cancellable():
    import asyncio
    from datetime import date

    from app.agents import relationship_agent
    from app.agents.state import InvestigationState
    from app.llm.planner import structured_plan

    plan = structured_plan("T2M", region_code="tibetan_plateau", start_year=1990, end_year=2020,
                           run_relationship_analysis=True)
    state = InvestigationState(investigation_id=None, question=None, mode="guided", plan=plan,
                               region=REGIONS_BY_CODE["tibetan_plateau"])
    started = asyncio.Event()

    async def slow_fetch(code, region, start, end):
        started.set()
        await asyncio.sleep(60)

    with patch.object(relationship_agent, "_fetch", new=slow_fetch):
        relationship_agent.start_prefetch(state)
        relationship_agent.start_prefetch(state)  # same period: no duplicate downloads
        n = len(state.related_prefetch)
        assert n == len(plan.candidate_related_variables[: relationship_agent.MAX_CANDIDATES]) and n > 0
        assert all(k[1] == date(1990, 1, 1) for k in state.related_prefetch)
        state.plan.start_year = 1995  # a widened/narrowed retry fetches its own window
        relationship_agent.start_prefetch(state)
        assert len(state.related_prefetch) == 2 * n
        await started.wait()
        relationship_agent.cancel_prefetch(state)
        await asyncio.gather(*state.related_prefetch.values(), return_exceptions=True)
        assert all(t.cancelled() for t in state.related_prefetch.values())
