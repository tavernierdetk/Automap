"""Presentation layer: apply a VisualIdentity to a scene via transformers.

Non-destructive. Reads a source glb (terrain/mesh) + a features list and emits a
NEW styled glb; the faithful sources are never modified. The visual identity is
*data* (asset/colour choices + an ordered transformer list), so changing the
game's look means changing config, not code.

Transformers: instance_trees replaces tree features with a procedural
stand-in asset, placed on the terrain surface (raycast) and scaled by height;
instance_buildings extrudes detected footprints into wall-colored prisms with
a flat slab or gable roof tinted by the roof color the detector sampled;
instance_roads drapes road ribbons over the terrain; instance_water floats a
sea plane at the level where the OSM coastline meets the terrain.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh


@dataclass
class VisualIdentity:
    name: str = "placeholder"
    transformers: list[str] = field(
        default_factory=lambda: [
            "instance_trees", "instance_buildings", "instance_roads", "instance_water"])
    trunk_color: tuple = (0.43, 0.31, 0.19)     # rgb 0-1
    canopy_color: tuple = (0.24, 0.47, 0.22)
    tree_scale: float = 1.0
    wall_color: tuple = (0.87, 0.83, 0.74)      # plaster-ish default walls
    road_color: tuple = (0.27, 0.26, 0.27)      # asphalt
    path_color: tuple = (0.52, 0.44, 0.33)      # dirt (footway/path/track)
    water_color: tuple = (0.16, 0.34, 0.45)
    # dropped-in IFC buildings render with their authored materials by
    # default; set True (via --restyle) to repaint them in this identity.
    restyle_assets: bool = False
    # --- richer looks (defaults keep the placeholder identity unchanged) ---
    tree_kit: str = "simple"                    # "simple" | "varied" (stacked forms + jitter)
    building_details: bool = False              # chimney + door/window quads
    trim_color: tuple = (0.95, 0.94, 0.90)      # door/window/chimney trim
    roof_saturation: float = 1.0                # boost detected roof colors (>1 = punchier)
    roof_palette: tuple = ()                    # colors for near-gray/unknown roofs
    # terrain zone colors (style_terrain transformer; None fields unused otherwise)
    grass_color: tuple = (0.50, 0.64, 0.30)
    cliff_color: tuple = (0.79, 0.66, 0.48)
    sand_color: tuple = (0.87, 0.78, 0.60)
    seafloor_color: tuple = (0.10, 0.30, 0.36)
    # --- decay (instance_buildings; all default OFF so existing identities are unchanged) ---
    ruin_fraction: float = 0.0                  # fraction of buildings collapsed to rubble
    damage_fraction: float = 0.0                # fraction (of the rest) with broken rooflines
    weather_variation: float = 0.0              # per-building wall value jitter (0-1, darkens)
    soot_color: tuple = (0.13, 0.12, 0.11)      # boarded openings / burn marks when decayed
    rubble_color: tuple = (0.42, 0.38, 0.34)    # collapsed-pile material
    # --- overgrowth (scatter_overgrowth transformer) ---
    overgrowth_density: float = 0.0             # clumps per 100 m of road (0 = transformer no-op)
    weed_colors: tuple = ((0.35, 0.38, 0.18), (0.50, 0.47, 0.24))  # dead-green to straw
    road_wear: float = 0.0                      # per-road bleach/patch jitter (0-1)
    # --- atmosphere (emitted as env.json beside the styled glb; applied by the
    # engine's map_loader — sky, sun, fog, ambient. None = engine defaults) ---
    environment: dict | None = None


def identity_from_dict(doc: dict) -> VisualIdentity:
    """A visual-identity JSON document -> VisualIdentity.

    The file form of the identity (visual-identity@2.0.0): unknown keys are
    ignored (schemas may run ahead of this consumer), lists become the tuples
    the dataclass expects, everything else passes through. Validation against
    the registry happens at the CLI seam, not here.
    """
    import dataclasses
    kwargs = {}
    known = {f.name for f in dataclasses.fields(VisualIdentity)}
    for key, val in doc.items():
        if key not in known:
            continue
        if isinstance(val, list):
            val = tuple(tuple(v) if isinstance(v, list) else v for v in val)
        kwargs[key] = val
    return VisualIdentity(**kwargs)


def _flat_material(rgb):
    return trimesh.visual.material.PBRMaterial(
        baseColorFactor=[rgb[0], rgb[1], rgb[2], 1.0],
        metallicFactor=0.0, roughnessFactor=1.0,
    )


def _instance_rng(x: float, z: float) -> np.random.Generator:
    """Deterministic per-instance RNG so re-runs style identically."""
    return np.random.default_rng(hash((round(float(x), 2), round(float(z), 2))) & 0xFFFFFFFF)


def _shift_color(rgb, hue: float = 0.0, value: float = 0.0):
    """Nudge a 0-1 RGB color in hue/brightness (small, stylized variation)."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*[float(np.clip(c, 0, 1)) for c in rgb])
    return colorsys.hsv_to_rgb((h + hue) % 1.0, s, float(np.clip(v + value, 0, 1)))


