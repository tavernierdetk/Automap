"""Casting-chain machinery: the casting sheet and its gate.

Three chairs from docs/studio-org.md meet here:

- The **Casting Director** owns ``games/<g>/casting/`` — ``cast-book.md``
  (the roster, for humans) and one casting sheet per populated scene.
- The **NPC Director** writes the sheets: which creature stands in which
  ``npc_slot``, with which dialogue.
- The **publisher** runs :func:`check_sheet` as the populate gate
  (ledger rows 8 and 10): a sheet that names a missing slot, an
  unbuilt creature, an unknown dialogue, an unadmitted canon person, or
  a creature from the wrong region (bible ruling R-005) is blocked.

A sheet is the Casting ⇄ Scene handshake artifact: the scene ships
sockets, the sheet fills them, the baker places ``OverworldNPC`` nodes.
Sheet shape::

    {"level": "vaporis_fair", "region": "vaporis",
     "npcs": [{"slot": "prefect", "creature": "prefect_cassia",
               "dialogue": "cassia_gate", "sprite": "prefect_cassia"}]}

``sprite`` is optional (defaults to the creature slug) — background
archetypes may share one sprite manifest while keeping their own
creature documents.
"""
from __future__ import annotations

import json
from pathlib import Path

from automap.story import Finding, level_index, level_sockets, load_canon


def casting_dir(game_dir: Path) -> Path:
    return game_dir / "casting"


def load_sheet(game_dir: Path, level_id: str) -> dict:
    path = casting_dir(game_dir) / f"{level_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"no casting sheet at {path}")
    return json.loads(path.read_text())


def list_sheets(game_dir: Path) -> list[str]:
    d = casting_dir(game_dir)
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def creature_ids(game_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    cdir = game_dir / "creatures"
    if cdir.exists():
        for p in sorted(cdir.glob("*.json")):
            out[p.stem] = json.loads(p.read_text())
    return out


def dialogue_ids(game_dir: Path) -> set[str]:
    ddir = game_dir / "dialogues"
    return {p.stem for p in ddir.glob("*.json")} if ddir.exists() else set()


def check_sheet(game_dir: Path, sheet: dict) -> list[Finding]:
    """The populate gate. Errors block the publish; warnings inform."""
    findings: list[Finding] = []
    err = lambda who, msg: findings.append(Finding("error", who, msg))
    warn = lambda who, msg: findings.append(Finding("warn", who, msg))

    level_id = str(sheet.get("level", "")).strip()
    region = str(sheet.get("region", "")).strip()
    if not level_id:
        err("-", "casting sheet has no `level`")
        return findings

    levels = level_index(game_dir)
    if level_id not in levels:
        err("-", f"level {level_id!r} does not exist")
        return findings
    sockets = level_sockets(levels[level_id])

    canon = load_canon(game_dir)
    creatures = creature_ids(game_dir)
    dialogues = dialogue_ids(game_dir)

    filled: set[str] = set()
    for npc in sheet.get("npcs", []):
        slot = str(npc.get("slot", "")).strip()
        creature = str(npc.get("creature", "")).strip()
        who = slot or "-"
        if not slot or not creature:
            err(who, "sheet entry needs both `slot` and `creature`")
            continue
        if slot not in sockets:
            err(who, f"slot {slot!r} does not exist in {level_id} — "
                     "sheets bind to the baked scene's npc_slots")
        if slot in filled:
            err(who, f"slot {slot!r} cast twice")
        filled.add(slot)

        ent = canon.get(creature)
        cdoc = creatures.get(creature)
        if cdoc is None:
            err(who, f"creature {creature!r} has no document in creatures/ — "
                     "the NPC Creator builds it first")
        else:
            # region from the creature's persona, falling back to canon
            # (reference-era creatures predate persona.region)
            c_region = (str(cdoc.get("persona", {}).get("region", "")).strip()
                        or (str(ent.get("region", "")).strip() if ent else ""))
            if region and c_region and c_region != region:
                err(who, f"creature {creature!r} is from region "
                         f"{c_region!r} — R-005 blocks cross-region casting "
                         "without a bible ruling")

        # a named canon person must be admitted (proposed/retired block)
        if ent is not None and ent["kind"] == "person" and ent["status"] != "canon":
            err(who, f"{creature!r} is {ent['status']} in canon — the Lore "
                     "Keeper admits people before they are cast")

        sprite = str(npc.get("sprite", creature)).strip()
        if sprite != creature and sprite not in creatures:
            warn(who, f"sprite {sprite!r} is not a creature slug — it must "
                      "name a published sprite manifest")

        dlg = str(npc.get("dialogue", "")).strip()
        if dlg and dlg not in dialogues:
            err(who, f"dialogue {dlg!r} has no document in dialogues/")

    for empty in sorted(sockets - filled):
        warn(empty, "socket uncast (allowed — story may fill it later)")
    return findings
