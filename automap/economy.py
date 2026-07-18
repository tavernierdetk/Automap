"""Economy Director's machinery: the economy document + its sim gate.

``games/<g>/economy/economy.json`` (economy@1) prices every item, places
shops with cast keepers, and schedules rewards. The gate (studio-org
ledger rows 22–25) is deliberately mechanical for v1: coverage,
keeper-cast, and shop-affordability checks. The full progression walk
(cumulative income vs required spend per beat) is a named debt — it
needs quest cost annotations that don't exist yet.
"""
from __future__ import annotations

import json
from pathlib import Path

from automap import casting, items, story
from automap.story import Finding


def load_economy(game_dir: Path) -> dict:
    path = game_dir / "economy" / "economy.json"
    if not path.exists():
        raise FileNotFoundError(f"no economy document at {path}")
    return json.loads(path.read_text())


def starting_gold(game_dir: Path) -> int:
    design = game_dir / "design.json"
    if design.exists():
        doc = json.loads(design.read_text())
        return int(doc.get("starting_loadout", {}).get("gold", 0))
    return 0


def check_economy(game_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    err = lambda who, msg: findings.append(Finding("error", who, msg))
    warn = lambda who, msg: findings.append(Finding("warn", who, msg))

    try:
        eco = load_economy(game_dir)
    except FileNotFoundError:
        return findings  # no economy yet — nothing to gate

    all_items = items.load_items(game_dir)
    prices = eco.get("price_book", {})

    # coverage: every non-key item priced; key items never priced
    for iid, doc in all_items.items():
        if doc.get("kind") == "key":
            if iid in prices:
                err(iid, "key items are quest-granted, never priced "
                         "(systems.md: Currency targets)")
        elif iid not in prices:
            err(iid, "unpriced item — every non-key item appears in the "
                     "price book (ledger row 22)")
    for iid in prices:
        if iid not in all_items:
            err(iid, "price for an item that does not exist")

    # shops: level exists, keeper cast there, inventory priced,
    # at least one line affordable in principle
    levels = story.level_index(game_dir)
    total_income = starting_gold(game_dir) + sum(
        int(r.get("amount", 0)) for r in eco.get("rewards", []))
    for shop in eco.get("shops", []):
        sid = shop.get("id", "-")
        level = shop.get("level", "")
        if level not in levels:
            err(sid, f"shop level {level!r} does not exist")
        else:
            try:
                sheet = casting.load_sheet(game_dir, level)
                cast_ids = {n.get("creature") for n in sheet.get("npcs", [])}
            except FileNotFoundError:
                cast_ids = set()
            if shop.get("keeper") not in cast_ids:
                err(sid, f"keeper {shop.get('keeper')!r} is not cast in "
                         f"{level} — a shop needs its keeper standing there "
                         "(ledger row 23)")
        line_prices = []
        for iid in shop.get("inventory", []):
            if iid not in all_items:
                err(sid, f"stocks unknown item {iid!r}")
            elif all_items[iid].get("kind") == "key":
                err(sid, f"stocks key item {iid!r} — key items are "
                         "quest-granted")
            elif iid not in prices:
                pass  # already reported as unpriced
            else:
                line_prices.append(prices[iid])
        if line_prices and min(line_prices) > total_income:
            err(sid, f"nothing affordable: cheapest line {min(line_prices)} "
                     f"> total obtainable {total_income} (starting gold + "
                     "rewards) — a dead shop (systems.md: Currency targets)")

    # rewards: sources should be real beats (warn — events may come later)
    beat_ids = set()
    for arc_id in story.list_arcs(game_dir):
        beat_ids |= {b.get("id") for b in
                     story.load_arc(game_dir, arc_id).get("beats", [])}
    for r in eco.get("rewards", []):
        if r.get("source") not in beat_ids:
            warn(r.get("source", "-"),
                 "reward source is not a known arc beat (event sources "
                 "arrive later — verify the name)")
    if eco.get("shops") and not eco.get("rewards") and \
            starting_gold(game_dir) == 0:
        err("-", "shops exist but no income exists (no rewards, zero "
                 "starting gold) — a dead-end wallet")
    return findings