def _saturate(rgb, factor: float):
    """Scale saturation of a 0-1 RGB color (postcard-boost detected colors)."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*[float(np.clip(c, 0, 1)) for c in rgb])
    return colorsys.hsv_to_rgb(h, float(np.clip(s * factor, 0, 1)), v)


def _sea_flat_level(ground: trimesh.Trimesh) -> float | None:
    """The sea level terrain.flatten_sea left behind: the dominant co-planar
    vertex set. Only face-referenced vertices count (grid meshes park their
    nodata vertices at a bogus y). None when no big flat exists."""
    vy = np.round(ground.vertices[np.unique(ground.faces), 1], 2)
    vals, counts = np.unique(vy, return_counts=True)
    if counts.max() >= 500:
        return float(vals[counts.argmax()])
    return None


_UP = None


def _up():
    global _UP
    if _UP is None:
        # trimesh primitives are built along +Z; rotate so the axis stands up (+Y).
        _UP = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
    return _UP


def proxy_tree_parts(height: float, radius: float, identity: VisualIdentity,
                     rng: np.random.Generator | None = None):
    """A low-poly stand-in tree, base at y=0, as separate colored meshes.

    tree_kit "simple": trunk cylinder + one canopy cone (the placeholder look).
    tree_kit "varied": conifers (tall/narrow -> 2-3 stacked cones) and
    squat deciduous forms (stacked spheres), with per-instance size/hue
    variation when an rng is provided.
    """
    h = max(height, 1.0) * identity.tree_scale
    r = max(radius, 0.8)
    canopy_rgb = identity.canopy_color
    if identity.tree_kit == "varied" and rng is not None:
        h *= 1.0 + float(rng.uniform(-0.15, 0.15))
        r *= 1.0 + float(rng.uniform(-0.15, 0.15))
        canopy_rgb = _shift_color(canopy_rgb, hue=float(rng.uniform(-0.02, 0.02)),
                                  value=float(rng.uniform(-0.05, 0.05)))

    trunk_h = h * 0.25
    trunk = trimesh.creation.cylinder(radius=max(r * 0.12, 0.1), height=trunk_h, sections=6)
    trunk.apply_transform(_up())
    trunk.apply_translation([0, -trunk.bounds[0][1], 0])              # base -> y=0
    trunk.visual = trimesh.visual.TextureVisuals(material=_flat_material(identity.trunk_color))
    parts = [trunk]

    if identity.tree_kit != "varied":
        canopy = trimesh.creation.cone(radius=r, height=h - trunk_h, sections=8)
        canopy.apply_transform(_up())
        canopy.apply_translation([0, trunk_h - canopy.bounds[0][1], 0])
        canopy.visual = trimesh.visual.TextureVisuals(material=_flat_material(canopy_rgb))
        return parts + [canopy]

    canopy_h = h - trunk_h
    if h >= 3.0 * r:                                                  # conifer: stacked cones
        tiers, y = 3 if h > 6 else 2, trunk_h
        for i in range(tiers):
            frac = 1.0 - 0.28 * i
            th = canopy_h / tiers * 1.45                              # tiers overlap
            cone = trimesh.creation.cone(radius=r * frac, height=th, sections=8)
            cone.apply_transform(_up())
            cone.apply_translation([0, y - cone.bounds[0][1], 0])
            cone.visual = trimesh.visual.TextureVisuals(
                material=_flat_material(_shift_color(canopy_rgb, value=0.03 * i)))
            parts.append(cone)
            y += canopy_h / tiers * 0.72
    else:                                                             # deciduous: stacked blobs
        blobs = [(0.0, 0.0, trunk_h + canopy_h * 0.35, r),
                 (r * 0.45, r * 0.2, trunk_h + canopy_h * 0.6, r * 0.7),
                 (-r * 0.4, -r * 0.25, trunk_h + canopy_h * 0.7, r * 0.6)]
        for bx, bz, by, br in blobs:
            br = max(br, 0.5)
            blob = trimesh.creation.icosphere(subdivisions=1, radius=br)
            blob.apply_translation([bx, max(by, br + 0.05), bz])  # keep off the ground
            blob.visual = trimesh.visual.TextureVisuals(
                material=_flat_material(_shift_color(canopy_rgb, value=0.02)))
            parts.append(blob)
    return parts


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
        rng = _instance_rng(t["x"], t["z"])
        T = trimesh.transformations.rotation_matrix(
            float(rng.uniform(0, 2 * np.pi)), [0, 1, 0])
        T[:3, 3] = [t["x"], y, t["z"]]
        for part in proxy_tree_parts(t["height"], t["radius"], identity, rng=rng):
            scene.add_geometry(part, transform=T)
        placed += 1
    return placed


def _solid(vertices, faces, rgb) -> trimesh.Trimesh:
    """A closed colored solid; winding repaired via face adjacency."""
    m = trimesh.Trimesh(vertices=np.asarray(vertices, float),
                        faces=np.asarray(faces, int), process=False)
    trimesh.repair.fix_normals(m)
    m.visual = trimesh.visual.TextureVisuals(material=_flat_material(rgb))
    return m


def proxy_building_parts(corners: np.ndarray, y0: float, wall_h: float,
                         ridge_h: float, roof: str, roof_rgb, identity: VisualIdentity,
                         *, wall_rgb=None, trim_rgb=None, top_offsets=None, skip_roof=False):
    """A stand-in building: wall prism + roof solid, in world coordinates.

    corners are 4 ordered (x, z) footprint corners; the body is sunk slightly
    below y0 so slopes leave no gap under the walls.

    Decay hooks (all default to the pristine building): wall_rgb/trim_rgb
    override the identity colors; top_offsets (4 values) drop individual top
    corners for a jagged broken parapet; skip_roof leaves the shell open.
    """
    c = np.asarray(corners, float)
    sink = 0.5
    wall_h = max(wall_h, 2.0)
    wall_rgb = identity.wall_color if wall_rgb is None else wall_rgb
    trim_rgb = identity.trim_color if trim_rgb is None else trim_rgb
    base = np.column_stack([c[:, 0], np.full(4, y0 - sink), c[:, 1]])
    top = base.copy()
    top[:, 1] = y0 + wall_h
    if top_offsets is not None:
        top[:, 1] -= np.clip(np.asarray(top_offsets, float), 0.0, wall_h - 1.0)
    quads = [[i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i] for i in range(4)] + [[3, 2, 1, 0], [4, 5, 6, 7]]
    body = _solid(np.vstack([base, top]),
                  [t for a, b, d, e in quads for t in ([a, b, d], [a, d, e])],
                  wall_rgb)

    parts = [body]
    ridge_pts = None
    if skip_roof:
        pass
    elif roof == "gable" and ridge_h > wall_h + 0.2:
        # ridge along the long axis: above the midpoints of the two short edges
        long01 = np.linalg.norm(c[1] - c[0]) >= np.linalg.norm(c[2] - c[1])
        (sa, sb), (sc_, sd) = ((1, 2), (3, 0)) if long01 else ((0, 1), (2, 3))
        t = top.copy()
        ra = (t[sa] + t[sb]) / 2.0
        rb = (t[sc_] + t[sd]) / 2.0
        ra[1] = rb[1] = y0 + ridge_h
        v = np.vstack([top, ra, rb])                 # 0-3 eaves, 4-5 ridge
        faces = [[sa, sb, 4], [sc_, sd, 5],          # gable end triangles
                 [sb, sc_, 5], [sb, 5, 4], [sd, sa, 4], [sd, 4, 5],  # slopes
                 [3, 2, 1], [3, 1, 0]]               # underside (closes it)
        parts.append(_solid(v, faces, roof_rgb))
        ridge_pts = (ra, rb)
    else:
        slab = top.copy()
        lid = top.copy()
        lid[:, 1] += 0.2
        parts.append(_solid(np.vstack([slab, lid]),
                            [t for a, b, d, e in quads for t in ([a, b, d], [a, d, e])],
                            roof_rgb))

    if identity.building_details:
        # chimney: a small trim-colored box near one end of the ridge (or slab)
        if ridge_pts is not None:
            spot = ridge_pts[0] * 0.7 + ridge_pts[1] * 0.3
        else:
            cx, cz = c.mean(axis=0)
            spot = np.array([cx, y0 + wall_h + 0.2, cz])
        chimney = trimesh.creation.box(extents=[0.6, 1.6, 0.6])
        chimney.apply_translation([spot[0], spot[1] + 0.4, spot[2]])
        chimney.visual = trimesh.visual.TextureVisuals(
            material=_flat_material(trim_rgb))
        parts.append(chimney)
        # door + window: thin trim-colored boxes proud of the longest wall
        e01, e12 = c[1] - c[0], c[2] - c[1]
        if np.linalg.norm(e01) >= np.linalg.norm(e12):
            a, b, inward = c[0], c[1], c[2] - c[1]
        else:
            a, b, inward = c[1], c[2], c[3] - c[2]
        out = -inward / max(np.linalg.norm(inward), 1e-9)
        along = (b - a) / max(np.linalg.norm(b - a), 1e-9)
        # rotate the box's local +X onto the wall direction in the XZ plane
        wall_dir = np.arctan2(-along[1], along[0])
        for frac, w, hgt, y_c in ((0.35, 0.9, 1.9, y0 + 0.95), (0.7, 1.0, 1.0, y0 + wall_h * 0.55)):
            p = a + (b - a) * frac + out * 0.06
            box = trimesh.creation.box(extents=[w, hgt, 0.12])
            rot = trimesh.transformations.rotation_matrix(wall_dir, [0, 1, 0])
            box.apply_transform(rot)
            box.apply_translation([p[0], y_c, p[1]])
            box.visual = trimesh.visual.TextureVisuals(
                material=_flat_material(trim_rgb))
            parts.append(box)
    return parts


def rubble_parts(corners: np.ndarray, y0: float, wall_h: float,
                 identity: VisualIdentity, rng: np.random.Generator):
    """A collapsed building: a low debris mound + one or two remnant wall slabs.

    Deterministic for a given rng; heights scale with what stood there so a
    fallen triplex leaves more debris than a fallen shed.
    """
    c = np.asarray(corners, float)
    y_top = min(max(wall_h * 0.25, 0.8), 3.0)
    parts = []
    for _ in range(int(rng.integers(5, 9))):
        # bilinear sample keeps every pile inside the footprint quad
        u, v = rng.uniform(0.15, 0.85), rng.uniform(0.15, 0.85)
        p = (c[0] * (1 - u) + c[1] * u) * (1 - v) + (c[3] * (1 - u) + c[2] * u) * v
        ext = [float(rng.uniform(1.2, 3.5)), float(rng.uniform(0.4, y_top)),
               float(rng.uniform(1.2, 3.5))]
        pile = trimesh.creation.box(extents=ext)
        pile.apply_transform(trimesh.transformations.rotation_matrix(
            float(rng.uniform(0, np.pi)), [0, 1, 0]))
        pile.apply_translation([p[0], y0 + ext[1] / 2.0 - 0.15, p[1]])
        shade = 0.85 + 0.3 * float(rng.random())
        pile.visual = trimesh.visual.TextureVisuals(material=_flat_material(
            tuple(min(1.0, ch * shade) for ch in identity.rubble_color)))
        parts.append(pile)
    # remnant wall fragments: charred stubs along random footprint edges
    char = tuple(0.55 * w + 0.45 * s for w, s in zip(identity.wall_color, identity.soot_color))
    for i in rng.choice(4, size=int(rng.integers(1, 3)), replace=False):
        a, b = c[i], c[(i + 1) % 4]
        frac0 = float(rng.uniform(0.0, 0.4))
        frac1 = frac0 + float(rng.uniform(0.25, 0.5))
        pa, pb = a + (b - a) * frac0, a + (b - a) * min(frac1, 1.0)
        h = wall_h * float(rng.uniform(0.25, 0.55))
        seg = pb - pa
        length = float(np.linalg.norm(seg))
        if length < 1.0:
            continue
        slab = trimesh.creation.box(extents=[length, h, 0.3])
        ang = float(np.arctan2(-seg[1], seg[0]))
        slab.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 1, 0]))
        mid = (pa + pb) / 2.0
        slab.apply_translation([mid[0], y0 + h / 2.0 - 0.15, mid[1]])
        slab.visual = trimesh.visual.TextureVisuals(material=_flat_material(char))
        parts.append(slab)
    return parts


def _place_asset(scene, ground, feature, identity) -> bool:
    """Instance a dropped-in building asset (representation override).

    The glb is pre-placed horizontally with its base at y=0 (see
    ifc.ifc_to_glb); here we only drape it onto the terrain by sampling the
    ground at ground_xz. Authored materials are kept unless the identity asks
    to restyle. Returns False if the asset can't be loaded/seated.
    """
    rep = feature["representation"]
    asset = rep.get("_abs", rep["asset"])
    try:
        loaded = trimesh.load(asset, force="scene")
    except Exception:  # noqa: BLE001 - missing/corrupt asset: fall back to proxy
        return False
    gx, gz = rep.get("ground_xz", np.asarray(feature["footprint"], float).mean(axis=0))
    y = _ground_heights(ground, np.array([[gx, gz]]))[0]
    if np.isnan(y):
        c = np.asarray(feature["footprint"], float)
        ys = _ground_heights(ground, np.vstack([c, c.mean(axis=0, keepdims=True)]))
        if np.isnan(ys).all():
            return False
        y = float(np.nanmin(ys))
    for geom in loaded.geometry.values():
        g = geom.copy()
        g.apply_translation([0.0, float(y), 0.0])
        if getattr(identity, "restyle_assets", False):
            g.visual = trimesh.visual.TextureVisuals(material=_flat_material(identity.wall_color))
        scene.add_geometry(g)
    return True


def instance_buildings(scene: trimesh.Scene, ground: trimesh.Trimesh, features, identity):
    blds = [f for f in features if f.get("type") == "building"]
    if not blds:
        return 0
    placed = 0
    for b in blds:
        if b.get("representation", {}).get("kind") == "asset":
            if _place_asset(scene, ground, b, identity):
                placed += 1
                continue  # dropped-in asset replaces the generated proxy
        c = np.asarray(b["footprint"], float)
        probe = np.vstack([c, c.mean(axis=0, keepdims=True)])
        ys = _ground_heights(ground, probe)
        if np.isnan(ys).all():
            continue  # outside the terrain footprint
        y0 = float(np.nanmin(ys))
        rgb = [v / 255.0 for v in b.get("roof_color", (120, 120, 120))]
        if identity.roof_palette and max(rgb) - min(rgb) < 0.08:
            # near-gray (or OSM default): paint it from the identity's palette
            rng = _instance_rng(*c.mean(axis=0))
            rgb = identity.roof_palette[int(rng.integers(len(identity.roof_palette)))]
        elif identity.roof_saturation != 1.0:
            rgb = _saturate(rgb, identity.roof_saturation)

        decay_on = (identity.ruin_fraction > 0 or identity.damage_fraction > 0
                    or identity.weather_variation > 0)
        if decay_on:
            # a SEPARATE deterministic stream (offset seed point) so decay
            # rolls never perturb the roof-palette draw above
            drng = _instance_rng(c.mean(axis=0)[0] + 17.0, c.mean(axis=0)[1] - 31.0)
            roll = float(drng.random())
            fade = float(drng.uniform(0.0, identity.weather_variation))
            wall = tuple(ch * (1.0 - 0.45 * fade) for ch in identity.wall_color)
            if roll < identity.ruin_fraction:
                for part in rubble_parts(c, y0, b["height"], identity, drng):
                    scene.add_geometry(part)
                placed += 1
                continue
            if roll < identity.ruin_fraction + identity.damage_fraction:
                offsets = drng.uniform(0.4, max(0.5, b["height"] * 0.45), 4)
                soot_wall = tuple(0.7 * w + 0.3 * s
                                  for w, s in zip(wall, identity.soot_color))
                for part in proxy_building_parts(
                        c, y0, b["height"], b.get("ridge", b["height"]),
                        b.get("roof", "flat"), rgb, identity,
                        wall_rgb=soot_wall, trim_rgb=identity.soot_color,
                        top_offsets=offsets, skip_roof=True):
                    scene.add_geometry(part)
                placed += 1
                continue
            for part in proxy_building_parts(
                    c, y0, b["height"], b.get("ridge", b["height"]),
                    b.get("roof", "flat"), rgb, identity,
                    wall_rgb=wall, trim_rgb=identity.soot_color):
                scene.add_geometry(part)
            placed += 1
            continue

        for part in proxy_building_parts(
                c, y0, b["height"], b.get("ridge", b["height"]),
                b.get("roof", "flat"), rgb, identity):
            scene.add_geometry(part)
        placed += 1
    return placed


def _resample_path(path: np.ndarray, step: float) -> np.ndarray:
    """Resample a polyline to roughly even spacing so draping follows terrain."""
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] < 1e-9:
        return path[:1]
    t = np.linspace(0.0, s[-1], max(int(np.ceil(s[-1] / step)) + 1, 2))
    return np.column_stack([np.interp(t, s, path[:, 0]), np.interp(t, s, path[:, 1])])


ROAD_LIFT = 0.35   # ribbon height above terrain (bumpy melt pokes through less)
DIRT_KINDS = {"footway", "path", "track", "steps", "bridleway"}


def road_ribbon(path: np.ndarray, width: float, ground: trimesh.Trimesh) -> trimesh.Trimesh | None:
    """A terrain-draped ribbon mesh for one road; None if it misses the terrain."""
    pts = _resample_path(np.asarray(path, float), step=2.0)
    if len(pts) < 2:
        return None
    d = np.gradient(pts, axis=0)
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    perp = np.column_stack([-d[:, 1], d[:, 0]]) * (width / 2.0)
    left, right = pts + perp, pts - perp
    ys = _ground_heights(ground, np.vstack([left, right]))
    yl, yr = ys[:len(pts)], ys[len(pts):]
    ok = np.isfinite(yl) & np.isfinite(yr)

    n = len(pts)
    verts = np.zeros((2 * n, 3))
    verts[:n] = np.column_stack([left[:, 0], yl + ROAD_LIFT, left[:, 1]])
    verts[n:] = np.column_stack([right[:, 0], yr + ROAD_LIFT, right[:, 1]])
    faces = []
    for i in range(n - 1):
        if ok[i] and ok[i + 1]:
            faces += [[i, i + 1, n + i], [n + i, i + 1, n + i + 1]]
    if not faces:
        return None
    m = trimesh.Trimesh(vertices=np.nan_to_num(verts), faces=faces, process=False)
    m.remove_unreferenced_vertices()
    return m


def instance_roads(scene: trimesh.Scene, ground: trimesh.Trimesh, features, identity):
    placed = 0
    for r in (f for f in features if f.get("type") == "road"):
        path = np.asarray(r["path"])
        ribbon = road_ribbon(path, r.get("width", 5.0), ground)
        if ribbon is None:
            continue
        color = identity.path_color if r.get("kind") in DIRT_KINDS else identity.road_color
        if identity.road_wear > 0:
            # per-road bleach: decades of sun and no resurfacing crews
            wrng = _instance_rng(path[0][0] + 3.0, path[0][1] + 5.0)
            lift = float(wrng.uniform(0.0, identity.road_wear))
            color = tuple(min(1.0, ch + (0.55 - ch) * lift * 0.8) for ch in color)
        ribbon.visual = trimesh.visual.TextureVisuals(material=_flat_material(color))
        scene.add_geometry(ribbon)
        placed += 1
    return placed


def weed_clump_parts(x: float, y: float, z: float, identity: VisualIdentity,
                     rng: np.random.Generator):
    """A small vegetation clump: 2-4 squashed spheres in the identity's weed colors."""
    parts = []
    for _ in range(int(rng.integers(2, 5))):
        r = float(rng.uniform(0.35, 1.1))
        blob = trimesh.creation.icosphere(subdivisions=1, radius=r)
        blob.apply_scale([1.0, float(rng.uniform(0.35, 0.7)), 1.0])
        blob.apply_translation([x + float(rng.uniform(-0.8, 0.8)), y + r * 0.25,
                                z + float(rng.uniform(-0.8, 0.8))])
        base = identity.weed_colors[int(rng.integers(len(identity.weed_colors)))]
        shade = 0.85 + 0.3 * float(rng.random())
        blob.visual = trimesh.visual.TextureVisuals(material=_flat_material(
            tuple(min(1.0, ch * shade) for ch in base)))
        parts.append(blob)
    return parts


