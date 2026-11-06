"""Write the static files the site reads. See DATA_CONTRACT.md for the schema."""

import json
import shutil
import subprocess
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd

from . import config

# Long column -> short tile attribute, plus rounding. Short keys keep tiles small.
TILE_ATTRS = {
    "lst_day": ("d", 1),
    "lst_night": ("n", 1),
    "night_ret": ("nr", 1),
    "pop": ("p", 0),
    "u5": ("u5", 0),
    "o65": ("o65", 0),
    "tree_pct": ("t", 0),
    "ndvi100": ("v", 0),
    "decile": ("dc", 0),
    "w": ("w", 0),
    "mapillary": ("mc", 0),
}

CREDITS = [
    "Landsat 8/9 C2 L2 surface temperature: USGS",
    "VIIRS VNP21A1N: NASA LP DAAC",
    "Population: WorldPop (CC-BY 4.0)",
    "Land cover: ESA WorldCover 2021 (CC-BY 4.0)",
    "Sentinel-2: Copernicus / ESA",
    "Wards: MCD 2022 via OpenCity",
    "Street photos: Mapillary contributors (CC-BY-SA 4.0)",
    "Basemap: OpenFreeMap, © OpenStreetMap contributors",
]


def hexes_geojson(grid: gpd.GeoDataFrame, table: pd.DataFrame) -> gpd.GeoDataFrame:
    df = table.copy()
    if "tree" in df:
        df["tree_pct"] = df["tree"] * 100
    if "ndvi" in df:
        df["ndvi100"] = df["ndvi"] * 100
    keep = grid[["h", "geometry"]].merge(df, left_on="h", right_index=True, how="inner")
    out = gpd.GeoDataFrame({"h": keep["h"]}, geometry=keep.geometry, crs=4326)
    for col, (key, nd) in TILE_ATTRS.items():
        if col not in keep:
            continue
        vals = pd.to_numeric(keep[col], errors="coerce").round(nd)
        out[key] = vals.astype("Int64") if nd == 0 else vals
    # Drop hexes with no heat value at all; they cannot be coloured.
    return out[out["d"].notna()] if "d" in out else out


def write_pmtiles(gdf: gpd.GeoDataFrame, name: str = "hexes") -> None:
    config.WEB_DATA.mkdir(parents=True, exist_ok=True)
    geojson = config.INTERIM / f"{name}.geojson"
    gdf.to_file(geojson, driver="GeoJSON", COORDINATE_PRECISION=5)
    if not shutil.which("tippecanoe"):
        raise RuntimeError(
            "tippecanoe not found (macOS: brew install tippecanoe). "
            f"GeoJSON left at {geojson}."
        )
    out = config.WEB_DATA / f"{name}.pmtiles"
    subprocess.run(
        [
            "tippecanoe", "-q", "-o", str(out), "--force",
            "-l", name, "-Z8", "-z13",
            "--no-feature-limit", "--no-tile-size-limit",
            "--detect-shared-borders", "--no-tiny-polygon-reduction",
            str(geojson),
        ],
        check=True,
    )
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")


def write_json(name: str, payload) -> None:
    config.WEB_DATA.mkdir(parents=True, exist_ok=True)
    path = config.WEB_DATA / name
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=_np))
    print(f"Wrote {path} ({path.stat().st_size / 1e3:.0f} kB)")


def _np(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    raise TypeError(type(o))


def city_stats(headline: dict, hotspots: list[dict], sample: bool) -> dict:
    return {
        "sample": sample,
        "generated": date.today().isoformat(),
        "periods": {
            "day": config.PERIOD_LABEL,
            "night": config.PERIOD_LABEL,
            "day_label": "daytime surface temperature (satellite, ~10:30 am)",
            "night_label": "night surface temperature (satellite, ~1:30 am, 1 km)",
        },
        "versions": {"population": config.WORLDPOP_POP_VERSION, "h3_res": config.H3_RES},
        **headline,
        "hotspots": hotspots,
        "credits": CREDITS,
    }
