"""Fusion-engine tests (worldmodel v1): stable ids, per-attribute provenance,
source priority, manual-edit survival, and the retirement rule.

All pure logic on plain dicts; the observation batches mimic what stage 5
builds from automap.features / automap.osm.
"""
import json

import numpy as np
import pytest

from automap import worldmodel as wm


def _tree(x, z, height=8.0, radius=2.0):
    return {"type": "tree", "x": x, "z": z, "height": height, "radius": radius}


def _bld(cx, cz, w=10.0, d=6.0, **kw):
    corners = [[cx - w / 2, cz - d / 2], [cx + w / 2, cz - d / 2],
               [cx + w / 2, cz + d / 2], [cx - w / 2, cz + d / 2]]
    f = {"type": "building", "footprint": corners, "height": 4.0, "ridge": 6.0,
         "roof": "gable", "roof_color": [90, 80, 70]}
    f.update(kw)
    return f


def _road(kind="residential"):
    return {"type": "road", "path": [[0.0, 0.0], [20.0, 5.0]], "width": 6.0, "kind": kind}


# ---------------------------------------------------------------- documents

def test_new_document_shape():
    doc = wm.new_document(scene="park")
    assert doc["frame"] == wm.FRAME
    assert doc["scene"] == "park" and doc["features"] == []


def test_load_upgrades_v1_documents(tmp_path):
    v1 = {"frame": wm.FRAME, "features": [dict(_tree(1.0, 2.0), source="scan")]}
    p = tmp_path / "features.json"
    p.write_text(json.dumps(v1))
    doc = wm.load(p)
    f = doc["features"][0]
    assert f["id"] == "tree-0000"
    assert "provenance" not in f          # legacy attrs stay unowned
    assert doc["counters"]["tree"] == 1


def test_save_round_trips(tmp_path):
    doc = wm.fuse(wm.new_document(), [_tree(0.0, 0.0)], "scan")
    p = tmp_path / "features.json"
    wm.save(doc, p)
    assert wm.load(p) == doc


# ------------------------------------------------------------------- fusion

def test_fuse_into_empty_assigns_ids_and_provenance():
    doc = wm.fuse(wm.new_document(), [_tree(0.0, 0.0), _tree(30.0, 0.0)], "scan")
    ids = [f["id"] for f in doc["features"]]
    assert ids == ["tree-0000", "tree-0001"]
    f = doc["features"][0]
    assert f["provenance"] == {k: "scan" for k in ("x", "z", "height", "radius")}
    assert f["source"] == "scan"
    assert doc["counters"] == {"tree": 2}


def test_rerun_keeps_ids_and_refreshes_values():
    doc = wm.fuse(wm.new_document(), [_tree(0.0, 0.0, height=8.0)], "scan")
    doc = wm.fuse(doc, [_tree(0.5, 0.2, height=9.5)], "scan")   # drifted re-detection
    assert len(doc["features"]) == 1
    f = doc["features"][0]
    assert f["id"] == "tree-0000"
    assert f["height"] == 9.5 and f["x"] == 0.5                 # same source refreshes


def test_rerun_retires_wholly_owned_unreported_features():
    doc = wm.fuse(wm.new_document(), [_tree(0.0, 0.0), _tree(50.0, 0.0)], "scan")
    doc = wm.fuse(doc, [_tree(0.0, 0.0)], "scan")               # second tree gone
    assert [f["id"] for f in doc["features"]] == ["tree-0000"]
    # ids are never reused after retirement
    doc = wm.fuse(doc, [_tree(0.0, 0.0), _tree(80.0, 0.0)], "scan")
    assert [f["id"] for f in doc["features"]] == ["tree-0000", "tree-0002"]


def test_retirement_respects_observed_types():
    doc = wm.fuse(wm.new_document(), [_tree(0.0, 0.0)], "scan")
    # a scan batch with only buildings, but declared as observing trees too
    doc2 = wm.fuse(doc, [_bld(100.0, 100.0)], "scan",
                   observed_types={"tree", "building"})
    assert not [f for f in doc2["features"] if f["type"] == "tree"]
    # without the declaration, the tree survives (batch had no tree statement)
    doc3 = wm.fuse(doc, [_bld(100.0, 100.0)], "scan")
    assert [f for f in doc3["features"] if f["type"] == "tree"]


def test_manual_touch_prevents_retirement():
    doc = wm.fuse(wm.new_document(), [_tree(0.0, 0.0)], "scan")
    doc["features"][0]["provenance"]["height"] = "manual"
    doc = wm.fuse(doc, [], "scan", observed_types={"tree"})
    assert len(doc["features"]) == 1                            # hand-touched: survives


def test_manual_attribute_survives_regeneration():
    doc = wm.fuse(wm.new_document(), [_tree(0.0, 0.0, height=8.0)], "scan")
    f = doc["features"][0]
    f["height"] = 12.0
    f["provenance"]["height"] = "manual"                        # the v1 edit mechanism
    doc = wm.fuse(doc, [_tree(0.0, 0.0, height=8.0)], "scan")
    f = doc["features"][0]
    assert f["height"] == 12.0 and f["provenance"]["height"] == "manual"
    assert f["x"] == 0.0 and f["provenance"]["x"] == "scan"     # rest still refreshes
    assert f["source"] == "manual+scan"


