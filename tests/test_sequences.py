"""The sequence gate (automap/sequences.py) — NS0.

Contract: the transcribed prologue passes (0 errors) while producing a
to-author checklist; genuine contradictions (undeclared ledger outputs,
non-discipline classes, phantom participants) are ERRORS; unbuilt
scenes/dialogue/cast are WARNINGS, not errors.
"""
from pathlib import Path

from automap import sequences

GAME = Path(__file__).resolve().parent.parent / "games" / "entropy"


def _seq(**over) -> dict:
    base = {
        "id": "t", "title": "T",
        "disciplines": ["shaper", "steward", "weaver", "breaker", "mentarch"],
        "characters": [{"id": "caden", "creature": "caden", "role": "protagonist"}],
        "state": {"persistent_outputs": ["out_a"], "hidden_outputs": []},
        "segments": [{"id": "s1", "segment_type": "cutscene",
                      "participants": {"required": ["caden"]},
                      "produces": ["out_a"]}],
    }
    base.update(over)
    return base


def _errs(doc) -> list[str]:
    return [f.message for f in sequences.check_sequence(GAME, doc)
            if f.severity == "error"]


def _warns(doc) -> list[str]:
    return [f.message for f in sequences.check_sequence(GAME, doc)
            if f.severity == "warn"]


def test_transcribed_prologue_passes_with_a_checklist():
    docs = sequences.load_sequences(GAME)
    assert "prologue_shared_origin" in docs
    findings = sequences.check_sequence(GAME, docs["prologue_shared_origin"])
    assert [f for f in findings if f.severity == "error"] == []
    # the whole point: it's a checklist of to-author warnings, never errors.
    # (The count shrinks as the prologue gets authored — placeholders become
    # real creatures/dialogues — so this floor only proves the mechanism.)
    assert len([f for f in findings if f.severity == "warn"]) >= 5


def test_clean_minimal_sequence_has_no_errors():
    assert _errs(_seq()) == []


def test_non_discipline_class_is_blocked():
    doc = _seq(characters=[{"id": "isaac", "creature": "isaac", "role": "major_npc",
                            "class": {"fixed_choice": "necromancer"}}])
    assert any("not a discipline" in m for m in _errs(doc))


def test_undeclared_produced_output_is_blocked():
    doc = _seq(segments=[{"id": "s1", "segment_type": "cutscene",
                          "participants": {"required": ["caden"]},
                          "produces": ["ghost_output"]}])
    assert any("ghost_output" in m and "never declares" in m for m in _errs(doc))


def test_phantom_participant_is_blocked():
    doc = _seq(segments=[{"id": "s1", "segment_type": "cutscene",
                          "participants": {"required": ["duke_ferrando"]}}])
    assert any("duke_ferrando" in m for m in _errs(doc))


def test_tbd_participant_only_warns():
    doc = _seq(
        characters=[{"id": "caden", "creature": "caden", "role": "protagonist"},
                    {"id": "professor_tbd", "role": "npc", "tbd": True}],
        segments=[{"id": "s1", "segment_type": "cutscene",
                   "participants": {"required": ["caden", "professor_tbd"]},
                   "produces": ["out_a"]}])
    assert _errs(doc) == []
    assert any("placeholder" in m for m in _warns(doc))


def test_unbuilt_scene_and_dialogue_warn_not_error():
    doc = _seq(segments=[{"id": "s1", "segment_type": "playable_exposition",
                          "location": {"scene_role": "x", "location_id": "loc.x"},
                          "participants": {"required": ["caden"]},
                          "dialogue_refs": ["dialogue.unwritten.thing"],
                          "produces": ["out_a"]}],
               dialogue_package={"required_dialogue_sets": [
                   {"id": "dialogue.unwritten.thing", "status": "unwritten"}]})
    assert _errs(doc) == []
    assert any("not authored" in m for m in _warns(doc))
    assert any("unwritten" in m for m in _warns(doc))


def test_undeclared_output_left_unproduced_warns():
    doc = _seq(state={"persistent_outputs": ["out_a", "never_made"],
                      "hidden_outputs": []})
    assert _errs(doc) == []
    assert any("never_made" in m and "no segment produces" in m
               for m in _warns(doc))
