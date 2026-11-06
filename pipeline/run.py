"""Delhi Heat Gap pipeline entry point.

    python run.py sample          # synthetic data for site development
    python run.py all             # full real pipeline (slow; see README)
    python run.py landsat|viirs|population|green|places   # one step, cached in data/interim
    python run.py check           # Landsat-only hotspot sanity check (Phase 0 step 4)
    python run.py export          # rebuild web/public/data from cached steps
"""

import argparse
import json

import pandas as pd

from delhiheat import checks, config, export, metrics, wards
from delhiheat.grid import build_grid


def _publish(grid, table, places, ward_gdf, sample: bool) -> None:
    streets_file = config.WEB_DATA / "streets.json"
    streets = json.loads(streets_file.read_text()) if streets_file.exists() else None
    hotspots = checks.hotspot_deciles(table)
    checks.report(hotspots)
    export.write_pmtiles(export.hexes_geojson(grid, table))
    export.write_json(
        "city_stats.json",
        export.city_stats(metrics.headline(table, streets), hotspots, sample),
    )
    export.write_json("wards.json", wards.summary(ward_gdf))
    export.write_json("places.json", places)


def run_sample() -> None:
    from delhiheat import sample, streets

    grid, table, places = sample.build()
    print(f"SAMPLE: {len(grid)} hexes (synthetic values, do not publish)")
    streets.sample(table)
    _publish(grid, table, places, None, sample=True)


def assemble(grid) -> pd.DataFrame:
    from delhiheat import green, landsat, population, viirs
    from delhiheat.zonal import aggregate, sample_at

    table = pd.DataFrame(index=grid["h"])
    table["lst_day"] = aggregate(landsat.composite(), "median", "lst_day")
    try:
        night = viirs.composite()
        table["lst_night"] = sample_at(night, grid["lat"].to_numpy(), grid["lng"].to_numpy())
    except Exception as exc:  # night layer is optional for a first export
        print(f"VIIRS skipped: {exc}")
    table = table.join(population.per_hex()).join(green.per_hex())
    mapillary = config.INTERIM / "mapillary_counts.parquet"
    if mapillary.exists():
        table = table.join(pd.read_parquet(mapillary))
    return table


def run_all() -> None:
    from delhiheat.places import fetch_places

    grid = build_grid()
    print(f"Grid: {len(grid)} res-{config.H3_RES} hexes")
    ward_gdf = wards.load_wards()
    table = assemble(grid)
    table["w"] = wards.assign(grid, ward_gdf)
    table = metrics.add_derived(table)
    table.to_parquet(config.INTERIM / "hex_table.parquet")
    _publish(grid, table, fetch_places(), ward_gdf, sample=False)


def run_check() -> None:
    from delhiheat import landsat
    from delhiheat.zonal import aggregate

    grid = build_grid()
    table = pd.DataFrame(index=grid["h"])
    table["lst_day"] = aggregate(landsat.composite(), "median", "lst_day")
    table["built"] = 1.0  # no land cover yet: treat every hex as built for this check
    table = metrics.add_derived(table)
    checks.report(checks.hotspot_deciles(table))
    h = metrics.headline(table)
    print(f"\nRough heat gap (all hexes): {h['heat_gap_c']} °C "
          f"(hot10 {h['hot10_median_c']}, cool10 {h['cool10_median_c']})")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=["sample", "all", "check", "export",
                                    "landsat", "viirs", "population", "green", "places"])
    p.add_argument("--force", action="store_true", help="ignore cached interim files")
    a = p.parse_args()

    if a.step == "sample":
        run_sample()
    elif a.step == "all":
        run_all()
    elif a.step == "check":
        run_check()
    elif a.step == "export":
        grid = build_grid()
        table = pd.read_parquet(config.INTERIM / "hex_table.parquet")
        from delhiheat.places import fetch_places
        _publish(grid, table, fetch_places(), wards.load_wards(), sample=False)
    elif a.step == "places":
        from delhiheat.places import fetch_places
        export.write_json("places.json", fetch_places())
    else:
        import importlib
        mod = importlib.import_module(f"delhiheat.{a.step}")
        fn = getattr(mod, "composite", None) or getattr(mod, "per_hex")
        print(fn(force=a.force))


if __name__ == "__main__":
    main()
