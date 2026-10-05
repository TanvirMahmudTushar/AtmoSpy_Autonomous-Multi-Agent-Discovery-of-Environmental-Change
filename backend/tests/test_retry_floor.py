"""The orchestrator's retry-widen branch used to widen every dataset's
insufficient-data retry back to a single hardcoded year (1985, right for
POWER). That's actively wrong for GRACE-FO (2002+) or SMAP (2015+): widening
back to 1985 doesn't add real data for those missions, it dilutes
completeness against a mostly-empty window and can turn a marginal-but-
fixable case into a hard failure — this happened for real, not
hypothetically, running a live SMAP question before this fix existed."""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.orchestrator import run_pipeline
from app.agents.state import InvestigationState
from app.llm.planner import InvestigationPlan
from app.nasa.grace import GRACE_FO_DATASET_INFO
from app.nasa.power import PowerAdapter
from app.nasa.regions import REGIONS_BY_CODE
from app.nasa.smap import SMAP_DATASET_INFO


def test_dataset_specific_retry_floors_are_sane():
    assert PowerAdapter().get_metadata().retry_floor_year == 1985
    assert GRACE_FO_DATASET_INFO.retry_floor_year == 2003
    assert SMAP_DATASET_INFO.retry_floor_year == 2016


@pytest.mark.asyncio
async def test_retry_widens_to_dataset_specific_floor_not_1985():
    plan = InvestigationPlan(variable_code="soil_moisture", region_code="california_central_valley", start_year=2018, end_year=2025)
    state = InvestigationState(
        investigation_id=None, question=None, mode="nlp", plan=plan, region=REGIONS_BY_CODE["california_central_valley"]
    )

    captured_plans = []

    async def fake_nasa_data_agent_run(session, recorder, state):
        captured_plans.append(state.plan.start_year)
        return state

    async def fake_quality_agent_run(session, recorder, state):
        # Always insufficient, so the retry branch always fires — we only
        # care what start_year it retries with, not the eventual outcome.
        state.status = "insufficient_data"
        return state

    recorder = AsyncMock()
    recorder.emit = AsyncMock()

    # SMAP is only "active" when NASA_EARTHDATA_TOKEN is set, so without a
    # token (CI) soil_moisture has no active dataset. Pin the lookup so this
    # test checks the retry floor, not the environment's credentials.
    with (
        patch("app.agents.orchestrator.dataset_code_for_variable", return_value=SMAP_DATASET_INFO.code),
        patch("app.agents.orchestrator.nasa_data_agent.run", new=AsyncMock(side_effect=fake_nasa_data_agent_run)),
        patch("app.agents.orchestrator.quality_agent.run", new=AsyncMock(side_effect=fake_quality_agent_run)),
    ):
        await run_pipeline(session=None, recorder=recorder, state=state, allow_retry=True)

    # First call uses the plan's own 2018 start year; the retry should use
    # SMAP's 2016 floor, never POWER's 1985.
    assert captured_plans == [2018, 2016]
