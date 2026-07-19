"""Tests for the presentation layer's procedural proxy assets."""
import numpy as np
import trimesh

from automap.presentation import (
    VisualIdentity,
    instance_buildings,
    instance_roads,
    instance_water,
    proxy_building_parts,
    proxy_tree_parts,
    road_ribbon,
    style_terrain,
)


def _flat_ground(size=40.0):
    ground = trimesh.creation.box(extents=[size, 1, size])
    ground.apply_translation([0, -0.5, 0])            # top face at y=0
    return ground


def test_proxy_tree_shape():
    trunk, canopy = proxy_tree_parts(10.0, 2.0, VisualIdentity())
    # two separately-colored parts
    assert trunk.volume > 0 and len(canopy.vertices) > 0
    # base sits on the ground (y ~ 0)
    assert trunk.bounds[0][1] >= -1e-4
    # roughly the requested height tall
    top = max(trunk.bounds[1][1], canopy.bounds[1][1])
    assert 9.0 < top <= 11.0
    # canopy sits above the trunk
    assert canopy.bounds[0][1] >= trunk.bounds[1][1] - 1e-4


def test_proxy_tree_scale():
    tall = proxy_tree_parts(10.0, 2.0, VisualIdentity(tree_scale=2.0))
    top = max(m.bounds[1][1] for m in tall)
    assert 19.0 < top <= 21.0


FOOTPRINT = [[-5.0, -3.0], [5.0, -3.0], [5.0, 3.0], [-5.0, 3.0]]


def test_proxy_building_gable():
    body, roof = proxy_building_parts(
        np.array(FOOTPRINT), y0=0.0, wall_h=4.0, ridge_h=6.0,
        roof="gable", roof_rgb=(0.8, 0.2, 0.2), identity=VisualIdentity())
    assert body.volume > 0 and roof.volume > 0            # closed solids
    assert body.bounds[0][1] < 0 <= 0.01                  # sunk below ground
    assert abs(roof.bounds[1][1] - 6.0) < 1e-6            # ridge at 6 m
    # ridge runs along the long (x) axis: the roof peak spans most of x
    peak = roof.vertices[np.isclose(roof.vertices[:, 1], 6.0)]
    assert np.ptp(peak[:, 0]) > 8.0 and np.ptp(peak[:, 2]) < 1e-6


def test_proxy_building_flat():
    body, roof = proxy_building_parts(
        np.array(FOOTPRINT), y0=10.0, wall_h=3.0, ridge_h=3.2,
        roof="flat", roof_rgb=(0.5, 0.5, 0.5), identity=VisualIdentity())
    assert abs(roof.bounds[1][1] - 13.2) < 0.01           # slab atop the walls
    assert body.volume > 0 and roof.volume > 0


def test_instance_buildings_on_terrain():
    ground = _flat_ground()
    scene = trimesh.Scene(ground.copy())
    n_before = len(scene.geometry)
    feature = {"type": "building", "footprint": FOOTPRINT, "height": 4.0,
               "ridge": 6.0, "roof": "gable", "roof_color": [200, 60, 60]}
    placed = instance_buildings(scene, ground, [feature], VisualIdentity())
    assert placed == 1
    assert len(scene.geometry) == n_before + 2            # body + roof
    assert abs(scene.bounds[1][1] - 6.0) < 0.01           # ridge above ground


def test_instance_buildings_skips_off_terrain():
    ground = _flat_ground()
    scene = trimesh.Scene(ground.copy())
    far = {"type": "building", "height": 4.0, "roof": "flat", "roof_color": [1, 2, 3],
           "footprint": [[100, 100], [110, 100], [110, 106], [100, 106]]}
    assert instance_buildings(scene, ground, [far], VisualIdentity()) == 0


def test_road_ribbon_drapes_flat_ground():
    ground = _flat_ground()
    from automap.presentation import ROAD_LIFT
    ribbon = road_ribbon(np.array([[-15.0, 0.0], [15.0, 0.0]]), 6.0, ground)
    assert ribbon is not None
    # sits just above the terrain, faces up, spans the requested width
    assert np.allclose(ribbon.vertices[:, 1], ROAD_LIFT, atol=0.01)
    assert (ribbon.face_normals[:, 1] > 0.99).all()
    assert 5.9 <= np.ptp(ribbon.vertices[:, 2]) <= 6.1
    assert np.ptp(ribbon.vertices[:, 0]) >= 29.0


