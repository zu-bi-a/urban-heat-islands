"""Mapillary API v4: coverage counts and per-street image metadata.

Needs a free client access token in MAPILLARY_TOKEN
(https://www.mapillary.com/dashboard/developers).
"""

import os
import time
from datetime import datetime, timezone

import h3
import mapbox_vector_tile
import mercantile
import pandas as pd
import requests
from tqdm import tqdm

from . import config
from .aoi import aoi_bbox

TILE_URL = "https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}"
GRAPH_URL = "https://graph.mapillary.com/images"
TILE_Z = 14  # the image layer is only served at z14

MIN_YEAR = 2021
MIN_MS = int(datetime(MIN_YEAR, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

POINTS = config.INTERIM / "mapillary_points.parquet"
COUNTS = config.INTERIM / "mapillary_counts.parquet"
TILE_CACHE = config.RAW / "mapillary_tiles"


def token() -> str:
    tok = os.environ.get("MAPILLARY_TOKEN")
    if not tok:
        raise RuntimeError("Set MAPILLARY_TOKEN (free client token from mapillary.com/dashboard/developers)")
    return tok


def _get(url: str, params: dict, tries: int = 4) -> requests.Response:
    for attempt in range(tries):
        resp = requests.get(url, params=params, timeout=60)
        if resp.status_code < 500 and resp.status_code != 429:
            return resp
        time.sleep(2 ** attempt)
    resp.raise_for_status()
    return resp


def _tile_points(t: mercantile.Tile) -> list[dict]:
    cache = TILE_CACHE / f"{t.z}_{t.x}_{t.y}.mvt"
    if cache.exists():
        data = cache.read_bytes()
    else:
        resp = _get(TILE_URL.format(z=t.z, x=t.x, y=t.y), {"access_token": token()})
        if resp.status_code == 404:
            data = b""
        else:
            resp.raise_for_status()
            data = resp.content
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    if not data:
        return []

    layer = mapbox_vector_tile.decode(data, default_options={"y_coord_down": True}).get("image")
    if not layer:
        return []
    extent = layer.get("extent", 4096)
    b = mercantile.bounds(t)
    out = []
    for f in layer["features"]:
        x, y = f["geometry"]["coordinates"]
        # Tile pixels -> lng/lat via the tile's Web Mercator bounds.
        lng = b.west + (b.east - b.west) * x / extent
        merc = mercantile.xy(b.west, b.north)[1] - (
            mercantile.xy(b.west, b.north)[1] - mercantile.xy(b.west, b.south)[1]
        ) * y / extent
        lat = mercantile.lnglat(0, merc).lat
        p = f["properties"]
        out.append(
            {
                "id": str(p.get("id")),
                "lat": lat,
                "lng": lng,
                "captured_at": p.get("captured_at"),
                "is_pano": bool(p.get("is_pano", False)),
                "sequence_id": p.get("sequence_id"),
            }
        )
    return out


def coverage(force: bool = False) -> pd.DataFrame:
    """Recent (2021+) non-panoramic images per hex, plus a cached point table."""
    if COUNTS.exists() and not force:
        return pd.read_parquet(COUNTS)
    w, s, e, n = aoi_bbox()
    tiles = list(mercantile.tiles(w, s, e, n, TILE_Z))
    rows = []
    for t in tqdm(tiles, desc="Mapillary tiles"):
        rows += _tile_points(t)
    pts = pd.DataFrame(rows)
    if pts.empty:
        raise RuntimeError("No Mapillary images found over Delhi; check the token")
    pts = pts[(pts["captured_at"] >= MIN_MS) & ~pts["is_pano"]].drop_duplicates("id")
    pts["h"] = [h3.latlng_to_cell(a, b, config.H3_RES) for a, b in zip(pts["lat"], pts["lng"])]
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    pts.to_parquet(POINTS)
    counts = pts.groupby("h").size().rename("mapillary").to_frame()
    counts.to_parquet(COUNTS)
    print(f"Mapillary: {len(pts)} images since {MIN_YEAR} in {len(counts)} hexes")
    return counts


def images_in_hex(cell: str, limit: int = 30) -> list[dict]:
    """Most recent non-pano images in one hex, with creator usernames for credits."""
    lats, lngs = zip(*h3.cell_to_boundary(cell))
    params = {
        "access_token": token(),
        "bbox": f"{min(lngs)},{min(lats)},{max(lngs)},{max(lats)}",
        "start_captured_at": f"{MIN_YEAR}-01-01T00:00:00Z",
        "is_pano": "false",
        "fields": "id,captured_at,creator,thumb_1024_url,computed_geometry,geometry,sequence",
        "limit": 500,
    }
    resp = _get(GRAPH_URL, params)
    resp.raise_for_status()
    out = []
    for img in resp.json().get("data", []):
        geom = img.get("computed_geometry") or img.get("geometry")
        lng, lat = geom["coordinates"]
        if h3.latlng_to_cell(lat, lng, config.H3_RES) != cell:
            continue  # bbox is wider than the hex
        out.append(
            {
                "id": img["id"],
                "h": cell,
                "lat": lat,
                "lng": lng,
                "captured_at": img["captured_at"],
                "year": datetime.fromtimestamp(img["captured_at"] / 1000, timezone.utc).year,
                "creator": (img.get("creator") or {}).get("username", "unknown"),
                "sequence": img.get("sequence"),
                "thumb_url": img.get("thumb_1024_url"),
            }
        )
    out.sort(key=lambda r: r["captured_at"], reverse=True)
    return _spread(out, limit)


def _spread(images: list[dict], limit: int) -> list[dict]:
    """Take images from as many sequences as possible so one drive does not dominate."""
    by_seq: dict = {}
    for img in images:
        by_seq.setdefault(img["sequence"], []).append(img)
    picked, queues = [], list(by_seq.values())
    while queues and len(picked) < limit:
        for q in list(queues):
            if q:
                picked.append(q.pop(0))
            if not q:
                queues.remove(q)
            if len(picked) >= limit:
                break
    return picked
