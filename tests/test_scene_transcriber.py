"""SceneCreator transcriber: authored .tscn -> level@2 documents (the reverse
projection). Fixture is a minimal scene in the original game's vocabulary."""
from pathlib import Path

from automap.scene_transcriber import build_uid_map, parse_tscn, transcribe

FIXTURE = '''[gd_scene load_steps=6 format=3 uid="uid://aaaa1"]

[ext_resource type="Script" path="res://System/Overworld/SceneSpawn.gd" id="1"]
[ext_resource type="Script" path="res://System/Overworld/TeleportArea2D.gd" id="2"]
[ext_resource type="Script" path="res://System/Overworld/OverworldPlayer.gd" id="3"]
[ext_resource type="Script" path="res://System/Overworld/OverworldNPC.gd" id="4"]
[ext_resource type="Texture2D" path="res://Assets/GenericBGs/room.png" id="5"]

[sub_resource type="RectangleShape2D" id="r1"]
size = Vector2(80, 120)

[node name="Root" type="Node2D"]

[node name="BG" type="Sprite2D" parent="."]
position = Vector2(500, 300)
scale = Vector2(0.5, 0.75)
texture = ExtResource("5")

[node name="S" type="Node2D" parent="."]
position = Vector2(100, 200)
script = ExtResource("1")
tag = "west"

[node name="T" type="Area2D" parent="."]
position = Vector2(10, 5)
script = ExtResource("2")
target_scene_path = "uid://bbbb2"
target_spawn_tag = "west"

[node name="CollisionShape2D" type="CollisionShape2D" parent="T"]
position = Vector2(30, 40)
shape = SubResource("r1")

[node name="Wall" type="StaticBody2D" parent="."]

[node name="CollisionShape2D" type="CollisionShape2D" parent="Wall"]
position = Vector2(600, 50)
shape = SubResource("r1")

[node name="OverworldPlayer" type="CharacterBody2D" parent="."]
position = Vector2(250, 260)
script = ExtResource("3")
creature_slug = "zo"

[node name="CharacterBody2D" type="CharacterBody2D" parent="."]
position = Vector2(400, 260)
script = ExtResource("4")
creature_slug = "carmilla"

[node name="Ghost" type="Node2D" parent="."]
position = Vector2(1, 1)
script = null
'''


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_transcribe_lifts_the_full_vocabulary(tmp_path):
    other = FIXTURE.replace("uid://aaaa1", "uid://bbbb2")
    _write(tmp_path, "next_room.tscn", other)
    scene = _write(tmp_path, "room_a.tscn", FIXTURE)
    doc, skipped = transcribe(scene, build_uid_map(tmp_path))
    assert doc["id"] == "room_a"
    assert doc["background"] == {"file": "room.png", "pos": [500, 300], "scale": [0.5, 0.75]}
    assert doc["spawns"] == [{"tag": "west", "pos": [100, 200]}]
    t = doc["teleports"][0]
    assert t["target_level"] == "next_room" and t["target_spawn_tag"] == "west"
    assert t["rect"] == {"pos": [40, 45], "size": [80, 120]}  # area offset + shape offset
    assert doc["collision_rects"] == [{"pos": [600, 50], "size": [80, 120]}]
    assert doc["player"] == {"slug": "zo", "pos": [250, 260]}
    assert doc["npcs"] == [{"slug": "carmilla", "pos": [400, 260]}]
    assert any("Ghost" in s for s in skipped)  # orphan reported, not dropped


def test_no_spawn_synthesizes_default_loudly(tmp_path):
    bare = "\n".join(l for l in FIXTURE.splitlines()
                     if "tag = " not in l and 'name="S"' not in l and "ExtResource(\"1\")" not in l)
    scene = _write(tmp_path, "bare.tscn", bare)
    doc, skipped = transcribe(scene, {})
    assert doc["spawns"][0]["tag"] == "default"
    assert any("synthesized" in s for s in skipped)


def test_committed_originals_still_roundtrip():
    ref = Path.home() / "Cowork" / "entropy-integrated" / "Scenes" / "Test" / "JeuZoeMila"
    if not ref.exists():
        import pytest
        pytest.skip("reference clone not present")
    import json
    uid_map = build_uid_map(ref.parent)
    doc, _ = transcribe(ref / "witch_cottage.tscn", uid_map)
    committed = json.loads(Path(
        "games/entropy/levels/witch_cottage/witch_cottage.json").read_text())
    assert doc["teleports"] == committed["teleports"]
    assert doc["spawns"] == committed["spawns"]
