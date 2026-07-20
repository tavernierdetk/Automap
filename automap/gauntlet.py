"""Combat Trial gauntlet generator.

From one spec (`games/<game>/gauntlet.json`) emit a chain of N backdrop levels —
each a bounded arena with two combats + a free store + a teleport to the next —
plus depth-scaled test enemies, three base hero docs, the free-store shop
(economy), its keeper casting + dialogue. Backdrops carry encounters at runtime
(engine location.gd), so NO bake is needed — just publish. Regenerate to retune
the whole series (the "highly modulable" knob).
"""
from __future__ import annotations

import glob
import json
import math
from pathlib import Path

STORE_ID = "gauntlet_store"
KEEPER = "trial_keeper"         # a gauntlet-region vendor (R-005 forbids casting
                               # the vaporis Naso here); renders like any ULPC vendor
STORE_DLG = "gauntlet_store_dlg"
HEROES = [("hero_a", "Hero Aran"), ("hero_b", "Hero Bly"), ("hero_c", "Hero Cass")]

DEFAULT_SPEC = {
    "levels": 16,
    "background": "BackgroundField.png",
    "enemy": {"per_encounter": 1, "xp_factor": 0.6,
              "stats": {"creature_affinity": 5, "chaos_mastery": 5,
                        "kinesthetic": 5, "lucidity": 5, "terrain_control": 6}},
}


def _xp_to_next(level: int, base: float = 100.0, growth: float = 1.35) -> int:
    return int(round(base * pow(growth, level - 1)))


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def _level_doc(game_dir: Path, k: int, n: int, bg: str, per_enc: int) -> dict:
    lid = "gauntlet_%02d" % k
    enemy = "gauntlet_e_%02d" % k
    nxt = "gauntlet_%02d" % (k + 1 if k < n else 1)   # last loops to the first
    enc = []
    for i in range(2):                                # two combats
        enc.append({"rect": {"pos": [420 + i * 380, 400], "size": [110, 120]},
                    "enemies": [enemy] * per_enc, "seed": k * 100 + i,
                    "layout": "field",
                    "intent": "Combat %d of Trial %d." % (i + 1, k)})
    doc = {
        "id": lid, "kind": "backdrop",
        "intent": "Combat Trial arena %d — two combats + a free store." % k,
        "background": {"file": bg, "pos": [576, 324], "scale": [1, 1]},
        "spawns": [{"tag": "entry", "pos": [180, 400]}],
        "encounters": enc,
        "npcs": [{"slug": KEEPER, "dialogue": STORE_DLG,
                  "trigger_radius": 80, "pos": [610, 250]}],
        "teleports": [{"target_level": nxt, "target_spawn_tag": "entry",
                       "require_action": True,
                       "rect": {"pos": [1040, 400], "size": [96, 150]}}],
        "player": {},
    }
    if k == 1:   # the shop's home level needs a matching npc_slot (casting gate)
        doc["npc_slots"] = [{"tag": "store", "pos": [610, 250]}]
    return doc


def _all_item_ids(game_dir: Path) -> list[str]:
    """Every sellable item — key items are quest-granted, never stocked."""
    ids = []
    for f in sorted(glob.glob(str(game_dir / "items" / "*.json"))):
        doc = json.loads(Path(f).read_text())
        if doc.get("kind") == "key":
            continue
        ids.append(Path(f).stem)
    return ids


def generate(game_dir: Path, log=print) -> dict:
    spec_path = game_dir / "gauntlet.json"
    spec = json.loads(spec_path.read_text()) if spec_path.exists() else DEFAULT_SPEC
    n = int(spec.get("levels", 16))
    bg = str(spec.get("background", "BackgroundField.png"))
    esp = spec.get("enemy", DEFAULT_SPEC["enemy"])
    per_enc = int(esp.get("per_encounter", 1))
    xp_factor = float(esp.get("xp_factor", 2.0))

    # --- the free-store keeper: a gauntlet-region ULPC vendor ---
    _write(game_dir / "creatures" / (KEEPER + ".json"), {
        "id": KEEPER, "name": "Quartermaster", "archetype": "vendor",
        "stats": {"lucidity": 6, "creature_affinity": 6, "kinesthetic": 5,
                  "terrain_control": 5, "chaos_mastery": 4},
        "skills": ["attack"], "xp_reward": 0,
        "visual": {"family": "ulpc"},
        "persona": {"faction": "the_order", "home": "gauntlet", "region": "gauntlet"},
        "intent": "Combat Trial — the free quartermaster (own region for R-005)."})

    # --- three base heroes (balanced base like player.json; look + discipline
    #     come from the creator at runtime) ---
    base_stats = json.loads((game_dir / "creatures" / "player.json").read_text())["stats"]
    for slug, name in HEROES:
        _write(game_dir / "creatures" / f"{slug}.json", {
            "id": slug, "name": name, "archetype": "wanderer",
            "stats": dict(base_stats), "skills": ["attack"], "xp_reward": 10,
            "visual": {"family": "ulpc"},
            "intent": "Combat Trial hero — the creator supplies look + discipline."})

    # --- per-level enemies (easy) + levels ---
    for k in range(1, n + 1):
        xp = int(math.ceil(xp_factor * _xp_to_next(k)))
        _write(game_dir / "creatures" / ("gauntlet_e_%02d.json" % k), {
            "id": "gauntlet_e_%02d" % k, "name": "Sparring Construct %d" % k,
            "archetype": "brute", "stats": dict(esp.get("stats", {})),
            "skills": ["attack"], "xp_reward": xp,
            "visual": {"family": "battle", "frames": "Alpha"},
            "intent": "Combat Trial dummy %d — low stats, %d xp (~1 level)." % (k, xp)})
        lid = "gauntlet_%02d" % k
        _write(game_dir / "levels" / "gauntlet" / lid / (lid + ".json"),
               _level_doc(game_dir, k, n, bg, per_enc))

    # --- the free store: dialogue + keeper casting + economy shop ---
    _write(game_dir / "dialogues" / (STORE_DLG + ".json"), {
        "id": STORE_DLG, "intent": "Combat Trial — the free quartermaster.",
        "start": "greet",
        "nodes": {
            "greet": {"speaker_id": KEEPER,
                "text": "Quartermaster's on the house for the Trial. Take what you need.",
                "choices": [
                    {"label": "Browse (free)", "next_node": "done",
                     "effects": [{"type": "shop", "id": STORE_ID}]},
                    {"label": "Not now", "next_node": "done"}]},
            "done": {"speaker_id": KEEPER, "text": "Give 'em hell.",
                     "end_session": True}}})
    _write(game_dir / "casting" / "gauntlet_01.json", {
        "level": "gauntlet_01", "region": "gauntlet",
        "intent": "Combat Trial — the free quartermaster.",
        "npcs": [{"slot": "store", "creature": KEEPER, "dialogue": STORE_DLG}]})

    eco_path = game_dir / "economy" / "economy.json"
    eco = json.loads(eco_path.read_text())
    eco["shops"] = [s for s in eco.get("shops", []) if s.get("id") != STORE_ID]
    eco["shops"].append({"id": STORE_ID, "level": "gauntlet_01", "keeper": KEEPER,
                         "inventory": _all_item_ids(game_dir), "free": True})
    eco_path.write_text(json.dumps(eco, indent=2) + "\n")

    log(f"[gauntlet] {n} levels + enemies, {len(HEROES)} heroes, free store "
        f"({len(_all_item_ids(game_dir))} items) -> {game_dir.name}")
    return {"levels": n}
