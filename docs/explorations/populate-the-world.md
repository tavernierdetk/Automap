# Populate the world — an admitted character becomes an NPC (plateau D, slice 2)

**Status: built, 2026-07-12.** Plateau locked at §9 step 5: **D, the
game-creation studio**, built as thin vertical slices on top of the proven
A/B worlds. This slice: the character creator's output enters the game loop —
walk up to Marguerite on La Grave, press E, take her quest.

## What it took (almost nothing — the seams were already there)

The game layer already had every hook this slice needed, which is the
platform thesis paying out:

- `game.json` `npcs[].profile` already loads a CharacterProfile `.tres` onto
  the spawned figure (`world_director` → `npc_controller.apply_profile`).
- `dialogue_variants` already switch trees by quest state
  (intro / reminder / turn-in / epilogue).
- `game@1.0.0` already validates all of it — no schema bump.

So the slice is **content plus proof**: `godot/scenes/lagrave/game.json`
(the per-scene game override, same data-layer pattern as `features.json`)
authored as an LLM-fills-spec artifact and schema-validated, plus a lagrave
chapter in the headless integration test.

## The content

Marguerite à Théodore — the stage-10-admitted character — stands on the
harbour front near the manoir (the IFC-substituted building), placed with
`xz_frac` anchors derived from the world model's real geometry (the sea
outline's little notch at the north shore is the "old quay"). Her quest hangs
off her v2 `personality.goal` ("find out who has been mooring at the old quay
after dark"): reach the quay zone, report back, epilogue in her voice.

The dialogue trees keep her `dialogue_seed` as the literal opening line —
the v2 narrative fields driving authoring exactly as designed.

## Proof

`tests/test_game_integration.gd` gained `[lagrave populate]`: instantiates
the published geodata scene, asserts the spawned figure wears
`marguerite_a_theodore.tres` (traits included — not a default profile), both
actors sit at 0.00 m gap on the terrain collider, then plays the full loop
through real physics triggers to quest completion. ALL PASS headless.

## Follow-ups

- **Dialogue generation** stays the next narrative step: trees here were
  authored by the session directly; generating them from the v2 fields wants
  the dialogue-node schema (still queued in platform-specs, from
  entropy-integrated's format — the narrative-module merge, not this slice).
- **/create-character step 6b**: offer "place them in a scene" (append to the
  scene's game.json npcs[] + a goal-derived quest skeleton).
- **Multi-NPC casts** and the party/cast admission idea from the
  character-creator follow-ups.
- The quay has no dock geometry — a pier asset via building/feature
  substitution would make the spot read on sight.
