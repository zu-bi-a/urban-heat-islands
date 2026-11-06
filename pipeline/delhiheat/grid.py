"""H3 resolution-9 grid over the AOI."""

import geopandas as gpd
import h3
from shapely.geometry import Polygon, mapping

from . import config
from .aoi import load_aoi


def hex_polygon(cell: str) -> Polygon:
    # h3 returns (lat, lng); shapely wants (x=lng, y=lat).
    return Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(cell)])


def build_grid() -> gpd.GeoDataFrame:
    """Every res-9 cell whose centre falls inside the NCT boundary."""
    aoi = load_aoi().geometry.iloc[0]
    cells = set()
    for part in getattr(aoi, "geoms", [aoi]):
        cells.update(h3.geo_to_cells(mapping(part), config.H3_RES))
    cells = sorted(cells)
    centres = [h3.cell_to_latlng(c) for c in cells]
    return gpd.GeoDataFrame(
        {
            "h": cells,
            "lat": [c[0] for c in centres],
            "lng": [c[1] for c in centres],
        },
        geometry=[hex_polygon(c) for c in cells],
        crs=4326,
    )
