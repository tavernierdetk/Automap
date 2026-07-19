"""The cutscene gate (automap/cutscenes.py) — the Cutscene Director's chair.

Contract (docs/explorations/cutscene-module.md): unknown stages, unbuilt
actors, cross-region staging (R-005), unstaged speakers, unknown
dialogues, and out-of-bounds choreography are BLOCKED; the committed
fair cutscenes pass.
"""
import json
from pathlib import Path

from automap import cutscenes

GAME = Path(__file__).resolve().parent.parent / "games" / "entropy"


def _doc(**over) -> dict:
    base = {
        "id": "t", "level": "vaporis_fair", "kind": "interstitial",
        "actors": [{"id": "druso", "creature": "operator_druso",
                    "spawn": [100, 100]}],
        "steps": [{"say": {"actor": "druso", "text": "hm."}}],
    }
    base.update(over)
    return base


def _errors(doc) -> list[str]:
    return [f.message for f in cutscenes.check_cutscene(GAME, doc)
            if f.severity == "error"]


def test_committed_cutscenes_pass():
    findings = cutscenes.check_all(GAME)
    assert [f for f in findings if f.severity == "error"] == []
    assert set(cutscenes.load_cutscenes(GAME)) >= {"gate_welcome", "first_turn"}


def test_unknown_stage_is_blocked():
    assert any("does not exist" in m for m in _errors(_doc(level="atlantis")))


def test_unbuilt_actor_is_blocked():
    doc = _doc(actors=[{"id": "x", "creature": "duke_ferrando",
                        "spawn": [1, 1]}])
    assert any("no document" in m for m in _errors(doc))


def test_cross_region_staging_is_blocked():
    # Carmilla (originals) may not be staged on a vaporis stage — R-005
    doc = _doc(actors=[{"id": "c", "creature": "carmilla", "spawn": [1, 1]}],
               steps=[{"wait": 0.1}])
    assert any("R-005" in m for m in _errors(doc))


def test_unstaged_speaker_is_blocked():
    doc = _doc(steps=[{"say": {"actor": "ghost", "text": "boo"}}])
    assert any("not staged" in m for m in _errors(doc))


def test_unknown_dialogue_ref_is_blocked():
    doc = _doc(steps=[{"say": {"dialogue": "ghost_script"}}])
    assert any("ghost_script" in m for m in _errors(doc))


def test_offstage_choreography_is_blocked():
    doc = _doc(steps=[{"move": {"actor": "druso", "to": [99999, 50]}}])
    assert any("outside" in m for m in _errors(doc))


def test_triggered_needs_its_trigger_inside_the_stage():
    doc = _doc(kind="triggered",
               trigger={"rect": {"pos": [99999, 0], "size": [10, 10]},
                        "once_flag": "f"})
    assert any("outside" in m for m in _errors(doc))


def test_flagless_trigger_warns_not_blocks():
    doc = _doc(kind="triggered",
               trigger={"rect": {"pos": [100, 100], "size": [10, 10]}})
    findings = cutscenes.check_cutscene(GAME, doc)
    assert [f for f in findings if f.severity == "error"] == []
    assert any("replay" in f.message for f in findings)