def test_road_ribbon_clips_off_terrain():
    ground = _flat_ground()                               # covers +-20
    on = road_ribbon(np.array([[-15.0, 0.0], [15.0, 0.0]]), 4.0, ground)
    half_off = road_ribbon(np.array([[0.0, 0.0], [60.0, 0.0]]), 4.0, ground)
    assert half_off is not None
    assert half_off.vertices[:, 0].max() < 25.0           # off-terrain part dropped
    assert road_ribbon(np.array([[100.0, 0.0], [130.0, 0.0]]), 4.0, ground) is None
    assert on is not None


def test_instance_roads_and_kinds():
    ground = _flat_ground()
    scene = trimesh.Scene(ground.copy())
    feats = [
        {"type": "road", "path": [[-15, 0], [15, 0]], "width": 6.0, "kind": "residential"},
        {"type": "road", "path": [[0, -15], [0, 15]], "width": 1.8, "kind": "footway"},
        {"type": "road", "path": [[100, 0], [130, 0]], "width": 6.0, "kind": "service"},
    ]
    assert instance_roads(scene, ground, feats, VisualIdentity()) == 2


def test_instance_water_sea_level():
    ground = _flat_ground()
    scene = trimesh.Scene(ground.copy())
    feat = {"type": "water", "kind": "sea", "outline": [[-10.0, -10.0], [10.0, 10.0]]}
    assert instance_water(scene, ground, [feat], VisualIdentity()) == 1
    plane = scene.geometry[list(scene.geometry)[-1]]
    assert np.allclose(plane.vertices[:, 1], 0.3, atol=0.01)   # ground 0 + offset
    assert (plane.face_normals[:, 1] > 0.99).all()
    assert np.ptp(plane.vertices[:, 0]) >= 39.0                # covers the scene


def test_instance_water_skips_off_terrain_outline():
    ground = _flat_ground()
    scene = trimesh.Scene(ground.copy())
    feat = {"type": "water", "kind": "sea", "outline": [[500.0, 500.0]]}
    assert instance_water(scene, ground, [feat], VisualIdentity()) == 0


VARIED = VisualIdentity(tree_kit="varied", building_details=True,
                        roof_palette=((0.8, 0.2, 0.2),))


def test_varied_tree_kit_conifer_and_deciduous():
    rng = np.random.default_rng(1)
    conifer = proxy_tree_parts(8.0, 1.5, VARIED, rng=rng)     # tall/narrow
    assert len(conifer) >= 3                                  # trunk + stacked cones
    top = max(m.bounds[1][1] for m in conifer)
    assert 6.0 < top < 12.0
    deciduous = proxy_tree_parts(3.0, 2.0, VARIED, rng=np.random.default_rng(2))
    assert len(deciduous) == 4                                # trunk + 3 blobs
    assert min(m.bounds[0][1] for m in deciduous) >= -1e-4    # base on the ground


def test_varied_tree_jitter_is_deterministic():
    a = proxy_tree_parts(8.0, 1.5, VARIED, rng=np.random.default_rng(7))
    b = proxy_tree_parts(8.0, 1.5, VARIED, rng=np.random.default_rng(7))
    assert np.allclose(a[1].vertices, b[1].vertices)
    c = proxy_tree_parts(8.0, 1.5, VARIED, rng=np.random.default_rng(8))
    assert not np.allclose(a[1].vertices, c[1].vertices)


def test_building_details_add_parts():
    plain = proxy_building_parts(np.array(FOOTPRINT), 0.0, 4.0, 6.0,
                                 "gable", (0.5, 0.5, 0.5), VisualIdentity())
    detailed = proxy_building_parts(np.array(FOOTPRINT), 0.0, 4.0, 6.0,
                                    "gable", (0.5, 0.5, 0.5), VARIED)
    assert len(plain) == 2
    assert len(detailed) == 5                                 # + chimney, door, window
    chimney = detailed[2]
    assert chimney.bounds[1][1] > 6.0                         # pokes above the ridge


