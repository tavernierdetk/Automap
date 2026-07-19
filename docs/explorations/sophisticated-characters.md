# Exploration — Sophisticated characters (characters v2)

**Status: brainstorm, 2026-07-14. Not greenlit.** Where the character system
could go after creator v1 + populate. Four axes explored together because they
share seams; proposed as thin vertical slices per the locked plateau-D approach.

## Where v1 stands

A character today is: `character-profile@2.0.0` JSON (narrative prose +
9-field parametric appearance + five Entropy stats) → stage-10 gate (schema +
autosim duels vs a four-archetype reference cast) → appearance-only `.tres` →
a **static** figure at an anchor with hand-authored dialogue trees switched by
quest state. Marguerite in lagrave is the one worked example, headless-tested
to quest completion.

What the runtime survey (2026-07-14) established:

- **NPCs cannot move.** `npc.tscn` root is a plain `Node3D` — no body, no
  navmesh anywhere. But `character.gd` already drives a full procedural walk
  cycle off an ancestor `CharacterBody3D.velocity`, so locomotion is a
  root-node swap plus a mover, not an animation project.
- **Nothing remembers anything.** No conversation memory, no flag store, no
  disposition, nothing persists between talks. `dialogue_finished` emits an
  `outcome` that **no consumer reads** (`quest_manager.gd:178`) — a dangling
  wire, first thread to pull.
- **The rich half of the profile never reaches the game.** Projection keeps
  only `appearance`; personality, goal, voice, stats, backstory, dialogue_seed
  all stop at the JSON. The five stats exist *only* inside the autosim.
- **The extension points are single, small, named:** dialogue effects are one
  `match` (`dialogue_manager.gd:147-152`, sole verb: `offer_quest`); objective
  types are two handlers in `quest_manager.gd` (`reach_zone`, `talk_to`);
  `map_loader.loaded_dir` + `minimap.json` already give runtime a world↔map
  transform, but `features.json` is not consumed at runtime.
- Anything new stays headless-testable by emitting through the frozen
  `GameEvents` bus — `test_game_integration.gd` drives real published scenes
  through real physics.

## The four axes

### 1. Dialogue depth — the foundational one

Everything else conditions on state, so state comes first.

- **A memory store**: a small `GameState` autoload (bus consumer, like
  QuestManager) holding named flags + per-NPC counters (times talked,
  disposition int). In-memory first; save/load is its own later slice.
- **Effects vocabulary** grows from one verb to a handful:
  `set_flag`, `disposition` (+/- n), keep `offer_quest`. Each is a case in the
  existing `match`.
- **Conditions**: dialogue choices and `dialogue_variants` gain an optional
  `when`/`requires` clause — flags, disposition thresholds, quest state, and
  **stat checks** (`{"stat": "lucidity", "gte": 6}`). Stat checks are the
  headline: the five attributes finally act outside the autosim, and the
  asset↔mechanics contract starts paying rent in dialogue.
- **Consume `outcome`**: declined/accepted/insulted outcomes feed disposition.
- Contract: `game@1.1.0`, strictly additive (v1 game.json stays valid).

### 2. Deeper character sheet — profile v2.1

The schema's own rule applies: *new fields arrive only when a consumer selects
on them.* So each field ships with its consumer, never speculatively:

- **Carry-through first** (no new fields): get the narrative block and stats
  into the runtime. Cheapest honest route: publish the character JSON as a
  sidecar the npc loads (`profiles/<slug>.json` beside the `.tres`), rather
  than fattening the `.tres` contract that the rig deliberately keeps minimal.
  Consumer: stat checks + disposition openers from axis 1.
- **Then additive fields with consumers**:
  - `relationships[]` (`{who, kind, note}`) — consumed by dialogue authoring/
    generation (NPCs reference each other) and by ensemble casting (axis 4).
  - `home` (a feature id or anchor) — consumed by living behavior (axis 3):
    where the route starts, where they stand at spawn.
  - `routine[]` — consumed by axis 3 v2 (time-of-day) only when a day cycle
    exists; do not add before then.
- Contract: `character-profile@2.1.0`, additive; the gate and rig read v2.0
  documents unchanged.

### 3. Living behavior — NPCs that do things

The world model is the differentiator here: routes come from *real geometry*,
same pattern as minimap and anchors.

- **Generation-side pathing, runtime-side walking.** No navmesh. Stage 5/6
  already knows the road graph (`features.json`); a route baker computes a
  waypoint loop along roads near the NPC's home/anchor and writes it into
  `game.json` as `npcs[].route[]` (a list of anchors — `xz_frac`, resolved to
  terrain by the existing raycast machinery). The runtime never learns about
  features.json; it just walks waypoints. Honors the §11 decoupling.
- **Runtime mover**: npc root becomes a `CharacterBody3D`; a trivial
  waypoint-follower sets velocity; the rig walk-animates for free; pause +
  face-player on interaction (the swivel logic already exists).
- **Roads are `deco_` (no colliders) by design** — good news: nothing to
  collide with; the terrain carries NPCs exactly as it carries the player.
- v2 (later): time-of-day presence once an env/day cycle exists; "meet them
  on the road" quest objectives (`near_npc` objective type).

### 4. Ensemble casting — a troupe, not a character

Scale the creator from one interview to a cast, keeping the LLM-fills-spec
boundary intact:

- **A casting-director flow** (skill v2 or a sibling skill): reads the scene's
  `features.json` + identity (madelinot vs postapo changes who plausibly lives
  there) and proposes a coherent troupe — roles anchored to real places (a
  fisher by the quay notch, a scavenger in the crumbled block), relationships
  between members (axis 2 fields), goals that interlock into a quest web.
- **Cast admission** (already queued in the creator follow-ups): evaluate each
  member against the *scene's* cast, not just the reference archetypes —
  `balance.evaluate(stats, cast=scene_cast)` already takes the parameter; the
  slice is stage-10 `--scene` wiring plus a policy (envelope vs whom).
- Output: N character JSONs (each through the gate) + the scene's `game.json`
  npcs/homes/routes/quest skeletons. Dialogue trees per member start from
  `dialogue_seed` + relationships; full dialogue *generation* remains gated on
  the dialogue-node schema extraction into platform-specs (long-queued).

## Proposed slice order

Dependencies run 1 → 2 → (3, 4); 3 and 4 are independent of each other.

| Slice | What ships | Proves |
|---|---|---|
| **C1 — dialogue state** | GameState autoload, effect verbs, `when` conditions incl. stat checks, outcome consumed; `game@1.1.0`; a lagrave scene beat using a flag + a lucidity check | NPCs remember; stats act in play |
| **C2 — profile carry-through (+v2.1)** | JSON sidecar into runtime; `relationships`/`home` fields with their consumers | the rich half of the profile reaches the game |
| **C3 — living behavior v1** | generation-side route baker (roads → waypoints in game.json), CharacterBody3D npc + waypoint mover | world-model-fed motion; the village breathes |
| **C4 — ensemble casting** | casting-director flow, cast admission (`--scene`), a 3–4 member troupe on lagrave or plateau with interlocking goals | populate scales; the gate holds at troupe size |

C1 is the recommended start: smallest diff, unblocks every conditional the
other slices want, and the dangling `outcome` wire makes it feel inevitable
rather than speculative.

## Ownership note

Per the session split, C1 and the runtime halves of C2/C3 live in `godot/`
(playback session's territory); the route baker, schema bumps, casting flow,
and cast admission are generation-side. C4 and the baker can proceed
independently of the runtime slices; coordinate before touching
`dialogue_manager.gd`/`npc_controller.gd`.
