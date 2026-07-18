"""The canon gate (automap/story.py) — R2 verification.

The contract from docs/studio-org.md: a beat that contradicts seeded
lore (unknown place, socket not in the baked scene, person the Lore
Keeper has not admitted, flag required before granted) is BLOCKED; the
committed fair_opening arc passes.
"""
from pathlib import Path

import pytest

from automap import story

GAME = Path(__file__).resolve().parent.parent / "games" / "entropy"


def _beat(**over) -> dict:
    base = {
        "id": "b1", "title": "t", "synopsis": "something happens",
        "place": "vaporis_fair", "sockets": [], "cast": [],
        "requires": [], "grants": [],
    }
    base.update(over)
    return base


def _arc(*beats) -> dict:
    return {"arc": "fair_opening", "title": "t", "beats": list(beats)}


def _error_messages(doc) -> list[str]:
    return [f.message for f in story.errors(story.check_arc(GAME, doc))]


def test_committed_fair_arc_passes_the_gate():
    doc = story.load_arc(GAME, "fair_opening")
    findings = story.check_arc(GAME, doc)
    assert story.errors(findings) == []
    # the R2 item warning is PAID: the valve is a canon item since the
    # game-shell round (R4) — the arc gates clean, no warnings
    assert not any("bronze_valve" in f.message for f in findings)


def test_unknown_place_is_blocked():
    msgs = _error_messages(_arc(_beat(place="atlantis_pier")))
    assert any("atlantis_pier" in m for m in msgs)


def test_socket_must_exist_in_the_baked_scene():
    msgs = _error_messages(_arc(_beat(sockets=["throne_herald"])))
    assert any("throne_herald" in m for m in msgs)


def test_unadmitted_person_is_blocked():
    msgs = _error_messages(_arc(_beat(cast=["duke_ferrando"])))
    assert any("duke_ferrando" in m and "not in canon" in m for m in msgs)


def test_retired_person_cannot_be_cast():
    # R-004: the Founder is dead and stays dead
    msgs = _error_messages(_arc(_beat(cast=["founder_minerva"])))
    assert any("retired" in m for m in msgs)


def test_proposed_person_is_blocked_until_promoted(tmp_path, monkeypatch):
    import json, shutil
    game = tmp_path / "game"
    (game / "lore").mkdir(parents=True)
    shutil.copytree(GAME / "levels" / "vaporis", game / "levels" / "vaporis")
    canon = json.loads((GAME / "lore" / "canon.json").read_text())
    canon["entities"].append({"id": "novice_pia", "kind": "person",
                              "name": "Novice Pia", "region": "vaporis",
                              "status": "proposed"})
    (game / "lore" / "canon.json").write_text(json.dumps(canon))
    msgs = [f.message for f in story.errors(
        story.check_arc(game, _arc(_beat(cast=["novice_pia"]))))]
    assert any("proposed" in m for m in msgs)


def test_non_person_cannot_be_cast():
    msgs = _error_messages(_arc(_beat(cast=["the_order"])))
    assert any("not a person" in m for m in msgs)


def test_archetypes_are_the_casting_chains_business():
    assert _error_messages(_arc(_beat(cast=["archetype:juggler"]))) == []


def test_flag_required_before_granted_is_blocked():
    msgs = _error_messages(_arc(
        _beat(id="b1", grants=["a"]),
        _beat(id="b2", requires=["a", "never_granted"]),
    ))
    assert any("never_granted" in m for m in msgs)
    assert not any("'a'" in m for m in msgs)


def test_duplicate_beat_ids_are_blocked():
    msgs = _error_messages(_arc(_beat(id="dup"), _beat(id="dup")))
    assert any("duplicate beat id" in m for m in msgs)


def test_canon_registry_rejects_bad_status(tmp_path):
    import json
    (tmp_path / "lore").mkdir()
    (tmp_path / "lore" / "canon.json").write_text(json.dumps(
        {"entities": [{"id": "x", "kind": "person", "status": "vibes"}]}))
    with pytest.raises(ValueError, match="status"):
        story.load_canon(tmp_path)
