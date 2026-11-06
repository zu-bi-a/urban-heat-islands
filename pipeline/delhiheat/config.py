"""Central settings for the offline pipeline. Edit here, not in the modules."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
WEB_DATA = ROOT / "web" / "public" / "data"

# Working projection: UTM 43N covers all of Delhi (72-78 E).
UTM = "EPSG:32643"
H3_RES = 9

# Area of interest: whole NCT of Delhi (MCD + NDMC + Cantonment).
AOI_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/"
    "gbOpen/IND/ADM1/geoBoundaries-IND-ADM1_simplified.geojson"
)
AOI_NAME_MATCH = "delhi"
AOI_FILE = RAW / "nct_delhi.geojson"

# Season and years for every satellite composite.
YEARS = range(2022, 2027)
MONTHS = (4, 6)  # April to June inclusive
PERIOD_LABEL = "Apr–Jun 2022–2026"
MAX_SCENE_CLOUD = 20  # percent, scene-level metadata filter
MIN_SCENE_CLEAR = 0.5  # drop scenes where less than half the AOI is clear

# Landsat C2 L2 surface temperature scaling (USGS).
LST_SCALE = 0.00341802
LST_OFFSET = 149.0

# Sentinel-2 is heavy; one recent season is enough for NDVI.
S2_YEARS = range(2025, 2027)

# VIIRS night LST (needs a free Earthdata login: ~/.netrc or EARTHDATA_USERNAME/PASSWORD).
VIIRS_SHORT_NAME = "VNP21A1N"
VIIRS_TILE = "h24v06"  # sinusoidal tile containing Delhi

# WorldPop. Verify these URLs on hub.worldpop.org before a real run; they are read
# remotely with a window over Delhi, so the full India rasters are never downloaded.
WORLDPOP_POP_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/IND/v1/"
    "100m/constrained/ind_pop_2025_CN_100m_R2025A_v1.tif"
)
WORLDPOP_POP_VERSION = "WorldPop R2025A v1, 2025, constrained, 100 m (alpha release)"
WORLDPOP_AGE_URL = (
    "https://data.worldpop.org/GIS/AgeSex_structures/Global_2000_2020/2020/IND/"
    "ind_{sex}_{age}_2020.tif"
)
AGES_CHILDREN = (0, 1)  # under 5
AGES_OLDER = (65, 70, 75, 80)  # 65 and over

# MCD wards 2022 from OpenCity. Download the GeoJSON by hand into this path;
# column names vary between uploads, so they are detected in wards.py.
WARDS_FILE = RAW / "mcd_wards_2022.geojson"

# Which hexes count as "built-up" for the headline metrics. This keeps leafy
# residential areas (the cool end of the story) but drops the Yamuna, the ridge
# forest and farmland.
BUILT_MIN_FRACTION = 0.15  # WorldCover built-up share of the hex
BUILT_MIN_POP = 500  # or at least this many residents (~5,000 per km²)
WATER_MAX_FRACTION = 0.5

# Heat Wave Action Plan 2026 hotspots, used only as a sanity check on the
# composite. Coordinates are approximate locality centres; verify before relying on them.
HAP_HOTSPOTS = {
    "Ayanagar": (28.4795, 77.1306),
    "Wazirpur": (28.6970, 77.1630),
    "Jahangirpuri": (28.7259, 77.1626),
    "Bhalswa": (28.7400, 77.1600),
}
# Hotspots named for high *air* temperature at a weather station (Ayanagar
# recorded 45.5 °C). Surface heat need not agree, so these are shown but not
# counted as pass/fail.
AIR_STATION_HOTSPOTS = {"Ayanagar"}
