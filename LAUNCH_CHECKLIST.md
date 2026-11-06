# Launch checklist

The build refuses to run while `city_stats.json` or `streets.json` is sample data, so the first two steps can't be skipped by accident.

## 1. Real data

- [ ] `run.py check`: the hottest hexes should match the Heat Wave Action Plan thermal hotspots (Wazirpur, Jahangirpuri, Bhalswa). Ayanagar is listed for its air-temperature weather station and is informational only.
- [ ] Verify the WorldPop R2025A URL in `pipeline/delhiheat/config.py` on hub.worldpop.org, and pin the version.
- [ ] Earthdata login set up (`~/.netrc`), then `run.py viirs`.
- [ ] Download MCD wards 2022 from OpenCity to `data/raw/mcd_wards_2022.geojson`.
- [ ] `run.py all`, then spot-check a few hexes against places you know.
- [ ] Check the `hexes.pmtiles` size (estimate: a few MB).

## 2. Street photos

- [ ] `MAPILLARY_TOKEN` set; `run_streets.py coverage` passes the gate, or record 4–6 streets yourself.
- [ ] `candidates` → `fetch` → `segment.py` on a GPU → `qa` (hand-check 50 images; tree % within ~10 points).
- [ ] Curate `pipeline/streets_selected.json`: 3–5 pairs, names corrected.
- [ ] Approve thumbnails in `pipeline/thumbs_approved.txt`: road or skyline only, no people, no recognisable homes.
- [ ] `run_streets.py build`, then `run.py export` (picks up the shade gap and redraws `og.png`).

## 3. Words and facts

- [ ] Recompute every metric from scratch once (`run.py all --force`) and compare.
- [ ] Fact-check story text against sources. Chapter 1 says "warmest in more than a decade". IMD reports said 12–14 years, and pre-1969 records weren't analysed, so don't call it a record.
- [ ] **NGO wording review.** Ask at least one Delhi organisation working with heat-affected communities to read the story, both cards and the methods page.
- [ ] Read every street name and locality label shown in the pairs for unintended stigma.

## 4. Deploy (Cloudflare Pages)

- [ ] Pages project: root directory `web`, build command `npm run build`, output `dist`, `NODE_VERSION=22` or newer.
- [ ] Environment variables:
  - `VITE_SITE_URL`: the final https URL. Used for share cards and link previews.
  - `VITE_REPO_URL`: public repository. Shown on the methods page for corrections.
  - `VITE_GOATCOUNTER_CODE`: optional. Counts story completion, shares and lookups with no cookies.
  - `VITE_CF_BEACON_TOKEN`: optional. Cloudflare Web Analytics page views; or enable it in the Pages dashboard instead.
  - `VITE_TILES_URL`: optional. Only if the tiles move to R2; then add that origin to `connect-src` in `web/public/_headers`.
- [ ] After deploy, paste the site URL and a `/p/<locality>/` URL into WhatsApp and check the previews.
- [ ] Test on a real mid-range Android phone over mobile data. The headless check measured ~810 KB first load, story text at ~1.1 s and the map ready at ~3.8 s on simulated fast 4G with 4× CPU slowdown.
- [ ] Share a card from that phone: the share sheet opens with the image attached.

## 5. After launch

- [ ] Watch the PRD success metrics: completion ≥ 40%, shares ≥ 10% of completers, own-area lookups ≥ 25% of visitors.
- [ ] Re-run the street pipeline after reader photo contributions build up.
- [ ] v1.1: ward councillor message (needs ward-to-councillor data) and heat-safety links.
