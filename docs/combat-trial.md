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
{ "levels": 16, "background": "BackgroundField.png",
  "enemy": { "per_encounter": 1, "xp_factor": 0.6,
             "stats": {"creature_affinity":5,"chaos_mastery":5,
                       "kinesthetic":5,"lucidity":5,"terrain_control":6} } }
```

- `levels` — arena count (the "15–20" range).
- `background` — shared backdrop (any published `content/backgrounds/*.png`).
- `enemy.per_encounter` — enemies per combat (raise for harder fights).
- `enemy.xp_factor` — each enemy grants `ceil(xp_factor · xp_to_next(k))`; two
  combats ≈ `2·xp_factor` levels. `0.6` → ~1.2 levels/area (crosses exactly one
  threshold). Over-granting is safe — the roulette resolves at most one draw per
  area — but backlogs pending draws, so keep it near 0.5–0.7 for a clean 1:1.
- `enemy.stats` — the sparring construct's five stats (low = easy).

Then:

```bash
.venv/bin/python scripts/18_gauntlet.py --game entropy      # emit
.venv/bin/python scripts/12_publish_game.py --game entropy  # publish (no bake — backdrops)
```

## What the generator emits (`automap/gauntlet.py`)

- `levels/gauntlet/gauntlet_NN/gauntlet_NN.json` — N **backdrop** arenas (bg +
  `entry` spawn + two data `encounters[]` + inline store NPC + one-way teleport;
  `gauntlet_01` also carries the `store` `npc_slot` its casting sheet needs).
- `creatures/gauntlet_e_NN.json` — depth-scaled sparring constructs (low stats,
  computed `xp_reward`).
- `creatures/hero_a|b|c.json` — balanced base party (look + discipline come from
  the creator at runtime).
- `creatures/trial_keeper.json` — a **gauntlet-region** vendor (R-005 forbids
  casting the vaporis Naso into this region).
- `dialogues/gauntlet_store_dlg.json` + `casting/gauntlet_01.json` — the store's
  dialogue (shop effect) + keeper casting.
- `economy/economy.json` — a `gauntlet_store` shop with `free: true` and every
  **sellable** item (key items are quest-granted, excluded). Honored engine-side
  by `ShopSession` (price 0, always buyable) — the real `price_book` is untouched.

## Engine seams reused

- **Backdrop encounters** — `engine/overworld/location.gd` builds an
  `EncounterArea` per `encounters[]` entry (previously only the tilemap baker
  did). Additive: no prior backdrop defined the field.
- **Per-slug party** — `PartyState.appearances/char_names/_baked[slug]`;
  `creature_sprites.gd` bakes any slug with an appearance. The creator is reused
  unchanged; the boot flow assigns each of the three to a slug.
- **Free shop** — `ShopSession` honors `doc.free` (schema `economy@1.1.0`).
- **Roulette** — `Game.on_level_entered` commits, `change_level` reveals; the
  free-roam cycle already works.

## Tests

- `tests/test_gauntlet.tscn` — the published chain is coherent (wired teleports,
  two encounter volumes build, free store stocks the sellable catalog at 0, two
  combats queue exactly one draw).
- `tests/test_gauntlet_primitives.tscn` — the S1 engine primitives in isolation.
- `tests/test_party_appearance.tscn` — three distinct baked bodies persist.
