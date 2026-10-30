"""Turns a free-text question into a structured InvestigationPlan.

Tries the LLM first (if configured); always has a deterministic rule-based
fallback so `/investigate` works without a Groq key. The LLM is only ever
asked to choose among *known* variable/region codes it's given — it cannot
invent a dataset or a number here.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from app.llm.client import get_llm_client
from app.nasa.catalog import VARIABLES_BY_CODE, earliest_year, related_candidates
from app.nasa.regions import REGIONS, REGIONS_BY_CODE, custom_region, find_region_by_name

DEFAULT_START_YEAR = 1990
CURRENT_YEAR = date.today().year
DEFAULT_END_YEAR = CURRENT_YEAR - 1

# Maps a keyword to the variable that answers it *when that variable's
# dataset is active* (checked dynamically against app.nasa.catalog below) —
# not necessarily NASA POWER. A keyword whose variable isn't active yet
# (e.g. GRACE_FO's lwe_thickness with no NASA_EARTHDATA_TOKEN configured)
# falls through to the proxy-with-explanation behavior automatically, no
# extra bookkeeping required; once that dataset becomes active, matching
# questions start routing there with zero further changes here.
# Each keyword lists candidate variables in order of preference; the first
# active one wins. Keywords are checked in order, so more specific phrases
# ("skin temperature", "stratosphere") come before general ones
# ("temperature").
KEYWORD_TO_VARIABLE: dict[str, list[str]] = {
    "stratospher": ["M2_T30"],  # stratosphere, stratospheric
    "upper atmosphere": ["M2_T250"],
    "skin temperature": ["TS", "AIRS_TSURF"],
    "land surface temperature": ["TS", "AIRS_TSURF"],
    "nitrogen dioxide": ["OMI_NO2"],
    "no2": ["OMI_NO2"],
    "air pollution": ["OMI_NO2", "M2_AOD"],
    "aerosol": ["M2_AOD"],
    "haze": ["M2_AOD"],
    "smog": ["OMI_NO2", "M2_AOD"],
    "dust": ["M2_AOD"],
    "water vapor": ["M2_TQV"],
    "water vapour": ["M2_TQV"],
    "evaporation": ["GLDAS_ET"],
    "evapotranspiration": ["GLDAS_ET"],
    "runoff": ["GLDAS_RUNOFF"],
    "streamflow": ["GLDAS_RUNOFF"],
    "river flow": ["GLDAS_RUNOFF"],
    "snow": ["GLDAS_SWE"],
    "ice sheet mass": ["lwe_thickness"],
    "ice mass": ["lwe_thickness"],
    "ice loss": ["lwe_thickness"],
    "groundwater": ["lwe_thickness"],
    "terrestrial water storage": ["lwe_thickness"],
    "water storage": ["lwe_thickness"],
    "mass anomaly": ["lwe_thickness"],
    "temperature": ["T2M", "M2_T2M"],
    "warming": ["T2M", "M2_T2M"],
    "heat": ["T2M_MAX"],
    "cold": ["T2M_MIN"],
    "precipitation": ["GPM_PRECIP", "PRECTOTCORR"],
    "rainfall": ["GPM_PRECIP", "PRECTOTCORR"],
    "rain": ["GPM_PRECIP", "PRECTOTCORR"],
    "drought": ["PRECTOTCORR", "GPM_PRECIP"],
    "humidity": ["RH2M"],
    "soil moisture": ["GWETROOT", "GLDAS_SOILM", "soil_moisture"],
    "root zone": ["GWETROOT"],
    "surface moisture": ["GWETTOP", "soil_moisture"],
    "wetness": ["GWETROOT"],
    "solar": ["ALLSKY_SFC_SW_DWN"],
    "radiation": ["ALLSKY_SFC_SW_DWN"],
    "sunlight": ["ALLSKY_SFC_SW_DWN"],
    "cloud": ["ALLSKY_SFC_SW_DWN"],
    "wind": ["WS2M"],
    "pressure": ["M2_SLP"],
}

# A human-readable name for a keyword's target variable/dataset, used only
# in the "not connected yet" message when that variable isn't active.
UNSUPPORTED_VARIABLE_LABEL = {
    "lwe_thickness": "GRACE-FO terrestrial water storage / mass anomaly",
    "OMI_NO2": "OMI nitrogen dioxide",
    "M2_AOD": "MERRA-2 aerosol optical depth",
    "M2_T30": "MERRA-2 stratospheric temperature",
    "M2_T250": "MERRA-2 upper-air temperature",
    "M2_TQV": "MERRA-2 water vapour",
    "GLDAS_ET": "GLDAS evapotranspiration",
    "GLDAS_RUNOFF": "GLDAS runoff",
    "GLDAS_SWE": "GLDAS snow water equivalent",
    "M2_SLP": "MERRA-2 sea-level pressure",
}

# Unavailable variables with a defensible stand-in: root-zone soil water is
# one part of terrestrial water storage. Everything else unavailable stops
# the investigation instead of analyzing an unrelated variable.
PROXY_OK = {"lwe_thickness"}

# Genuinely unintegrated — no variable code exists for these at all (not
# even a stubbed adapter), unlike the KEYWORD_TO_VARIABLE entries above.
UNSUPPORTED_HINTS = {
    "vegetation": "NDVI (MODIS_NDVI adapter is registered but requires Earthdata credentials)",
    "ndvi": "NDVI (MODIS_NDVI adapter is registered but requires Earthdata credentials)",
    "greenness": "NDVI (MODIS_NDVI adapter is registered but requires Earthdata credentials)",
    "sea level": "sea surface height (not yet integrated)",
    "co2": "OCO-2/3 column CO2 (not yet integrated)",
}

RELATIONSHIP_KEYWORDS = ["why", "relat", "cause", "correlat", "driven by", "linked to", "because"]
COMPARE_KEYWORDS = ["compare", " vs ", " versus ", "difference between"]


@dataclass
class InvestigationPlan:
    variable_code: str
    region_code: str
    start_year: int
    end_year: int
    compare_region_code: str | None = None
    run_spatial_analysis: bool = True
    run_relationship_analysis: bool = False
    unsupported_variable_note: str | None = None
    reasoning: str = ""
    source: str = "fallback"  # "llm" | "fallback" | "structured" | ...
    candidate_related_variables: list[str] = field(default_factory=list)
    # A user-drawn box (min_lat, max_lat, min_lon, max_lon); region_code is then its bbox_ code.
    bbox: tuple[float, float, float, float] | None = None


def structured_plan(
    variable_code: str,
    region_code: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    compare_region_code: str | None = None,
    run_relationship_analysis: bool = False,
) -> InvestigationPlan:
    """A plan chosen directly (guided wizard), validated against the catalog.
    Raises ValueError with a message fit to show the user."""
    if variable_code not in VARIABLES_BY_CODE:
        raise ValueError(f"Variable {variable_code!r} isn't available.")
    if bbox is not None:
        region = custom_region(*bbox)
    elif region_code in REGIONS_BY_CODE:
        region = REGIONS_BY_CODE[region_code]
    else:
        raise ValueError(f"Unknown region {region_code!r}.")
    if compare_region_code is not None and compare_region_code not in REGIONS_BY_CODE:
        raise ValueError(f"Unknown comparison region {compare_region_code!r}.")
    first = earliest_year(variable_code)
    start = max(start_year or DEFAULT_START_YEAR, first)
    end = min(end_year or DEFAULT_END_YEAR, DEFAULT_END_YEAR)
    if end <= start:
        raise ValueError(f"The period must end after it starts; {VARIABLES_BY_CODE[variable_code].name} begins in {first}.")
    return InvestigationPlan(
        variable_code=variable_code,
        region_code=region.code,
        start_year=start,
        end_year=end,
        compare_region_code=compare_region_code,
        run_spatial_analysis=True,
        run_relationship_analysis=run_relationship_analysis,
        reasoning=f"Chosen directly: {VARIABLES_BY_CODE[variable_code].name} over {region.name}, {start}-{end}.",
        source="structured",
        candidate_related_variables=related_candidates(variable_code),
        bbox=(region.min_lat, region.max_lat, region.min_lon, region.max_lon) if bbox is not None else None,
    )


def region_for_plan(plan: InvestigationPlan):
    return custom_region(*plan.bbox) if plan.bbox else REGIONS_BY_CODE[plan.region_code]


def _extract_years(text: str) -> tuple[int, int]:
    years = [int(y) for y in re.findall(r"\b(19[8-9]\d|20[0-4]\d)\b", text)]
    years = [y for y in years if DEFAULT_START_YEAR - 20 <= y <= CURRENT_YEAR]
    if len(years) >= 2:
        return min(years), min(max(years), DEFAULT_END_YEAR)
    if len(years) == 1:
        return years[0], DEFAULT_END_YEAR
    return DEFAULT_START_YEAR, DEFAULT_END_YEAR


def _extract_variable(text: str) -> tuple[str, str | None]:
    lowered = text.lower()
    for keyword, codes in KEYWORD_TO_VARIABLE.items():
        if not re.search(rf"\b{re.escape(keyword)}", lowered):
            continue
        active = [c for c in codes if c in VARIABLES_BY_CODE]
        if active:
            return active[0], None
        label = UNSUPPORTED_VARIABLE_LABEL.get(codes[0], codes[0])
        if codes[0] not in PROXY_OK:
            # No honest stand-in exists (soil wetness says nothing about NO2 or
            # the stratosphere), so return the unavailable code and let the
            # orchestrator stop with this explanation.
            return codes[0], (
                f"You asked about {label}, which isn't available in this build yet (its data hasn't been "
                "connected). Nothing was analyzed, rather than substituting an unrelated variable."
            )
        return "GWETROOT", (
            f"You asked about {keyword}, which this build doesn't have a connected NASA source "
            f"for yet ({label} — adapter registered but requires Earthdata credentials). Showing "
            "the closest available proxy (root-zone soil wetness) instead — treat this as "
            "illustrative, not a direct answer."
        )
    for hint, note in UNSUPPORTED_HINTS.items():
        if hint in lowered:
            return "GWETROOT", (
                f"You asked about {hint}, which this build doesn't have a connected NASA source "
                f"for yet ({note}). Showing the closest available proxy (root-zone soil wetness) "
                "instead — treat this as illustrative, not a direct answer."
            )
    return "T2M", None


def fallback_plan(question: str) -> InvestigationPlan:
    lowered = question.lower()
    variable_code, note = _extract_variable(question)
    start_year, end_year = _extract_years(question)
    start_year = max(start_year, earliest_year(variable_code))

    region = find_region_by_name(question)
    region_code = region.code if region else "bangladesh"

    compare_region_code = None
    if any(kw in lowered for kw in COMPARE_KEYWORDS):
        # look for a second region mention after removing the first match
        remainder = lowered.replace(region.name.lower(), "", 1) if region else lowered
        second = find_region_by_name(remainder)
        if second and (not region or second.code != region.code):
            compare_region_code = second.code

    run_relationship = any(kw in lowered for kw in RELATIONSHIP_KEYWORDS)

    reasoning = (
        f"No LLM configured — used rule-based parsing. Matched variable '{variable_code}' and "
        f"region '{region_code}'" + (f", comparing against '{compare_region_code}'" if compare_region_code else "")
        + f", period {start_year}-{end_year}."
    )

    return InvestigationPlan(
        variable_code=variable_code,
        region_code=region_code,
        start_year=start_year,
        end_year=end_year,
        compare_region_code=compare_region_code,
        run_spatial_analysis=True,
        run_relationship_analysis=run_relationship,
        unsupported_variable_note=note,
        reasoning=reasoning,
        source="fallback",
        candidate_related_variables=related_candidates(variable_code),
    )


PLANNER_SYSTEM_PROMPT = """You are the planning module of a NASA Earth-data investigation system.
Given a user's question, output ONLY a JSON object (no prose) with these fields:
- variable_code: the code (not the name in parentheses) of the best-matching variable from: {variables}
- region_code: one of {regions} (pick the best-matching named region; if none fits well, pick the closest)
- compare_region_code: one of {regions} or null, ONLY if the user is explicitly comparing two regions
- start_year: integer >= 1990
- end_year: integer <= {current_year_minus_1}
- run_relationship_analysis: boolean, true if the user asks "why" or about relationships/causes between variables
- reasoning: one short sentence explaining your choices
You must not invent variable or region codes outside the provided lists. You must not compute or state any statistic — that is done separately by deterministic tools."""


def is_unavailable(plan: InvestigationPlan) -> bool:
    return plan.variable_code not in VARIABLES_BY_CODE


async def build_plan(question: str) -> InvestigationPlan:
    fallback = fallback_plan(question)

    llm = get_llm_client()
    # An explicitly requested but unavailable variable stays unavailable: the
    # LLM would otherwise pick some active variable that doesn't answer it.
    if not llm.is_available() or is_unavailable(fallback):
        return fallback

    # Bare codes (e.g. "lwe_thickness") give the LLM no signal about what a
    # variable actually measures — it picked GWETROOT (soil wetness) over
    # lwe_thickness for a groundwater-depletion question in testing, purely
    # because the code name alone doesn't say "groundwater/ice mass" to it.
    # A short name alongside each code fixes that with no other changes.
    variable_descriptions = ", ".join(f"{code} ({info.name})" for code, info in VARIABLES_BY_CODE.items())
    system_prompt = PLANNER_SYSTEM_PROMPT.format(
        variables=variable_descriptions,
        regions=", ".join(r.code for r in REGIONS),
        current_year_minus_1=DEFAULT_END_YEAR,
    )
    result = await llm.complete_json(system_prompt, f"Question: {question}")
    if not result:
        return fallback

    try:
        variable_code = result.get("variable_code")
        region_code = result.get("region_code")
        if variable_code not in VARIABLES_BY_CODE or region_code not in REGIONS_BY_CODE:
            return fallback

        compare_region_code = result.get("compare_region_code")
        if compare_region_code not in REGIONS_BY_CODE:
            compare_region_code = None

        start_year = int(result.get("start_year") or DEFAULT_START_YEAR)
        end_year = int(result.get("end_year") or DEFAULT_END_YEAR)
        start_year = max(earliest_year(variable_code), min(start_year, DEFAULT_END_YEAR))
        end_year = max(start_year + 4, min(end_year, DEFAULT_END_YEAR))

        return InvestigationPlan(
            variable_code=variable_code,
            region_code=region_code,
            start_year=start_year,
            end_year=end_year,
            compare_region_code=compare_region_code,
            run_spatial_analysis=True,
            run_relationship_analysis=bool(result.get("run_relationship_analysis", False)),
            unsupported_variable_note=fallback.unsupported_variable_note,
            reasoning=str(result.get("reasoning", "")),
            source="llm",
            candidate_related_variables=related_candidates(variable_code),
        )
    except (TypeError, ValueError):
        return fallback
