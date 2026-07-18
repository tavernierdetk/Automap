"""Story-chair machinery: the canon registry and the canon gate.

Two chairs from docs/studio-org.md share this module:

- The **Lore Keeper** owns ``games/<g>/lore/`` — ``bible.md`` (the canon,
  for humans) and ``canon.json`` (the registry the gate reads). Entities
  are admitted as ``proposed`` and promoted to ``canon`` by the keeper;
  rulings in the bible are append-only.
- The **Story Director** owns ``games/<g>/story/<arc>/`` — ``<arc>.arc.md``
  (premise and prose) and ``<arc>.beats.json`` (the machine-checkable
  beats). ``check_arc`` is the canon gate (ledger rows 3–4): a beat that
  names an unknown place, socket, or person — or a person the keeper has
  not admitted — is blocked, not warned.

The gate is deliberately mechanical: names, places, sockets, flag
continuity. Judgments of tone and contradiction-in-prose stay with the
Lore Keeper's skill; this module only enforces what a script can prove.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CANON_STATUSES = {"canon", "proposed", "retired"}
ENTITY_KINDS = {"place", "person", "faction", "term", "item"}
ARCHETYPE_PREFIX = "archetype:"


@dataclass(frozen=True)
class Finding:
    severity: str  # "error" blocks the gate; "warn" does not
    beat: str      # beat id, or "-" for arc-level findings
    message: str


def _lore_dir(game_dir: Path) -> Path:
    return game_dir / "lore"


def story_dir(game_dir: Path) -> Path:
    return game_dir / "story"


def load_canon(game_dir: Path) -> dict[str, dict]:
    """The registry, keyed by entity id. Malformed entries are errors at
    load time — the Lore Keeper's own document must pass its own bar."""
    path = _lore_dir(game_dir) / "canon.json"
    if not path.exists():
        raise FileNotFoundError(
            f"no canon registry at {path} — the Lore Keeper seeds it "
            "(docs/studio-org.md, R2)")
    doc = json.loads(path.read_text())
    entities: dict[str, dict] = {}
    for ent in doc.get("entities", []):
        eid = ent.get("id", "")
        if not eid or eid in entities:
            raise ValueError(f"canon.json: missing or duplicate entity id {eid!r}")
        if ent.get("kind") not in ENTITY_KINDS:
            raise ValueError(f"canon.json: {eid}: kind must be one of {sorted(ENTITY_KINDS)}")
        if ent.get("status") not in CANON_STATUSES:
            raise ValueError(f"canon.json: {eid}: status must be one of {sorted(CANON_STATUSES)}")
        entities[eid] = ent
    return entities


def level_index(game_dir: Path) -> dict[str, Path]:
    """Level id -> JSON path, across the three filing layouts (regional
    first — same contract as the publisher's _json_files)."""
    levels = game_dir / "levels"
    index: dict[str, Path] = {}
    for pattern in ("*/*/", "*/"):
        for folder in sorted(levels.glob(pattern)):
            cand = folder / f"{folder.name}.json"
            if cand.exists():
                index.setdefault(folder.name, cand)
    for flat in sorted(levels.glob("*.json")):
        index.setdefault(flat.stem, flat)
    return index


def level_sockets(level_json: Path) -> set[str]:
    doc = json.loads(level_json.read_text())
    return {s.get("tag", "") for s in doc.get("npc_slots", [])}


def load_arc(game_dir: Path, arc_id: str) -> dict:
    path = story_dir(game_dir) / arc_id / f"{arc_id}.beats.json"
    if not path.exists():
        raise FileNotFoundError(f"no beats document at {path}")
    return json.loads(path.read_text())


def list_arcs(game_dir: Path) -> list[str]:
    root = story_dir(game_dir)
    if not root.exists():
        return []
    return sorted(p.parent.name for p in root.glob("*/*.beats.json"))


def check_arc(game_dir: Path, beats_doc: dict) -> list[Finding]:
    """The canon gate. Errors block; warnings inform.

    Blocking: unknown/missing place, socket not in the baked level's
    npc_slots, cast person absent from canon or not admitted (proposed/
    retired), a `requires` flag no earlier beat grants, malformed beats.
    Warning: items named before the item registry exists (R4), duplicate
    grants, an arc without an .arc.md beside its beats.
    """
    findings: list[Finding] = []
    err = lambda beat, msg: findings.append(Finding("error", beat, msg))
    warn = lambda beat, msg: findings.append(Finding("warn", beat, msg))

    arc_id = str(beats_doc.get("arc", "")).strip()
    if not arc_id:
        err("-", "beats document has no `arc` id")
    beats = beats_doc.get("beats", [])
    if not isinstance(beats, list) or not beats:
        err("-", "beats document has no `beats` list")
        return findings

    arc_md = story_dir(game_dir) / arc_id / f"{arc_id}.arc.md"
    if arc_id and not arc_md.exists():
        warn("-", f"no {arc_id}.arc.md beside the beats — the premise "
                  "belongs in prose, not only in synopses")

    canon = load_canon(game_dir)
    levels = level_index(game_dir)
    people = {eid for eid, e in canon.items() if e["kind"] == "person"}
    items = {eid for eid, e in canon.items() if e["kind"] == "item"}

    granted: set[str] = set()
    all_grants: list[str] = []
    seen_ids: set[str] = set()
    for beat in beats:
        bid = str(beat.get("id", "")).strip()
        if not bid:
            err("-", "a beat has no id")
            continue
        if bid in seen_ids:
            err(bid, "duplicate beat id")
        seen_ids.add(bid)
        if not str(beat.get("synopsis", "")).strip():
            err(bid, "beat has no synopsis")

        place = str(beat.get("place", "")).strip()
        if not place:
            err(bid, "beat has no place — every beat happens somewhere")
        elif place not in levels:
            err(bid, f"place {place!r} is not a level "
                     "(commission the scene, or fix the id)")
        else:
            sockets = level_sockets(levels[place])
            for sock in beat.get("sockets", []):
                if sock not in sockets:
                    err(bid, f"socket {sock!r} does not exist in {place} — "
                             "beats bind to the baked scene's npc_slots")

        for member in beat.get("cast", []):
            if member.startswith(ARCHETYPE_PREFIX):
                continue  # unnamed roles are the Casting chain's to fill (R3)
            if member not in canon:
                err(bid, f"cast {member!r} is not in canon — the Lore Keeper "
                         "admits people before beats use them")
            elif member not in people:
                err(bid, f"cast {member!r} is canon but not a person "
                         f"(kind={canon[member]['kind']})")
            elif canon[member]["status"] != "canon":
                err(bid, f"cast {member!r} is {canon[member]['status']} — "
                         "not yet admitted (or retired) by the Lore Keeper")

        for flag in beat.get("requires", []):
            if flag not in granted:
                err(bid, f"requires {flag!r} but no earlier beat grants it")
        for flag in beat.get("grants", []):
            if flag in all_grants:
                warn(bid, f"grants {flag!r} again (already granted earlier)")
            all_grants.append(flag)
            granted.add(flag)

        for item in beat.get("items", []):
            if item not in items:
                warn(bid, f"item {item!r} not in canon — the item registry "
                          "is the Item Director's (R4); listed as intent")

    return findings


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "error"]
