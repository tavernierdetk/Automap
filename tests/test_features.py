"""Tests for tree detection (semantic layer)."""
import numpy as np

from automap.features import detect_trees, excess_green


def _two_bumps(H=60, W=60, peak=8.0, sigma=4.0, centers=((15, 15), (40, 45))):
    yy, xx = np.mgrid[0:H, 0:W]
    chm = np.zeros((H, W))
    for cy, cx in centers:
        chm += peak * np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * sigma ** 2)))
    return chm


def _green(H, W):
    rgb = np.zeros((H, W, 3), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = 40, 200, 40
    return rgb


def test_excess_green():
    green = np.array([[[40, 200, 40]]], np.uint8)
    gray = np.array([[[128, 128, 128]]], np.uint8)
    assert excess_green(green)[0, 0] > 0.2
    assert abs(excess_green(gray)[0, 0]) < 0.05


def test_detect_finds_bumps():
    chm = _two_bumps()
    trees = detect_trees(chm, _green(60, 60), pixel_size=1.0,
                         min_height=2.0, exg_threshold=0.05, min_spacing_m=5.0)
    assert 2 <= len(trees) <= 4
    assert max(t.height for t in trees) > 6.0        # peak ~8 m


def test_detect_none_when_short():
    trees = detect_trees(np.full((30, 30), 0.5), _green(30, 30),
                         pixel_size=1.0, min_height=2.0)
    assert trees == []


def test_detect_none_when_not_green():
    chm = _two_bumps(40, 40, centers=((20, 20),))
    gray = np.full((40, 40, 3), 120, np.uint8)       # tall but not vegetation
    assert detect_trees(chm, gray, pixel_size=1.0, min_height=2.0, exg_threshold=0.1) == []


def test_detect_coords_centered():
    # single central bump -> tree near origin in the centered metric frame
    chm = _two_bumps(41, 41, centers=((20, 20),))
    trees = detect_trees(chm, _green(41, 41), pixel_size=2.0, min_height=2.0, min_spacing_m=6.0)
    assert trees
    t = min(trees, key=lambda t: t.x ** 2 + t.z ** 2)
    assert abs(t.x) < 2.0 and abs(t.z) < 2.0         # center pixel -> ~origin
