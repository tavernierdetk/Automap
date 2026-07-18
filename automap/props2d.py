"""Procedural 2D prop sprites: the free-standing objects of layered scenes.

tiles2d's sibling for the y-sort world: RGBA sprites (trees, rocks, stumps)
rendered from a visual identity's colors, each with the two facts the depth
illusion depends on, carried in props.json:

- `anchor_y` — the FOOT line in pixels from the sprite top. The baker offsets
  the sprite so its node position sits on that line; the y-sorted world then
  draws the player in front when below it, behind when above it.
- `collision` — the walk-blocking FOOTPRINT only (a tree blocks at its trunk,
  never its canopy) as a circle radius at the anchor.

Deterministic per (identity, prop, variant) via sha256 — the tiles2d contract.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

Rgb = tuple[float, float, float]

# name -> (canvas w, h, variants, collision radius px)
PROPS: dict[str, dict] = {
    "tree": {"size": (96, 128), "variants": 3, "collision_r": 10},
    "pine": {"size": (80, 128), "variants": 2, "collision_r": 9},
    "rock": {"size": (56, 40), "variants": 3, "collision_r": 16},
    "stump": {"size": (40, 36), "variants": 2, "collision_r": 11},
}


def _rng(identity: str, prop: str, variant: int) -> np.random.Generator:
    digest = hashlib.sha256(f"{identity}:{prop}:{variant}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def _blob(a, cx, cy, rx, ry, rgb, rng, noise=0.08, rim=0.7):
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    inside = d < 1.0
    shade = 1.0 + rng.uniform(-noise, noise, size=(h, w))
    for c in range(3):
        a[:, :, c] = np.where(inside, rgb[c] * shade * np.where(d > 0.72, rim, 1.0), a[:, :, c])
    a[:, :, 3] = np.maximum(a[:, :, 3], inside.astype(float))


def _tree(a, trunk: Rgb, canopy: Rgb, rng):
    h, w = a.shape[:2]
    tw = 12 + int(rng.integers(-2, 3))
    x0 = w // 2 - tw // 2
    a[h - 46:h - 2, x0:x0 + tw, :3] = trunk
    a[h - 46:h - 2, x0:x0 + tw, :3] *= 1.0 + rng.uniform(-0.1, 0.1, size=(44, tw, 1))
    a[h - 46:h - 2, x0:x0 + tw, 3] = 1.0
    for i in range(3):  # stacked canopy blobs
        _blob(a, w / 2 + rng.uniform(-8, 8), 44 + i * 16, 30 - i * 3 + rng.uniform(-3, 3),
              22 - i * 2, canopy, rng)
    for _ in range(10):  # leaf highlights
        x, y = int(rng.integers(16, w - 16)), int(rng.integers(16, 72))
        if a[y, x, 3] > 0:
            a[y, x, :3] = np.clip(np.array(canopy) * 1.35, 0, 1)


def _pine(a, trunk: Rgb, canopy: Rgb, rng):
    h, w = a.shape[:2]
    a[h - 30:h - 2, w // 2 - 4:w // 2 + 4, :3] = trunk
    a[h - 30:h - 2, w // 2 - 4:w // 2 + 4, 3] = 1.0
    for i in range(4):  # narrowing tiers
        y = h - 40 - i * 24
        half = 26 - i * 5 + float(rng.uniform(-2, 2))
        for row in range(22):
            span = half * (row / 22.0)
            x0, x1 = int(w / 2 - span), int(w / 2 + span)
            shade = 1.0 - 0.25 * (1.0 - row / 22.0)
            a[y + row, x0:x1, :3] = np.array(canopy) * shade
            a[y + row, x0:x1, 3] = 1.0


def _rock(a, base: Rgb, rng):
    h, w = a.shape[:2]
    _blob(a, w / 2, h - 16, w / 2 - 4, 15, base, rng, noise=0.12, rim=0.6)
    a[: h - 26, :, 3] *= 0.0  # flatten the top a little
    _blob(a, w / 2 + rng.uniform(-4, 4), h - 22, w / 2 - 10, 10,
          tuple(min(1.0, c * 1.15) for c in base), rng, noise=0.1)


def _stump(a, trunk: Rgb, rng):
    h, w = a.shape[:2]
    a[h - 26:h - 2, 8:w - 8, :3] = trunk
    a[h - 26:h - 2, 8:w - 8, 3] = 1.0
    top = tuple(min(1.0, c * 1.3) for c in trunk)
    _blob(a, w / 2, h - 26, w / 2 - 9, 6, top, rng, noise=0.05)
    for r in (4, 8, 12):  # rings
        _blob(a, w / 2, h - 26, r, r * 0.45, tuple(c * 0.85 for c in top), rng, noise=0.02)


def build_props(identity) -> tuple[dict[str, Image.Image], dict]:
    """Render every prop variant; returns ({'tree_0': img,...}, props.json dict)."""
    get = (lambda k, d: identity.get(k, d)) if isinstance(identity, dict) \
        else (lambda k, d: getattr(identity, k, d))
    name = str(get("name", "identity"))
    trunk = tuple(get("trunk_color", (0.34, 0.26, 0.18)))
    canopy = tuple(get("canopy_color", (0.22, 0.42, 0.2)))
    rockc = tuple(get("cliff_color", (0.47, 0.45, 0.43)))

    images: dict[str, Image.Image] = {}
    catalog: dict = {"schema": "props/1.0", "identity": name, "props": {}}
    for prop, spec in PROPS.items():
        w, h = spec["size"]
        for v in range(spec["variants"]):
            rng = _rng(name, prop, v)
            a = np.zeros((h, w, 4), dtype=float)
            if prop == "tree":
                _tree(a, trunk, canopy, rng)
            elif prop == "pine":
                _pine(a, trunk, canopy, rng)
            elif prop == "rock":
                _rock(a, rockc, rng)
            else:
                _stump(a, trunk, rng)
            key = f"{prop}_{v}"
            images[key] = Image.fromarray(
                (np.clip(a, 0, 1) * 255).astype(np.uint8), "RGBA")
            catalog["props"][key] = {
                "file": key + ".png", "size": [w, h],
                "anchor_y": h - 4,               # the foot line
                "collision_r": spec["collision_r"],
            }
    return images, catalog


def write_props(out_dir: Path, identity) -> dict:
    images, catalog = build_props(identity)
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, img in images.items():
        img.save(out_dir / f"{key}.png")
    # merge: other generators (asset_creator) share this catalog
    path = out_dir / "props.json"
    if path.exists():
        existing = json.loads(path.read_text())
        merged = existing.get("props", {})
        merged.update(catalog["props"])
        catalog = dict(existing, **{k: v for k, v in catalog.items() if k != "props"})
        catalog["props"] = merged
    path.write_text(json.dumps(catalog, indent=2) + "\n")
    return catalog
