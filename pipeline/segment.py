"""Street-photo segmentation (Phase 2, step 2). Run on a GPU: Colab or Kaggle.

Standalone on purpose: it needs only requirements-vision.txt, not the geo stack.

    python segment.py IMAGES_DIR OUT.parquet [--model ID] [--qa-dir DIR --qa-n 50]

Writes one row per image: share of pixels that are vegetation, sky, building,
road and person. The camera's own vehicle (Ego Vehicle, Car Mount) is left out
of the denominator.
"""

import argparse
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from transformers import AutoImageProcessor, Mask2FormerForUniversalSegmentation

DEFAULT_MODEL = "facebook/mask2former-swin-large-mapillary-vistas-semantic"

GROUPS = {
    "tree": {"Vegetation"},
    "sky": {"Sky"},
    "building": {"Building"},
    "road": {"Road", "Service Lane", "Lane Marking - General", "Crosswalk - Plain",
             "Lane Marking - Crosswalk", "Manhole", "Pothole", "Catch Basin"},
    "person": {"Person", "Bicyclist", "Motorcyclist", "Other Rider"},
}
IGNORE = {"Ego Vehicle", "Car Mount"}

# Overlay colours for the hand-check images.
QA_COLOURS = {"tree": (40, 160, 60), "sky": (90, 160, 230), "building": (200, 90, 60),
              "road": (120, 120, 120), "person": (255, 0, 255)}


def class_ids(id2label: dict) -> tuple[dict, set]:
    names = {v: int(k) for k, v in id2label.items()}
    missing = {n for g in GROUPS.values() for n in g} - names.keys()
    if missing:
        print(f"Warning: labels not in this model: {sorted(missing)}")
    groups = {g: {names[n] for n in ns if n in names} for g, ns in GROUPS.items()}
    return groups, {names[n] for n in IGNORE if n in names}


def shares(seg: np.ndarray, groups: dict, ignore: set) -> dict:
    valid = ~np.isin(seg, list(ignore))
    total = max(int(valid.sum()), 1)
    return {g: float(np.isin(seg[valid], list(ids)).sum()) / total for g, ids in groups.items()}


def overlay(img: Image.Image, seg: np.ndarray, groups: dict) -> Image.Image:
    base = np.asarray(img.convert("RGB")).copy()
    for g, ids in groups.items():
        mask = np.isin(seg, list(ids))
        base[mask] = (0.45 * base[mask] + 0.55 * np.array(QA_COLOURS[g])).astype("uint8")
    side = Image.new("RGB", (img.width * 2, img.height))
    side.paste(img.convert("RGB"), (0, 0))
    side.paste(Image.fromarray(base), (img.width, 0))
    return side


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("images", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--qa-dir", type=Path)
    p.add_argument("--qa-n", type=int, default=50)
    p.add_argument("--batch", type=int, default=4)
    a = p.parse_args()

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Model {a.model} on {device}")
    proc = AutoImageProcessor.from_pretrained(a.model)
    model = Mask2FormerForUniversalSegmentation.from_pretrained(a.model).to(device).eval()
    groups, ignore = class_ids(model.config.id2label)

    files = sorted(a.images.glob("*.jpg"))
    done = set(pd.read_parquet(a.out)["id"]) if a.out.exists() else set()
    todo = [f for f in files if f.stem not in done]
    qa_ids = set(random.Random(0).sample([f.stem for f in files], min(a.qa_n, len(files))))
    print(f"{len(files)} images, {len(todo)} to do")

    rows = []
    for i in range(0, len(todo), a.batch):
        batch = todo[i : i + a.batch]
        imgs = [Image.open(f).convert("RGB") for f in batch]
        inputs = proc(images=imgs, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        segs = proc.post_process_semantic_segmentation(
            outputs, target_sizes=[im.size[::-1] for im in imgs]
        )
        for f, im, seg in zip(batch, imgs, segs):
            seg = seg.cpu().numpy()
            rows.append({"id": f.stem, **shares(seg, groups, ignore)})
            if a.qa_dir and f.stem in qa_ids:
                a.qa_dir.mkdir(parents=True, exist_ok=True)
                overlay(im, seg, groups).save(a.qa_dir / f"{f.stem}.jpg", quality=80)
        print(f"  {min(i + a.batch, len(todo))}/{len(todo)}", end="\r")
        if len(rows) >= 200:  # checkpoint so a Colab disconnect loses little
            _append(a.out, rows)
            rows = []
    _append(a.out, rows)
    print(f"\nWrote {a.out}")


def _append(path: Path, rows: list) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    df.to_parquet(path)


if __name__ == "__main__":
    main()
