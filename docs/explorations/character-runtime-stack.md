# Exploration — Character runtime stack (rig tiers · movement module · creation screen)

**Status: R1 (consignment) + R2 (movement module v1) built 2026-07-15;
R3 (creation screen) / R4 (skeletal-3) brainstorm.** R2 as built:
`godot/scripts/locomotion.gd` (the shared mover; player adapter in
`player_tps.gd`, waypoint adapter in `game/npc/npc_mover.gd` — runtime API
only, routes via `set_route()` until C3 bakes them into game.json),
`balance.derive_movement` (stats → walk/jump/turn; the all-5 deckhand lands
exactly on the old engine constants), stage 10 projects the params into the
`.tres`, NPCs carry a CharacterBody3D + capsule (they settle, can walk, and
block movement), and `tests/test_locomotion.tscn` covers the module headless.
Fixed en route: the NPC face-the-player swivel pointed +Z (the figure's back)
at the player — invisible on the faceless figure-1, a real bug on figure-2.
Written right after the v2 rig build to place
it in the platform: the rig stops being "a nicer figure" and becomes a named
**out-of-the-box tier** the studio guarantees, with a movement module underneath
it and a creation screen on top of the same contract. Companion to
[sophisticated-characters](sophisticated-characters.md) (the narrative/behavior
axes); this doc is the physical stack.

## Where the v2 rig leaves us

The 2026-07-15 rebuild (see `docs/character-pipeline.md` §3 Stage A): articulated
two-segment limbs with gait flexion, human proportions, a face, an idle-life
layer (breathing/blink/weight shift) — all procedural primitives, all text
(.tscn/.gd), zero binary assets, and the two seams that matter held:

- **The appearance contract didn't move.** Still the 9-field
  `character-profile` appearance block; every existing `.tres` renders on the
  new rig unchanged.
- **The animator only reads `CharacterBody3D.velocity`.** The rig doesn't know
  who moves it. That seam is what makes a movement module a clean insertion,
  and it must survive every tier below.

## 1. Consign it: `figure-2`, the out-of-the-box tier

Name the tiers so specs can eventually select on them:

| Tier | What | Status |
|---|---|---|
| `figure-1` | box torso, swing-only limbs | retired 2026-07-15 |
| `figure-2` | articulated primitives + face + idle life | **the out-of-the-box default** |
| `skeletal-3` | Skeleton3D on the standard humanoid profile, animation libraries | future (§2) |
| styled/skinned | asset-factory-produced bodies per visual identity | far future |

Consignment rule (the schema registry's own discipline): **the tier enum enters
a spec only when a consumer selects on it** — i.e. when a second live tier
exists. Until then, consignment = this name, `scenes/character.tscn` as the
reference implementation, and the gallery renders
(`tests/character_gallery.tscn` → `work/character_gallery/`) as its acceptance
images. The field's eventual home is the **game spec** (the brief's gspec box):
a game declares the character tier it ships with, the way a scene declares its
visual identity. Visual identity may later gain a `characters` block (outfit
palettes, wear-and-tear for postapo) — restyling *within* a tier, not a tier.

## 2. The movement module

### Split that must happen: mover vs animator

Today locomotion lives in `player_tps.gd` — input handling and physics fused,
with hardcoded constants (`walk_speed 6.0`, `sprint_mult`, `jump_velocity 6.0`,
fly mode). NPCs have no mover at all (static `Node3D`). The movement module is
the extraction of the physics half into a shared component:

```
input adapter (player)  ──┐
                          ├─→ locomotion.gd (verbs: walk/run/jump/…) ─→ CharacterBody3D.velocity ─→ rig animates
waypoint adapter (NPC) ───┘         ↑
                          movement params (derived from stats)
```

One component, two drivers — the NPC waypoint follower is the same slice as
living-behavior C3 in the companion doc. The rig keeps reading velocity and
never learns which adapter is pushing.

### Regimented by the mechanics module

`automap/balance.py` already derives speed from the five attributes
(`BASE_SPEED + 0.25·kinesthetic + 0.25·lucidity`) — but only inside duels; the
runtime ignores stats entirely. The movement module closes that gap with the
same pattern: **movement params are derived, never hand-set**, and the mapping
is owned by the mechanics module (it is a mechanics opinion, like the Fighter
formulas — big bases, small per-point terms):

- `kinesthetic` → run speed, jump impulse
- `terrain_control` → slope tolerance / rough-ground penalty reduction
- `lucidity` → (with kinesthetic) acceleration/turn composure
- `chaos_mastery`, `creature_affinity` → stay priced in combat; no free movement

Movement *verbs* (walk/run/jump now; crouch/swim/climb later) are likewise a
game-spec decision — the mechanics module declares which regimes a game has;
the movement module executes them. Params reach the runtime through the profile
carry-through (C2 in the companion doc), not through new hardcoded exports.

### Bone management (`skeletal-3`)

The "standard bone package" question has a Godot-native answer:

- **Skeleton standard: `SkeletonProfileHumanoid`** — Godot 4's built-in
  humanoid bone profile — plus **`BoneMap`** for retargeting any external
  humanoid rig onto it. Adopting it makes every standard animation source
  reachable.
- **Text survives the no-binary rule.** `Skeleton3D` lives in text `.tscn`;
  animations live in text `.tres` `AnimationLibrary`. So the pipeline shape is:
  a stage script imports/retargets an external pack once, **bakes the curves to
  text**, commits text. Binary sources never enter git (same posture as
  footage).
- **Animation sources**, in preference order: CC0 packs (Quaternius universal
  animation library, Kenney animated characters — redistributable, bakeable);
  Mixamo (usable in products but redistribution-restricted — verify before
  committing baked curves; worst case it stays a local-only source like the
  park clip). ⚠️ license check is a to-do on this line.
- **The procedural gait stays as the zero-asset fallback** — a scene with no
  animation library still walks. Movement regimes map to an `AnimationTree`
  state machine whose states are the game-spec verbs; `figure-2` implements the
  same verbs procedurally, which is what makes the tiers swappable.

`skeletal-3` is deliberately last: it changes how the rig is *driven*, so the
verb set and param derivation (movement module v1) should be proven on
`figure-2` first.

## 3. The character creation screen

The second surface over the same contract. `/create-character` (conversation)
and the screen (direct manipulation) both emit `character-profile@2.0.0` JSON,
and **the stage-10 gate stays the only door** — the screen must not become a
side-channel around admission.

- **Appearance tab**: the appearance block is exactly 9 fields — a perfect
  form. Live preview on the v2 rig (it already rebuilds via `_apply_profile`;
  the gallery scene's turntable/walk toggle is the preview widget in embryo).
- **Narrative tab**: name, role, traits, goal, dialogue seed — free text,
  schema-bounded lengths.
- **Stats tab**: point allocation with live feedback — and here sits the one
  hard decision. The autosim is Python, and a GDScript port would fork the RNG
  (Python's Mersenne `gauss` streams are not reproducible with Godot's
  `randfn`), so ported verdicts would drift from gate verdicts. **Recommended:
  don't port.** The studio runs on this machine; the screen shells out to the
  real gate (`OS.execute` → `scripts/10_create_character.py`), renders the
  verdict and per-matchup evidence in-UI, and hosts the revise loop in place.
  A GDScript sim becomes worth it only if creation ever ships *inside* a game
  (player-facing), and then the envelope graduates into the game spec with
  golden-verdict fixtures.
- **Placement**: a studio tool scene (`godot/tools/`), not part of the shipped
  `game.tscn` shell.

## Proposed slices

| Slice | What ships | Why this order |
|---|---|---|
| **R1 — consign `figure-2`** | tier names, docs, gallery as acceptance render | tiny; makes the default a commitment |
| **R2 — movement module v1** | `locomotion.gd` extraction, player adapter, stats→params via mechanics, NPC waypoint adapter | unlocks living behavior (C3) with the same component; proves the verb set |
| **R3 — creation screen v1** | appearance+narrative+stats tabs, live rig preview, shell-out gate | studio surface; no new contracts |
| **R4 — `skeletal-3`** | humanoid bone profile, retarget/bake stage (text output), AnimationTree regimes | the big one; sits on R2's proven verbs |

R2 and R3 are independent of each other; both sit on the v2 rig as-is.
Cross-links: [sophisticated-characters](sophisticated-characters.md) (C2
carry-through feeds R2's params; C3 shares R2's component),
[character-creator](character-creator.md) (the gate and its rules),
[populate-the-world](populate-the-world.md) (the NPC spawn path R2 plugs into).
