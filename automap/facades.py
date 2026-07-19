"""Procedural surface textures: the identity's look, baked into the glb.

Stage 6's texture tier (visual-identity@2.1.0 `textures` block). Everything
here is pure PIL/numpy, deterministic for a given identity + variant, and
network-free. The design constraint that shapes the API: textures must be
FEW and SHARED (a scene has ~1,500 buildings; the glb embeds each image
once) while buildings still vary — so:

- a wall texture is one tileable **storey tile**: u spans one window bay
  (`window_tile_m`), v spans one storey (`storey_m`). The geometry's UVs
  repeat it, so a building's measured LiDAR height produces the right number
  of window rows with a single 256px image (storey-awareness for free).
- roof and road tiles are near-neutral (mean luminance ~1) and get their
  color from the material's baseColorFactor, which glTF multiplies over the
  texture — one image serves every palette entry and every per-road wear tint.
- per-building variety comes from a small variant pool (window states drawn
  per variant from the identity's weights) plus the factor tint.

This generator sits behind the same `baseColorTexture` slot an image-model
backend would fill: when genserver grows a diffusion worker, a "generated"
facade_style routes there and nothing downstream changes.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image

SIZE = 256                      # every tile is SIZE x SIZE
WINDOW_STATES = ("dark", "lit", "boarded", "broken")

# The near-neutral wall body (visual-identity@2.3.0): pass this as wall_tile's
# `wall` and let the building's actual color arrive via the material factor —
# the roof/road pattern applied to walls, so a wall_palette shares one image
# per (style, state, variant). Note the factor also modulates the absolute
# window/trim colors in the tile; identities with bright `lit` windows should
# keep walls colored in-tile instead.
NEUTRAL_BODY = (0.94, 0.94, 0.94)

Rgb = tuple[float, float, float]


def _to_image(arr: np.ndarray) -> Image.Image:
    return Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8), "RGB")


def _noise(rng: np.random.Generator, shape, lo: float, hi: float) -> np.ndarray:
    return rng.uniform(lo, hi, size=shape)


def _fill(arr: np.ndarray, rgb: Rgb) -> None:
    arr[:, :, 0], arr[:, :, 1], arr[:, :, 2] = rgb


# --- wall body styles ---------------------------------------------------------

def _brick_body(arr: np.ndarray, wall: Rgb, rng: np.random.Generator) -> None:
    _fill(arr, wall)
    course = 16                                     # px per brick course
    for row0 in range(0, SIZE, course):
        offset = 32 if (row0 // course) % 2 else 0
        for col0 in range(-64, SIZE, 64):
            c0 = col0 + offset
            jitter = float(rng.uniform(0.82, 1.18))
            arr[row0:row0 + course, max(c0, 0):max(c0 + 64, 0)] *= jitter
        arr[row0:row0 + 2] *= 0.68                  # horizontal mortar
        for col0 in range(-64, SIZE, 64):
            c0 = (col0 + offset) % (SIZE + 64)
            arr[row0:row0 + course, c0:c0 + 2] *= 0.72   # head joints
    arr *= 1.0 + _noise(rng, arr.shape[:2], -0.04, 0.04)[..., None]


def _siding_body(arr: np.ndarray, wall: Rgb, rng: np.random.Generator) -> None:
    _fill(arr, wall)
    board = 20
    for row0 in range(0, SIZE, board):
        arr[row0:row0 + board] *= float(rng.uniform(0.94, 1.06))
        arr[row0:row0 + 2] *= 0.72                  # shadow under each lap
    arr *= 1.0 + _noise(rng, arr.shape[:2], -0.03, 0.03)[..., None]


def _concrete_body(arr: np.ndarray, wall: Rgb, rng: np.random.Generator) -> None:
    _fill(arr, wall)
    arr *= 1.0 + _noise(rng, arr.shape[:2], -0.06, 0.06)[..., None]
    for line in range(0, SIZE, 128):                # faint panel joints
        arr[line:line + 1] *= 0.85
        arr[:, line:line + 1] *= 0.85


_BODIES = {"brick": _brick_body, "siding": _siding_body, "concrete": _concrete_body}


# --- the window bay -----------------------------------------------------------

def _draw_window(arr: np.ndarray, state: str, trim: Rgb, soot: Rgb,
                 rng: np.random.Generator) -> None:
    """One window in the tile's bay: frame + glass in the requested state."""
    r0, r1, c0, c1 = 64, 192, 88, 168               # window rect (rows, cols)
    f = 6                                           # frame thickness
    arr[r0 - f:r1 + f, c0 - f:c1 + f] = trim        # frame
    glass = arr[r0:r1, c0:c1]
    if state == "lit":
        glass[:] = (0.85, 0.73, 0.42)
        glass *= 1.0 + _noise(rng, glass.shape[:2], -0.08, 0.02)[..., None]
    elif state == "boarded":
        glass[:] = soot
        plank = 18
        for row in range(0, glass.shape[0], plank):
            glass[row:row + plank] *= float(rng.uniform(0.8, 1.25))
            glass[row:row + 2] *= 0.6               # gaps between planks
    elif state == "broken":
        glass[:] = (0.07, 0.08, 0.09)
        glass *= 1.0 + _noise(rng, glass.shape[:2], -0.3, 0.3)[..., None]
        for _ in range(int(rng.integers(2, 5))):    # remaining shards catch light
            rr = int(rng.integers(0, glass.shape[0] - 12))
            cc = int(rng.integers(0, glass.shape[1] - 12))
            glass[rr:rr + int(rng.integers(4, 12)), cc:cc + int(rng.integers(4, 12))] = 0.45
    else:  # dark
        glass[:] = (0.10, 0.12, 0.15)
        glass *= 1.0 + _noise(rng, glass.shape[:2], -0.15, 0.15)[..., None]
    # sill
    arr[r1 + f:r1 + f + 4, c0 - f:c1 + f] = tuple(t * 0.8 for t in trim)


