"""NCT of Delhi boundary."""

import geopandas as gpd
import requests

from . import config


def load_aoi() -> gpd.GeoDataFrame:
    """Return the NCT boundary as a single-row GeoDataFrame in EPSG:4326."""
    if not config.AOI_FILE.exists():
        config.RAW.mkdir(parents=True, exist_ok=True)
        resp = requests.get(config.AOI_URL, timeout=300)
        resp.raise_for_status()
        states = gpd.read_file(resp.text)
        match = states[states["shapeName"].str.lower().str.contains(config.AOI_NAME_MATCH)]
        if len(match) != 1:
            raise RuntimeError(f"Expected one Delhi row, got {match['shapeName'].tolist()}")
        match[["shapeName", "geometry"]].to_file(config.AOI_FILE, driver="GeoJSON")
    return gpd.read_file(config.AOI_FILE).to_crs(4326).dissolve()


def aoi_bbox() -> tuple[float, float, float, float]:
    return tuple(load_aoi().total_bounds)