def scatter_overgrowth(scene: trimesh.Scene, ground: trimesh.Trimesh, features, identity):
    """Vegetation reclaiming the streets: weed clumps scattered along roads.

    Density is clumps per 100 m of road. Deterministic per station; capped so
    a dense city cannot explode the scene. No-op at density 0 (the default),
    so identities that don't ask for overgrowth are untouched.
    """
    if identity.overgrowth_density <= 0:
        return 0
    step = 100.0 / identity.overgrowth_density
    placed = 0
    cap = 3000
    for r in (f for f in features if f.get("type") == "road"):
        path = _resample_path(np.asarray(r["path"], float), max(step, 4.0))
        width = r.get("width", 5.0)
        for px, pz in path:
            rng = _instance_rng(px + 11.0, pz - 7.0)
            if rng.random() > 0.75:   # leave stretches clear so it reads patchy
                continue
            ox = float(rng.uniform(-0.6, 0.6)) * width
            oz = float(rng.uniform(-0.6, 0.6)) * width
            y = _ground_heights(ground, np.array([[px + ox, pz + oz]]))[0]
            if np.isnan(y):
                continue
            for part in weed_clump_parts(px + ox, float(y), pz + oz, identity, rng):
                scene.add_geometry(part)
            placed += 1
            if placed >= cap:
                return placed
    return placed


