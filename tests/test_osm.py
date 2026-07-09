"""Tests for the OSM fetch/parse layer (pure logic; no network).

Reconciliation with scan detections lives in automap.worldmodel and is
tested in test_worldmodel.py; here we only check that OSM elements parse
into correct observation batches.
"""
import numpy as np

from automap.features import Road, Water
from automap.osm import (
    building_batch,
    buildings_from_osm,
    coastline_from_osm,
    overpass_query,
    road_width,
    roads_from_osm,
    tag_heights,
)


def _rect(cx, cz, w=10.0, d=6.0):
    return [(cx - w / 2, cz - d / 2), (cx + w / 2, cz - d / 2),
            (cx + w / 2, cz + d / 2), (cx - w / 2, cz + d / 2)]


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


def test_building_batch_footprint_only_when_untagged():
    (feat,) = building_batch([_osm(2.0, 1.0)])
    assert feat["type"] == "building"
    assert np.allclose(np.asarray(feat["footprint"]).mean(axis=0), [2.0, 1.0], atol=0.1)
    assert "height" not in feat and "roof" not in feat    # OSM observed no heights


def test_building_batch_carries_tagged_heights():
    (feat,) = building_batch([_osm(50.0, 50.0, {"building": "yes", "height": "6"})])
    assert feat["ridge"] == 6.0 and feat["height"] == 3.6
    assert feat["roof"] == "gable"                        # ridge - wall >= 1 m


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


