"""Story Director's top tier: the narrative-sequence loader + gate.

A sequence (sequence@1) composes segments, a state ledger, and a
revelation plan into one prologue-scale arc. The gate's governing
principle: **distinguish "not built yet" from "contradiction."** A
scene, dialogue, or cast member that is declared-but-unbuilt WARNS (it
is a checklist item); only a genuine contradiction ERRORS (a class
outside the discipline vocabulary, a segment producing an output the
ledger never declares, a participant that is neither a declared
character nor an existing creature nor a tbd placeholder). This is what
lets a transcribed concept document act as a living to-do list.
"""
from __future__ import annotations

import json
from pathlib import Path

from automap import casting, story
from automap.story import Finding

DISCIPLINES = {"shaper", "steward", "weaver", "breaker", "mentarch"}
_TBD_MARK = ("tbd", "unresolved", "to_author", "missing_core_design", "blocked")


def sequences_dir(game_dir: Path) -> Path:
    return game_dir / "story" / "sequences"


def load_sequences(game_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = sequences_dir(game_dir)
    if d.exists():
        for p in sorted(d.glob("*.json")):
            out[p.stem] = json.loads(p.read_text())
    return out


def _is_placeholder(name: str) -> bool:
    low = name.lower()
    return low.endswith("_tbd") or any(m in low for m in _TBD_MARK)


def check_sequence(game_dir: Path, doc: dict) -> list[Finding]:
    findings: list[Finding] = []
    err = lambda who, msg: findings.append(Finding("error", who, msg))
    warn = lambda who, msg: findings.append(Finding("warn", who, msg))

    sid = str(doc.get("id", "-"))
    creatures = casting.creature_ids(game_dir)
    dialogues = casting.dialogue_ids(game_dir)
    levels = story.level_index(game_dir)

    # dialogues the sequence itself declares as still-unwritten (a checklist
    # in dialogue_package) — referencing one of these WARNS, never errors
    declared_unwritten: set[str] = set()
    for entry in doc.get("dialogue_package", {}).get("required_dialogue_sets", []):
        if isinstance(entry, dict) and entry.get("id"):
            declared_unwritten.add(entry["id"])

    # --- characters: creature-backed, tbd, or a genuine unknown ---
    char_ids: set[str] = set()
    for ch in doc.get("characters", []):
        cid = str(ch.get("id", "-"))
        char_ids.add(cid)
        slug = str(ch.get("creature", cid))
        if ch.get("tbd") or _is_placeholder(cid) or _is_placeholder(slug):
            warn(cid, "character is a tbd placeholder — the Casting chain "
                      "casts it before this segment can play")
        elif slug not in creatures:
            err(cid, f"character maps to no creature {slug!r} (and is not "
                     "marked tbd) — cast it or fix the id")
        cls = ch.get("class", {})
        for key in ("fixed_choice",):
            v = cls.get(key)
            if v and v not in DISCIPLINES:
                err(cid, f"class.{key} {v!r} is not a discipline")
        for v in cls.get("allowed_choices", []):
            if v not in DISCIPLINES:
                err(cid, f"class.allowed_choices has non-discipline {v!r}")

    # --- the state ledger ---
    declared_outputs: set[str] = set()
    st = doc.get("state", {})
    for key in ("persistent_outputs", "hidden_outputs"):
        declared_outputs |= set(st.get(key, []))
    produced: set[str] = set()

    # --- segments ---
    for seg in doc.get("segments", []):
        seg_id = str(seg.get("id", "-"))
        status = str(seg.get("status", ""))
        if status in ("missing_core_design", "blocked"):
            warn(seg_id, f"segment is design-blocked ({status}) — human "
                         "design decision, not a build task")

        loc = seg.get("location", {})
        level = str(loc.get("level", ""))
        if level:
            if level not in levels:
                err(seg_id, f"location.level {level!r} does not exist")
        elif loc.get("scene_role") or loc.get("location_id"):
            warn(seg_id, "stage scene not authored yet — Scene Director "
                         f"builds {loc.get('location_id', loc.get('scene_role'))}")

        participants = seg.get("participants", {})
        for role_key in ("required", "supporting", "ambient"):
            for p in participants.get(role_key, []):
                p = str(p)
                if p in char_ids or p in creatures or _is_placeholder(p):
                    continue
                # a bare group label ("auregate_students") is ambient colour
                if role_key == "ambient":
                    warn(seg_id, f"ambient group {p!r} — Casting fills the crowd")
                else:
                    err(seg_id, f"participant {p!r} is neither a declared "
                                "character, an existing creature, nor tbd")

        for d in seg.get("dialogue_refs", []):
            d = str(d)
            if d in dialogues:
                continue
            if d in declared_unwritten or _is_placeholder(d):
                warn(seg_id, f"dialogue {d!r} unwritten — Dialogue Writer's queue")
            else:
                err(seg_id, f"dialogue {d!r} referenced but never declared "
                            "(add it to dialogue_package or write it)")

        for out_id in seg.get("produces", []):
            produced.add(out_id)
            if out_id not in declared_outputs:
                err(seg_id, f"produces {out_id!r} which the state ledger "
                            "never declares")
        for req in seg.get("requires", []):
            if req not in declared_outputs:
                err(seg_id, f"requires {req!r} which the state ledger never "
                            "declares")

    # --- ledger completeness: declared outputs someone must produce ---
    for out_id in sorted(declared_outputs):
        if out_id not in produced:
            warn(sid, f"output {out_id!r} is declared but no segment produces "
                      "it yet (checklist)")

    if not doc.get("segments"):
        warn(sid, "sequence has no segments")
    return findings


def check_all(game_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    for sid, doc in load_sequences(game_dir).items():
        if doc.get("id") and str(doc["id"]).replace(".", "_") != sid \
                and doc["id"] != sid:
            findings.append(Finding("warn", sid,
                f"file stem and id differ ({doc['id']!r}) — fine if intentional"))
        findings += check_sequence(game_dir, doc)
    return findings
