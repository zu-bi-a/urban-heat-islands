# Delhi Heat Gap

A free, mobile-first scroll story showing who in Delhi lives in the most heat, and why their streets run hotter. It ends with a two-street comparison card readers can share.

- `pipeline/`: offline Python pipeline. It runs once and writes static files.
- `web/`: the static site (Vite + MapLibre + Scrollama). Added in Phase 3.
- `DATA_CONTRACT.md`: the files the pipeline hands to the site.

Scope: the whole NCT of Delhi (MCD, NDMC and Cantonment), H3 resolution-9 hexes (about 0.1 km²).

## Pipeline setup

```bash
cd pipeline
uv venv --python 3.12 .venv          # or python3.12 -m venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
brew install tippecanoe              # PMTiles export
```

### Sample data (for site development)

```bash
.venv/bin/python run.py sample
```

This writes **synthetic** values on the real Delhi hex grid to `web/public/data/`. `city_stats.json` gets `"sample": true`, and the site shows a banner while that flag is set. Never publish sample data.

### Real data

| Step | Command | Needs |
|------|---------|-------|
| Landsat sanity check (Phase 0) | `run.py check` | Network only (Planetary Computer, no account) |
| Daytime heat | `run.py landsat` | Network only |
| Night heat | `run.py viirs` | Free [NASA Earthdata](https://urs.earthdata.nasa.gov/) login in `~/.netrc` or `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` |
| Population | `run.py population` | Network. Check the WorldPop URLs in `delhiheat/config.py` first |
| Green cover | `run.py green` | Network only (heaviest step) |
| Everything + export | `run.py all` | All of the above. Optionally add `data/raw/mcd_wards_2022.geojson` from OpenCity |

Each step caches its result in `data/interim/`. Pass `--force` to recompute. `run.py export` rebuilds the web files from the cache.

`run.py check` compares the hottest hexes with the Heat Wave Action Plan 2026 hotspots (Ayanagar, Wazirpur, Jahangirpuri, Bhalswa). If they are not in the hottest 30%, suspect a pipeline bug before trusting the map.

## Credits

Landsat (USGS) · VIIRS (NASA) · WorldPop (CC-BY 4.0) · ESA WorldCover (CC-BY 4.0) · Sentinel-2 (Copernicus) · MCD wards via OpenCity · Mapillary contributors (CC-BY-SA 4.0) · OpenFreeMap / © OpenStreetMap contributors. Analysts should also see Artha Global's Delhi Climate & Health Explorer (link in the PRD sources).