def instance_water(scene: trimesh.Scene, ground: trimesh.Trimesh, features, identity):
    """A sea plane at the level the coastline meets the terrain."""
    placed = 0
    for w in (f for f in features if f.get("type") == "water"):
        outline = np.asarray(w["outline"], float)
        ys = _ground_heights(ground, outline)
        ys = ys[np.isfinite(ys)]
        if len(ys) == 0:
            continue
        # terrain.flatten_sea leaves a huge co-planar vertex set at the sea
        # level; when present that modal flat is the exact anchor. Otherwise
        # fall back to a low percentile of the coastline raycasts (err low so
        # the water never floods the town).
        flat = _sea_flat_level(ground)
        level = flat + 0.15 if flat is not None else float(np.percentile(ys, 10)) + 0.3
        (x0, _, z0), (x1, _, z1) = ground.bounds
        verts = [[x0, level, z0], [x1, level, z0], [x1, level, z1], [x0, level, z1]]
        # wound so the normal faces +Y (up)
        plane = trimesh.Trimesh(vertices=verts, faces=[[0, 2, 1], [0, 3, 2]], process=False)
        plane.visual = trimesh.visual.TextureVisuals(material=_flat_material(identity.water_color))
        scene.add_geometry(plane)
        placed += 1
    return placed