def test_osm_over_scan_footprint_scan_over_osm_heights():
    doc = wm.fuse(wm.new_document(), [_bld(0.0, 0.0, height=4.0, ridge=6.0)], "scan")
    osm_obs = {"type": "building",
               "footprint": [[-4.0, -2.0], [4.0, -2.0], [4.0, 3.0], [-4.0, 3.0]],
               "height": 3.0, "ridge": 9.0, "roof": "flat"}     # tag-derived
    doc = wm.fuse(doc, [osm_obs], "osm")
    assert len(doc["features"]) == 1
    b = doc["features"][0]
    assert b["footprint"] == osm_obs["footprint"]               # survey footprint wins
    assert b["provenance"]["footprint"] == "osm"
    assert b["height"] == 4.0 and b["ridge"] == 6.0             # scan heights win
    assert b["roof"] == "gable" and b["provenance"]["roof"] == "scan"
    assert b["source"] == "osm+scan"


def test_bim_dropin_outranks_and_survives_scan_rerun():
    # a scan-detected building, then an IFC plan dropped onto it (source bim)
    doc = wm.fuse(wm.new_document(), [_bld(0.0, 0.0, height=4.0)], "scan")
    dropin = dict(_bld(0.2, 0.1, height=7.5, ridge=9.0),
                  representation={"kind": "asset", "asset": "assets/building-0000.glb"})
    doc = wm.fuse(doc, [dropin], "bim")
    b = doc["features"][0]
    assert b["height"] == 7.5 and b["provenance"]["height"] == "bim"    # bim > scan
    assert b["provenance"]["footprint"] == "bim"
    assert b["representation"]["kind"] == "asset"
    # a later scan re-run must not clobber the dropped-in geometry
    doc = wm.fuse(doc, [_bld(0.0, 0.0, height=4.0)], "scan",
                  observed_types={"building"})
    b = doc["features"][0]
    assert b["height"] == 7.5 and b["representation"]["asset"].endswith(".glb")
    assert b["provenance"]["footprint"] == "bim"


def test_osm_backfill_and_finalize_defaults():
    footprint_only = {"type": "building",
                      "footprint": [[50.0, 50.0], [58.0, 50.0], [58.0, 55.0], [50.0, 55.0]]}
    doc = wm.fuse(wm.new_document(), [footprint_only], "osm")
    doc = wm.finalize(doc)
    b = doc["features"][0]
    assert b["height"] == 3.0 and b["ridge"] == 5.0             # defaults filled
    assert b["provenance"]["height"] == "default"
    assert b["lod"] == 2 and b["source"] == "default+osm"
    # a later real observation outranks the defaults
    doc = wm.fuse(doc, [_bld(54.0, 52.5, height=4.5, ridge=7.0)], "scan")
    b = doc["features"][0]
    assert b["height"] == 4.5 and b["provenance"]["height"] == "scan"


def test_osm_refetch_retires_deleted_backfills_despite_defaults():
    footprint_only = {"type": "building",
                      "footprint": [[50.0, 50.0], [58.0, 50.0], [58.0, 55.0], [50.0, 55.0]]}
    doc = wm.finalize(wm.fuse(wm.new_document(), [footprint_only], "osm"))
    doc = wm.fuse(doc, [], "osm", observed_types={"building"})
    assert doc["features"] == []      # default-filled attrs don't block retirement


def test_matching_is_one_to_one_nearest_first():
    doc = wm.fuse(wm.new_document(),
                  [_bld(0.0, 0.0), _bld(3.0, 0.0)], "scan")
    doc = wm.fuse(doc, [_bld(2.5, 0.0, w=8.0, d=5.0)], "osm")
    srcs = sorted(f["source"] for f in doc["features"])
    assert srcs == ["osm+scan", "scan"]
    matched = next(f for f in doc["features"] if f["source"] == "osm+scan")
    assert np.allclose(np.asarray(matched["footprint"]).mean(axis=0), [2.5, 0.0], atol=0.1)


def test_roads_and_water_get_ids_and_stay_stable_on_refetch():
    batch = [_road(), {"type": "water", "kind": "sea",
                       "outline": [[0.0, 40.0], [30.0, 42.0]]}]
    doc = wm.fuse(wm.new_document(), batch, "osm")
    doc = wm.fuse(doc, batch, "osm")
    assert sorted(f["id"] for f in doc["features"]) == ["road-0000", "water-0000"]


def test_fuse_does_not_mutate_input():
    doc = wm.fuse(wm.new_document(), [_tree(0.0, 0.0)], "scan")
    before = json.dumps(doc, sort_keys=True)
    wm.fuse(doc, [_tree(0.0, 0.0, height=20.0)], "scan")
    assert json.dumps(doc, sort_keys=True) == before


# --------------------------------------------------------------- validation

def test_finalized_fused_doc_validates_when_registry_present(tmp_path):
    pytest.importorskip("platform_specs")
    doc = wm.new_document(scene="park")
    doc = wm.fuse(doc, [_tree(0.0, 0.0), _bld(20.0, 0.0)], "scan")
    doc = wm.fuse(doc, [_road()], "osm")
    doc = wm.finalize(doc)
    assert wm.validate(doc) is True
