"""Per-hex table and the four headline metrics.

All headline numbers use built-up hexes only (see config.BUILT_*), which drops
the Yamuna, the ridge forest and farmland but keeps leafy residential areas.
"""

import numpy as np
import pandas as pd

from . import config


def round_people(x: float, step: int = 10_000) -> int:
    return int(round(x / step) * step)


def built_mask(df: pd.DataFrame) -> pd.Series:
    built = df.get("built", pd.Series(0, index=df.index)).fillna(0)
    water = df.get("water", pd.Series(0, index=df.index)).fillna(0)
    pop = df.get("pop", pd.Series(0, index=df.index)).fillna(0)
    return ((built >= config.BUILT_MIN_FRACTION) | (pop >= config.BUILT_MIN_POP)) & (
        water < config.WATER_MAX_FRACTION
    ) & df["lst_day"].notna()


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Adds is_built, decile (1 = coolest, 10 = hottest; 0 = not built) and night retention."""
    df = df.copy()
    df["is_built"] = built_mask(df)
    b = df["is_built"]
    ranks = df.loc[b, "lst_day"].rank(pct=True, method="first")
    df["decile"] = 0
    df.loc[b, "decile"] = np.ceil(ranks * 10).clip(1, 10).astype(int)
    if "lst_night" in df:
        df["night_ret"] = df["lst_night"] - df.loc[b, "lst_night"].median()
    return df


def headline(df: pd.DataFrame, streets: dict | None = None) -> dict:
    b = df[df["is_built"]]
    hot, cool = b[b["decile"] == 10], b[b["decile"] == 1]
    out = {
        "built_hex_count": int(len(b)),
        "median_day_c": round(float(b["lst_day"].median()), 1),
        "hot10_median_c": round(float(hot["lst_day"].median()), 1),
        "cool10_median_c": round(float(cool["lst_day"].median()), 1),
        "heat_gap_c": round(float(hot["lst_day"].median() - cool["lst_day"].median()), 1),
        "decile_breaks_c": [
            round(float(b["lst_day"].quantile(q / 10)), 1) for q in range(1, 10)
        ],
    }
    if "pop" in df:
        out.update(
            people_in_heat=round_people(hot["pop"].sum()),
            children_u5_in_heat=round_people(hot["u5"].sum(), 1_000),
            older_65_in_heat=round_people(hot["o65"].sum(), 1_000),
            total_people=round_people(b["pop"].sum(), 100_000),
            hot10_tree_pct=round(float(hot["tree"].mean() * 100), 1) if "tree" in df else None,
            cool10_tree_pct=round(float(cool["tree"].mean() * 100), 1) if "tree" in df else None,
        )
    if "lst_night" in df and df["lst_night"].notna().any():
        out["median_night_c"] = round(float(b["lst_night"].median()), 1)
        out["hot10_night_ret_c"] = round(float(hot["night_ret"].median()), 1)
    out["shade_gap_pct"] = (streets or {}).get("shade_gap_pct")
    return out