def style_terrain(scene: trimesh.Scene, ground: trimesh.Trimesh, features, identity):
    """Replace the terrain's photo texture with stylized per-vertex zone colors.

    Zones come from the geometry itself: below/at the sea flat -> seafloor,
    a strip just above it -> sand, steep faces -> cliff, everything else ->
    grass, with a little deterministic brightness variation so fields don't
    read as one flat poster. Applies to the source terrain meshes (the scene
    content present before any instancing runs), so it must be first in the
    transformer chain.
    """
    sea = _sea_flat_level(ground)
    styled = 0
    for name, mesh in list(scene.geometry.items()):
        v = mesh.vertices
        # slope from height-smoothed geometry: real cliffs are large-amplitude
        # features that survive smoothing, reconstruction-melt bumps are not —
        # without this the whole melt zone reads as cliff. Hand-rolled (heights
        # only, edge-adjacency averaging) because trimesh's filter_laplacian
        # rejects meshes with unreferenced (nodata) vertices.
        from scipy.sparse import coo_matrix
        e = mesh.edges_unique
        adj = coo_matrix(
            (np.ones(2 * len(e)),
             (np.concatenate([e[:, 0], e[:, 1]]), np.concatenate([e[:, 1], e[:, 0]]))),
            shape=(len(v), len(v))).tocsr()
        deg = np.maximum(np.asarray(adj.sum(axis=1)).ravel(), 1)
        y_s = v[:, 1].copy()
        for _ in range(6):
            y_s = 0.5 * y_s + 0.5 * (adj.dot(y_s) / deg)
        smooth = mesh.copy()
        sv = smooth.vertices.copy()
        sv[:, 1] = y_s
        smooth.vertices = sv
        steep = smooth.vertex_normals[:, 1] < np.cos(np.radians(38))
        colors = np.tile(np.array(identity.grass_color), (len(v), 1))
        colors[steep] = identity.cliff_color
        if sea is not None:
            # sand = low AND close to actual sea cells — low-lying inland melt
            # (raised to just above sea level) must stay grass, not beach
            on_sea = v[:, 1] <= sea + 0.05
            near_shore = np.zeros(len(v), bool)
            if on_sea.any():
                from scipy.spatial import cKDTree
                d, _ = cKDTree(v[on_sea][:, [0, 2]]).query(
                    v[:, [0, 2]], distance_upper_bound=15.0)
                near_shore = np.isfinite(d)
            colors[(v[:, 1] <= sea + 1.2) & ~steep & near_shore] = identity.sand_color
            colors[on_sea] = identity.seafloor_color
        # deterministic per-vertex brightness grain
        grain = (np.sin(v[:, 0] * 12.9898 + v[:, 2] * 78.233) * 43758.5453) % 1.0
        colors *= (0.95 + 0.08 * grain)[:, None]
        rgba = np.hstack([np.clip(colors, 0, 1) * 255, np.full((len(v), 1), 255)])
        mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=rgba.astype(np.uint8))
        styled += 1
    return styled


TRANSFORMERS = {
    "style_terrain": style_terrain,
    "instance_trees": instance_trees,
    "instance_buildings": instance_buildings,
    "instance_roads": instance_roads,
    "instance_water": instance_water,
    "scatter_overgrowth": scatter_overgrowth,
}


def style_scene(source_glb, features, identity: VisualIdentity, on_log=lambda _m: None,
                scene_dir=None):
    """Load the source glb, run the identity's transformer chain, return a Scene.

    scene_dir (the work/<scene>/ folder) resolves scene-relative asset paths
    in building representation overrides to absolute, so on-disk paths stay
    portable while the transformer just loads a file.
    """
    if scene_dir is not None:
        from pathlib import Path
        for feat in features:
            rep = feat.get("representation") if isinstance(feat, dict) else None
            if rep and rep.get("asset"):
                rep["_abs"] = str(Path(scene_dir) / rep["asset"])
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
