"""Street-view pipeline (Phase 2). Needs MAPILLARY_TOKEN and a real `run.py all` first.

    python run_streets.py nus          # is Delhi in NUS Global Streetscapes?
    python run_streets.py coverage     # images per hex + go/no-go gate
    python run_streets.py candidates   # hot/cool hexes with enough photos, named via OSM
    python run_streets.py fetch        # download photos for candidates
    python segment.py ...              # on a GPU (command is printed by fetch)
    python run_streets.py qa           # 50-image hand-check sheet
    python run_streets.py build        # streets.json + approved thumbnails
"""

import argparse
import io

import pandas as pd
import requests

from delhiheat import mapillary, streets

NUS_CITIES = "https://huggingface.co/datasets/NUS-UAL/global-streetscapes/resolve/main/cities688.csv"


def nus() -> None:
    cities = pd.read_csv(io.StringIO(requests.get(NUS_CITIES, timeout=60).text))
    hits = cities[cities["admin_name"].str.contains("Delhi", na=False)
                  | cities["city"].str.contains("Delhi", na=False)]
    if hits.empty:
        print("Delhi is not in NUS Global Streetscapes.")
    for _, r in hits.iterrows():
        print(f"{r['city']}: {r['img_count']} images "
              "(too few to replace our own segmentation if this is in the low thousands)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=["nus", "coverage", "candidates", "fetch", "qa", "build"])
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    if a.step == "nus":
        nus()
    elif a.step == "coverage":
        print(mapillary.coverage(force=a.force).describe())
    else:
        {"candidates": streets.candidates, "fetch": streets.fetch,
         "qa": streets.qa_sheet, "build": streets.build}[a.step]()


if __name__ == "__main__":
    main()
