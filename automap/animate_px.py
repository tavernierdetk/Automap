"""Frame variations for pixel-art assets — animation in INDEX SPACE.

Both generation backends (procedural trees_px, genlab repixel) produce
(material, band) maps; a frame variation is a small, principled edit to the
BAND map only, restricted to the family descriptor's `mutable` materials.
Everything else — silhouette, outline, trunk, footprint, ground shadow — is
LOCKED by construction: material indices never change, so frame k resolves
to the exact same alpha and the exact same collision as the base.

`foliage_sway` (trees): highlights drift 1px sideways (leading edge
brightens, trailing edge dims) plus a scatter of clump twinkles — leaves
catching light. Two frames read as a rustle; dead trees have no mutable
pixels and simply don't animate.

Deterministic (sha-seeded), palette-member by construction, validated by
asset_qc.qc_frames.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from automap import pixelart as px

# a canopy smaller than this doesn't animate (nothing to rustle)
_MIN_MUTABLE_PX = 40


def _mutable_mask(material: np.ndarray, names: dict, mutable) -> np.ndarray:
    mask = np.zeros(material.shape, bool)
    for idx, name in names.items():
        if name in mutable:
            mask |= material == idx
    return mask


def sway_frames(material: np.ndarray, band: np.ndarray, names: dict,
                pal: dict, mutable, base_img: Image.Image,
                frames: int = 2, seed_key: str = "anim") -> list[Image.Image]:
    """Frames 1..N-1 (frame 0 IS the base asset). May return [] (no canopy)."""
    mask = _mutable_mask(material, names, mutable)
    if mask.sum() < _MIN_MUTABLE_PX or frames < 2:
        return []
    base = np.asarray(base_img.convert("RGBA"))
    out = []
    for k in range(1, frames):
        rng = px.rng_for(seed_key, k)
        b = band.copy()
        # highlights drift sideways: leading edge brightens, trailing dims
        dx = 1 if k % 2 else -1
        hl = mask & (b >= 3)
        moved = np.roll(hl, dx, axis=1) & mask
        lead = moved & ~hl
        trail = hl & ~moved
        b[lead] = np.minimum(b[lead] + 1, 4)
        b[trail] = np.maximum(b[trail].astype(int) - 1, 1).astype(b.dtype)
        # clump twinkles on the mid bands — leaves turning in the wind
        n = max(int(mask.sum() / 260), 3)
        px.stamp(b, mask & (band >= 1) & (band <= 3), rng, n, +1, 1, 4)
        px.stamp(b, mask & (band >= 1) & (band <= 3), rng, n, -1, 0, 3)
        img = px.resolve(material, b, pal, names)
        arr = np.array(img)
        # pixels the maps don't cover (dithered shadow, special paints) come
        # straight from the base frame — alpha stays IDENTICAL by construction
        hole = (arr[:, :, 3] == 0) & (base[:, :, 3] > 0)
        arr[hole] = base[hole]
        out.append(Image.fromarray(arr, "RGBA"))
    return out


def attach_frames(staging_dir, name: str, material: np.ndarray,
                  band: np.ndarray, names: dict, pal: dict, anim: dict,
                  base_img: Image.Image, seed_key: str, log=None) -> int:
    """Generate + save frame files beside the base sprite; return frame count
    (1 = static). Files: <name>.f1.png … — each hash-guarded on publish."""
    frames = sway_frames(material, band, names, pal, anim.get("mutable", ()),
                         base_img, int(anim.get("frames", 2)), seed_key)
    if frames and log is not None:
        from automap import asset_qc
        checks = asset_qc.qc_frames(np.asarray(base_img.convert("RGBA")),
                                    [np.asarray(f) for f in frames], pal)
        for c in checks:
            if not c.ok:
                log(f"[anim] WARNING {name}: {c.name} failed ({c.detail})")
    for k, img in enumerate(frames, start=1):
        img.save(staging_dir / f"{name}.f{k}.png")
    return 1 + len(frames)
