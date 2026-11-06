"""MCD ward boundaries (2022 delimitation, from OpenCity).

The file is optional: without it hexes get no ward and search falls back to
place names. NDMC and Cantonment areas are not MCD wards and stay blank.
"""

import geopandas as gpd
import pandas as pd

from . import config

NO_COLS = ("ward_no", "wardno", "ward_num", "ward_number", "ward_id", "ward")
NAME_COLS = ("ward_name", "wardname", "name")


def _pick(cols, candidates):
    lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    return None


def load_wards() -> gpd.GeoDataFrame | None:
    if not config.WARDS_FILE.exists():
        print(f"Wards: {config.WARDS_FILE} not found, skipping")
        return None
    gdf = gpd.read_file(config.WARDS_FILE).to_crs(4326)
    no_col, name_col = _pick(gdf.columns, NO_COLS), _pick(gdf.columns, NAME_COLS)
    if not no_col or not name_col:
        raise RuntimeError(f"Could not find ward number/name columns in {list(gdf.columns)}")
    gdf = gdf.rename(columns={no_col: "no", name_col: "name"})[["no", "name", "geometry"]]
    gdf["no"] = pd.to_numeric(gdf["no"], errors="coerce").astype("Int64")
    gdf["name"] = gdf["name"].astype(str).str.strip().str.title()
    return gdf


def assign(grid: gpd.GeoDataFrame, wards: gpd.GeoDataFrame | None) -> pd.Series:
    """Ward number for each hex, by hex centre."""
    if wards is None:
        return pd.Series(pd.NA, index=grid["h"], dtype="Int64", name="w")
    pts = gpd.GeoDataFrame(
        {"h": grid["h"]}, geometry=gpd.points_from_xy(grid["lng"], grid["lat"]), crs=4326
    )
    joined = gpd.sjoin(pts, wards, how="left", predicate="within")
    return joined.drop_duplicates("h").set_index("h")["no"].rename("w")


def summary(wards: gpd.GeoDataFrame | None) -> list[dict]:
    """Small search index for the web: number, name, centre, bbox."""
    if wards is None:
        return []
    utm = wards.to_crs(config.UTM)
    centres = utm.geometry.representative_point().to_crs(4326)
    out = []
    for (_, row), c in zip(wards.iterrows(), centres):
        w, s, e, n = row.geometry.bounds
        out.append(
            {
                "no": int(row["no"]) if pd.notna(row["no"]) else None,
                "name": row["name"],
                "lat": round(c.y, 5),
                "lng": round(c.x, 5),
                "bbox": [round(v, 4) for v in (w, s, e, n)],
            }
        )
    return sorted(out, key=lambda r: (r["no"] is None, r["no"] or 0))
