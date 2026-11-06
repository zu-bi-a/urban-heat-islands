"""Green cover per hex: Sentinel-2 NDVI and ESA WorldCover land-cover shares."""

import numpy as np
import pandas as pd
from odc.stac import load

from . import config
from .aoi import aoi_bbox
from .stac import LOAD_KW, catalog, search
from .zonal import aggregate, fractions

OUT = config.INTERIM / "green.parquet"

# Sentinel-2 SCL classes to drop: cloud shadow, cloud medium/high, cirrus.
SCL_BAD = (3, 8, 9, 10)

# ESA WorldCover classes.
WORLDCOVER = {"tree": 10, "built": 50, "water": 80, "crop": 40, "bare": 60}


def ndvi_per_hex(bbox) -> pd.Series:
    items = search(
        "sentinel-2-l2a",
        bbox,
        config.S2_YEARS,
        query={"eo:cloud_cover": {"lt": config.MAX_SCENE_CLOUD}},
    )
    print(f"Sentinel-2: {len(items)} scenes")
    ds = load(
        items,
        bands=["B04", "B08", "SCL"],
        bbox=bbox,
        crs=config.UTM,
        resolution=30,  # matches Landsat; plenty for a per-hex mean
        groupby="solar_day",
        chunks={"x": 1024, "y": 1024},
        **LOAD_KW,
    )
    ok = ~ds.SCL.isin(SCL_BAD) & (ds.SCL > 0)
    # Processing baseline 04.00+ (all scenes since 2022) adds a +1000 offset to reflectance.
    red = (ds.B04.where(ok).astype("float32") - 1000).clip(min=0)
    nir = (ds.B08.where(ok).astype("float32") - 1000).clip(min=0)
    ndvi = ((nir - red) / (nir + red)).chunk({"time": -1}).median("time").compute()
    ndvi = ndvi.where(np.isfinite(ndvi)).rio.write_crs(config.UTM)
    return aggregate(ndvi, "mean", "ndvi")


def worldcover_per_hex(bbox) -> pd.DataFrame:
    items = list(catalog().search(collections=["esa-worldcover"], bbox=bbox).items())
    latest = max(items, key=lambda i: i.properties.get("esa_worldcover:product_version", ""))
    same = [i for i in items if i.datetime == latest.datetime]
    wc = load(same, bands=["map"], bbox=bbox, crs=config.UTM, resolution=10, **LOAD_KW).map.isel(time=0)
    return fractions(wc.rio.write_crs(config.UTM), WORLDCOVER)


def per_hex(force: bool = False) -> pd.DataFrame:
    if OUT.exists() and not force:
        return pd.read_parquet(OUT)
    bbox = aoi_bbox()
    df = worldcover_per_hex(bbox).join(ndvi_per_hex(bbox), how="outer")
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT)
    return df
