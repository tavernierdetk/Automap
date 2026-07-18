"""Prop sprites: determinism, alpha, anchors, catalog shape."""
from automap.props2d import PROPS, build_props

IDENTITY = {"name": "t", "trunk_color": (0.3, 0.25, 0.2),
            "canopy_color": (0.2, 0.4, 0.2), "cliff_color": (0.5, 0.5, 0.5)}


def test_every_prop_variant_renders_with_alpha():
    images, catalog = build_props(IDENTITY)
    import numpy as np
    for key, img in images.items():
        assert img.mode == "RGBA"
        a = np.asarray(img)
        assert (a[:, :, 3] > 0).any(), key + " has visible pixels"
        assert (a[:, :, 3] == 0).any(), key + " has transparency"
    assert len(images) == sum(s["variants"] for s in PROPS.values())
    for key, spec in catalog["props"].items():
        assert spec["anchor_y"] <= spec["size"][1]
        assert spec["collision_r"] > 0


def test_deterministic():
    a, _ = build_props(IDENTITY)
    b, _ = build_props(IDENTITY)
    assert all(a[k].tobytes() == b[k].tobytes() for k in a)


def test_foot_is_opaque_at_anchor():
    # the anchor line must land on drawn pixels (the foot), not empty air
    import numpy as np
    images, catalog = build_props(IDENTITY)
    for key, spec in catalog["props"].items():
        a = np.asarray(images[key])
        w = spec["size"][0]
        band = a[spec["anchor_y"] - 8:spec["anchor_y"], w // 2 - 6:w // 2 + 6, 3]
        assert (band > 0).any(), key + " anchor sits on the sprite's foot"
