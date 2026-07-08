"""Tests for the OSM overlay merge (pure logic; no network)."""
import numpy as np

from automap.features import Building, Road, Water
from automap.osm import (
    buildings_from_osm,
    coastline_from_osm,
    merge_osm_buildings,
    overpass_query,
    road_width,
    roads_from_osm,
    tag_heights,
)


def _rect(cx, cz, w=10.0, d=6.0):
    return [(cx - w / 2, cz - d / 2), (cx + w / 2, cz - d / 2),
            (cx + w / 2, cz + d / 2), (cx - w / 2, cz + d / 2)]


def _det(cx, cz, **kw):
    kw.setdefault("height", 4.0)
    kw.setdefault("ridge", 6.0)
    kw.setdefault("roof", "gable")
    kw.setdefault("roof_color", (90, 80, 70))
    return Building(footprint=_rect(cx, cz), **kw)


def _osm(cx, cz, tags=None, w=8.0, d=5.0):
    poly = np.array(_rect(cx, cz, w, d) + [_rect(cx, cz, w, d)[0]])
    return {"poly": poly, "tags": tags or {"building": "yes"}}


def test_overpass_query_mentions_layers():
    q = overpass_query((-61.85, 47.23, -61.84, 47.24))
    for key in ("building", "highway", "coastline", "water"):
        assert key in q


def test_buildings_from_osm_parses_ways():
    doc = {"elements": [
        {"type": "way", "tags": {"building": "house"},
         "geometry": [{"lon": 1.0, "lat": 1.0}, {"lon": 2.0, "lat": 1.0},
                      {"lon": 2.0, "lat": 2.0}, {"lon": 1.0, "lat": 1.0}]},
        {"type": "way", "tags": {"highway": "residential"},
         "geometry": [{"lon": 0.0, "lat": 0.0}, {"lon": 5.0, "lat": 5.0}]},
    ]}
    out = buildings_from_osm(doc, lambda lons, lats: (lons * 10, lats * 10))
    assert len(out) == 1                              # highway is not a building
    assert out[0]["poly"].shape == (4, 2)
    assert out[0]["poly"][0, 0] == 10.0               # projected


def test_tag_heights():
    assert tag_heights({"height": "7.5"}) == (4.5, 7.5)
    wall, ridge = tag_heights({"building:levels": "2"}, level_m=3.0)
    assert wall == 6.0 and ridge > wall
    assert tag_heights({"building": "yes"}) is None
    assert tag_heights({"height": "tall"}) is None


def test_merge_matched_keeps_scan_attrs_takes_osm_footprint():
    det = [_det(0.0, 0.0)]
    merged = merge_osm_buildings(det, [_osm(2.0, 1.0)])   # 2.2 m apart -> match
    assert len(merged) == 1
    b = merged[0]
    assert b.source == "scan+osm"
    assert b.height == 4.0 and b.roof == "gable"          # scan attributes kept
    c = np.asarray(b.footprint).mean(axis=0)              # OSM footprint adopted
    assert np.allclose(c, [2.0, 1.0], atol=0.1)


def test_merge_backfills_unmatched_osm():
    merged = merge_osm_buildings([], [_osm(50.0, 50.0, {"building": "yes", "height": "6"})])
    assert len(merged) == 1
    b = merged[0]
    assert b.source == "osm" and b.ridge == 6.0


def test_merge_keeps_scan_only():
    merged = merge_osm_buildings([_det(0.0, 0.0)], [_osm(100.0, 100.0)])
    srcs = sorted(b.source for b in merged)
    assert srcs == ["osm", "scan"]


def test_roads_and_coastline_parsing():
    doc = {"elements": [
        {"type": "way", "tags": {"highway": "residential"},
         "geometry": [{"lon": 0.0, "lat": 0.0}, {"lon": 1.0, "lat": 0.0}]},
        {"type": "way", "tags": {"natural": "coastline"},
         "geometry": [{"lon": 0.0, "lat": 2.0}, {"lon": 1.0, "lat": 2.0}]},
        {"type": "way", "tags": {"building": "yes"},
         "geometry": [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 0},
                      {"lon": 1, "lat": 1}, {"lon": 0, "lat": 0}]},
    ]}
    ident = lambda lons, lats: (lons, lats)
    roads = roads_from_osm(doc, ident)
    assert len(roads) == 1 and roads[0]["tags"]["highway"] == "residential"
    coast = coastline_from_osm(doc, ident)
    assert len(coast) == 1 and coast[0].shape == (2, 2)


def test_road_width():
    assert road_width({"highway": "primary"}) == 8.0
    assert road_width({"highway": "footway"}) < 3.0
    assert road_width({"highway": "residential", "width": "7.5"}) == 7.5
    assert road_width({"highway": "weird_new_kind"}) == 5.0


def test_road_water_features_schema():
    r = Road(path=[(0.0, 0.0), (10.0, 0.0)], width=6.0, kind="residential").as_feature()
    assert r["type"] == "road" and r["width"] == 6.0 and len(r["path"]) == 2
    w = Water(kind="sea", outline=[(0.0, 0.0), (5.0, 5.0)]).as_feature()
    assert w["type"] == "water" and w["kind"] == "sea" and w["source"] == "osm"


def test_merge_is_one_to_one():
    # two detections near one OSM footprint: only the closest pairs up
    det = [_det(0.0, 0.0), _det(3.0, 0.0)]
    merged = merge_osm_buildings(det, [_osm(2.5, 0.0)])
    srcs = sorted(b.source for b in merged)
    assert srcs == ["scan", "scan+osm"]
    matched = next(b for b in merged if b.source == "scan+osm")
    assert np.allclose(np.asarray(matched.footprint).mean(axis=0), [2.5, 0.0], atol=0.1)