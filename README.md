# Delhi Heat Gap

A free, mobile-first scroll story showing who in Delhi lives in the most heat, and why their streets run hotter. It ends with a two-street comparison card readers can share.

- `pipeline/`: offline Python pipeline. It runs once and writes static files.
- `web/`: the static site (Vite + MapLibre + Scrollama). Added in Phase 3.
- `DATA_CONTRACT.md`: the files the pipeline hands to the site.

Scope: the whole NCT of Delhi (MCD, NDMC and Cantonment), H3 resolution-9 hexes (about 0.1 km²).

## Site

```bash
cd web
npm install
npm run dev            # http://localhost:5173
npm run build          # static files in web/dist; fails on sample data
npm run build:sample   # local test build of the sample data (never deploy it)
```

Deploying to Cloudflare Pages, environment variables, and everything still to do before launch: see [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md). How the map is made is explained to readers at `/methods.html`.

The site reads only `web/public/data/` (see `DATA_CONTRACT.md`). A fresh checkout already has sample data. Run `pipeline/run.py sample` to regenerate it.

- **Phones:** the map fills the screen and chapter cards scroll over it.
- **From 900 px wide:** text column on the left, sticky map on the right.
- **The map:** doesn't capture scrolling until chapter 6, where it becomes draggable and zoomable.

**Links and sharing**

- `/#n=<hex>&ll=<lat>,<lng>` opens the explorer on one hexagon. It's what readers get when they pick an area.
- `/#place=<slug>` opens it on a locality.
- `npm run build` also writes one small page per locality to `dist/p/<slug>/`, so links like `/p/rohini/` get a proper WhatsApp/Instagram preview ("How hot is Rohini?") before forwarding into the explorer.
- Set `VITE_SITE_URL=https://your.domain` when building. It's printed on share cards and used for preview links; it defaults to the current origin.
- Share cards use the native share sheet on touch devices and download a PNG everywhere else.

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

### Street photos (Phase 2)

These steps need a free Mapillary client token (`export MAPILLARY_TOKEN=...`) and a finished `run.py all`.

```bash
.venv/bin/python run_streets.py coverage     # images per hex since 2021, prints PASS/FAIL gate
.venv/bin/python run.py all                  # rerun so hexes get the `mc` coverage count
.venv/bin/python run_streets.py candidates   # hot/cool hexes with 10+ photos, named via OSM
.venv/bin/python run_streets.py fetch        # downloads ≤30 photos per street
```

Segmentation runs on a GPU. In Colab or Kaggle, upload `pipeline/segment.py`, `requirements-vision.txt` and `data/raw/mapillary/images/`, then:

```bash
pip install -r requirements-vision.txt
python segment.py images/ segmentation.parquet --qa-dir qa/
```

Copy `segmentation.parquet` and `qa/` back into `data/interim/`, then:

```bash
.venv/bin/python run_streets.py qa      # data/interim/qa_sheet.csv: hand-check 50 images
.venv/bin/python run_streets.py build   # web/public/data/streets.json
.venv/bin/python run.py export          # pulls the shade gap into city_stats.json
```

**Gate fails (thin coverage)?** Record 4–6 streets yourself with the Mapillary app, upload them, wait for processing, then rerun from `coverage`.

**Curating pairs.** `build` writes suggestions to `data/interim/street_pairs_suggested.json`. Copy it to `pipeline/streets_selected.json` and edit it: drop pairs, and add `hot_name` / `cool_name` to fix OSM names.

**Thumbnails need a human.** None is published until its Mapillary image id is in `pipeline/thumbs_approved.txt`. `streets.json` lists up to three model-screened candidates per street under `thumb_review`. Approve only road or skyline shots with no people and no recognisable homes. Derived images stay CC-BY-SA.

NUS Global Streetscapes (checked 2026-10-25) lists only 1,371 images for "New Delhi", too few to reuse. Rerun the check with `run_streets.py nus`.

## Credits

Landsat (USGS) · VIIRS (NASA) · WorldPop (CC-BY 4.0) · ESA WorldCover (CC-BY 4.0) · Sentinel-2 (Copernicus) · MCD wards via OpenCity · Mapillary contributors (CC-BY-SA 4.0) · OpenFreeMap / © OpenStreetMap contributors. Analysts should also see Artha Global's Delhi Climate & Health Explorer (link in the PRD sources).
