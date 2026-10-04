"""Adapter parsing tests using a mocked HTTP transport — verifies our JSON
parsing logic against NASA POWER's actual response shape without requiring
network access, so this stays fast and deterministic in CI.
"""

from datetime import date

import httpx
import pytest
import respx

from app.nasa.power import PowerAdapter


@pytest.mark.asyncio
@respx.mock
async def test_query_point_series_parses_daily_response_and_skips_fill_values():
    payload = {
        "properties": {"parameter": {"T2M": {"20200101": 20.1, "20200102": -999.0, "20200103": 21.4}}},
        "messages": [],
    }
    respx.get("https://power.larc.nasa.gov/api/temporal/daily/point").mock(
        return_value=httpx.Response(200, json=payload)
    )

    adapter = PowerAdapter()
    result = await adapter.query_point_series("T2M", 23.8, 90.4, date(2020, 1, 1), date(2020, 1, 3), temporal="daily")

    assert result.values == [20.1, 21.4]
    assert result.missing_dates == [date(2020, 1, 2)]
    assert result.units == "degC"


@pytest.mark.asyncio
@respx.mock
async def test_query_point_series_raises_on_power_error_message():
    payload = {"properties": {"parameter": {}}, "messages": ["Invalid parameter requested"]}
    respx.get("https://power.larc.nasa.gov/api/temporal/daily/point").mock(
        return_value=httpx.Response(200, json=payload)
    )

    adapter = PowerAdapter()
    with pytest.raises(Exception):
        await adapter.query_point_series("T2M", 23.8, 90.4, date(2020, 1, 1), date(2020, 1, 3), temporal="daily")


@pytest.mark.asyncio
@respx.mock
async def test_query_grid_series_extracts_annual_values_only():
    payload = {
        "features": [
            {
                "geometry": {"coordinates": [90.0, 23.0, 5.0]},
                "properties": {"parameter": {"T2M": {"202001": 20.0, "202002": 21.0, "202013": 20.5}}},
            }
        ]
    }
    respx.get("https://power.larc.nasa.gov/api/temporal/monthly/regional").mock(
        return_value=httpx.Response(200, json=payload)
    )

    adapter = PowerAdapter()
    result = await adapter.query_grid_series("T2M", 22.0, 24.0, 89.0, 91.0, date(2020, 1, 1), date(2020, 12, 31))

    assert len(result.cells) == 1
    assert result.cells[0].values == [20.5]  # only the "13" annual-average entry
