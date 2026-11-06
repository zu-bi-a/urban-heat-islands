"""Night surface temperature: VIIRS VNP21A1N (1 km), Apr–Jun median.

Needs a free NASA Earthdata login (~/.netrc, or EARTHDATA_USERNAME and
EARTHDATA_PASSWORD in the environment).
"""

import earthaccess
import h5py
import numpy as np
import rioxarray  # noqa: F401
import xarray as xr
from rasterio.transform import from_origin

from . import config
from .aoi import aoi_bbox, load_aoi
from .stac import season_ranges

OUT = config.INTERIM / "lst_night_c.tif"
RAW_DIR = config.RAW / "viirs"

# MODIS/VIIRS sinusoidal grid constants.
SINU = "+proj=sinu +R=6371007.181 +nadgrids=@null +wktext"
TILE_M = 1111950.5197665233
X0, Y0 = -20015109.355798, 10007554.677899
N_PIX = 1200


def _read_granule(path) -> np.ndarray:
    with h5py.File(path, "r") as f:
        lst_ds = qc_ds = None

        def find(name, obj):
            nonlocal lst_ds, qc_ds
            if isinstance(obj, h5py.Dataset):
                leaf = name.rsplit("/", 1)[-1]
                if leaf == "LST_1KM":
                    lst_ds = obj
                elif leaf == "QC":
                    qc_ds = obj

        f.visititems(find)
        if lst_ds is None:
            raise RuntimeError(f"LST_1KM not found in {path}")
        raw = lst_ds[()].astype("float64")
        scale = float(np.ravel(lst_ds.attrs.get("scale_factor", [0.02]))[0])
        offset = float(np.ravel(lst_ds.attrs.get("add_offset", [0.0]))[0])
        fill = float(np.ravel(lst_ds.attrs.get("_FillValue", [0]))[0])
        lst = np.where(raw == fill, np.nan, raw * scale + offset - 273.15)
        if qc_ds is not None:
            # Bits 0-1 (mandatory QA): 0 = good, 1 = produced, other quality.
            mandatory = qc_ds[()] & 0b11
            lst = np.where(mandatory <= 1, lst, np.nan)
    return lst


def composite(force: bool = False) -> xr.DataArray:
    if OUT.exists() and not force:
        return rioxarray.open_rasterio(OUT, masked=True).squeeze("band", drop=True)

    earthaccess.login()  # tries environment variables, then ~/.netrc
    bbox = aoi_bbox()
    granules = []
    for dt in season_ranges(config.YEARS):
        start, end = dt.split("/")
        granules += earthaccess.search_data(
            short_name=config.VIIRS_SHORT_NAME, bounding_box=bbox, temporal=(start, end)
        )
    granules = [g for g in granules if config.VIIRS_TILE in str(g.data_links())]
    print(f"VIIRS: {len(granules)} granules on tile {config.VIIRS_TILE}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = earthaccess.download(granules, str(RAW_DIR))

    stack = np.stack([_read_granule(p) for p in files])
    med = np.nanmedian(stack, axis=0).astype("float32")

    h, v = int(config.VIIRS_TILE[1:3]), int(config.VIIRS_TILE[4:6])
    px = TILE_M / N_PIX
    transform = from_origin(X0 + h * TILE_M, Y0 - v * TILE_M, px, px)
    xs = transform.c + px * (np.arange(N_PIX) + 0.5)
    ys = transform.f - px * (np.arange(N_PIX) + 0.5)
    da = xr.DataArray(med, coords={"y": ys, "x": xs}, dims=("y", "x"), name="lst_night")
    da = da.rio.write_crs(SINU).rio.write_transform(transform)

    da = da.rio.reproject(config.UTM, resolution=1000)
    da = da.rio.clip(load_aoi().to_crs(config.UTM).geometry.buffer(2000), drop=True)
    da = da.where(np.isfinite(da))
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    da.rio.to_raster(OUT, compress="deflate")
    return da
