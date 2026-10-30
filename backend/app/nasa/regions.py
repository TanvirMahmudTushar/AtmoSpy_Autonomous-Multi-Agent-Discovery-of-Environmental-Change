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

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class RegionDef:
    code: str
    name: str
    kind: str  # country | basin | delta | ice | plateau | plain | city | ocean | desert | lake | custom
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    notes: str
    # kinds of place, matched against each variable's place_tags (variables.yaml)
    # to suggest what to investigate here
    place_tags: tuple[str, ...] = ()

    @property
    def centroid_lat(self) -> float:
        return (self.min_lat + self.max_lat) / 2

    @property
    def centroid_lon(self) -> float:
        return (self.min_lon + self.max_lon) / 2


def custom_region(min_lat: float, max_lat: float, min_lon: float, max_lon: float, name: str | None = None) -> RegionDef:
    """A user-drawn box. The code is a stable hash of the rounded corners, so
    drawing the same box twice reuses the same stored region."""
    corners = tuple(float(round(v, 2)) for v in (min_lat, max_lat, min_lon, max_lon))  # float: 10 and 10.0 hash alike
    if not (-90 <= corners[0] < corners[1] <= 90 and -180 <= corners[2] < corners[3] <= 180):
        raise ValueError("A box needs min < max, latitudes within ±90 and longitudes within ±180.")
    digest = hashlib.sha1(repr(corners).encode()).hexdigest()[:10]
    label = name or (
        f"Custom area {abs(corners[0]):.1f}°{'S' if corners[0] < 0 else 'N'}–{abs(corners[1]):.1f}°{'S' if corners[1] < 0 else 'N'}, "
        f"{abs(corners[2]):.1f}°{'W' if corners[2] < 0 else 'E'}–{abs(corners[3]):.1f}°{'W' if corners[3] < 0 else 'E'}"
    )
    return RegionDef(f"bbox_{digest}", label, "custom", *corners, "Drawn by a user on the map.")


