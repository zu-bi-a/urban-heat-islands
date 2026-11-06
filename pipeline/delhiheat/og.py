"""Link-preview image (web/public/og.png, 1200×630) drawn from the hex table.

A small heat map of Delhi plus the headline heat gap, so previews on WhatsApp
and elsewhere carry the story's main number. Sample data is watermarked.
"""

from pathlib import Path

import h3
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from . import config

W, H = 1200, 630
BG = (246, 243, 238)
INK = (31, 27, 22)
INK2 = (90, 82, 73)
HOT = (190, 50, 46)
NOT_BUILT = (207, 202, 193)
# Same ramp as web/src/palette.js.
DECILES = ["#fff1c2", "#fde09c", "#fcc87a", "#fbac5e", "#f58d4a",
           "#ea6b3c", "#d84c33", "#be322e", "#9c1f2b", "#701425"]

SERIF = ["/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
         "C:/Windows/Fonts/georgiab.ttf"]
SANS = ["/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf"]
SANS_BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf"]


def _font(paths, size):
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _draw_map(img: Image.Image, table: pd.DataFrame, box):
    x0, y0, x1, y1 = box
    cells = table.index.to_list()
    centres = np.array([h3.cell_to_latlng(c) for c in cells])
    lat_min, lat_max = centres[:, 0].min(), centres[:, 0].max()
    lng_min, lng_max = centres[:, 1].min(), centres[:, 1].max()
    # Equirectangular with cos(lat) correction is plenty at city scale.
    kx = np.cos(np.radians((lat_min + lat_max) / 2))
    span_x, span_y = (lng_max - lng_min) * kx, lat_max - lat_min
    scale = min((x1 - x0) / span_x, (y1 - y0) / span_y)
    ox = x0 + ((x1 - x0) - span_x * scale) / 2
    oy = y0 + ((y1 - y0) - span_y * scale) / 2
    draw = ImageDraw.Draw(img)
    dec = table["decile"].to_numpy()
    for c, d in zip(cells, dec):
        pts = [(ox + (lng - lng_min) * kx * scale, oy + (lat_max - lat) * scale)
               for lat, lng in h3.cell_to_boundary(c)]
        draw.polygon(pts, fill=_hex_rgb(DECILES[int(d) - 1]) if d > 0 else NOT_BUILT)


def write(table: pd.DataFrame, stats: dict, sample: bool) -> Path:
    # Draw at 2x and downsample for smooth hexagon edges.
    s = 2
    img = Image.new("RGB", (W * s, H * s), BG)
    _draw_map(img, table, (640 * s, 30 * s, 1170 * s, 600 * s))
    draw = ImageDraw.Draw(img)

    draw.text((60 * s, 64 * s), "DELHI HEAT GAP", font=_font(SANS_BOLD, 24 * s), fill=INK2)
    draw.text((60 * s, 110 * s), f"{stats['heat_gap_c']:.1f} °C", font=_font(SERIF, 112 * s), fill=HOT)
    lines = ["between Delhi’s hottest and", "coolest neighbourhoods"]
    for i, line in enumerate(lines):
        draw.text((60 * s, (250 + i * 50) * s), line, font=_font(SERIF, 40 * s), fill=INK)
    draw.text((60 * s, 380 * s), "Who lives in the heat, and why some", font=_font(SANS, 26 * s), fill=INK2)
    draw.text((60 * s, 414 * s), "streets run hotter. Find your own.", font=_font(SANS, 26 * s), fill=INK2)
    draw.text((60 * s, 540 * s), f"Daytime surface temperature (satellite), {config.PERIOD_LABEL}",
              font=_font(SANS, 19 * s), fill=INK2)
    if sample:
        draw.text((60 * s, 480 * s), "SAMPLE DATA, NOT REAL", font=_font(SANS_BOLD, 30 * s), fill=HOT)

    out = config.ROOT / "web" / "public" / "og.png"
    img.resize((W, H), Image.LANCZOS).save(out, optimize=True)
    print(f"Wrote {out} ({out.stat().st_size / 1e3:.0f} kB)")
    return out
