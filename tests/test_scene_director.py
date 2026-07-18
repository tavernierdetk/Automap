"""Stage-13 (scene director) checks: the brief gate — a level is baked FROM
a brief (`<id>.brief.md` beside the JSON, `intent` summarizing it), never
before one. Retro-authored briefs are the failure this guards against
(docs/explorations/scene-generation-correction-plan.md, S1)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "scene_director", ROOT / "scripts" / "13_scene_director.py")
scene_director = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene_director)


def _scene(levels_dir, lid, *, brief="# Brief\n\nA place.", intent="a place"):
    doc = {"id": lid, "kind": "tilemap"}
    if intent is not None:
        doc["intent"] = intent
    (levels_dir / f"{lid}.json").write_text(json.dumps(doc))
    if brief is not None:
        (levels_dir / f"{lid}.brief.md").write_text(brief)


def test_briefed_level_passes(tmp_path):
    _scene(tmp_path, "hall")
    assert scene_director._check_briefs(tmp_path, ["hall"]) == []


def test_missing_brief_is_an_error(tmp_path):
    _scene(tmp_path, "hall", brief=None)
    errors = scene_director._check_briefs(tmp_path, ["hall"])
    assert len(errors) == 1 and "hall.brief.md" in errors[0]


def test_empty_brief_is_an_error(tmp_path):
    _scene(tmp_path, "hall", brief="   \n")
    errors = scene_director._check_briefs(tmp_path, ["hall"])
    assert len(errors) == 1


def test_missing_intent_is_an_error(tmp_path):
    _scene(tmp_path, "hall", intent=None)
    errors = scene_director._check_briefs(tmp_path, ["hall"])
    assert len(errors) == 1 and "intent" in errors[0]


def test_existing_scenes_are_gated_too():
    """The committed vaporis scenes must keep passing the gate they inspired."""
    levels = ROOT / "games" / "entropy" / "levels"
    assert scene_director._check_briefs(levels, ["vaporis_mine_hall"]) == []


def test_foldered_layout_is_found(tmp_path):
    """Per-scene folders (levels/<id>/<id>.json + brief) are the organized
    layout; flat files remain a fallback."""
    d = tmp_path / "hall"
    d.mkdir()
    (d / "hall.json").write_text(json.dumps({"id": "hall", "intent": "x"}))
    (d / "hall.brief.md").write_text("# Brief\n\nA place.")
    assert scene_director._check_briefs(tmp_path, ["hall"]) == []
    assert scene_director._level_path(tmp_path, "hall", "json") == d / "hall.json"
