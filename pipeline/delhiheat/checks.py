"""Sanity check: Heat Wave Action Plan 2026 hotspots should sit in hot deciles.

Large disagreement usually means a pipeline bug (bad scaling, clouds left in,
wrong projection), not a finding.
"""

import h3
import pandas as pd

from . import config


def hotspot_deciles(table: pd.DataFrame) -> list[dict]:
    out = []
    for name, (lat, lng) in config.HAP_HOTSPOTS.items():
        centre = h3.latlng_to_cell(lat, lng, config.H3_RES)
        # Look at the hex and its ring of neighbours; locality centres are approximate.
        ring = [c for c in h3.grid_disk(centre, 1) if c in table.index]
        rows = table.loc[ring]
        rows = rows[rows["decile"] > 0]
        decile = int(rows["decile"].median()) if len(rows) else None
        out.append({"name": name, "decile": decile})
    return out


def report(hotspots: list[dict]) -> bool:
    ok = True
    print("\nHeat Wave Action Plan hotspot check (decile 10 = hottest):")
    for h in hotspots:
        flag = "ok" if h["decile"] and h["decile"] >= 7 else "CHECK"
        ok &= flag == "ok"
        print(f"  {h['name']:<14} decile {h['decile']}  {flag}")
    if not ok:
        print("  Some hotspots are not in the hottest 30%. Inspect the composite before publishing.")
    return ok