def pick_window_state(weights: dict, rng: np.random.Generator) -> str:
    states = [s for s in WINDOW_STATES if weights.get(s, 0) > 0] or ["dark"]
    w = np.array([float(weights.get(s, 0)) or 1.0 for s in states])
    return states[int(rng.choice(len(states), p=w / w.sum()))]


@lru_cache(maxsize=128)
def wall_tile(style: str, wall: Rgb, trim: Rgb, soot: Rgb,
              state: str, variant: int) -> Image.Image:
    """One tileable storey tile. Cached — a scene shares a handful of images."""
    rng = np.random.default_rng(hash((style, state, variant)) & 0xFFFFFFFF)
    arr = np.empty((SIZE, SIZE, 3), dtype=float)
    _BODIES.get(style, _brick_body)(arr, wall, rng)
    _draw_window(arr, state, trim, soot, rng)
    return _to_image(arr)


# --- roofs (near-neutral; color arrives via baseColorFactor) --------------------

@lru_cache(maxsize=32)
def roof_tile(style: str, variant: int) -> Image.Image:
    rng = np.random.default_rng(hash(("roof", style, variant)) & 0xFFFFFFFF)
    arr = np.full((SIZE, SIZE, 3), 0.94, dtype=float)
    if style == "tin":
        for col in range(0, SIZE, 24):              # standing seams
            arr[:, col:col + 2] *= 0.72
            arr[:, col + 2:col + 3] *= 1.12
        for _ in range(6):                          # weather streaks along the fall line
            c = int(rng.integers(0, SIZE))
            arr[:, c:c + int(rng.integers(2, 6))] *= float(rng.uniform(0.85, 0.97))
    elif style == "shingle":
        row_h = 20
        for row0 in range(0, SIZE, row_h):
            offset = 24 if (row0 // row_h) % 2 else 0
            arr[row0:row0 + 2] *= 0.7                # shadow line per course
            for col0 in range(-48, SIZE, 48):
                c0 = col0 + offset
                arr[row0:row0 + row_h,
                    max(c0, 0):max(c0 + 48, 0)] *= float(rng.uniform(0.92, 1.06))
                if 0 <= c0 < SIZE:
                    arr[row0:row0 + row_h, c0:c0 + 1] *= 0.8   # tab joints
    else:  # membrane
        arr[:] = 0.9
        arr *= 1.0 + _noise(rng, arr.shape[:2], -0.05, 0.05)[..., None]
        for line in range(0, SIZE, 96):             # rolled seams
            arr[line:line + 2] *= 0.8
        for _ in range(4):                          # ponding stains
            r, c = int(rng.integers(0, SIZE - 40)), int(rng.integers(0, SIZE - 40))
            arr[r:r + 40, c:c + 40] *= float(rng.uniform(0.88, 0.96))
    arr *= 1.0 + _noise(rng, arr.shape[:2], -0.03, 0.03)[..., None]
    return _to_image(arr)


# --- roads (near-neutral; per-road color/wear via baseColorFactor) --------------

@lru_cache(maxsize=8)
def road_tile(variant: int, centerline: bool = True, cracks: int = 4) -> Image.Image:
    """Asphalt tile: u across the road width, v along its length (repeats)."""
    rng = np.random.default_rng(hash(("road", variant, centerline, cracks)) & 0xFFFFFFFF)
    arr = np.full((SIZE, SIZE, 3), 0.92, dtype=float)
    arr *= 1.0 + _noise(rng, arr.shape[:2], -0.06, 0.06)[..., None]
    arr[:, :10] *= 0.85                              # gutter grime at both edges
    arr[:, -10:] *= 0.85
    for _ in range(cracks):                          # meandering cracks along v
        c = float(rng.integers(20, SIZE - 20))
        for row in range(SIZE):
            c += float(rng.uniform(-1.2, 1.2))
            ci = int(np.clip(c, 1, SIZE - 2))
            arr[row, ci - 1:ci + 1] *= 0.55
    if centerline:                                   # faded dashes down the middle
        mid = SIZE // 2
        for row0 in range(0, SIZE, 64):
            arr[row0:row0 + 28, mid - 3:mid + 3] *= 1.18
    return _to_image(arr)
