"""The populate gate (automap/casting.py) — R3 verification.

Contract from docs/studio-org.md rows 8/10: a casting sheet binding a
missing slot, an unbuilt creature, an unknown dialogue, or a creature
from the wrong region (bible ruling R-005) is BLOCKED; the committed
vaporis_fair sheet passes.
"""
from pathlib import Path

from automap import casting, npc_creator

GAME = Path(__file__).resolve().parent.parent / "games" / "entropy"


def _sheet(*npcs) -> dict:
    return {"level": "vaporis_fair", "region": "vaporis", "npcs": list(npcs)}


def _errors(sheet) -> list[str]:
    return [f.message for f in casting.check_sheet(GAME, sheet)
            if f.severity == "error"]


def test_committed_fair_sheet_passes():
    sheet = casting.load_sheet(GAME, "vaporis_fair")
    assert _errors(sheet) == []
    assert len(sheet["npcs"]) == 20  # every socket filled


def test_unknown_slot_is_blocked():
    msgs = _errors(_sheet({"slot": "throne", "creature": "prefect_cassia"}))
    assert any("'throne'" in m for m in msgs)


def test_unbuilt_creature_is_blocked():
    msgs = _errors(_sheet({"slot": "prefect", "creature": "duke_ferrando"}))
    assert any("no document" in m for m in msgs)


def test_cross_region_casting_is_blocked_by_r005():
    # Carmilla belongs to the originals region — R-005 keeps her out of
    # vaporis without a bible ruling
    msgs = _errors(_sheet({"slot": "prefect", "creature": "carmilla"}))
    assert any("R-005" in m for m in msgs)


def test_unknown_dialogue_is_blocked():
    msgs = _errors(_sheet({"slot": "prefect", "creature": "prefect_cassia",
                           "dialogue": "ghost_script"}))
    assert any("ghost_script" in m for m in msgs)


def test_double_cast_slot_is_blocked():
    msgs = _errors(_sheet(
        {"slot": "prefect", "creature": "prefect_cassia"},
        {"slot": "prefect", "creature": "porter_felix"}))
    assert any("cast twice" in m for m in msgs)


def test_uncast_sockets_warn_but_do_not_block():
    findings = casting.check_sheet(
        GAME, _sheet({"slot": "prefect", "creature": "prefect_cassia"}))
    assert [f for f in findings if f.severity == "error"] == []
    assert any("uncast" in f.message for f in findings)


def test_npc_stats_stay_in_the_admission_band():
    for arch in npc_creator.ARCHETYPE_STATS:
        for slug in (f"{arch}_a", f"{arch}_b", f"{arch}_c"):
            stats = npc_creator.npc_stats(slug, arch)
            assert 24 <= sum(stats.values()) <= 28
            assert all(1 <= v <= 20 for v in stats.values())


def test_creature_docs_carry_region_for_the_gate():
    # vaporis people are generated (ulpc composed bodies, or figure_px
    # one-offs) — never reference-repo families without a region
    for doc in casting.creature_ids(GAME).values():
        home = doc.get("persona", {})
        if home.get("region") == "vaporis":
            assert doc["visual"]["family"] in ("ulpc", "figure_px")
