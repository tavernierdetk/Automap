"""Tests for the presentation layer's procedural proxy asset."""
from automap.presentation import VisualIdentity, proxy_tree_parts


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
