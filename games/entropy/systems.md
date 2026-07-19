# Systems — the rulers for game `entropy`

Owned by the **Systems Director** (docs/studio-org.md; the chair is
formalized in R6 — until then this document IS the chair). Every number
a gate enforces lives here first; the enforcement constants in
`automap/items.py` / `automap/economy.py` / `automap/ui_gate.py` mirror
this file and cite it. Changing a ruler = editing this file AND its
constant in the same commit.

## Stat budgets (the stat-budget gate, ledger row 20)

- The five attributes: creature_affinity, chaos_mastery, kinesthetic,
  lucidity, terrain_control. Creature admission band: totals 25–27
  (the autosim envelope, unchanged).
- **Equipment modifier budget**: Σ|modifiers| ≤ **tier + 1**
  (t1 = 2 points, t2 = 3 … t5 = 6). A +2 kinesthetic charm is a t1
  item at its ceiling.
- **Skill caps**: `formula.atk_mult` ≤ **8.0** (the basic attack is
  6.0 — skills may exceed it, never dwarf it); heal skills follow the same
  atk_mult cap as heal power.
- **Status/tactics caps** (typed statuses, `status.kind` + `turns`):
  per-kind magnitude ceilings — poison ≤ **60**, regen/shield ≤ **40**,
  buffs/debuffs (atk/def up/down) ≤ **0.5** (a fraction, so +50% at most);
  stun carries no magnitude. `status.turns` ≤ **5** (a status primes, never
  perma-locks). `hits` (multi-hit) ≤ **4** (a flurry may split, never
  machine-gun). `anim` must be one of strike/thrust/bash/cast/bolt/heal/
  buff/debuff/self.

## Class budgets (the class stat-budget gate, `automap/classes.py`)

- The five disciplines map onto the five attributes: **shaper**=
  terrain_control, **steward**=creature_affinity, **breaker**=
  kinesthetic, **mentarch**=lucidity, **weaver**=chaos_mastery (the
  discipline nearest the Road — prediction/probability).
- A discipline's `attribute_bonus` sums to ≤ **3** (a +2 primary and at
  most one +1 elsewhere). Chosen once, at age 15, it is irreversible.
- Every ability in a discipline's `ability_pool` must be a real skill@
  (and should include the basic `attack`). Pools stay within the skill
  caps above.

## Progression (design.json `progression`, game-design@1.1)

- XP curve: `base 100, growth 1.35`, max level **20**.
- Per level: kinesthetic +1, terrain_control +1 (the reference game's
  intent, kept). Derived hp/spd follow automatically via `derived`.
- Learnsets are per-creature in the design doc; a skill unlocks at its
  stated level, never retroactively removed.

## Currency targets (the economy-sim gate, ledger row 25)

- Currency: **brass tokens** (`brass_token`) — the fair's own fiction
  (Pippa is one token short; Mirella counts four a ride).
- Starting gold: **20 tokens** (design.json `starting_loadout`).
- Price bands: t1 consumables 5–15; t1 equipment 20–40; t2 equipment
  45–80; key items are NEVER priced (quest-granted only).
- Every non-key item must appear in the price book; every shop's
  keeper must be cast in its level's sheet; each shop must have at
  least one line affordable within starting gold + the arc's rewards.

## Interface floors (the readability gate, ledger row 30)

- Reference resolution 1152×648. Font floors: default ≥ **12 px**,
  small ≥ **10 px**, title ≥ **16 px**.
- Contrast (WCAG relative luminance): text vs panel_bg ≥ **4.5**,
  accent vs panel_bg ≥ **3.0**; disabled vs panel_bg ≥ 2.0 (warn).
- Required pause tabs: **items, save, quit** (equipment/status may be
  staged in later).

## Save contract (Systems fold: save/progression)

- 3 slots (`user://saves/slot_<n>.json`) + legacy single file read as
  slot 0. A save is SERIALIZATION of PartyState + WorldState — never
  state invention; every field read with a default so older saves load.
