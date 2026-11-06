"""Hot/cool street pairs from Mapillary photos (Phase 2).

A "street" here is the set of recent photos inside one H3 hex, named after the
road OpenStreetMap places at their centre. Flow:

    candidates -> fetch -> (segment.py on a GPU) -> qa -> build
"""

import json
import math
import random
import time
from datetime import date

import h3
import numpy as np
import pandas as pd
import requests
from PIL import Image
from tqdm import tqdm

from . import config, mapillary

HEX_TABLE = config.INTERIM / "hex_table.parquet"
CANDIDATES = config.INTERIM / "street_candidates.csv"
IMAGES = config.INTERIM / "street_images.parquet"
IMAGE_DIR = config.RAW / "mapillary" / "images"
SEGMENTATION = config.INTERIM / "segmentation.parquet"
QA_DIR = config.INTERIM / "qa"
SUGGESTED = config.INTERIM / "street_pairs_suggested.json"
NAMES_CACHE = config.INTERIM / "street_names.json"

PIPELINE = config.ROOT / "pipeline"
SELECTED = PIPELINE / "streets_selected.json"  # hand-curated pairs, committed
THUMBS_APPROVED = PIPELINE / "thumbs_approved.txt"  # one Mapillary image id per line
WEB_THUMBS = config.ROOT / "web" / "public" / "streets"

MIN_IMAGES = 10
MAX_IMAGES = 30
MAX_PER_SIDE = 40
MAX_PHOTO_AGE_YEARS = 5
GATE_PAIRS = 5

# A thumbnail is only a candidate if it shows almost no people and is not a building facade.
THUMB_MAX_PERSON = 0.001
THUMB_MAX_BUILDING = 0.35

LICENCE = "Street photos and images derived from them: Mapillary contributors, CC-BY-SA 4.0"


def km(a_lat, a_lng, b_lat, b_lng) -> float:
    p = math.pi / 180
    h = (math.sin((b_lat - a_lat) * p / 2) ** 2
         + math.cos(a_lat * p) * math.cos(b_lat * p) * math.sin((b_lng - a_lng) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def people_within(table: pd.DataFrame, lat: float, lng: float, metres: int = 500) -> int:
    """Residents of hexes whose centre lies within `metres` (k=2 ring covers ~650 m)."""
    centre = h3.latlng_to_cell(lat, lng, config.H3_RES)
    total = 0.0
    for c in h3.grid_disk(centre, 2):
        if c not in table.index:
            continue
        c_lat, c_lng = h3.cell_to_latlng(c)
        if km(lat, lng, c_lat, c_lng) * 1000 <= metres:
            total += float(table.at[c, "pop"] or 0)
    return int(round(total, -2))


# --- naming ---------------------------------------------------------------

def _name_cache() -> dict:
    return json.loads(NAMES_CACHE.read_text()) if NAMES_CACHE.exists() else {}


def street_name(lat: float, lng: float, cache: dict) -> dict:
    key = f"{lat:.5f},{lng:.5f}"
    if key not in cache:
        time.sleep(1.1)  # Nominatim policy: at most one request per second
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lng, "zoom": 17, "format": "jsonv2", "accept-language": "en"},
            headers={"User-Agent": "delhi-heat-gap-pipeline"},
            timeout=60,
        )
        resp.raise_for_status()
        addr = resp.json().get("address", {})
        cache[key] = {
            "road": addr.get("road") or addr.get("pedestrian") or addr.get("residential"),
            "area": addr.get("neighbourhood") or addr.get("suburb") or addr.get("quarter")
            or addr.get("city_district"),
        }
        NAMES_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    return cache[key]


# --- steps ----------------------------------------------------------------