def test_style_terrain_zones():
    from automap.terrain import build_grid_mesh
    h = np.zeros((30, 40))
    for c in range(20, 26):
        h[:, c] = (c - 19) * 4.0                              # steep ramp up to 24 m
    h[:, 26:] = 24.0                                          # high plateau
    verts, faces, _ = build_grid_mesh(h, pixel_size=2.0)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    scene = trimesh.Scene(mesh)
    ident = VisualIdentity()
    assert style_terrain(scene, mesh, [], ident) == 1
    styled = list(scene.geometry.values())[0]
    colors = styled.visual.vertex_colors[:, :3].astype(float)
    y = styled.vertices[:, 1]
    nrm = styled.vertex_normals[:, 1]
    x = styled.vertices[:, 0]
    sea = colors[(y < 0.05) & (nrm > 0.99) & (x < -10)]       # flat at 0, far from ramp
    grass = colors[(y > 23.9) & (nrm > 0.99) & (x > 26)]      # plateau, past the rim bleed
    cliff = colors[(nrm < 0.6) & (y > 2.0) & (y < 22.0)]      # mid-ramp faces
    assert (sea[:, 2] > sea[:, 0]).all()                      # seafloor: blue over red
    assert (grass[:, 1] > grass[:, 0]).all()                  # grass: green dominant
    assert len(cliff) and (cliff[:, 0] > cliff[:, 1]).all()   # cliff: warm sand


# --- decay, overgrowth, file identities (visual-identity v2) -------------------

def _bld(cx, cz, w=8.0, d=6.0, h=9.0):
    return {"type": "building", "height": h, "ridge": h, "roof": "flat",
            "footprint": [[cx - w/2, cz - d/2], [cx + w/2, cz - d/2],
                          [cx + w/2, cz + d/2], [cx - w/2, cz + d/2]]}


def _road(x0, z0, x1, z1):
    return {"type": "road", "path": [[x0, z0], [x1, z1]], "width": 5.0, "kind": "residential"}


def _decay_identity(**kw):
    base = dict(ruin_fraction=0.5, damage_fraction=0.5, weather_variation=0.5)
    base.update(kw)
    return VisualIdentity(**base)


def test_decay_off_is_byte_identical_to_v1():
    feats = [_bld(0, 0), _bld(12, 0)]
    a, b = trimesh.Scene(), trimesh.Scene()
    instance_buildings(a, _flat_ground(), feats, VisualIdentity())
    instance_buildings(b, _flat_ground(), feats, VisualIdentity(ruin_fraction=0.0))
    assert len(a.geometry) == len(b.geometry)


def test_decay_is_deterministic():
    feats = [_bld(i * 15.0, 0) for i in range(8)]
    counts = []
    for _ in range(2):
        s = trimesh.Scene()
        instance_buildings(s, _flat_ground(200), feats, _decay_identity())
        counts.append(sorted(round(g.bounds[1][1], 3) for g in s.geometry.values()))
    assert counts[0] == counts[1]


def test_ruin_replaces_building_with_low_rubble():
    feats = [_bld(0, 0, h=12.0)]
    ruined = trimesh.Scene()
    instance_buildings(ruined, _flat_ground(), feats,
                       VisualIdentity(ruin_fraction=1.0))
    # everything placed is debris: nothing anywhere near the original 12 m
    top = max(g.bounds[1][1] for g in ruined.geometry.values())
    assert top < 8.0
    assert len(ruined.geometry) >= 5   # piles + remnant wall stubs


def test_damage_breaks_the_roofline():
    feats = [_bld(0, 0, h=10.0)]
    damaged = trimesh.Scene()
    instance_buildings(damaged, _flat_ground(), feats,
                       VisualIdentity(damage_fraction=1.0))
    pristine = trimesh.Scene()
    instance_buildings(pristine, _flat_ground(), feats, VisualIdentity())
    top_d = max(g.bounds[1][1] for g in damaged.geometry.values())
    top_p = max(g.bounds[1][1] for g in pristine.geometry.values())
    assert top_d < top_p  # parapet dropped, roof gone


