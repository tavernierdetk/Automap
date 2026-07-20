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


# --- the arena: a bounded tiled yard (all arenas share this layout) ----------
TILE = 32
COLS, ROWS = 26, 18                 # 832 x 576 px
MID = ROWS // 2                     # centre row (9)
LEFT_RING = (8, MID)                # (col, row) — combat 1
RIGHT_RING = (17, MID)              # combat 2
ENTRY = (2, MID)                    # west spawn
STORE = (13, 3)                     # north quartermaster
EXIT = (23, MID)                    # east gate (teleport onward)


def _px(cell: tuple[int, int]) -> list[int]:
    """Cell (col, row) -> pixel centre."""
    return [cell[0] * TILE + TILE // 2, cell[1] * TILE + TILE // 2]


def _arena_rows() -> list[str]:
    """The ground layer: a wall enclosure, grass field, two dirt combat rings,
    a gate-path leading to the east exit."""
    g = [["g"] * COLS for _ in range(ROWS)]
    for r in range(ROWS):
        for c in range(COLS):
            if r in (0, ROWS - 1) or c in (0, COLS - 1):
                g[r][c] = "w"                       # stone enclosure (blocks)
    for (cc, cr) in (LEFT_RING, RIGHT_RING):        # 4x4 packed-dirt rings
        for dr in range(-2, 2):
            for dc in range(-2, 2):
                r, c = cr + dr, cc + dc
                if 0 < r < ROWS - 1 and 0 < c < COLS - 1:
                    g[r][c] = "d"
    for dr in range(-1, 2):                         # worn gate-path to the exit
        r = MID + dr
        for c in range(EXIT[0] - 1, COLS - 1):
            g[r][c] = "p"
    return ["".join(row) for row in g]


def _level_doc(game_dir: Path, k: int, n: int, per_enc: int) -> dict:
    lid = "gauntlet_%02d" % k
    enemy = "gauntlet_e_%02d" % k
    nxt = "gauntlet_%02d" % (k + 1 if k < n else 1)   # last loops to the first
    rings = [LEFT_RING, RIGHT_RING]
    enc = []
    for i in range(2):                                # two combats, one per ring
        enc.append({"id": "%s#%d" % (lid, i + 1),
                    "rect": {"pos": _px(rings[i]), "size": [120, 120]},
                    "enemies": [enemy] * per_enc, "seed": k * 100 + i,
                    "layout": "field",
                    "intent": "Combat %d of Trial %d." % (i + 1, k)})
    return {
        "id": lid, "kind": "tilemap",
        "intent": "Combat Trial arena %d — a walled yard, two combats, a free "
                  "store, a gate east to arena %s." % (k, nxt.split("_")[1]),
        "tilemap": {"atlas": "gauntlet", "tile_size": TILE,
                    "grid_size": [COLS, ROWS],
                    "layers": [{"name": "ground",
                                "palette": {"g": "grass", "d": "dirt",
                                            "w": "wall", "p": "gate"},
                                "rows": _arena_rows()}]},
        "spawns": [{"tag": "entry", "pos": _px(ENTRY)}],
        "npc_slots": [{"tag": "store", "pos": _px(STORE)}],
        "encounters": enc,
        "teleports": [{"target_level": nxt, "target_spawn_tag": "entry",
                       "require_action": True,
                       "rect": {"pos": _px(EXIT), "size": [64, 120]}}],
        "player": {"pos": _px(ENTRY)},
    }


def _brief(k: int, n: int) -> str:
    nxt = k + 1 if k < n else 1
    return (
        "# Combat Trial — Arena %d (generated)\n\n"
        "## The place\n"
        "A bounded practice yard: a stone wall encloses a grass field. Two\n"
        "packed-dirt rings mark where the fights happen; a worn gate-path leads\n"
        "east to the next arena. Reads: (1) an enclosed ring, (2) two combat\n"
        "grounds left and right, (3) the gate onward.\n\n"
        "## Light & air\n"
        "Neutral daylight, no biome — a flat, legible sparring yard.\n\n"
        "## Zones\n"
        "- Entry (west) — the player spawns here.\n"
        "- Ring 1 / Ring 2 (dirt) — the two combats.\n"
        "- Quartermaster (north) — the free store.\n"
        "- Gate (east) — teleport to arena %d.\n\n"
        "## Register\n"
        "- Terrain: grass (floor), dirt (rings), wall (enclosure, blocks),\n"
        "  gate (path). Atlas: gauntlet.\n"
        "- Assets reused: none. Assets to create: none.\n\n"
        "## Motion\n"
        "Nothing lives here — a static yard.\n\n"
        "## Acceptance reads\n"
        "- The wall fully encloses the field but for the east gate.\n"
        "- Two dirt rings are visible and reachable.\n"
        "- The gate reads as the way out.\n" % (k, nxt)
    )


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
        ldir = game_dir / "levels" / "gauntlet" / lid
        _write(ldir / (lid + ".json"), _level_doc(game_dir, k, n, per_enc))
        # a brief per arena (the bake gate: intent before pixels) — generated
        # test content, so every arena shares one honest template
        (ldir / (lid + ".brief.md")).write_text(_brief(k, n))
        # every arena seats the free quartermaster (baked scenes populate NPCs
        # from the casting sheet, not inline level npcs)
        _write(game_dir / "casting" / (lid + ".json"), {
            "level": lid, "region": "gauntlet",
            "intent": "Combat Trial — the free quartermaster.",
            "npcs": [{"slot": "store", "creature": KEEPER,
                      "dialogue": STORE_DLG}]})

    # --- the free store: the shared dialogue + economy shop ---
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

    eco_path = game_dir / "economy" / "economy.json"
    eco = json.loads(eco_path.read_text())
    eco["shops"] = [s for s in eco.get("shops", []) if s.get("id") != STORE_ID]
    eco["shops"].append({"id": STORE_ID, "level": "gauntlet_01", "keeper": KEEPER,
                         "inventory": _all_item_ids(game_dir), "free": True})
    eco_path.write_text(json.dumps(eco, indent=2) + "\n")

    log(f"[gauntlet] {n} levels + enemies, {len(HEROES)} heroes, free store "
        f"({len(_all_item_ids(game_dir))} items) -> {game_dir.name}")
    return {"levels": n}
