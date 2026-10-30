"""Suggest variables worth investigating in a place.

Deterministic first: every available variable is scored by how many of its
place tags (variables.yaml) match the place types the user picked and the
region's own tags. The LLM, when configured, may only reorder those same
candidates and write a one-sentence reason for each. It cannot add a
variable, and a reason containing a digit is discarded (it must not invent
numbers), falling back to the rule-based reason.
"""

import re

from cachetools import TTLCache

from app.llm.client import get_llm_client
from app.nasa.base import VariableInfo
from app.nasa.catalog import VARIABLES_BY_CODE
from app.nasa.regions import RegionDef

PLACE_PHRASE = {
    "city": "the air above cities",
    "desert": "deserts",
    "rainforest": "rainforests",
    "coast": "coasts and estuaries",
    "ice": "icy and polar places",
    "ocean": "the open ocean",
    "farmland": "farming regions",
    "mountains": "mountains",
    "river_basin": "river basins",
}

SYSTEM_PROMPT = """You help students choose NASA Earth-science variables to investigate for trends.
You get a place and a numbered list of candidate variables with definitions. Return ONLY JSON:
{"suggestions": [{"code": "<candidate code>", "reason": "<one sentence>"}]}
Rules: use only candidate codes; order the best first; at most 6. Each reason is one plain sentence
(under 30 words) on why this variable might be changing in this kind of place. Never state numbers,
dates, percentages or measured results: nothing has been analyzed yet."""


def _score(v: VariableInfo, tags: set[str]) -> float:
    return len(set(v.place_tags) & tags)


def _rule_reason(v: VariableInfo, matched: list[str]) -> str:
    places = " and ".join(PLACE_PHRASE.get(t, t) for t in matched[:2])
    why = v.why_it_matters.rstrip(".")
    return f"Often worth checking in {places}: {why[0].lower() + why[1:]}." if places and why else v.definition


def rule_based(place_tags: list[str], region: RegionDef | None, limit: int = 6) -> list[dict]:
    tags = set(place_tags) | set(region.place_tags if region else ())
    ranked = []
    for code, v in VARIABLES_BY_CODE.items():
        score = _score(v, tags)
        if score > 0:
            # prefer longer records (more chance a trend is detectable), then name
            ranked.append((-score, v.coverage_start or 9999, v.name, code))
    ranked.sort()
    # Variety first: the best of each family (air temperature, snow, ...),
    # then the runners-up, so four products measuring one quantity can't
    # crowd out everything else.
    codes = [r[3] for r in ranked]
    families: set[str] = set()
    first, rest = [], []
    for code in codes:
        fam = VARIABLES_BY_CODE[code].family or code
        (rest if fam in families else first).append(code)
        families.add(fam)
    out = []
    for code in (first + rest)[:limit]:
        v = VARIABLES_BY_CODE[code]
        matched = [t for t in place_tags if t in v.place_tags] or [t for t in tags if t in v.place_tags]
        out.append(_entry(v, _rule_reason(v, matched)))
    return out


def _entry(v: VariableInfo, reason: str) -> dict:
    return {
        "variable_code": v.code, "name": v.name, "units": v.units, "definition": v.definition,
        "reason": reason, "source_label": v.source_label, "coverage_start": v.coverage_start,
        "level_hpa": v.level_hpa, "domain": v.domain,
    }


# Suggestions depend only on the place types, the region and the catalog, so
# repeat visits (and other students picking the same place) are instant.
_CACHE: TTLCache = TTLCache(maxsize=512, ttl=6 * 3600)


async def suggest_variables(place_tags: list[str], region: RegionDef | None, limit: int = 6) -> dict:
    key = (tuple(sorted(place_tags)), region.code if region else None, limit)
    if key in _CACHE:
        return _CACHE[key]
    result = await _suggest(place_tags, region, limit)
    if result["source"] == "llm":  # rule-based results are instant; don't pin a transient LLM failure
        _CACHE[key] = result
    return result


async def _suggest(place_tags: list[str], region: RegionDef | None, limit: int) -> dict:
    rules = rule_based(place_tags, region, limit=limit + 4)  # a few extra for the LLM to choose from
    llm = get_llm_client()
    if not llm.is_available() or not rules:
        return {"source": "rules", "suggestions": rules[:limit]}

    place = region.name if region else "a place"
    lines = [f"{i + 1}. {s['variable_code']}: {s['name']}. {s['definition']}" for i, s in enumerate(rules)]
    user = (
        f"Place: {place}. Place types: {', '.join(PLACE_PHRASE.get(t, t) for t in place_tags) or 'not given'}."
        + (f" About this place: {region.notes}" if region and region.notes else "")
        + "\nCandidates:\n" + "\n".join(lines)
    )
    result = await llm.complete_json(SYSTEM_PROMPT, user)
    by_code = {s["variable_code"]: s for s in rules}
    picked = []
    for item in (result or {}).get("suggestions", []) if isinstance(result, dict) else []:
        code, reason = item.get("code"), str(item.get("reason", "")).strip()
        if code not in by_code or code in {p["variable_code"] for p in picked}:
            continue
        entry = dict(by_code[code])
        if reason and not re.search(r"\d", reason) and len(reason) <= 240:
            entry["reason"] = reason
        picked.append(entry)
        if len(picked) == limit:
            break
    if not picked:
        return {"source": "rules", "suggestions": rules[:limit]}
    return {"source": "llm", "suggestions": picked}
