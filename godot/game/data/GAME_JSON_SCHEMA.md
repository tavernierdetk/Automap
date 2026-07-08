# `game.json` schema — per-scene game override

A `game.json` sitting in a published scene's folder (`godot/scenes/<name>/game.json`)
hand-tunes the narrative/quest game for that place. It is **optional** and **git-clean
text** — the same data-layer pattern as `features.json` beside geometry. When absent or
malformed, `WorldDirector` builds a minimal procedural game instead (one NPC + one
"reach that point" objective), so the loop always works.

Parsed by `godot/game/data/game_data_loader.gd` → a `GameConfig` of typed resources
(`NpcSpawn`, `QuestDef`, `ZoneDef`, `DialogueTree`). Unknown keys are ignored; missing
keys use defaults; parsing never crashes.

## Top-level shape

```json
{
  "spawn":  { "anchor": "top_center" },
  "npcs":   [ /* NpcSpawn */ ],
  "zones":  [ /* ZoneDef */ ],
  "quests": [ /* QuestDef */ ],
  "dialogue": { "<tree_id>": { /* DialogueTree */ } }
}
```

## `anchor` — placement vocabulary (NPCs, zones, spawn)

Resolved by `WorldDirector` against the loaded map's world AABB (reusing
`map_loader._world_aabb`) plus a downward raycast to sit on the terrain, so placements
are **scene-size-agnostic**. One of:

| Form | Meaning |
|---|---|
| `"top_center"` | centre of the map (string shortcut) |
| `{ "xz_frac": [0.3, 0.4] }` | fraction across the map's X / Z extent, dropped to ground |
| `{ "world": [x, y, z] }` | absolute world coordinates |

The scan's footprint rarely fills its axis-aligned AABB (rotated flights, ragged
edges), so an `xz_frac` near 0/1 can point at empty air. When the ground raycast
misses, the point is **walked toward the map centre** until terrain is found (a
warning is logged with the moved position) — anchors always land somewhere the
player can walk to. The player body is excluded from the raycast.

## `npcs[]` (→ `NpcSpawn`)

```json
{ "id": "keeper", "name": "The Keeper",
  "profile": "res://profiles/keeper.tres",
  "anchor": { "xz_frac": [0.3, 0.4] },
  "dialogue": "keeper_intro" }
```
`profile` is a `CharacterProfile` `.tres` (rendered by the existing `character.tscn`).
Omit it to use `npc.tscn`'s default profile. `dialogue` keys into `dialogue{}`.

### `dialogue_variants` — quest-state-aware dialogue (optional)

What an NPC says can depend on a quest's state. Variants are evaluated top-down at
interact time; the **first match wins**, `dialogue` is the fallback:

```json
"dialogue": "keeper_intro",
"dialogue_variants": [
  { "when": "turn_in",  "quest": "light_the_way", "tree": "keeper_report"   },
  { "when": "active",   "quest": "light_the_way", "tree": "keeper_reminder" },
  { "when": "complete", "quest": "light_the_way", "tree": "keeper_after"    }
]
```

`when` ∈ `turn_in` | `active` | `complete` | `inactive` (default `active`).
`turn_in` means the quest is active **and its current objective is `talk_to` this
npc** — finishing that tree completes the objective. `active` also holds during
turn-in, so list `turn_in` first. All of an NPC's trees (default + variants) satisfy
a `talk_to` objective — "talk to X" counts whichever conversation X gives.

## `zones[]` (→ `ZoneDef`)

```json
{ "id": "light", "anchor": { "xz_frac": [0.8, 0.2] }, "radius": 8 }
```
Entering the zone emits `GameEvents.zone_reached("light")`.

## `quests[]` (→ `QuestDef`)

```json
{ "id": "reach_light", "title": "Find the old lighthouse", "auto_start": false,
  "objectives": [
    { "type": "reach_zone", "zone": "light",  "text": "Reach the lighthouse" },
    { "type": "talk_to",    "npc":  "keeper", "text": "Report back to the keeper" }
  ] }
```
Objectives are walked in order. `type` ∈ `reach_zone` | `talk_to`. `auto_start: true`
activates the quest on load; otherwise it waits to be offered from dialogue.

## `dialogue{}` (→ `DialogueTree` each)

A tree is `{ "start": "<node_id>", "nodes": { "<id>": <node> } }`, or just the bare
`nodes` map (start defaults to `"start"`). Node shape:

```json
{
  "speaker": "The Keeper",
  "text": "Storm's coming. Would you check the old light for me?",
  "choices": [
    { "text": "I'll go.",   "goto": "thanks", "effects": [ { "offer_quest": "reach_light" } ] },
    { "text": "Not today.", "goto": "end",    "outcome": "declined" }
  ],
  "next": "<node_id>",
  "effects": [ { "offer_quest": "reach_light" } ],
  "outcome": "accepted"
}
```
- `choices` (optional): branch. Each has `text`, `goto` (next node id, or `"end"`), and
  optional `effects` / `outcome`.
- `next`: linear successor when there are no choices.
- `effects`: list of one-key dicts applied when the node is shown. Vocabulary lives with
  `DialogueManager`; the canonical one is `{ "offer_quest": "<quest_id>" }`.
- `outcome`: free-form tag surfaced on `GameEvents.dialogue_finished(tree_id, outcome)`.
- A node with `goto`/`next` of `""` or `"end"` (or missing) terminates the tree.

## Cross-module seam (for the game modules)

- All modules communicate via the **`GameEvents` autoload signal bus** — see
  `godot/game/game_events.gd` (the frozen signal list). Managers own logic; UI only
  consumes; NPCs only emit intent.
- **Interaction input** follows the existing codebase idiom (`player_tps.gd`): read
  physical keys directly (`Input.is_physical_key_pressed(KEY_E)` / match on
  `event.physical_keycode`). No `InputMap` actions are added.
- Autoloads (registered in `project.godot`, in load order): `GameEvents`,
  `DialogueManager`, `QuestManager`.
