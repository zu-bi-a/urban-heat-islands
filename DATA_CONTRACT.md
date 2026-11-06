# Data contract: pipeline → site

The pipeline writes these static files to `web/public/data/`. The site reads nothing else.

## `hexes.pmtiles`

Vector tiles, layer `hexes`, zooms 8–13. One polygon per H3 resolution-9 cell inside the NCT of Delhi.

| Key   | Meaning                                                        | Unit / range        |
|-------|----------------------------------------------------------------|---------------------|
| `h`   | H3 cell id                                                     | string              |
| `d`   | Daytime surface temperature, Apr–Jun median 2022–2026 (Landsat) | °C, 1 dp            |
| `n`   | Night surface temperature (VIIRS, 1 km, sampled at hex centre) | °C, 1 dp, optional  |
| `nr`  | Night retention: `n` minus the built-up median of `n`          | °C, 1 dp, optional  |
| `p`   | Residents (WorldPop, modelled)                                 | people              |
| `u5`  | Children under 5                                               | people              |
| `o65` | Adults 65 and over                                             | people              |
| `t`   | Tree cover (ESA WorldCover class 10)                           | % of hex            |
| `v`   | NDVI × 100 (Sentinel-2)                                        | −100 to 100         |
| `dc`  | Heat decile among built-up hexes: 1 coolest, 10 hottest; 0 = not built-up (river, forest, farmland) | 0–10 |
| `w`   | MCD ward number (blank in NDMC and Cantonment areas)           | integer, optional   |
| `mc`  | Mapillary images in the hex since 2021 (Phase 2)               | count, optional     |

## `city_stats.json`

Headline numbers, all computed over built-up hexes only.

- `sample` — **true for synthetic data.** The site shows a warning banner while it is true. Never publish with `true`.
- `periods.day`, `periods.night`, `periods.day_label`, `periods.night_label`
- `heat_gap_c` — median of hottest-10% hexes minus median of coolest-10%
- `hot10_median_c`, `cool10_median_c`, `median_day_c`, `median_night_c`, `hot10_night_ret_c`
- `decile_breaks_c` — 9 thresholds between deciles (legend)
- `people_in_heat` (rounded to 10,000), `children_u5_in_heat`, `older_65_in_heat` (to 1,000), `total_people`
- `hot10_tree_pct`, `cool10_tree_pct`
- `shade_gap_pct` — from street photos (Phase 2), else null
- `hotspots` — `[{name, decile}]`, the Heat Wave Action Plan sanity check
- `credits`, `versions`, `generated`

## `wards.json`

`[{no, name, lat, lng, bbox: [w, s, e, n]}]` — empty list if the ward file was not supplied.

## `places.json`

`[{name, lat, lng}]` — OSM locality names for search.

## `streets.json`

Hot/cool street pairs for chapter 5 and the "Two streets" card. A "street" is the recent Mapillary photos inside one hex, named after the OSM road at their centre.

- `sample`: **true for synthetic data** (names read "Sample hot street 1").
- `licence`: CC-BY-SA notice for photos and anything derived from them.
- `shade_gap_pct`: mean vegetation-view % on cool streets minus hot streets, over every segmented candidate street, not just the pairs.
- `shade`: `{hot_tree_pct, n_hot, cool_tree_pct, n_cool}`
- `credits`: every Mapillary username whose photos were used.
- `pairs`: `[{id, diff_c, hot: Street, cool: Street}]`

Street:

| Key | Meaning |
|-----|---------|
| `name`, `area` | OSM road and neighbourhood (can be hand-overridden) |
| `h`, `lat`, `lng` | Hex and photo-cluster centre |
| `lst_day` | Hex daytime surface temperature, °C |
| `tree_pct`, `sky_pct`, `building_pct`, `road_pct` | Mean pixel share across the street's photos ("tree" = all vegetation) |
| `people_500m` | Residents of hexes within 500 m, rounded to 100 |
| `n_images`, `years` | Photo count and capture-year range |
| `credits` | Mapillary usernames for this street |
| `thumb` | `streets/<id>.webp`, or `null` until a human approves one |
| `thumb_credit`, `thumb_year` | Present when `thumb` is set |
