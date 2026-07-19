"""Cutscene Director's machinery: loaders + the cutscene gate.

The chair sits under the Story Director and requisitions actors from
the Casting Director's world (docs/explorations/cutscene-module.md; the
studio-org addendum). The gate is mechanical: the stage must exist, the
actors must be real creatures obeying the region law (R-005), speakers
must be staged, referenced dialogues must exist, named canon persons
must be admitted, and a trigger must sit inside the stage's bounds.
"""
from __future__ import annotations

import json
from pathlib import Path

from automap import casting, story
from automap.story import Finding


def load_cutscenes(game_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = game_dir / "cutscenes"
    if d.exists():
        for p in sorted(d.glob("*.json")):
            out[p.stem] = json.loads(p.read_text())
    return out


def _level_bounds_px(level_json: Path) -> tuple[int, int] | None:
    doc = json.loads(level_json.read_text())
    grid = doc.get("tilemap", {}).get("grid_size")
    if not grid:
        return None  # backdrop levels: bounds unknown, skip the check
    tile = int(doc.get("tilemap", {}).get("tile_size", 32))
    return int(grid[0]) * tile, int(grid[1]) * tile


def _region_of_level(game_dir: Path, level_id: str) -> str:
    for region_dir in (game_dir / "levels").iterdir():
        if (region_dir / level_id).is_dir():
            return region_dir.name
    return ""


def check_cutscene(game_dir: Path, doc: dict) -> list[Finding]:
    findings: list[Finding] = []
    err = lambda who, msg: findings.append(Finding("error", who, msg))
    warn = lambda who, msg: findings.append(Finding("warn", who, msg))

    cid = str(doc.get("id", "-"))
    level_id = str(doc.get("level", ""))
    levels = story.level_index(game_dir)
    if level_id not in levels:
        err(cid, f"stage level {level_id!r} does not exist")
        return findings

    canon = story.load_canon(game_dir)
    creatures = casting.creature_ids(game_dir)
    dialogues = casting.dialogue_ids(game_dir)
    level_region = _region_of_level(game_dir, level_id)

    staged: set[str] = set()
    for actor in doc.get("actors", []):
        aid = str(actor.get("id", "-"))
        staged.add(aid)
        creature = str(actor.get("creature", ""))
        cdoc = creatures.get(creature)
        if cdoc is None:
            err(aid, f"actor's creature {creature!r} has no document — "
                     "requisition the Casting chain first")
            continue
        ent = canon.get(creature)
        c_region = (str(cdoc.get("persona", {}).get("region", "")).strip()
                    or (str(ent.get("region", "")).strip() if ent else ""))
        if level_region and c_region and level_region != "originals" \
                and c_region != level_region:
            err(aid, f"{creature!r} is from region {c_region!r} — R-005 "
                     f"blocks staging in {level_region!r} without a ruling")
        if ent is not None and ent["kind"] == "person" \
                and ent["status"] != "canon":
            err(aid, f"{creature!r} is {ent['status']} in canon — the Lore "
                     "Keeper admits people before they are staged")
        sprite = str(actor.get("sprite", creature))
        if sprite != creature and sprite not in creatures:
            warn(aid, f"sprite {sprite!r} is not a creature slug")

    bounds = _level_bounds_px(levels[level_id])

    def _check_point(who: str, label: str, pt) -> None:
        if bounds and pt and not (0 <= pt[0] <= bounds[0]
                                  and 0 <= pt[1] <= bounds[1]):
            err(who, f"{label} {pt} is outside {level_id}'s "
                     f"{bounds[0]}×{bounds[1]} px stage")

    for actor in doc.get("actors", []):
        _check_point(str(actor.get("id", "-")), "spawn", actor.get("spawn"))

    if doc.get("kind") == "triggered":
        rect = doc.get("trigger", {}).get("rect")
        if rect:
            _check_point(cid, "trigger pos", rect.get("pos"))
        if not doc.get("trigger", {}).get("once_flag"):
            warn(cid, "triggered cutscene without once_flag — it will "
                      "replay on every entry")

    def _walk_steps(steps: list, depth: int = 0) -> None:
        for step in steps:
            if "say" in step:
                say = step["say"]
                if say.get("dialogue"):
                    if say["dialogue"] not in dialogues:
                        err(cid, f"say references unknown dialogue "
                                 f"{say['dialogue']!r}")
                elif not str(say.get("text", "")).strip():
                    err(cid, "say needs `text` or `dialogue`")
                elif say.get("actor", "") not in staged:
                    err(cid, f"say actor {say.get('actor')!r} is not staged "
                             "in this cutscene's actors")
            if "move" in step and step["move"].get("actor", "") not in staged:
                err(cid, f"move actor {step['move'].get('actor')!r} not staged")
            if "face" in step and step["face"].get("actor", "") not in staged:
                err(cid, f"face actor {step['face'].get('actor')!r} not staged")
            if "move" in step:
                _check_point(cid, "move target", step["move"].get("to"))
            if "parallel" in step:
                _walk_steps(step["parallel"], depth + 1)

    _walk_steps(doc.get("steps", []))
    if not doc.get("steps"):
        warn(cid, "a cutscene with no steps stages nothing")
    return findings


def check_all(game_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    for cid, doc in load_cutscenes(game_dir).items():
        if doc.get("id") != cid:
            findings.append(Finding("error", cid,
                                    f"file name and id disagree ({doc.get('id')!r})"))
        findings += check_cutscene(game_dir, doc)
    return findings
