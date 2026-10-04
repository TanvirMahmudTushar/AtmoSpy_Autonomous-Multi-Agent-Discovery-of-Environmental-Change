"""Curated, cited context for "why might this be happening, what does it mean,
what can be done" — the part of a finding that the data itself cannot answer.

This is deliberately *static and hand-written*, not generated: the pipeline's
rule is that every number is computed and nothing is invented, and an LLM
writing causes and remedies on the fly would break that. Everything here is
general scientific context for a *kind* of change (e.g. "warming", "drying
soil"), worded with "can"/"often"/"commonly cited" because a regional trend
rarely has one provable cause. Nothing here attributes a specific finding to
a specific cause — see app/knowledge/insight.py for how it is gated and
labelled. Sources are the IPCC AR6 assessment reports plus NASA.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    """Context for one (variable family, direction) pair."""

    # concerning: a rise/fall in this direction is usually harmful.
    # mixed: it helps some things and harms others.
    # neutral: no general judgement (or the direction is unexpected — check the data).
    polarity: str
    headline: str
    drivers: tuple[tuple[str, str], ...]  # (title, text)
    impacts: tuple[tuple[str, str], ...]  # (sector, text)
    mitigate: tuple[str, ...]  # address the cause (usually global in scale)
    adapt: tuple[str, ...]  # cope with the effect (usually local)


@dataclass(frozen=True)
class Extra:
    """Additions layered on an Entry for a kind of place (delta, ice, plateau...)."""

    impacts: tuple[tuple[str, str], ...] = ()
    mitigate: tuple[str, ...] = ()
    adapt: tuple[str, ...] = ()


# Sectors the UI has an icon for.
SECTORS = ("agriculture", "water", "health", "ecosystems", "infrastructure", "energy", "cryosphere")

REFERENCES = {
    "wg1": ("IPCC AR6 WG1 — The Physical Science Basis", "https://www.ipcc.ch/report/ar6/wg1/"),
    "wg2": ("IPCC AR6 WG2 — Impacts, Adaptation and Vulnerability", "https://www.ipcc.ch/report/ar6/wg2/"),
    "wg3": ("IPCC AR6 WG3 — Mitigation of Climate Change", "https://www.ipcc.ch/report/ar6/wg3/"),
    "nasa": ("NASA Climate — evidence and causes", "https://climate.nasa.gov/"),
    "grace": ("NASA GRACE / GRACE-FO — water and ice mass change", "https://grace.jpl.nasa.gov/"),
}

FAMILY_REFERENCES = {
    "temperature": ("wg1", "wg2", "wg3", "nasa"),
    "precipitation": ("wg1", "wg2", "wg3"),
    "soil": ("wg1", "wg2", "wg3"),
    "humidity": ("wg1", "wg2"),
    "solar": ("wg1", "wg3"),
    "wind": ("wg1", "wg2"),
    "water_mass": ("wg1", "wg2", "grace"),
    "generic": ("wg1", "wg2", "wg3"),
}

VARIABLE_FAMILY = {
    "T2M": "temperature",
    "T2M_MAX": "temperature",
    "T2M_MIN": "temperature",
    "TS": "temperature",
    "PRECTOTCORR": "precipitation",
    "GWETROOT": "soil",
    "GWETTOP": "soil",
    "GWETPROF": "soil",
    "soil_moisture": "soil",
    "RH2M": "humidity",
    "ALLSKY_SFC_SW_DWN": "solar",
    "WS2M": "wind",
    "lwe_thickness": "water_mass",
}

_GLOBAL_NOTE = "Global action — one region cannot reverse a global trend, but it can cut its own share."

ENTRIES: dict[tuple[str, str], Entry] = {
    # ------------------------------------------------------------ temperature
    ("temperature", "up"): Entry(
        polarity="concerning",
        headline="Sustained warming raises heat stress and speeds up melting and drying.",
        drivers=(
            ("Greenhouse-gas warming", "Rising CO₂ and other greenhouse gases are the dominant cause of the global warming trend measured since the mid-20th century."),
            ("Local land use and urban heat", "Land clearing, changes in irrigation and growing cities can add local warming on top of the global signal."),
            ("Natural variability", "El Niño/La Niña and multi-decade ocean cycles can push a regional record up or down for years at a time."),
        ),
        impacts=(
            ("health", "More dangerous heat days raise the risk of heat illness, especially for outdoor workers, older people and homes without cooling."),
            ("agriculture", "Heat during flowering and grain-filling can cut yields, and warmer nights raise crop water demand."),
            ("water", "Higher evaporation dries soils and shrinks reservoirs faster."),
            ("ecosystems", "Species ranges shift, and heat plus drought raise wildfire and forest stress."),
            ("energy", "Cooling demand and peak electricity load rise."),
        ),
        mitigate=(
            "Cut fossil-fuel emissions: renewables, efficiency, electrified transport and heating.",
            "Protect and restore forests, peatlands and wetlands that store carbon.",
            "Reduce methane from leaks, landfills and livestock, which acts quickly on warming.",
            _GLOBAL_NOTE,
        ),
        adapt=(
            "Heat-health action plans and early-warning systems.",
            "Urban trees, cool roofs and shaded public space.",
            "Heat-tolerant crop varieties and shifted planting dates.",
            "Efficient irrigation and a power grid built for peak cooling load.",
        ),
    ),
    ("temperature", "down"): Entry(
        polarity="neutral",
        headline="A cooling trend runs against global warming, so check the data before reading anything into it.",
        drivers=(
            ("Data or model artifact", "Reanalysis products can carry step changes when the observations feeding them change (new satellites or sensors), which can look like a trend."),
            ("Local cooling influences", "Irrigation expansion, more cloud or aerosol cover, or land-cover change can locally offset warming."),
            ("Short record or endpoints", "A window that starts in a warm year and ends in a cool one can show cooling even in a warming climate."),
        ),
        impacts=(
            ("energy", "If real, heating demand would rise slightly and cooling demand fall."),
            ("agriculture", "If real, cooler seasons would shift crop calendars — helpful or harmful depending on the crop."),
            ("ecosystems", "Effects depend on how large the change is; a small change would have little effect."),
        ),
        mitigate=(),
        adapt=(
            "Compare against weather-station records before acting on this result.",
            "Keep monitoring: a real, sustained cooling would need its own explanation.",
        ),
    ),
    # ---------------------------------------------------------- precipitation
    ("precipitation", "up"): Entry(
        polarity="mixed",
        headline="More rain can refill water supplies — and raise flood, erosion and disease risk.",
        drivers=(
            ("Warmer air holds more moisture", "A warmer atmosphere holds more water vapour, which tends to intensify heavy rainfall."),
            ("Shifting circulation and monsoons", "Changes in monsoon strength, storm tracks and ocean cycles (ENSO, Indian Ocean Dipole) move rain from one region to another."),
            ("Land use and aerosols", "Deforestation, irrigation and aerosol pollution can change local rainfall."),
        ),
        impacts=(
            ("water", "Reservoirs, rivers and aquifers can recover, easing water shortages."),
            ("agriculture", "Rain-fed crops may benefit, but waterlogging, erosion and floods can destroy fields."),
            ("health", "Flooding and standing water raise the risk of cholera, malaria and dengue."),
            ("infrastructure", "Drainage, roads and embankments are stressed by heavier downpours."),
        ),
        mitigate=(
            "Cut emissions to limit the intensification of heavy rain.",
            "Protect wetlands, forests and floodplains that slow runoff.",
            _GLOBAL_NOTE,
        ),
        adapt=(
            "Flood early warning and evacuation planning.",
            "Better drainage, embankments and floodplain zoning.",
            "Rainwater harvesting and groundwater recharge to store the surplus.",
            "Crop insurance and flood-tolerant varieties.",
        ),
    ),
    ("precipitation", "down"): Entry(
        polarity="concerning",
        headline="Less rain means less water for crops, rivers and people — drought risk rises.",
        drivers=(
            ("Circulation shifts", "Shifts in the tropical belt, monsoons and storm tracks can move rain away from a region."),
            ("Ocean cycles", "El Niño and other ocean cycles cause multi-year dry spells in many regions."),
            ("Land-use change", "Deforestation reduces the moisture forests recycle back into the air, which can dry a region further."),
        ),
        impacts=(
            ("agriculture", "Rain-fed crops fail or yield less, and livestock lose pasture and water."),
            ("water", "Rivers, reservoirs and shallow wells decline, and groundwater is over-pumped to compensate."),
            ("health", "Hunger, malnutrition and unsafe water raise disease risk."),
            ("ecosystems", "Dry forests and grasslands burn more easily and trees die back."),
            ("infrastructure", "Hydropower and river transport lose reliability."),
        ),
        mitigate=(
            "Cut emissions to limit warming-driven changes in rainfall patterns.",
            "Stop deforestation and restore forests that recycle moisture.",
            _GLOBAL_NOTE,
        ),
        adapt=(
            "Drought early warning and contingency plans before the dry season.",
            "Drip irrigation and drought-tolerant crops.",
            "Water reuse, leak repair and demand management in cities.",
            "Managed aquifer recharge and diversified water sources.",
        ),
    ),
    # ------------------------------------------------------------------- soil
    ("soil", "up"): Entry(
        polarity="mixed",
        headline="Wetter soils help crops and recharge groundwater, but saturated ground raises flood and landslide risk.",
        drivers=(
            ("More rainfall or slower evaporation", "Higher rainfall, or cooler or more humid conditions that slow evaporation, keep soils wetter."),
            ("Irrigation expansion", "More irrigated land raises soil moisture directly."),
            ("Land-cover change", "Less vegetation means less water drawn out of the soil by plants."),
        ),
        impacts=(
            ("agriculture", "Crops may benefit from more available water, or suffer from waterlogging."),
            ("water", "Better groundwater recharge and higher river baseflow."),
            ("infrastructure", "Saturated slopes are more prone to landslides, and saturated ground floods sooner in heavy rain."),
            ("health", "Wet ground supports mosquito breeding and some soil-borne disease."),
        ),
        mitigate=(
            "Cut emissions to limit the intensification of the water cycle.",
            _GLOBAL_NOTE,
        ),
        adapt=(
            "Field drainage where waterlogging damages crops.",
            "Monitor and stabilise landslide-prone slopes.",
            "Time planting and machinery use to soil conditions.",
        ),
    ),
    ("soil", "down"): Entry(
        polarity="concerning",
        headline="Drier soils stress crops and vegetation and feed drought and wildfire.",
        drivers=(
            ("Reduced rainfall", "Less rain, or rain arriving in fewer, heavier events, leaves soils drier."),
            ("Warming-driven evaporation", "Higher temperatures pull more water out of soils and plants."),
            ("Groundwater and irrigation withdrawals", "Heavy pumping and diversion can dry the soil profile and the water table below it."),
            ("Vegetation and land-use change", "Clearing and degradation reduce the soil's ability to hold water."),
        ),
        impacts=(
            ("agriculture", "Crop stress and yield loss, with the greatest risk during flowering and grain-filling."),
            ("ecosystems", "Vegetation stress, tree mortality and greater wildfire risk."),
            ("water", "Streamflow and groundwater fall as soils take up more of what rain there is."),
            ("infrastructure", "Erosion, dust and, in some soils, land subsidence and building damage."),
            ("health", "Dust storms and worse air quality."),
        ),
        mitigate=(
            "Cut emissions to slow warming-driven drying.",
            "Protect peatlands and wetlands and stop draining them.",
            "Restore vegetation and soil carbon.",
            _GLOBAL_NOTE,
        ),
        adapt=(
            "Moisture-conserving farming: mulch, cover crops and reduced tillage.",
            "Irrigation scheduled by measured soil moisture, using drip where possible.",
            "Drought-tolerant crops and adjusted planting dates.",
            "Caps on groundwater pumping, with managed recharge.",
        ),
    ),
    # --------------------------------------------------------------- humidity
    ("humidity", "up"): Entry(
        polarity="mixed",
        headline="Moister air adds heat stress in warm places and mould risk, but eases dryness and fire danger.",
        drivers=(
            ("Warmer air holds more vapour", "As air warms it can carry more water vapour."),
            ("Rainfall and irrigation changes", "More rain, wetter soils or more irrigation put more moisture into the air."),
            ("Ocean and monsoon variability", "Changes in ocean temperature and monsoon flow change the moisture reaching land."),
        ),
        impacts=(
            ("health", "Humid heat is harder for the body to shed, and damp homes bring mould and respiratory problems."),
            ("energy", "Cooling demand rises as humid heat becomes harder to bear."),
            ("agriculture", "More fungal disease in crops, but less evaporative stress."),
            ("ecosystems", "Lower fire danger where fuels stay damp."),
        ),
        mitigate=("Cut emissions to slow warming and the humid-heat it brings.", _GLOBAL_NOTE),
        adapt=(
            "Heat–humidity (wet-bulb) early warnings, not temperature alone.",
            "Ventilation and dehumidification in buildings and stores.",
            "Crop disease monitoring during humid spells.",
        ),
    ),
    ("humidity", "down"): Entry(
        polarity="mixed",
        headline="Drier air raises evaporation demand and fire danger.",
        drivers=(
            ("Land warming faster than moisture supply", "Land air can dry out as it warms faster than oceans can supply moisture; a decline in land humidity has been reported since around 2000."),
            ("Soil drying and vegetation change", "Drier soils and less vegetation put less moisture into the air."),
            ("Circulation changes", "Shifts in winds and pressure patterns change where moist air flows."),
        ),
        impacts=(
            ("ecosystems", "Vegetation dries faster, raising wildfire risk."),
            ("agriculture", "Crops and livestock need more water for the same growth."),
            ("health", "Dust and dry air irritate lungs and eyes."),
        ),
        mitigate=("Cut emissions to slow land warming.", "Protect vegetation and wetlands that add moisture to the air.", _GLOBAL_NOTE),
        adapt=(
            "Fire-weather warnings and fuel management.",
            "More efficient irrigation and water storage.",
        ),
    ),
    # ------------------------------------------------------------------ solar
    ("solar", "up"): Entry(
        polarity="mixed",
        headline="More sunlight raises solar-power potential but also heating and evaporation.",
        drivers=(
            ("Fewer clouds", "Changes in cloud cover change how much sunlight reaches the ground."),
            ("Cleaner air", "Less aerosol pollution lets more sunlight through — 'brightening', reported in parts of Europe and North America after air-quality controls."),
            ("Circulation changes", "Shifts in weather patterns change how often skies are clear."),
        ),
        impacts=(
            ("energy", "Solar farms produce more electricity."),
            ("water", "Higher evaporation from soils, crops and reservoirs."),
            ("agriculture", "More light can boost growth where light is limiting, but heat and water stress can offset it."),
            ("health", "Higher heat load and UV exposure."),
        ),
        mitigate=(),
        adapt=(
            "Update solar-resource assessments with recent data.",
            "Shade, sun protection and water-saving measures in bright, hot spells.",
        ),
    ),
    ("solar", "down"): Entry(
        polarity="mixed",
        headline="Less sunlight ('dimming') lowers solar-power output and can slow crop growth.",
        drivers=(
            ("More cloud", "Changes in cloud cover can reduce sunlight at the surface."),
            ("Air pollution and smoke", "Aerosols, haze and wildfire smoke scatter and absorb sunlight — 'dimming', reported for decades in parts of South Asia."),
            ("Volcanic eruptions", "Large eruptions temporarily reduce sunlight."),
        ),
        impacts=(
            ("energy", "Solar farms produce less electricity."),
            ("agriculture", "Slower growth where light is limiting."),
            ("health", "If pollution is the cause, dirtier air harms lungs and hearts."),
        ),
        mitigate=("Cut particulate pollution and biomass burning, which also improves health.",),
        adapt=(
            "Size solar plants using observed, not assumed, sunshine.",
            "Clean-air programmes and smoke-day advisories.",
        ),
    ),
    # ------------------------------------------------------------------- wind
    ("wind", "up"): Entry(
        polarity="mixed",
        headline="Stronger winds add wind-power potential but also storm damage, erosion and dust.",
        drivers=(
            ("Circulation changes", "Shifting pressure patterns and storm tracks change surface wind speeds."),
            ("Land-cover change", "Less vegetation and fewer buildings mean less surface friction."),
            ("Decadal variability", "Surface winds vary in multi-decade swings that can look like trends."),
        ),
        impacts=(
            ("energy", "Wind farms produce more electricity."),
            ("infrastructure", "More damage from wind storms."),
            ("agriculture", "Soil erosion and crop damage on open ground."),
            ("ecosystems", "More dust and faster spread of fire."),
        ),
        mitigate=(),
        adapt=(
            "Wind-resilient building codes and roof standards.",
            "Windbreaks and shelterbelts on farmland.",
            "Refresh wind-resource assessments.",
        ),
    ),
    ("wind", "down"): Entry(
        polarity="mixed",
        headline="Calmer winds reduce wind-power output and let air pollution build up.",
        drivers=(
            ("Circulation changes", "Surface winds over many land areas weakened for decades ('stilling') before partly recovering in the 2010s, linked to circulation changes."),
            ("Rougher land surfaces", "More vegetation, crops and buildings slow winds near the ground."),
            ("Decadal variability", "Surface winds vary in multi-decade swings that can look like trends."),
        ),
        impacts=(
            ("energy", "Wind farms produce less electricity than planned."),
            ("health", "Stagnant air lets pollution and heat linger."),
        ),
        mitigate=(),
        adapt=(
            "Diversify the energy mix and review wind-farm yield forecasts.",
            "Air-quality management for stagnant periods.",
        ),
    ),
    # -------------------------------------------------------------- water mass
    ("water_mass", "down"): Entry(
        polarity="concerning",
        headline="Falling total water storage points to groundwater depletion or ice and lake loss.",
        drivers=(
            ("Groundwater pumping beyond recharge", "Where more is drawn out than rain refills, aquifers fall steadily."),
            ("Prolonged drought", "Multi-year dry spells drain soils, rivers and aquifers together."),
            ("Melting ice", "Loss of glaciers and ice sheets removes stored water mass."),
        ),
        impacts=(
            ("water", "Wells run dry and cities and farms lose their supply."),
            ("agriculture", "Irrigated farming depends on groundwater and becomes uncertain."),
            ("infrastructure", "Over-pumped ground can sink, damaging buildings, canals and roads."),
            ("cryosphere", "Ice loss adds to sea-level rise."),
        ),
        mitigate=("Limit warming to slow ice loss.", "End over-extraction so storage can stabilise.", _GLOBAL_NOTE),
        adapt=(
            "Groundwater metering, pumping limits and managed recharge.",
            "Efficient irrigation and crop choices matched to available water.",
            "Water reuse and diversified supplies.",
        ),
    ),
    ("water_mass", "up"): Entry(
        polarity="mixed",
        headline="Rising water storage can mean recovery after drought — or flooding and rising water tables.",
        drivers=(
            ("Wetter years", "Above-average rain and snow add to soil, groundwater and surface water."),
            ("Reduced extraction or new reservoirs", "Pumping limits or new storage raise the total stored."),
            ("Ice or snow accumulation", "More snow and ice hold more water on land."),
        ),
        impacts=(
            ("water", "Supplies recover."),
            ("infrastructure", "High water tables can flood basements and damage foundations."),
            ("agriculture", "Salinity and waterlogging where drainage is poor."),
        ),
        mitigate=(),
        adapt=("Monitor water tables and drainage.", "Store surplus water for the next dry spell."),
    ),
}

# What the UI shows for a variable with no curated profile: honest, not invented.
GENERIC_ENTRY = Entry(
    polarity="neutral",
    headline="This variable does not have a curated cause-and-impact profile yet.",
    drivers=(),
    impacts=(),
    mitigate=(),
    adapt=(),
)

# Place-type additions: (family, direction, region kind) -> extras.
KIND_EXTRAS: dict[tuple[str, str, str], Extra] = {
    ("temperature", "up", "ice"): Extra(
        impacts=(("cryosphere", "Melting ice and thawing ground add to sea-level rise and destabilise buildings and pipelines."),),
        mitigate=("Emission cuts are the only lever that slows ice loss.",),
        adapt=("Monitor and engineer for thaw-prone ground.",),
    ),
    ("temperature", "up", "plateau"): Extra(
        impacts=(("water", "Glacier melt changes river flows downstream — more water at first, then less as glaciers shrink."),),
        adapt=("Plan downstream water supply for the 'peak water' turning point.",),
    ),
    ("precipitation", "down", "plain"): Extra(
        impacts=(("water", "Irrigated plains lean on groundwater, so falling rain speeds over-pumping."),),
        adapt=("Shift to less water-hungry crops and cap pumping.",),
    ),
    ("soil", "down", "plain"): Extra(
        impacts=(("water", "Irrigated plains lean on groundwater, so drying soils speed over-pumping."),),
        adapt=("Cap pumping and shift to less water-hungry crops.",),
    ),
    ("precipitation", "down", "basin"): Extra(
        adapt=("Coordinated basin-wide water allocation, including agreements across borders where the river is shared.",),
    ),
    ("soil", "down", "basin"): Extra(
        adapt=("Coordinated basin-wide water allocation, including agreements across borders where the river is shared.",),
    ),
}

# Additions for specific places, where the region "kind" is too coarse (no
# region is tagged "delta": Bangladesh is a country, the Mekong a basin).
_DELTA_RAIN = Extra(
    impacts=(("infrastructure", "Low-lying deltas add storm-surge, river-flood and salt-intrusion risk to heavy rain."),),
    adapt=("Embankments, cyclone shelters and salt-tolerant crops.",),
)
REGION_EXTRAS: dict[tuple[str, str, str], Extra] = {
    ("precipitation", "up", "bangladesh"): _DELTA_RAIN,
    ("precipitation", "up", "mekong_lower_basin"): _DELTA_RAIN,
}

# One hedged sentence of place-specific background per region.
REGION_CONTEXT: dict[str, str] = {
    "bangladesh": "A low-lying delta nation exposed to floods, cyclones, sea-level rise and salt intrusion.",
    "indo_gangetic_plain": "An intensively irrigated farming belt where groundwater depletion has been documented by satellite gravity data.",
    "amazon_core": "A rainforest sensitive to deforestation, fire and drought; some research warns of a possible shift toward savanna if clearing and warming continue.",
    "sahel_west_africa": "Severe droughts in the 1970s and 1980s were followed by a partial rainfall recovery; the region remains highly variable and exposed to both drought and flash floods.",
    "horn_of_africa": "Recurrent drought and food insecurity, strongly influenced by El Niño and the Indian Ocean Dipole.",
    "california_central_valley": "A major farming region that relies heavily on irrigation and groundwater pumping, with land subsidence in places.",
    "mekong_lower_basin": "A densely populated river basin and delta affected by upstream dams, delta subsidence and salt intrusion.",
    "murray_darling_basin": "Australia's largest river system, which went through the multi-year Millennium Drought (roughly 1997–2009).",
    "arctic_alaska_north_slope": "Permafrost tundra in a part of the world that is warming faster than the global average.",
    "lake_chad_basin": "Lake Chad has shrunk substantially since the 1960s, with both drought and water withdrawals cited as causes.",
    "congo_basin": "The second-largest tropical rainforest, an important store of carbon.",
    "tibetan_plateau": "A glacier-fed plateau at the source of major Asian rivers, where glaciers have been retreating.",
    "greenland_south": "The Greenland Ice Sheet has been losing mass, and its margins are where melt is most active.",
    "west_antarctica": "The Amundsen Sea sector is a focus of ice-loss research.",
    "great_plains_us": "A major grain region above the Ogallala Aquifer, which has been heavily drawn down.",
    "yangtze_basin": "China's longest river basin: heavily dammed and densely populated.",
    "nile_valley": "A desert river valley that depends almost entirely on Nile flow, managed through upstream dams and shared between countries.",
    "patagonia": "The southern Andes, where glaciers have been retreating.",
    "southeast_australia": "A drought- and bushfire-prone region.",
    "indus_basin": "A glacier- and monsoon-fed basin on which Pakistani agriculture depends.",
    "iberian_peninsula": "A Mediterranean-climate region where warming, drying and wildfire risk are of growing concern.",
    "east_africa_rift_lakes": "Rift-valley lakes whose levels and surrounding flood risk are sensitive to rainfall variability.",
}


@dataclass(frozen=True)
class Reference:
    label: str
    url: str


def references_for(family: str) -> list[Reference]:
    keys = FAMILY_REFERENCES.get(family, FAMILY_REFERENCES["generic"])
    return [Reference(*REFERENCES[k]) for k in keys]
