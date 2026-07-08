# Automap — Game Layer (future-C)

The **narrative/quest game** built on top of the walkable viewer. This is the
"future-C" ambition from the [design spec](2026-06-30-automap-pipeline-design.md) §1/§8:
the reconstructed place becomes set dressing for a real (if rudimentary) game loop —
meet NPCs, talk, take a task, go somewhere in the scan, report back.

It is a **bolt-on inside `godot/`** that honours the §11 engine/pipeline decoupling:
generation (stages 0–3/5/6) never learns about quests, and the game plays on *any*
`.glb` the pipeline emits. Per-scene content is an optional `game.json` sitting beside
the published scene — the same data-layer pattern as `features.json` beside geometry.

## The loop

You spawn as your (third-person) character. A HUD shows your objective. Walk near an
NPC — a `character.tscn` figure driven by a `CharacterProfile` — and a "Press E to
talk" prompt appears. Talking opens a dialogue panel; a choice can **offer a quest**.
The quest activates a world-space marker + HUD tracker; reaching a zone or talking to
an NPC advances it; the last objective completes it. On a scene with **no `game.json`**,
a procedural fallback spawns one NPC + one "reach that point" quest so the loop always
works.

## Architecture — one bus, five modules

Everything talks through a single autoload **signal bus**, `GameEvents`
(`godot/game/game_events.gd`) — a frozen signal list. Managers own logic and emit/consume;
UI only consumes; NPCs only emit intent. This is what let the modules be built in
parallel without importing each other.

```
godot/
├── game/
│   ├── game_events.gd          autoload GameEvents — the frozen signal bus (the seam)
│   ├── quest_manager.gd        autoload QuestManager — state machine (inactive→active→complete)
│   ├── dialogue_manager.gd     autoload DialogueManager — DialogueTree traversal + effects
│   ├── world_director.gd       node in game.tscn — reads game.json / procedural fallback,
│   │                           resolves anchors on the terrain, spawns NPCs/zones/UI/marker
│   ├── objective_marker.tscn   world-space beacon that follows the tracked objective
│   ├── interactable.gd         tiny base (prompt_text / interact)
│   ├── objective_zone.tscn     Area3D → GameEvents.zone_reached(id)
│   ├── npc/npc.tscn            character.tscn + interaction Area3D + name label
│   └── data/                   GameConfig · QuestDef · DialogueTree · NpcSpawn · ZoneDef
│       ├── game_data_loader.gd JSON (game.json) → the typed resources above
│       └── GAME_JSON_SCHEMA.md the authoring reference for game.json
├── ui/
│   ├── hud.tscn                interaction prompt + quest tracker (bus-driven, mouse-transparent)
│   └── dialogue_ui.tscn        dialogue panel (speaker/text/choices; E or click to advance)
├── scenes/game.tscn            the third-person shell — inherits into every published scene;
│                               carries the WorldDirector node
└── tests/test_game_layer.tscn  headless unit test (dialogue traversal + quest state machine)
```

`WorldDirector` spawns the HUD, dialogue panel, and objective marker **at runtime** by
`res://` path, so the only edit to `game.tscn` is the single `WorldDirector` node — and
because published scenes inherit `game.tscn` (see `scripts/07_publish_godot_scenes.py`),
every scene gets the game for free.

### The signal contract (`GameEvents`)

| Signal | Emitted by | Consumed by |
|---|---|---|
| `interact_prompt_changed(text)` | NPC proximity | HUD |
| `dialogue_started/line/choice_made/finished` | DialogueManager ↔ dialogue UI | UI / QuestManager |
| `quest_offered(id)` | dialogue effect `offer_quest` | QuestManager |
| `quest_state_changed(id, state)` | QuestManager | HUD |
| `objective_changed(id, text, world_pos)` | QuestManager | HUD + objective marker |
| `zone_reached(id)` | objective zone | QuestManager |

## `game.json` — authoring a scene's game

Optional, git-clean, lives at `godot/scenes/<name>/game.json`. Full reference:
[`godot/game/data/GAME_JSON_SCHEMA.md`](../godot/game/data/GAME_JSON_SCHEMA.md).
A worked example ships at `godot/scenes/phare/game.json` (the lighthouse slice: two
NPCs, a two-step "Light the Way" quest offered through a dialogue choice).

Placements use `anchor` — `"top_center"`, `{"xz_frac":[x,z]}` (fraction of the map
extent, dropped onto the terrain by raycast), or `{"world":[x,y,z]}` — so authored
content is **scale-agnostic** and survives re-generation of the mesh. An anchor that
points off the actual scan footprint (the mesh rarely fills its AABB) is walked toward
the map centre until terrain is found, so every placement stays reachable on foot.

Objective types: `reach_zone` (enter a zone) and `talk_to` (finish an NPC's dialogue).
Dialogue effects: `{"offer_quest": "<id>"}` (extend the vocabulary in
`DialogueManager._apply_effect`).

**Quest-state-aware dialogue:** an NPC's `dialogue` is its default tree; an optional
`dialogue_variants` list overrides it by quest state (`turn_in` / `active` /
`complete` / `inactive`, first match wins) — so the Keeper nags while the quest is
running, reacts when you report back, and gets an epilogue afterwards. The selection
runs in `npc_controller.gd` against the public QuestManager API; the phare
`game.json` and the procedural fallback both author the full arc.

## How to run

```bash
# Play the lighthouse slice (loads scenes/phare/game.json):
python scripts/04_prepare_godot.py res://scenes/phare/sf_phare.tscn
#   Controls: WASD move · mouse look · E talk · Shift sprint · F fly · R respawn · Esc cursor

# Any scene with no game.json falls back to a procedural NPC + objective.

# Headless unit test (dialogue traversal + quest state machine):
/Applications/Godot.app/Contents/MacOS/Godot --headless --path godot \
    res://tests/test_game_layer.tscn --quit-after 600   # exit 0 = all pass

# Headless INTEGRATION test — loads the real published phare scene and plays the whole
# loop through actual physics (anchor raycasts, proximity prompt, zone trigger), then
# does the same for the procedural fallback:
/Applications/Godot.app/Contents/MacOS/Godot --headless --path godot \
    res://tests/test_game_integration.tscn --quit-after 2000   # exit 0 = all pass
```

## Known limitations

- Variant selection is per-quest-state, not per-node: a tree can't branch on quest
  state *mid-conversation* (each state gets its own tree instead).
- No inventory/combat/save; single tracked quest in the HUD.
- `game.json` is hand-authored (a future pipeline stage could scaffold one).

See the design spec's "Deferred" items for the fuller roadmap.
