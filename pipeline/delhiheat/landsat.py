"""Daytime surface temperature: Landsat 8/9 C2 L2, Apr–Jun median 2022–2026."""

import numpy as np
import rioxarray  # noqa: F401  (registers .rio)
import xarray as xr
from odc.stac import load

from . import config
from .aoi import aoi_bbox, load_aoi
from .stac import LOAD_KW, search

OUT = config.INTERIM / "lst_day_c.tif"

# QA_PIXEL bits: 0 fill, 1 dilated cloud, 2 cirrus, 3 cloud, 4 cloud shadow.
QA_BAD = 0b11111


def composite(force: bool = False) -> xr.DataArray:
    if OUT.exists() and not force:
        return rioxarray.open_rasterio(OUT, masked=True).squeeze("band", drop=True)

    bbox = aoi_bbox()
    items = search(
        "landsat-c2-l2",
        bbox,
        config.YEARS,
        query={
            "platform": {"in": ["landsat-8", "landsat-9"]},
            "eo:cloud_cover": {"lt": config.MAX_SCENE_CLOUD},
        },
    )
    print(f"Landsat: {len(items)} scenes")
    if not items:
        raise RuntimeError("No Landsat scenes found")

    ds = load(
        items,
        bands=["lwir11", "qa_pixel"],
        bbox=bbox,
        crs=config.UTM,
        resolution=30,
        groupby="solar_day",
        chunks={"x": 1024, "y": 1024},
        **LOAD_KW,
    )
    clear = (ds.qa_pixel & QA_BAD) == 0
    lst = ds.lwir11.where(clear & (ds.lwir11 > 0)) * config.LST_SCALE + config.LST_OFFSET - 273.15

    # Clip to the NCT before judging scene quality so empty corners do not count.
    aoi = load_aoi().to_crs(config.UTM)
    # The raw band's nodata=0 survives the arithmetic; reset it or clip fills with 0 °C.
    lst = lst.rio.write_crs(config.UTM).rio.write_nodata(np.nan, encoded=False)
    lst = lst.rio.clip(aoi.geometry, drop=True)

    # Pre-monsoon haze and partial scenes: keep days where most of Delhi is clear.
    ones = xr.ones_like(lst.isel(time=0), dtype="float32").compute()
    inside = ones.rio.write_crs(config.UTM).rio.clip(aoi.geometry).notnull()
    clear_frac = lst.notnull().where(inside).sum(dim=["x", "y"]).compute() / int(inside.sum())
    keep = clear_frac >= config.MIN_SCENE_CLEAR
    lst = lst.sel(time=keep.values)
    print(f"Landsat: kept {int(keep.sum())} of {keep.size} days after clear-sky filter")

    med = lst.chunk({"time": -1}).median("time").compute()
    med = med.where(np.isfinite(med)).astype("float32")
    med.name = "lst_day"
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    med.rio.write_crs(config.UTM).rio.to_raster(OUT, compress="deflate")
    return med
