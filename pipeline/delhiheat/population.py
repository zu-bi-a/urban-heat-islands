"""People per hex from WorldPop (total, under-5, 65+).

Rasters are read over HTTP with a window around Delhi, so the national files
are never downloaded in full.
"""

import pandas as pd
import rioxarray
import xarray as xr

from . import config
from .aoi import aoi_bbox
from .zonal import aggregate

OUT = config.INTERIM / "population.parquet"


def _window(url: str) -> xr.DataArray:
    da = rioxarray.open_rasterio(f"/vsicurl/{url}", masked=True).squeeze("band", drop=True)
    w, s, e, n = aoi_bbox()
    pad = 0.01
    return da.rio.clip_box(w - pad, s - pad, e + pad, n + pad).load()


def _age_sum(ages) -> xr.DataArray:
    total = None
    for sex in ("m", "f"):
        for age in ages:
            da = _window(config.WORLDPOP_AGE_URL.format(sex=sex, age=age)).fillna(0)
            total = da if total is None else total + da
    return total


def per_hex(force: bool = False) -> pd.DataFrame:
    if OUT.exists() and not force:
        return pd.read_parquet(OUT)
    df = pd.DataFrame(
        {
            "pop": aggregate(_window(config.WORLDPOP_POP_URL), "sum"),
            "u5": aggregate(_age_sum(config.AGES_CHILDREN), "sum"),
            "o65": aggregate(_age_sum(config.AGES_OLDER), "sum"),
        }
    ).fillna(0)
    # The 2020 age rasters have different totals from the 2025 counts; keep their
    # shares and apply them to the newer total so the groups never exceed it.
    all_ages = (0, 1, *range(5, 85, 5))  # WorldPop bands: 0, 1-4, 5-9 ... 80+
    age_total = aggregate(_age_sum(all_ages), "sum").reindex(df.index)
    share = lambda col: (df[col] / age_total).clip(0, 1).fillna(0)
    df["u5"] = df["pop"] * share("u5")
    df["o65"] = df["pop"] * share("o65")
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT)
    return df
