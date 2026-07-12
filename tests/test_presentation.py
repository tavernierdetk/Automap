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
