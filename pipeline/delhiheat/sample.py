"""SYNTHETIC data for building the site before the real pipeline has run.

Uses the real NCT boundary and H3 grid, but every value is invented from a
simple spatial pattern. city_stats.json carries "sample": true and the site
shows a banner while it is set. Never publish these numbers.
"""

import numpy as np
import pandas as pd

from .grid import build_grid
from .metrics import add_derived

# (lat, lng, strength): rough anchors so the pattern looks plausibly Delhi-shaped.
HOT = [(28.697, 77.163, 1.0), (28.726, 77.163, 0.9), (28.480, 77.131, 0.8),
       (28.800, 77.050, 0.9), (28.840, 77.090, 0.7), (28.530, 77.280, 0.7)]
COOL = [(28.605, 77.205, 1.0), (28.590, 77.170, 0.8), (28.680, 77.210, 0.6),
        (28.560, 77.240, 0.5)]
DENSE = [(28.690, 77.290, 1.0), (28.650, 77.230, 0.9), (28.720, 77.160, 0.8),
         (28.630, 77.080, 0.7)]

SAMPLE_PLACES = [
    ("Connaught Place", 28.6315, 77.2167), ("Chandni Chowk", 28.6506, 77.2303),
    ("Jahangirpuri", 28.7259, 77.1626), ("Wazirpur", 28.6970, 77.1630),
    ("Ayanagar", 28.4795, 77.1306), ("Bhalswa", 28.7400, 77.1600),
    ("Lajpat Nagar", 28.5677, 77.2433), ("Rohini", 28.7383, 77.0822),
    ("Dwarka", 28.5921, 77.0460), ("Mayur Vihar", 28.6077, 77.2958),
    ("Seelampur", 28.6640, 77.2700), ("Saket", 28.5245, 77.2066),
    ("Karol Bagh", 28.6519, 77.1909), ("Shahdara", 28.6730, 77.2890),
    ("Narela", 28.8527, 77.0929), ("Okhla", 28.5355, 77.2780),
]


def _bumps(lat, lng, anchors, scale_km):
    out = np.zeros_like(lat)
    for a_lat, a_lng, s in anchors:
        dy = (lat - a_lat) * 111
        dx = (lng - a_lng) * 111 * np.cos(np.radians(a_lat))
        out += s * np.exp(-(dx**2 + dy**2) / (2 * scale_km**2))
    return out


def build(seed: int = 7) -> tuple:
    rng = np.random.default_rng(seed)
    grid = build_grid()
    lat, lng = grid["lat"].to_numpy(), grid["lng"].to_numpy()

    hot = _bumps(lat, lng, HOT, 3.0)
    cool = _bumps(lat, lng, COOL, 2.5)
    dense = _bumps(lat, lng, DENSE, 3.5)

    tree = np.clip(0.12 + 0.45 * cool - 0.10 * hot + rng.normal(0, 0.05, len(grid)), 0.01, 0.85)
    built = np.clip(0.35 + 0.5 * dense + 0.3 * hot - 0.3 * cool + rng.normal(0, 0.1, len(grid)), 0, 1)
    pop = np.clip(400 + 3500 * dense * built + rng.gamma(2, 150, len(grid)) - 500 * cool, 0, None)
    pop[built < 0.1] *= 0.1
    day = 41 + 6 * hot - 5 * cool - 8 * (tree - 0.15) + 2 * built + rng.normal(0, 0.8, len(grid))
    night = 30 + 2.2 * dense + 1.2 * built - 1.0 * cool + rng.normal(0, 0.3, len(grid))

    table = pd.DataFrame(
        {
            "lst_day": day,
            "lst_night": night,
            "pop": pop,
            "u5": pop * rng.uniform(0.07, 0.10, len(grid)),
            "o65": pop * rng.uniform(0.04, 0.08, len(grid)),
            "tree": tree,
            "built": built,
            "water": np.zeros(len(grid)),
            "ndvi": np.clip(0.1 + 0.6 * tree, 0, 0.8),
            "w": pd.array([pd.NA] * len(grid), dtype="Int64"),
            "mapillary": rng.poisson(np.where(dense > 0.3, 12, 2)),
        },
        index=grid["h"],
    )
    table = add_derived(table)
    places = [{"name": n, "lat": a, "lng": b} for n, a, b in SAMPLE_PLACES]
    return grid, table, places
