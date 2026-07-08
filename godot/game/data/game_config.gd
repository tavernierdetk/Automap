class_name GameConfig
extends Resource
## The parsed contents of a scene's game.json — the per-scene game override.
##
## Produced by GameDataLoader from a game.json sitting beside a published scene
## (godot/scenes/<name>/game.json), exactly like features.json sits beside geometry.
## WorldDirector consumes it to populate a scene; when no game.json exists, WorldDirector
## builds a minimal procedural GameConfig instead so the loop always works.
##
## This object is pure data — it holds NO runtime state and does NO placement. Anchor
## resolution (fraction/world → Vector3 on the terrain) belongs to WorldDirector, which
## has the map AABB and can raycast to the ground.

## Player spawn override, e.g. {"anchor": "top_center"} or {"anchor": {"xz_frac": [..]}}.
## Empty → map_loader's default top-of-mesh placement is kept.
@export var spawn: Dictionary = {}
@export var npcs: Array[NpcSpawn] = []
@export var quests: Array[QuestDef] = []
@export var zones: Array[ZoneDef] = []
## dialogue tree id (String) -> DialogueTree.
@export var dialogues: Dictionary = {}


func dialogue(tree_id: String) -> DialogueTree:
	return dialogues.get(tree_id, null)


## True when this config carries no authored content (WorldDirector then falls back).
func is_empty() -> bool:
	return npcs.is_empty() and quests.is_empty() and zones.is_empty()
