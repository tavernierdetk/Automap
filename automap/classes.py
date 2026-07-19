"""Systems Director: the discipline (class@1) loader + stat-budget gate.

A discipline bundles a starting attribute bonus, a learnable ability
pool, and markers. The gate (studio-org ledger row 20 sibling) enforces
the rulers in ``games/<g>/systems.md``: the bonus stays within the class
budget, every ability in the pool is a real skill@, the five entropy
disciplines are present. Constants mirror systems.md.
"""
from __future__ import annotations

import json
from pathlib import Path

from automap import items
from automap.story import Finding

CLASS_BUDGET = 3            # Σ attribute_bonus ≤ this (systems.md Class budgets)
STATS = {"creature_affinity", "chaos_mastery", "kinesthetic", "lucidity",
         "terrain_control"}
ENTROPY_DISCIPLINES = {"shaper", "steward", "breaker", "mentarch", "weaver"}


def load_classes(game_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = game_dir / "classes"
    if d.exists():
        for p in sorted(d.glob("*.json")):
            out[p.stem] = json.loads(p.read_text())
    return out


def check_classes(game_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    err = lambda who, msg: findings.append(Finding("error", who, msg))
    warn = lambda who, msg: findings.append(Finding("warn", who, msg))

    classes = load_classes(game_dir)
    skills = set(items.load_skills(game_dir))
    for cid, doc in classes.items():
        if doc.get("id") != cid:
            err(cid, f"file name and id disagree ({doc.get('id')!r})")
        if doc.get("primary_stat") not in STATS:
            err(cid, f"primary_stat {doc.get('primary_stat')!r} is not a stat")
        bonus = doc.get("attribute_bonus", {})
        spent = sum(int(v) for v in bonus.values())
        if spent > CLASS_BUDGET:
            err(cid, f"attribute_bonus spends {spent} > class budget "
                     f"{CLASS_BUDGET} (systems.md)")
        if spent == 0:
            warn(cid, "discipline grants no attribute bonus")
        for ability in doc.get("ability_pool", []):
            if ability not in skills:
                err(cid, f"ability {ability!r} is not a real skill@")
        if "attack" not in doc.get("ability_pool", []):
            warn(cid, "ability_pool lacks the basic 'attack' — every fighter "
                      "should keep it")

    if classes:
        missing = ENTROPY_DISCIPLINES - set(classes)
        if missing:
            warn("-", f"the entropy discipline set is incomplete: missing "
                      f"{sorted(missing)}")
    return findings