REGIONS: list[RegionDef] = [
    RegionDef("bangladesh", "Bangladesh", "country", 20.5, 26.7, 88.0, 92.7,
              "Low-lying delta nation, high exposure to monsoon and sea-level variability.", ("coast", "farmland", "river_basin")),
    RegionDef("indo_gangetic_plain", "Indo-Gangetic Plain", "plain", 24.0, 31.0, 75.0, 85.0,
              "Intensively irrigated agricultural belt across northern India.", ("farmland", "river_basin", "city")),
    RegionDef("amazon_core", "Central Amazon Basin", "basin", -7.0, 3.0, -69.0, -59.0,
              "Tropical rainforest core, sensitive to deforestation and drought cycles.", ("rainforest", "river_basin")),
    RegionDef("sahel_west_africa", "West Sahel", "region", 12.0, 18.0, -16.0, -6.0,
              "Semi-arid transition zone between Sahara and tropical savanna.", ("desert", "farmland")),
    RegionDef("horn_of_africa", "Horn of Africa", "region", 3.0, 13.0, 37.0, 47.0,
              "Drought- and famine-prone region of East Africa.", ("desert", "farmland")),
    RegionDef("california_central_valley", "California Central Valley", "basin", 35.0, 40.0, -122.0, -119.0,
              "Major US agricultural region with heavy groundwater/irrigation dependence.", ("farmland", "river_basin")),
    RegionDef("mekong_lower_basin", "Lower Mekong Basin", "basin", 10.0, 20.0, 100.0, 107.0,
              "Densely populated river delta and basin in Southeast Asia.", ("river_basin", "farmland", "coast")),
    RegionDef("murray_darling_basin", "Murray-Darling Basin", "basin", -35.5, -25.5, 140.5, 150.5,
              "Australia's largest river system, subject to prolonged droughts.", ("farmland", "river_basin", "desert")),
    RegionDef("arctic_alaska_north_slope", "Arctic Alaska North Slope", "region", 68.0, 72.0, -159.0, -149.0,
              "Permafrost-dominated Arctic tundra, an amplified-warming region.", ("ice", "coast")),
    RegionDef("lake_chad_basin", "Lake Chad Basin", "basin", 6.0, 15.0, 8.0, 18.0,
              "Basin surrounding a lake that has dramatically shrunk since the 1960s.", ("desert", "river_basin")),
    RegionDef("congo_basin", "Congo Basin", "basin", -5.0, 3.0, 16.0, 26.0,
              "Second-largest tropical rainforest on Earth.", ("rainforest", "river_basin")),
    RegionDef("tibetan_plateau", "Tibetan Plateau", "plateau", 28.0, 38.0, 79.0, 89.0,
              "High-elevation plateau, source of major Asian rivers, glacier-fed.", ("mountains", "ice")),
    RegionDef("greenland_south", "Southern Greenland Ice Sheet Margin", "ice", 67.0, 77.0, -47.0, -37.0,
              "Ice-sheet margin region with active melt/ablation dynamics.", ("ice",)),
    RegionDef("west_antarctica", "West Antarctica", "ice", -78.0, -70.0, -94.0, -84.0,
              "Region including the Amundsen Sea sector, notable for ice loss.", ("ice",)),
    RegionDef("great_plains_us", "US Great Plains", "plain", 35.0, 45.0, -104.0, -95.0,
              "Major grain-producing region overlying the Ogallala Aquifer.", ("farmland",)),
    RegionDef("yangtze_basin", "Yangtze River Basin", "basin", 27.0, 33.0, 109.0, 119.0,
              "China's longest river basin, heavily engineered and populated.", ("river_basin", "farmland", "city")),
    RegionDef("nile_valley", "Nile Valley (Egypt-Sudan)", "basin", 15.0, 25.0, 29.0, 35.0,
              "Arid-region river valley sustaining major agriculture and population.", ("desert", "river_basin", "farmland")),
    RegionDef("patagonia", "Patagonia", "region", -51.0, -41.0, -75.0, -65.0,
              "Southern Andes and steppe region with retreating glaciers.", ("mountains", "ice")),
    RegionDef("southeast_australia", "Southeast Australia", "region", -38.0, -28.0, 142.0, 152.0,
              "Region including the Murray basin fringe and eastern coast, fire- and drought-prone.", ("farmland", "coast")),
    RegionDef("indus_basin", "Indus Basin (Pakistan)", "basin", 25.0, 35.0, 66.0, 76.0,
              "Glacier- and monsoon-fed basin critical to Pakistani agriculture.", ("river_basin", "farmland", "mountains")),
    RegionDef("iberian_peninsula", "Iberian Peninsula", "region", 36.0, 44.0, -8.0, 2.0,
              "Mediterranean-climate peninsula facing increasing aridification.", ("farmland", "coast")),
    RegionDef("east_africa_rift_lakes", "East African Rift Lakes", "region", -3.0, 3.0, 28.0, 36.0,
              "Rift valley lake region sensitive to rainfall variability.", ("river_basin", "farmland")),
    # Megacities: 2-degree boxes, the air above the city and its suburbs.
    RegionDef("delhi", "Delhi (air above the city)", "city", 27.6, 29.6, 76.1, 78.1,
              "Fast-growing megacity with some of the world's highest particle and NO2 pollution.", ("city", "farmland")),
    RegionDef("dhaka", "Dhaka (air above the city)", "city", 22.7, 24.7, 89.4, 91.4,
              "Rapidly growing megacity on a river delta.", ("city", "river_basin")),
    RegionDef("lagos", "Lagos (air above the city)", "city", 5.5, 7.5, 2.4, 4.4,
              "Africa's largest city, growing fast along the Gulf of Guinea coast.", ("city", "coast")),
    RegionDef("beijing", "Beijing (air above the city)", "city", 38.9, 40.9, 115.4, 117.4,
              "Megacity where air-pollution controls since 2013 cut emissions sharply.", ("city",)),
    RegionDef("los_angeles", "Los Angeles (air above the city)", "city", 33.0, 35.0, -119.2, -117.2,
              "Megacity with decades of vehicle-emission controls.", ("city", "coast", "desert")),
    RegionDef("cairo", "Cairo (air above the city)", "city", 29.0, 31.0, 30.2, 32.2,
              "Desert megacity on the Nile, affected by both pollution and dust.", ("city", "desert", "river_basin")),
    # Estuaries and coasts
    RegionDef("chesapeake_bay", "Chesapeake Bay", "delta", 36.8, 39.6, -77.4, -75.6,
              "Largest US estuary, where river water, farm runoff and the Atlantic meet.", ("coast", "river_basin", "farmland")),
    RegionDef("mississippi_delta", "Mississippi Delta and Gulf coast", "delta", 28.5, 30.5, -91.5, -88.5,
              "River mouth feeding the Gulf of Mexico's seasonal low-oxygen 'dead zone'.", ("coast", "river_basin")),
    RegionDef("ganges_brahmaputra_delta", "Ganges-Brahmaputra Delta", "delta", 21.5, 24.5, 88.0, 91.0,
              "The world's largest delta, home to the Sundarbans mangroves.", ("coast", "river_basin", "farmland")),
    # Open ocean
    RegionDef("north_atlantic_warming_hole", "North Atlantic 'warming hole'", "ocean", 47.0, 57.0, -42.0, -32.0,
              "A patch of ocean south of Greenland that has cooled while most of the planet warmed.", ("ocean",)),
    RegionDef("arabian_sea", "Arabian Sea", "ocean", 10.0, 20.0, 60.0, 70.0,
              "Monsoon-driven sea between Arabia and India.", ("ocean",)),
    RegionDef("great_barrier_reef", "Great Barrier Reef waters", "ocean", -24.0, -14.0, 145.0, 155.0,
              "Coral reef system repeatedly hit by marine heatwaves and bleaching.", ("ocean", "coast")),
    # Deserts and drying lakes
    RegionDef("central_sahara", "Central Sahara", "desert", 20.0, 28.0, 5.0, 15.0,
              "The heart of the largest hot desert on Earth.", ("desert",)),
    RegionDef("atacama", "Atacama Desert", "desert", -27.0, -19.0, -71.0, -67.0,
              "One of the driest places on Earth, between the Andes and the Pacific.", ("desert", "mountains")),
    RegionDef("aral_sea", "Aral Sea", "lake", 43.0, 47.0, 58.0, 62.0,
              "Once the world's fourth-largest lake, mostly dried up after its rivers were diverted.", ("desert", "river_basin")),
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
        # specific places first, so "Beijing, China" isn't caught by "china"
        "delhi": "delhi",
        "dhaka": "dhaka",
        "lagos": "lagos",
        "beijing": "beijing",
        "los angeles": "los_angeles",
        "cairo": "cairo",
        "chesapeake": "chesapeake_bay",
        "mississippi": "mississippi_delta",
        "gulf of mexico": "mississippi_delta",
        "dead zone": "mississippi_delta",
        "ganges": "ganges_brahmaputra_delta",
        "brahmaputra": "ganges_brahmaputra_delta",
        "sundarbans": "ganges_brahmaputra_delta",
        "warming hole": "north_atlantic_warming_hole",
        "north atlantic": "north_atlantic_warming_hole",
        "arabian sea": "arabian_sea",
        "great barrier reef": "great_barrier_reef",
        "sahara": "central_sahara",
        "atacama": "atacama",
        "aral": "aral_sea",
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
