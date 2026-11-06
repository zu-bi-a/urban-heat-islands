"""Planetary Computer STAC helpers (no account needed)."""

import os

import planetary_computer
import pystac_client

from . import config

# Blob reads fail transiently on long runs; retry inside GDAL before giving up.
for key, val in {
    "GDAL_HTTP_MAX_RETRY": "6",
    "GDAL_HTTP_RETRY_DELAY": "3",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "VSI_CACHE": "TRUE",
}.items():
    os.environ.setdefault(key, val)

# Passed to odc.stac.load: a tile that still fails is left empty, not fatal.
LOAD_KW = {"fail_on_error": False}

PC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def catalog() -> pystac_client.Client:
    return pystac_client.Client.open(PC_URL, modifier=planetary_computer.sign_inplace)


def season_ranges(years) -> list[str]:
    start, end = config.MONTHS
    last_day = {4: 30, 6: 30, 5: 31}[end]
    return [f"{y}-{start:02d}-01/{y}-{end:02d}-{last_day}" for y in years]


def search(collection: str, bbox, years, query: dict | None = None) -> list:
    items = []
    cat = catalog()
    for dt in season_ranges(years):
        found = cat.search(collections=[collection], bbox=bbox, datetime=dt, query=query or {})
        items.extend(found.items())
    return items
