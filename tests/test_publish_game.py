"""Stage-12 (game publish) checks: the teleport-graph gate that guards the
cascade — dangling level = error, dangling spawn tag / orphan level = warning
(the original game contains both; fidelity keeps them, loudly)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "publish_game", ROOT / "scripts" / "12_publish_game.py")
publish_game = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish_game)


def _lvl(id, teleports=(), spawns=(("a", (0, 0)),)):
    return {"id": id,
            "spawns": [{"tag": t, "pos": list(p)} for t, p in spawns],
            "teleports": [{"target_level": tl, "target_spawn_tag": tag,
                           "rect": {"pos": [0, 0], "size": [10, 10]}}
                          for tl, tag in teleports]}


def test_closed_graph_passes():
    levels = {"x": _lvl("x", [("y", "a")]), "y": _lvl("y", [("x", "a")])}
    assert publish_game._check_teleport_graph(levels, lambda m: None) == []


def test_unknown_target_level_is_an_error():
    levels = {"x": _lvl("x", [("nowhere", "a")])}
    errors = publish_game._check_teleport_graph(levels, lambda m: None)
    assert len(errors) == 1 and "nowhere" in errors[0]


def test_dangling_spawn_tag_and_orphan_only_warn():
    warnings = []
    levels = {"x": _lvl("x", [("y", "missing_tag")]), "y": _lvl("y", [("x", "a")])}
    assert publish_game._check_teleport_graph(levels, warnings.append) == []
    assert any("missing_tag" in w for w in warnings)


def test_committed_entropy_levels_pass_the_gate():
    levels = {}
    lv = ROOT / "games" / "entropy" / "levels"
    for f in sorted(list(lv.glob("*.json")) + list(lv.glob("*/*.json"))):
        doc = json.loads(f.read_text())
        levels[doc["id"]] = doc
    assert len(levels) >= 5  # the director keeps growing the world
    assert publish_game._check_teleport_graph(levels, lambda m: None) == []
