"""Placement solver tests: footprint-fit recovers a known rigid transform,
and georeference placement matches the anchor offset."""
import numpy as np

from automap.placement import Placement, fit_footprint, from_georeference


def _rect(cx, cz, w, d, ang_deg=0.0):
    a = np.radians(ang_deg)
    corners = np.array([[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]])
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    return corners @ rot.T + [cx, cz]


def test_fit_footprint_recovers_translation_and_yaw():
    source = _rect(0.0, 0.0, 12.0, 8.0, 0.0)          # at origin, axis-aligned
    target = _rect(30.0, -15.0, 12.0, 8.0, 25.0)      # moved + rotated 25°
    p = fit_footprint(source, target)
    placed = p.apply_xz(source)
    # placed source should sit on the target (bbox corners align)
    drift = np.abs(np.sort(placed, 0) - np.sort(target, 0)).max()
    assert drift < 1e-6
    assert np.allclose(p.ground_xz, [30.0, -15.0], atol=1e-6)


def test_fit_footprint_resolves_axis_flip():
    # target rotated 180° from source must not double-flip
    source = _rect(0.0, 0.0, 10.0, 4.0, 0.0)
    target = _rect(5.0, 5.0, 10.0, 4.0, 180.0)
    p = fit_footprint(source, target)
    placed = p.apply_xz(source)
    assert np.abs(np.sort(placed, 0) - np.sort(target, 0)).max() < 1e-6


def test_from_georeference_offsets_by_anchor_difference():
    src = {"eastings": 588160.0, "northings": 5232220.0, "crs": "EPSG:32620"}
    scene = {"eastings": 588153.2, "northings": 5232215.5, "crs": "EPSG:32620"}
    tgt = _rect(6.8, -4.5, 8.0, 6.0)
    p = from_georeference(src, scene, tgt)
    assert np.allclose(p.translate_xz, [6.8, -4.5], atol=1e-6)   # dE, -dN
    assert p.yaw_deg == 0.0


def test_from_georeference_rejects_crs_mismatch():
    import pytest
    with pytest.raises(ValueError, match="CRS mismatch"):
        from_georeference({"eastings": 0, "northings": 0, "crs": "EPSG:32620"},
                          {"eastings": 0, "northings": 0, "crs": "EPSG:32618"},
                          _rect(0, 0, 1, 1))