def test_overgrowth_scatters_only_when_asked():
    from automap.presentation import scatter_overgrowth
    feats = [_road(-15, 0, 15, 0)]
    off = trimesh.Scene()
    assert scatter_overgrowth(off, _flat_ground(), feats, VisualIdentity()) == 0
    on = trimesh.Scene()
    n = scatter_overgrowth(on, _flat_ground(), feats,
                           VisualIdentity(overgrowth_density=30.0))
    assert n > 0 and len(on.geometry) >= n  # clumps are multi-part


def test_identity_from_dict_loads_the_file_form():
    import json
    from pathlib import Path
    from automap.presentation import identity_from_dict
    doc = json.loads((Path(__file__).parent.parent / "identities" / "postapo.json").read_text())
    ident = identity_from_dict(doc)
    assert ident.name == "postapo"
    assert ident.ruin_fraction > 0 and ident.overgrowth_density > 0
    assert isinstance(ident.roof_palette[0], tuple)     # lists became tuples
    assert ident.environment["fog_density"] > 0
    # unknown keys are ignored, not fatal (schemas may run ahead)
    ident2 = identity_from_dict({"name": "x", "from_the_future": 1})
    assert ident2.name == "x"


# --- textures (visual-identity v2.1) + decoration naming -----------------------

TEX = {"facade_style": "brick", "window_states": {"dark": 1},
       "roof_style": "tin", "road_texture": True, "variants": 3}


def test_textured_buildings_carry_uv_and_image():
    feats = [_bld(0, 0, h=10.5), _bld(20, 0, h=7.0)]
    s = trimesh.Scene()
    instance_buildings(s, _flat_ground(80), feats, VisualIdentity(textures=TEX))
    textured = [g for g in s.geometry.values()
                if getattr(getattr(g.visual, "material", None), "baseColorTexture", None) is not None]
    assert len(textured) >= 4                       # walls + roofs for both
    for g in textured:
        assert g.visual.uv is not None and len(g.visual.uv) == len(g.vertices)
    # storey-awareness: the taller building's wall UVs reach a higher v
    vmaxes = sorted(float(g.visual.uv[:, 1].max()) for g in textured)
    assert vmaxes[-1] > 2.5                         # ~10.5m / 3m storeys


def test_texture_images_are_shared_across_buildings():
    feats = [_bld(i * 15.0, 0) for i in range(10)]
    s = trimesh.Scene()
    instance_buildings(s, _flat_ground(200), feats, VisualIdentity(textures=TEX))
    images = {id(g.visual.material.baseColorTexture) for g in s.geometry.values()
              if getattr(getattr(g.visual, "material", None), "baseColorTexture", None) is not None}
    assert len(images) <= 2 * TEX["variants"]       # pooled, not per-building


def test_no_textures_means_no_uv_anywhere():
    feats = [_bld(0, 0)]
    s = trimesh.Scene()
    instance_buildings(s, _flat_ground(), feats, VisualIdentity())
    for g in s.geometry.values():
        assert getattr(g.visual, "uv", None) is None or len(g.visual.uv) == 0


def test_decoration_meshes_are_named_deco():
    from automap.presentation import instance_water, scatter_overgrowth
    feats = [_road(-15, 0, 15, 0),
             {"type": "water", "outline": [[-10, -10], [10, -10], [10, 10]]}]
    s = trimesh.Scene()
    instance_roads(s, _flat_ground(), feats, VisualIdentity(textures=TEX))
    scatter_overgrowth(s, _flat_ground(), feats, VisualIdentity(overgrowth_density=30.0))
    instance_water(s, _flat_ground(), feats, VisualIdentity())
    names = list(s.geometry)
    assert names and all(n.startswith("deco_") for n in names), names
    kinds = {n.split("_")[1] for n in names}
    assert {"road", "weed", "water"} <= kinds


def test_textured_road_uv_runs_along_length():
    from automap.presentation import road_ribbon
    ribbon = road_ribbon(np.array([[-30.0, 0.0], [30.0, 0.0]]), 6.0, _flat_ground(80),
                         uv_length_m=6.0)
    assert ribbon.visual.uv is not None
    v = ribbon.visual.uv[:, 1]
    assert v.max() > 8.0                            # 60 m / 6 m per tile


