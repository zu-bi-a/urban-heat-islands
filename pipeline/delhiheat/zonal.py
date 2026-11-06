"""Raster-to-hex aggregation.

Pixels are assigned to the hex containing their centre. That is accurate for
rasters finer than a res-9 hex (Landsat 30 m, Sentinel-2, WorldCover, WorldPop
100 m). Coarser rasters (VIIRS 1 km) are sampled at hex centres instead.
"""

import h3
import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

from . import config


def _pixel_cells(da: xr.DataArray, valid: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(valid)
    x = da["x"].values[xs]
    y = da["y"].values[ys]
    to_wgs = Transformer.from_crs(da.rio.crs, 4326, always_xy=True)
    lng, lat = to_wgs.transform(x, y)
    res = config.H3_RES
    return np.array([h3.latlng_to_cell(a, b, res) for a, b in zip(lat, lng)])


def aggregate(da: xr.DataArray, how: str = "mean", name: str | None = None) -> pd.Series:
    """Aggregate a 2-D raster (NaN = no data) per hex. how: mean, median or sum."""
    values = np.asarray(da.values, dtype="float64")
    valid = np.isfinite(values)
    cells = _pixel_cells(da, valid)
    s = pd.Series(values[valid]).groupby(cells)
    out = getattr(s, how)()
    out.name = name or da.name
    return out


def fractions(da: xr.DataArray, classes: dict[str, int | tuple[int, ...]]) -> pd.DataFrame:
    """Share of each hex's pixels falling in each named class (categorical raster)."""
    values = np.asarray(da.values)
    valid = values > 0
    cells = _pixel_cells(da, valid)
    v = values[valid]
    df = pd.DataFrame({"cell": cells})
    for label, codes in classes.items():
        codes = codes if isinstance(codes, tuple) else (codes,)
        df[label] = np.isin(v, codes).astype("float32")
    return df.groupby("cell").mean()


def sample_at(da: xr.DataArray, lat: np.ndarray, lng: np.ndarray) -> np.ndarray:
    """Nearest-pixel sample of a coarse raster at the given points."""
    to_crs = Transformer.from_crs(4326, da.rio.crs, always_xy=True)
    x, y = to_crs.transform(lng, lat)
    picked = da.sel(
        x=xr.DataArray(x, dims="pt"), y=xr.DataArray(y, dims="pt"), method="nearest"
    )
    return np.asarray(picked.values, dtype="float64")
