"""Locality names for the search box, from OpenStreetMap (Overpass API).

Bundled as a static file so the site needs no geocoding service.
"""

import geopandas as gpd
import requests

from .aoi import load_aoi

OVERPASS = "https://overpass-api.de/api/interpreter"
PLACE_TYPES = "suburb|neighbourhood|quarter|village|town"


def fetch_places() -> list[dict]:
    w, s, e, n = load_aoi().total_bounds
    q = f"""
    [out:json][timeout:120];
    node["place"~"^({PLACE_TYPES})$"]["name"]({s},{w},{n},{e});
    out body;
    """
    resp = requests.post(OVERPASS, data={"data": q}, timeout=180,
                         headers={"User-Agent": "delhi-heat-gap-pipeline"})
    resp.raise_for_status()
    nodes = resp.json()["elements"]
    pts = gpd.GeoDataFrame(
        nodes, geometry=gpd.points_from_xy([n["lon"] for n in nodes], [n["lat"] for n in nodes]),
        crs=4326,
    )
    inside = pts[pts.within(load_aoi().geometry.iloc[0])]
    seen, out = set(), []
    for _, row in inside.iterrows():
        name = row["tags"].get("name:en") or row["tags"]["name"]
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append({"name": name, "lat": round(row["lat"], 5), "lng": round(row["lon"], 5)})
    return sorted(out, key=lambda p: p["name"])
