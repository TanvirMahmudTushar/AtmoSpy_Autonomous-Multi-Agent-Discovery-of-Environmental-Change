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
from app.nasa.catalog import VARIABLES_BY_CODE
from app.nasa.power import POWER_VARIABLES
from app.nasa.regions import REGIONS, REGIONS_BY_CODE, find_region_by_name

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
KEYWORD_TO_VARIABLE = {
    "temperature": "T2M",
    "warming": "T2M",
    "heat": "T2M_MAX",
    "cold": "T2M_MIN",
    "precipitation": "PRECTOTCORR",
    "rainfall": "PRECTOTCORR",
    "rain": "PRECTOTCORR",
    "drought": "PRECTOTCORR",
    "humidity": "RH2M",
    "soil moisture": "GWETROOT",
    "root zone": "GWETROOT",
    "surface moisture": "GWETTOP",
    "wetness": "GWETROOT",
    "solar": "ALLSKY_SFC_SW_DWN",
    "radiation": "ALLSKY_SFC_SW_DWN",
    "sunlight": "ALLSKY_SFC_SW_DWN",
    "cloud": "ALLSKY_SFC_SW_DWN",
    "wind": "WS2M",
    "skin temperature": "TS",
    "land surface temperature": "TS",
    "ice sheet mass": "lwe_thickness",
    "ice mass": "lwe_thickness",
    "ice loss": "lwe_thickness",
    "groundwater": "lwe_thickness",
    "terrestrial water storage": "lwe_thickness",
    "water storage": "lwe_thickness",
    "mass anomaly": "lwe_thickness",
}

# A human-readable name for a keyword's target variable/dataset, used only
# in the "not connected yet" message when that variable isn't active.
UNSUPPORTED_VARIABLE_LABEL = {
    "lwe_thickness": "GRACE-FO terrestrial water storage / mass anomaly",
}

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
    source: str = "fallback"  # "llm" | "fallback"
    candidate_related_variables: list[str] = field(default_factory=list)


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
    for keyword, code in KEYWORD_TO_VARIABLE.items():
        if keyword not in lowered:
            continue
        if code in VARIABLES_BY_CODE:
            return code, None
        label = UNSUPPORTED_VARIABLE_LABEL.get(code, code)
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
        # Deliberately POWER-only: relationship_agent.py correlates the seed
        # variable against these, and mixing in a monthly, 2002-onward
        # source (GRACE-FO) would need its own alignment/latency handling
        # that hasn't been built — a scope boundary, not an oversight.
        candidate_related_variables=[v.code for v in POWER_VARIABLES if v.code != variable_code],
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


async def build_plan(question: str) -> InvestigationPlan:
    fallback = fallback_plan(question)

    llm = get_llm_client()
    if not llm.is_available():
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
        start_year = max(1981, min(start_year, DEFAULT_END_YEAR))
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
            candidate_related_variables=[v.code for v in POWER_VARIABLES if v.code != variable_code],
        )
    except (TypeError, ValueError):
        return fallback
