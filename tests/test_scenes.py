"""Tests for multi-scene namespacing and the manifest."""
from automap.scenes import load_manifest, manifest_path, scene_paths, upsert_scene


def test_scene_paths(tmp_path):
    sp = scene_paths(tmp_path, "birch-park")
    base = tmp_path / "work" / "birch-park"
    assert sp.frames == base / "frames"
    assert sp.odm == base / "odm"
    assert sp.glb == base / "mesh" / "birch-park.glb"
    assert sp.obj == base / "odm" / "odm_texturing" / "odm_textured_model_geo.obj"


def test_manifest_empty_when_missing(tmp_path):
    assert load_manifest(tmp_path) == {"scenes": {}}


def test_manifest_upsert_roundtrip(tmp_path):
    upsert_scene(tmp_path, "a", {"glb": "work/a/mesh/a.glb", "frames": 30})
    upsert_scene(tmp_path, "b", {"glb": "work/b/mesh/b.glb", "frames": 40})
    data = load_manifest(tmp_path)
    assert set(data["scenes"]) == {"a", "b"}
    assert data["scenes"]["a"]["frames"] == 30
    # re-ingest replaces the entry in place
    upsert_scene(tmp_path, "a", {"glb": "work/a/mesh/a.glb", "frames": 99})
    data = load_manifest(tmp_path)
    assert data["scenes"]["a"]["frames"] == 99
    assert set(data["scenes"]) == {"a", "b"}
    assert manifest_path(tmp_path).exists()


def test_manifest_recovers_from_corruption(tmp_path):
    p = manifest_path(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text("{ not valid json")
    assert load_manifest(tmp_path) == {"scenes": {}}