def candidates() -> pd.DataFrame:
    """Hot (decile 10) and cool (deciles 1-2, residential) hexes with enough recent photos."""
    table = pd.read_parquet(HEX_TABLE)
    counts = mapillary.coverage()
    t = table.join(counts, how="left", rsuffix="_c")
    t["mapillary"] = t.get("mapillary_c", t.get("mapillary")).fillna(0)
    ok = t["mapillary"] >= MIN_IMAGES
    hot = t[ok & (t["decile"] == 10)].nlargest(MAX_PER_SIDE, "lst_day").assign(kind="hot")
    cool = t[ok & t["decile"].between(1, 2) & (t["pop"] >= config.BUILT_MIN_POP / 2)]
    cool = cool.nsmallest(MAX_PER_SIDE, "lst_day").assign(kind="cool")

    passed = min(len(hot), len(cool)) >= GATE_PAIRS
    print(f"Coverage gate: {len(hot)} hot and {len(cool)} cool hexes with {MIN_IMAGES}+ photos "
          f"since {mapillary.MIN_YEAR} -> {'PASS' if passed else 'FAIL: record your own streets'}")

    pts = pd.read_parquet(mapillary.POINTS)
    centres = pts.groupby("h")[["lat", "lng"]].median()
    cache = _name_cache()
    rows = []
    for h, r in tqdm(list(pd.concat([hot, cool]).iterrows()), desc="Naming"):
        lat, lng = centres.loc[h] if h in centres.index else h3.cell_to_latlng(h)
        name = street_name(lat, lng, cache)
        rows.append({"h": h, "kind": r["kind"], "lst_day": round(r["lst_day"], 1),
                     "images": int(r["mapillary"]), "lat": lat, "lng": lng, **name})
    df = pd.DataFrame(rows)
    df.to_csv(CANDIDATES, index=False)
    print(f"Wrote {CANDIDATES}")
    return df


def fetch() -> pd.DataFrame:
    """Download up to MAX_IMAGES recent photos per candidate hex."""
    cands = pd.read_csv(CANDIDATES)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    oldest = date.today().year - MAX_PHOTO_AGE_YEARS
    rows = []
    for h in tqdm(cands["h"], desc="Hexes"):
        imgs = [i for i in mapillary.images_in_hex(h, MAX_IMAGES) if i["year"] >= oldest]
        if len(imgs) < MIN_IMAGES:
            continue
        for img in imgs:
            path = IMAGE_DIR / f"{img['id']}.jpg"
            if not path.exists() and img["thumb_url"]:
                resp = requests.get(img["thumb_url"], timeout=60)
                if resp.ok:
                    path.write_bytes(resp.content)
            if path.exists():
                rows.append({k: v for k, v in img.items() if k != "thumb_url"})
    df = pd.DataFrame(rows)
    df.to_parquet(IMAGES)
    print(f"Fetched {len(df)} images for {df['h'].nunique() if len(df) else 0} streets into {IMAGE_DIR}")
    print(f"Next, on a GPU:  python segment.py {IMAGE_DIR} {SEGMENTATION} --qa-dir {QA_DIR}")
    return df


def qa_sheet() -> None:
    """CSV for the 50-image hand check: fill in your own tree % next to the model's."""
    seg = pd.read_parquet(SEGMENTATION).set_index("id")
    ids = [p.stem for p in sorted(QA_DIR.glob("*.jpg"))]
    sheet = pd.DataFrame({
        "id": ids,
        "overlay": [str(QA_DIR / f"{i}.jpg") for i in ids],
        "model_tree_pct": [round(seg.at[i, "tree"] * 100) for i in ids],
        "your_tree_pct": "",
    })
    out = config.INTERIM / "qa_sheet.csv"
    sheet.to_csv(out, index=False)
    print(f"Wrote {out}. If tree % is off by more than ~10 points on many rows, try another checkpoint.")


