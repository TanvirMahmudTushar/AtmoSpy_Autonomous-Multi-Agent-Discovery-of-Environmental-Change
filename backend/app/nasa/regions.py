"""Curated region gazetteer.

Every bounding box is kept to <=10 degrees per side — not a soft internal
choice, but NASA POWER's regional-query endpoint itself hard-rejects
(HTTP 422) anything larger ("please provide a maximum of 10 degree range"
in both latitude and longitude, confirmed against the live API). Getting
this wrong doesn't fail loudly: the Spatial Agent just silently skips with
a "grid analysis skipped" log line, so a region that's 1 degree too wide
quietly loses opposite-regional-trend detection — worth being exact about.
Regions were chosen to cover places with well-documented, scientifically
interesting environmental change signals (deltas, drylands, ice sheets,
agricultural basins) so discovery mode has good places to look.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionDef:
    code: str
    name: str
    kind: str  # country | basin | delta | ice | plateau | plain
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    notes: str

    @property
    def centroid_lat(self) -> float:
        return (self.min_lat + self.max_lat) / 2

    @property
    def centroid_lon(self) -> float:
        return (self.min_lon + self.max_lon) / 2


REGIONS: list[RegionDef] = [
    RegionDef("bangladesh", "Bangladesh", "country", 20.5, 26.7, 88.0, 92.7,
              "Low-lying delta nation, high exposure to monsoon and sea-level variability."),
    RegionDef("indo_gangetic_plain", "Indo-Gangetic Plain", "plain", 24.0, 31.0, 75.0, 85.0,
              "Intensively irrigated agricultural belt across northern India."),
    RegionDef("amazon_core", "Central Amazon Basin", "basin", -7.0, 3.0, -69.0, -59.0,
              "Tropical rainforest core, sensitive to deforestation and drought cycles."),
    RegionDef("sahel_west_africa", "West Sahel", "region", 12.0, 18.0, -16.0, -6.0,
              "Semi-arid transition zone between Sahara and tropical savanna."),
    RegionDef("horn_of_africa", "Horn of Africa", "region", 3.0, 13.0, 37.0, 47.0,
              "Drought- and famine-prone region of East Africa."),
    RegionDef("california_central_valley", "California Central Valley", "basin", 35.0, 40.0, -122.0, -119.0,
              "Major US agricultural region with heavy groundwater/irrigation dependence."),
    RegionDef("mekong_lower_basin", "Lower Mekong Basin", "basin", 10.0, 20.0, 100.0, 107.0,
              "Densely populated river delta and basin in Southeast Asia."),
    RegionDef("murray_darling_basin", "Murray-Darling Basin", "basin", -35.5, -25.5, 140.5, 150.5,
              "Australia's largest river system, subject to prolonged droughts."),
    RegionDef("arctic_alaska_north_slope", "Arctic Alaska North Slope", "region", 68.0, 72.0, -159.0, -149.0,
              "Permafrost-dominated Arctic tundra, an amplified-warming region."),
    RegionDef("lake_chad_basin", "Lake Chad Basin", "basin", 6.0, 15.0, 8.0, 18.0,
              "Basin surrounding a lake that has dramatically shrunk since the 1960s."),
    RegionDef("congo_basin", "Congo Basin", "basin", -5.0, 3.0, 16.0, 26.0,
              "Second-largest tropical rainforest on Earth."),
    RegionDef("tibetan_plateau", "Tibetan Plateau", "plateau", 28.0, 38.0, 79.0, 89.0,
              "High-elevation plateau, source of major Asian rivers, glacier-fed."),
    RegionDef("greenland_south", "Southern Greenland Ice Sheet Margin", "ice", 67.0, 77.0, -47.0, -37.0,
              "Ice-sheet margin region with active melt/ablation dynamics."),
    RegionDef("west_antarctica", "West Antarctica", "ice", -78.0, -70.0, -94.0, -84.0,
              "Region including the Amundsen Sea sector, notable for ice loss."),
    RegionDef("great_plains_us", "US Great Plains", "plain", 35.0, 45.0, -104.0, -95.0,
              "Major grain-producing region overlying the Ogallala Aquifer."),
    RegionDef("yangtze_basin", "Yangtze River Basin", "basin", 27.0, 33.0, 109.0, 119.0,
              "China's longest river basin, heavily engineered and populated."),
    RegionDef("nile_valley", "Nile Valley (Egypt-Sudan)", "basin", 15.0, 25.0, 29.0, 35.0,
              "Arid-region river valley sustaining major agriculture and population."),
    RegionDef("patagonia", "Patagonia", "region", -51.0, -41.0, -75.0, -65.0,
              "Southern Andes and steppe region with retreating glaciers."),
    RegionDef("southeast_australia", "Southeast Australia", "region", -38.0, -28.0, 142.0, 152.0,
              "Region including the Murray basin fringe and eastern coast, fire- and drought-prone."),
    RegionDef("indus_basin", "Indus Basin (Pakistan)", "basin", 25.0, 35.0, 66.0, 76.0,
              "Glacier- and monsoon-fed basin critical to Pakistani agriculture."),
    RegionDef("iberian_peninsula", "Iberian Peninsula", "region", 36.0, 44.0, -8.0, 2.0,
              "Mediterranean-climate peninsula facing increasing aridification."),
    RegionDef("east_africa_rift_lakes", "East African Rift Lakes", "region", -3.0, 3.0, 28.0, 36.0,
              "Rift valley lake region sensitive to rainfall variability."),
]

REGIONS_BY_CODE = {r.code: r for r in REGIONS}


def find_region_by_name(text: str) -> RegionDef | None:
    """Best-effort keyword match used by the fallback (no-LLM) question parser."""
    lowered = text.lower()
    for region in REGIONS:
        if region.name.lower() in lowered or region.code.replace("_", " ") in lowered:
            return region
    # loose alias matching for common short names
    aliases = {
        "india": "indo_gangetic_plain",
        "amazon": "amazon_core",
        "sahel": "sahel_west_africa",
        "california": "california_central_valley",
        "mekong": "mekong_lower_basin",
        "australia": "murray_darling_basin",
        "alaska": "arctic_alaska_north_slope",
        "arctic": "arctic_alaska_north_slope",
        "chad": "lake_chad_basin",
        "congo": "congo_basin",
        "tibet": "tibetan_plateau",
        "greenland": "greenland_south",
        "antarctica": "west_antarctica",
        "great plains": "great_plains_us",
        "yangtze": "yangtze_basin",
        "china": "yangtze_basin",
        "nile": "nile_valley",
        "egypt": "nile_valley",
        "patagonia": "patagonia",
        "pakistan": "indus_basin",
        "indus": "indus_basin",
        "spain": "iberian_peninsula",
        "portugal": "iberian_peninsula",
        "iberia": "iberian_peninsula",
        "east africa": "east_africa_rift_lakes",
        "horn of africa": "horn_of_africa",
        "ethiopia": "horn_of_africa",
        "somalia": "horn_of_africa",
        "bangladesh": "bangladesh",
    }
    for alias, code in aliases.items():
        if alias in lowered:
            return REGIONS_BY_CODE[code]
    return None


# Default candidate set for autonomous Discover mode: (region_code, variable_code) pairs
# spanning distinct climate stories, kept small enough to scan concurrently and fast.
DISCOVERY_CANDIDATES: list[tuple[str, str]] = [
    ("bangladesh", "T2M"),
    ("bangladesh", "PRECTOTCORR"),
    ("indo_gangetic_plain", "GWETROOT"),
    ("amazon_core", "PRECTOTCORR"),
    ("amazon_core", "GWETROOT"),
    ("sahel_west_africa", "PRECTOTCORR"),
    ("horn_of_africa", "PRECTOTCORR"),
    ("california_central_valley", "GWETROOT"),
    ("lake_chad_basin", "GWETTOP"),
    ("arctic_alaska_north_slope", "T2M"),
    ("murray_darling_basin", "GWETROOT"),
    ("tibetan_plateau", "T2M"),
    ("greenland_south", "T2M"),
    ("great_plains_us", "GWETROOT"),
    ("nile_valley", "T2M"),
    ("iberian_peninsula", "PRECTOTCORR"),
]
