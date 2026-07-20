# The Combat Trial — a generated gauntlet for exercising combat end-to-end

A dedicated test path that runs a custom 3-hero party through a chain of bounded
arenas, each **two scaled combats + a free store**, so combat, the roulette
level-up, the character creator, and shops all get exercised together under
control. Everything is **generated from one spec** — retune by editing the spec
and regenerating, never by hand-editing content.

## Run it

1. Launch the game → title menu → **Combat Trial**.
2. The ULPC character creator opens **three times** — build hero A, B, C
   (look + name + discipline each). They become `party_ids = [hero_a, hero_b,
   hero_c]`, embodied leader `hero_a`.
3. You spawn in `gauntlet_01`. Each arena: walk into the two encounter volumes
   (a combat each), visit the **free quartermaster** (every sellable item at 0),
   then take the exit teleport to the next arena. The last loops back to the
   first.
4. Two combats grant ≈1.2 levels → the roulette **commits** on entering the next
   arena and **reveals** on leaving — one level-up per area.

A `combat_trial` world flag isolates the run from the Caden prologue.

## Regenerate / retune

The spec is `games/entropy/gauntlet.json`:

```json
{ "levels": 16,
  "enemy": { "per_encounter": 1, "xp_factor": 0.6,
             "stats": {"creature_affinity":5,"chaos_mastery":5,
                       "kinesthetic":5,"lucidity":5,"terrain_control":6} } }
```

- `levels` — arena count (the "15–20" range).
- `enemy.per_encounter` — enemies per combat (raise for harder fights).
- `enemy.xp_factor` — each enemy grants `ceil(xp_factor · xp_to_next(k))`; two
  combats ≈ `2·xp_factor` levels. `0.6` → ~1.2 levels/area (crosses exactly one
  threshold). Over-granting is safe — the roulette resolves at most one draw per
  area — but backlogs pending draws, so keep it near 0.5–0.7 for a clean 1:1.
- `enemy.stats` — the sparring construct's five stats (low = easy).

The arenas are **tiled** (not painted backdrops): a walled yard, a grass field,
two packed-dirt combat rings, a gate-path east. They share one atlas
(`games/entropy/atlases/gauntlet.spec.json` → grass/dirt/wall/gate). Tilemaps
must be **baked**, so:

```bash
.venv/bin/python scripts/18_gauntlet.py --game entropy               # emit
IDS=$(python3 -c "print(' '.join('gauntlet_%02d'%k for k in range(1,17)))")
.venv/bin/python scripts/13_scene_director.py bake --game entropy ${=IDS}  # publish + bake
```

`bake` publishes (stage 12), reimports, then projects each `content/scenes/
gauntlet_NN.tscn`. To retune enemy count/xp only, editing the atlas isn't
needed — but the level count/layout change re-bakes all arenas.

## What the generator emits (`automap/gauntlet.py`)

- `levels/gauntlet/gauntlet_NN/gauntlet_NN.json` — N **tilemap** arenas (a
  `ground` layer: wall enclosure, grass, two dirt rings, gate-path; `entry`
  spawn + two `encounters[]` with stable ids + a `store` `npc_slot` + a one-way
  teleport). Last loops back to the first.
- `levels/gauntlet/gauntlet_NN/gauntlet_NN.brief.md` — a templated brief per
  arena (the bake gate wants intent before pixels; generated test content
  shares one honest template).
- `casting/gauntlet_NN.json` — every arena seats the free quartermaster (baked
  scenes populate NPCs from the casting sheet, not inline level `npcs`).
- `creatures/gauntlet_e_NN.json` — depth-scaled sparring constructs (low stats,
  computed `xp_reward`).
- `creatures/hero_a|b|c.json` — balanced base party (look + discipline come from
  the creator at runtime).
- `creatures/trial_keeper.json` — a **gauntlet-region** vendor (R-005 forbids
  casting the vaporis Naso into this region).
- `dialogues/gauntlet_store_dlg.json` — the store's dialogue (shop effect).
- `economy/economy.json` — a `gauntlet_store` shop with `free: true` and every
  **sellable** item (key items are quest-granted, excluded). Honored engine-side
  by `ShopSession` (price 0, always buyable) — the real `price_book` is untouched.

## Engine seams reused

- **One-shot encounters** — an `EncounterArea` carries an `encounter_id`; a won
  battle calls `WorldState.clear_encounter(id)` (a saved flag), and a cleared
  ring never re-arms (no re-trigger loop). Both the loader
  (`overworld/location.gd`, backdrops) and the baker (`tools/bake_scene.gd`,
  tilemaps) stamp the id + unique node names. Empty id = the legacy reusable
  sparring ring (untouched baked scenes).
- **Per-slug party** — `PartyState.appearances/char_names/_baked[slug]`;
  `creature_sprites.gd` bakes any slug with an appearance. The creator is reused
  unchanged; the boot flow sets `party_ids` first, then assigns each slug, then
  `rebuild_party()` (so combat gets the trio, not the default lily/zo cache).
- **Free shop** — `ShopSession` honors `doc.free` (schema `economy@1.1.0`).
- **Roulette** — `Game.on_level_entered` commits, `change_level` reveals; the
  free-roam cycle already works.

## Tests

- `tests/test_gauntlet.tscn` — the baked chain is coherent (tilemap kind, wired
  teleports, the baked scene carries a tiled ground + both one-shot encounters +
  the cast keeper, free store at 0, two combats queue one draw, `rebuild_party`
  refreshes the roster, a cleared ring stays spent).
- `tests/test_gauntlet_primitives.tscn` — the encounter/free-shop primitives.
- `tests/test_party_appearance.tscn` — three distinct baked bodies persist.