def _street_stats(images: pd.DataFrame, seg: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    df = images.merge(seg, on="id")
    g = df.groupby("h")
    out = pd.DataFrame({
        "tree_pct": g["tree"].mean() * 100,
        "sky_pct": g["sky"].mean() * 100,
        "building_pct": g["building"].mean() * 100,
        "road_pct": g["road"].mean() * 100,
        "n_images": g.size(),
        "year_min": g["year"].min(),
        "year_max": g["year"].max(),
        "credits": g["creator"].agg(lambda s: sorted(set(s))),
    })
    return out.join(cands.set_index("h")).round({"tree_pct": 0, "sky_pct": 0, "building_pct": 0, "road_pct": 0})


def suggest_pairs(stats: pd.DataFrame, n: int = 5) -> list[dict]:
    """Biggest heat differences first, preferring pairs within ~10 km; no street used twice."""
    hot, cool = stats[stats["kind"] == "hot"], stats[stats["kind"] == "cool"]
    options = []
    for hh, a in hot.iterrows():
        for ch, b in cool.iterrows():
            d = km(a["lat"], a["lng"], b["lat"], b["lng"])
            diff = a["lst_day"] - b["lst_day"]
            options.append((diff - max(0, d - 10) * 0.3, hh, ch, round(diff, 1), round(d, 1)))
    used, pairs = set(), []
    for _, hh, ch, diff, d in sorted(options, reverse=True):
        if hh in used or ch in used:
            continue
        used |= {hh, ch}
        pairs.append({"hot": hh, "cool": ch, "diff_c": diff, "distance_km": d})
        if len(pairs) == n:
            break
    return pairs


def _thumb(h: str, images: pd.DataFrame, seg: pd.DataFrame, approved: set) -> dict:
    df = images[images["h"] == h].merge(seg, on="id")
    ok = df[(df["person"] <= THUMB_MAX_PERSON) & (df["building"] <= THUMB_MAX_BUILDING)]
    for _, r in ok.assign(score=ok["road"] + ok["sky"]).sort_values("score", ascending=False).iterrows():
        WEB_THUMBS.mkdir(parents=True, exist_ok=True)
        dest = WEB_THUMBS / f"{r['id']}.webp"
        if r["id"] in approved:
            if not dest.exists():
                im = Image.open(IMAGE_DIR / f"{r['id']}.jpg").convert("RGB")
                im.thumbnail((720, 720))
                im.save(dest, "WEBP", quality=70)
            return {"thumb": f"streets/{dest.name}", "thumb_credit": r["creator"], "thumb_year": int(r["year"])}
    return {"thumb": None, "thumb_review": ok["id"].head(3).tolist()}


def _street(h: str, s: pd.Series, table: pd.DataFrame, images, seg, approved, override: str | None):
    name = override or s.get("road") or "Unnamed street"
    return {
        "name": name,
        "area": s.get("area") if isinstance(s.get("area"), str) else None,
        "h": h,
        "lat": round(float(s["lat"]), 5),
        "lng": round(float(s["lng"]), 5),
        "lst_day": float(s["lst_day"]),
        "tree_pct": int(s["tree_pct"]),
        "sky_pct": int(s["sky_pct"]),
        "building_pct": int(s["building_pct"]),
        "road_pct": int(s["road_pct"]),
        "people_500m": people_within(table, s["lat"], s["lng"]),
        "n_images": int(s["n_images"]),
        "years": [int(s["year_min"]), int(s["year_max"])],
        "credits": s["credits"],
        **_thumb(h, images, seg, approved),
    }


def build() -> dict:
    table = pd.read_parquet(HEX_TABLE)
    images = pd.read_parquet(IMAGES)
    seg = pd.read_parquet(SEGMENTATION)
    stats = _street_stats(images, seg, pd.read_csv(CANDIDATES))
    approved = set(THUMBS_APPROVED.read_text().split()) if THUMBS_APPROVED.exists() else set()

    suggested = suggest_pairs(stats)
    SUGGESTED.write_text(json.dumps(suggested, indent=1))
    if SELECTED.exists():
        chosen = json.loads(SELECTED.read_text())
        print(f"Using {len(chosen)} hand-picked pairs from {SELECTED.name}")
    else:
        chosen = suggested
        print(f"No {SELECTED.name} yet; using {len(chosen)} suggested pairs. Copy {SUGGESTED} there to curate.")

    pairs = []
    for i, p in enumerate(chosen, 1):
        hot = _street(p["hot"], stats.loc[p["hot"]], table, images, seg, approved, p.get("hot_name"))
        cool = _street(p["cool"], stats.loc[p["cool"]], table, images, seg, approved, p.get("cool_name"))
        pairs.append({"id": f"p{i}", "hot": hot, "cool": cool,
                      "diff_c": round(hot["lst_day"] - cool["lst_day"], 1)})

    hot_tree = stats.loc[stats["kind"] == "hot", "tree_pct"]
    cool_tree = stats.loc[stats["kind"] == "cool", "tree_pct"]
    out = {
        "sample": False,
        "generated": date.today().isoformat(),
        "licence": LICENCE,
        "shade_gap_pct": round(float(cool_tree.mean() - hot_tree.mean()), 1),
        "shade": {"hot_tree_pct": round(float(hot_tree.mean()), 1), "n_hot": int(len(hot_tree)),
                  "cool_tree_pct": round(float(cool_tree.mean()), 1), "n_cool": int(len(cool_tree))},
        "pairs": pairs,
        "credits": sorted({c for cs in stats["credits"] for c in cs}),
    }
    _write(out)
    pending = [x for p in pairs for x in (p["hot"], p["cool"]) if not x["thumb"]]
    if pending:
        print(f"{len(pending)} streets have no approved thumbnail. Look at the ids under "
              f"'thumb_review' in streets.json; add safe ones (road or skyline only, no people "
              f"or recognisable homes) to {THUMBS_APPROVED.name} and rerun build.")
    print("Then rerun `run.py export` so city_stats.json picks up the shade gap.")
    return out


def _write(out: dict) -> None:
    config.WEB_DATA.mkdir(parents=True, exist_ok=True)
    path = config.WEB_DATA / "streets.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"Wrote {path}")


# --- synthetic -----------------------------------------------------------

def sample(table: pd.DataFrame, n: int = 3, seed: int = 7) -> dict:
    """SYNTHETIC street pairs for site development, drawn from the sample hex table."""
    rng = random.Random(seed)
    b = table[table["decile"] > 0]
    hot = b[b["decile"] == 10].sample(n, random_state=seed)
    cool = b[(b["decile"] == 1) & (b["pop"] > config.BUILT_MIN_POP)].sample(n, random_state=seed)

    def street(h, r, kind, i):
        lat, lng = h3.cell_to_latlng(h)
        tree = rng.randint(2, 9) if kind == "hot" else rng.randint(28, 45)
        sky = rng.randint(30, 45) if kind == "hot" else rng.randint(10, 22)
        building = rng.randint(25, 40) if kind == "hot" else rng.randint(15, 25)
        return {"name": f"Sample {kind} street {i}", "area": "Synthetic data", "h": h,
                "lat": round(lat, 5), "lng": round(lng, 5), "lst_day": round(float(r["lst_day"]), 1),
                "tree_pct": tree, "sky_pct": sky, "building_pct": building,
                "road_pct": 100 - tree - sky - building - rng.randint(5, 12),
                "people_500m": people_within(table, lat, lng), "n_images": rng.randint(12, 30),
                "years": [2023, 2025], "credits": ["sample-data"], "thumb": None}

    pairs = []
    for i, ((hh, a), (ch, c)) in enumerate(zip(hot.iterrows(), cool.iterrows()), 1):
        hs, cs = street(hh, a, "hot", i), street(ch, c, "cool", i)
        pairs.append({"id": f"p{i}", "hot": hs, "cool": cs, "diff_c": round(hs["lst_day"] - cs["lst_day"], 1)})
    hot_t = np.mean([p["hot"]["tree_pct"] for p in pairs])
    cool_t = np.mean([p["cool"]["tree_pct"] for p in pairs])
    out = {"sample": True, "generated": date.today().isoformat(), "licence": LICENCE,
           "shade_gap_pct": round(float(cool_t - hot_t), 1),
           "shade": {"hot_tree_pct": round(float(hot_t), 1), "n_hot": n,
                     "cool_tree_pct": round(float(cool_t), 1), "n_cool": n},
           "pairs": pairs, "credits": ["sample-data"]}
    _write(out)
    return out
