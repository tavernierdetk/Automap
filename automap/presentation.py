"""Presentation layer: apply a VisualIdentity to a scene via transformers.

Non-destructive. Reads a source glb (terrain/mesh) + a features list and emits a
NEW styled glb; the faithful sources are never modified. The visual identity is
*data* (asset/colour choices + an ordered transformer list), so changing the
game's look means changing config, not code.

First transformer: instance_trees - replace tree features with a procedural
stand-in asset, placed on the terrain surface (raycast) and scaled by height.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh


@dataclass
class VisualIdentity:
    name: str = "placeholder"
    transformers: list[str] = field(default_factory=lambda: ["instance_trees"])
    trunk_color: tuple = (0.43, 0.31, 0.19)     # rgb 0-1
    canopy_color: tuple = (0.24, 0.47, 0.22)
    tree_scale: float = 1.0


def _flat_material(rgb):
    return trimesh.visual.material.PBRMaterial(
        baseColorFactor=[rgb[0], rgb[1], rgb[2], 1.0],
        metallicFactor=0.0, roughnessFactor=1.0,
    )


def proxy_tree_parts(height: float, radius: float, identity: VisualIdentity):
    """A low-poly stand-in tree (trunk cylinder + canopy cone), base at y=0.

    Returns [trunk, canopy] as separate colored meshes so each keeps a flat
    material that renders reliably in Godot.
    """
    h = max(height, 1.0) * identity.tree_scale
    trunk_h, canopy_h = h * 0.3, h * 0.7
    # trimesh primitives are built along +Z; rotate so the axis stands up (+Y).
    up = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])

    trunk = trimesh.creation.cylinder(radius=max(radius * 0.15, 0.1), height=trunk_h, sections=6)
    trunk.apply_transform(up)
    trunk.apply_translation([0, -trunk.bounds[0][1], 0])              # base -> y=0

    canopy = trimesh.creation.cone(radius=max(radius, 0.8), height=canopy_h, sections=8)
    canopy.apply_transform(up)
    canopy.apply_translation([0, trunk_h - canopy.bounds[0][1], 0])   # base -> trunk top

    trunk.visual = trimesh.visual.TextureVisuals(material=_flat_material(identity.trunk_color))
    canopy.visual = trimesh.visual.TextureVisuals(material=_flat_material(identity.canopy_color))
    return [trunk, canopy]


def _ground_heights(ground: trimesh.Trimesh, xz: np.ndarray) -> np.ndarray:
    """Raycast straight down to find terrain Y at each (x, z). NaN where it misses."""
    if len(xz) == 0:
        return np.array([])
    ytop = ground.bounds[1][1] + 50.0
    origins = np.column_stack([xz[:, 0], np.full(len(xz), ytop), xz[:, 1]])
    dirs = np.tile([0.0, -1.0, 0.0], (len(xz), 1))
    locs, ray_idx, _ = ground.ray.intersects_location(origins, dirs, multiple_hits=False)
    ys = np.full(len(xz), np.nan)
    for loc, i in zip(locs, ray_idx):
        # keep the highest hit per ray (first surface from above)
        if np.isnan(ys[i]) or loc[1] > ys[i]:
            ys[i] = loc[1]
    return ys


def instance_trees(scene: trimesh.Scene, ground: trimesh.Trimesh, features, identity):
    trees = [f for f in features if f.get("type") == "tree"]
    if not trees:
        return 0
    xz = np.array([[t["x"], t["z"]] for t in trees])
    ys = _ground_heights(ground, xz)
    placed = 0
    for t, y in zip(trees, ys):
        if np.isnan(y):
            continue  # outside the terrain footprint
        T = np.eye(4)
        T[:3, 3] = [t["x"], y, t["z"]]
        for part in proxy_tree_parts(t["height"], t["radius"], identity):
            scene.add_geometry(part, transform=T)
        placed += 1
    return placed


TRANSFORMERS = {"instance_trees": instance_trees}


def style_scene(source_glb, features, identity: VisualIdentity, on_log=lambda _m: None):
    """Load the source glb, run the identity's transformer chain, return a Scene."""
    scene = trimesh.load(source_glb)
    if not isinstance(scene, trimesh.Scene):
        scene = trimesh.Scene(scene)
    ground = scene.dump(concatenate=True)  # geometry-only copy for raycasting
    for name in identity.transformers:
        fn = TRANSFORMERS.get(name)
        if fn is None:
            on_log(f"unknown transformer {name!r} - skipped")
            continue
        n = fn(scene, ground, features, identity)
        on_log(f"{name}: placed {n}")
    return scene