# --- winding + crumble (the missing-walls fix) ----------------------------------

def test_textured_walls_face_outward_for_both_orientations():
    # regression: a sign slip here culls every wall from outside
    from automap.presentation import _textured_walls
    from automap.facades import wall_tile
    img = wall_tile("brick", (0.4, 0.3, 0.2), (0.9, 0.9, 0.8), (0.1, 0.1, 0.1), "dark", 0)
    for corners in ([[-5, -5], [5, -5], [5, 5], [-5, 5]],     # CCW
                    [[-5, 5], [5, 5], [5, -5], [-5, -5]]):    # CW
        c = np.asarray(corners, float)
        m = _textured_walls(c, np.zeros(4), np.full(4, 9.0), 0.0, img, (1, 1, 1), 3.5, 3.0)
        centre = c.mean(axis=0)
        for f in m.faces:
            tri = m.vertices[f]
            n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            mid = tri.mean(axis=0)
            assert np.dot([n[0], n[2]], [mid[0] - centre[0], mid[2] - centre[1]]) >= 0


def test_damaged_buildings_keep_all_four_walls():
    # the crumble contract: sections erode, walls never disappear
    feats = [_bld(0, 0, w=14.0, d=10.0, h=9.0)]
    s = trimesh.Scene()
    instance_buildings(s, _flat_ground(), feats,
                       VisualIdentity(damage_fraction=1.0, textures=TEX))
    walls = [g for g in s.geometry.values()
             if getattr(getattr(g.visual, "material", None), "baseColorTexture", None) is not None]
    assert walls, "crumbled walls missing entirely"
    m = walls[0]
    # every wall midpoint has geometry at least 1.5 m high (the crumble floor)
    c = np.asarray(feats[0]["footprint"], float)
    for i in range(4):
        mid = (c[i] + c[(i + 1) % 4]) / 2.0
        near = m.vertices[np.linalg.norm(m.vertices[:, [0, 2]] - mid, axis=1) < 3.0]
        assert len(near) > 0 and near[:, 1].max() >= 1.4, f"wall {i} vanished"
    # winding still outward on the crumbled strips
    centre = c.mean(axis=0)
    for f in m.faces:
        tri = m.vertices[f]
        n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        mid = tri.mean(axis=0)
        assert np.dot([n[0], n[2]], [mid[0] - centre[0], mid[2] - centre[1]]) >= -1e-9


def test_crumbled_flat_path_needs_no_texture():
    # decay without a textures block still crumbles (flat colors)
    feats = [_bld(0, 0, h=8.0)]
    s = trimesh.Scene()
    instance_buildings(s, _flat_ground(), feats, VisualIdentity(damage_fraction=1.0))
    tops = [float(g.vertices[:, 1].max()) for g in s.geometry.values()]
    assert max(tops) < 8.0                          # eroded below full height
    assert max(tops) > 1.4                          # but still standing


# --- minimap (world model -> identity-colored map) ------------------------------

def test_minimap_renders_features_in_identity_colors():
    from automap.minimap import render_minimap
    feats = [_bld(0, 0, w=10, d=10), _road(-30, 0, 30, 0),
             {"type": "water", "outline": [[-40, -40], [40, -40], [40, -20], [-40, -20]]}]
    ident = VisualIdentity()
    img, meta = render_minimap(feats, (-50, -50, 50, 50), ident, m_per_px=1.0)
    assert (img.width, img.height) == (100, 100)
    assert meta["m_per_px"] == 1.0 and meta["origin_x"] == -50
    px = img.load()
    def near(a, b): return all(abs(x - y) <= 12 for x, y in zip(a, b))
    grass = tuple(int(c * 0.9 * 255) for c in ident.grass_color)
    assert near(px[5, 95], grass)                       # open ground
    assert near(px[50, 25], tuple(int(c * 255) for c in ident.water_color))
    assert near(px[20, 50], tuple(int(c * 255) for c in ident.road_color))
    assert near(px[50, 50], tuple(int(c * 0.8 * 255) for c in ident.wall_color))


def test_minimap_caps_resolution_for_huge_scenes(tmp_path):
    from automap.minimap import MAX_PX, write_minimap
    meta = write_minimap([], (-3000, -3000, 3000, 3000), VisualIdentity(),
                         tmp_path / "m.minimap.png", m_per_px=1.0)
    assert max(meta["width"], meta["height"]) <= MAX_PX
    assert (tmp_path / "m.minimap.png").exists() and (tmp_path / "m.minimap.json").exists()


# --- per-building variety (visual-identity@2.3.0) ------------------------------

PALETTE = ((0.45, 0.26, 0.20), (0.52, 0.50, 0.46), (0.30, 0.28, 0.26))


def test_wall_palette_varies_flat_buildings():
    feats = [_bld(i * 15.0, 0) for i in range(10)]
    s = trimesh.Scene()
    instance_buildings(s, _flat_ground(200), feats, VisualIdentity(wall_palette=PALETTE))
    colors = set()
    for g in s.geometry.values():
        mat = getattr(g.visual, "material", None)
        if getattr(mat, "baseColorFactor", None) is not None:
            colors.add(tuple(np.round(np.asarray(mat.baseColorFactor[:3], float)
                                      / max(np.max(mat.baseColorFactor[:3]), 1e-9), 2)))
    hues = {tuple(np.round(np.asarray(p) / max(p), 2)) for p in PALETTE}
    assert len(colors & hues) >= 2                  # several pool entries in use


def test_wall_palette_is_deterministic():
    feats = [_bld(i * 15.0, 0) for i in range(6)]
    runs = []
    for _ in range(2):
        s = trimesh.Scene()
        instance_buildings(s, _flat_ground(120), feats, VisualIdentity(wall_palette=PALETTE))
        runs.append(sorted(
            tuple(np.round(np.asarray(g.visual.material.baseColorFactor[:3], float), 4))
            for g in s.geometry.values()
            if getattr(getattr(g.visual, "material", None), "baseColorFactor", None) is not None))
    assert runs[0] == runs[1]


def test_wall_palette_adds_no_texture_images():
    # the palette rides the material factor over shared near-neutral tiles
    feats = [_bld(i * 15.0, 0) for i in range(10)]
    s = trimesh.Scene()
    instance_buildings(s, _flat_ground(200), feats,
                       VisualIdentity(wall_palette=PALETTE, textures=TEX))
    images = {id(g.visual.material.baseColorTexture) for g in s.geometry.values()
              if getattr(getattr(g.visual, "material", None), "baseColorTexture", None) is not None}
    assert len(images) <= 2 * TEX["variants"]       # same pool bound as one color

    factors = {tuple(np.round(np.asarray(g.visual.material.baseColorFactor[:3]), 3))
               for g in s.geometry.values()
               if getattr(getattr(g.visual, "material", None), "baseColorTexture", None) is not None}
    assert len(factors) >= 4                        # ...while the buildings still differ


def test_weighted_pick_respects_weights():
    from automap.presentation import _weighted_pick, _instance_rng
    rng = _instance_rng(1.0, 2.0)
    draws = {_weighted_pick({"brick": 1, "siding": 1, "concrete": 0}, rng)
             for _ in range(200)}
    assert draws == {"brick", "siding"}             # both mix in, weight-0 never
    assert _weighted_pick(None, rng) is None
    assert _weighted_pick({}, rng) is None


def test_style_mixes_and_uv_jitter_are_deterministic():
    tex = dict(TEX, facade_styles={"brick": 2, "concrete": 1},
               roof_styles={"tin": 1, "membrane": 1}, uv_jitter=0.12)
    feats = [_bld(i * 15.0, 0) for i in range(8)]
    runs = []
    for _ in range(2):
        s = trimesh.Scene()
        instance_buildings(s, _flat_ground(160), feats, VisualIdentity(textures=tex))
        runs.append(sorted(
            (id and 0,  # placeholder to keep tuple shape stable
             tuple(np.round(np.asarray(g.visual.material.baseColorFactor[:3]), 4)),
             float(np.round(g.visual.uv[:, 1].max(), 4)))
            for g in s.geometry.values()
            if getattr(getattr(g.visual, "material", None), "baseColorTexture", None) is not None
            and getattr(g.visual, "uv", None) is not None and len(g.visual.uv)))
    assert runs[0] == runs[1]
