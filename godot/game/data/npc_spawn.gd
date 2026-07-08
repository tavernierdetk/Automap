class_name NpcSpawn
extends Resource
## Placement + identity for one NPC — consumed by WorldDirector to instance an NPC.
##
## An NPC is rendered by the existing character pipeline: WorldDirector instances
## godot/game/npc/npc.tscn (which wraps character.tscn), loads `profile_path` as its
## CharacterProfile, positions it at `anchor` on the terrain, and hands it `dialogue_id`
## so talking to it starts that DialogueTree.

@export var id: String = ""
## HUD/dialogue display name; falls back to `id` when empty.
@export var display_name: String = ""
## res:// path to a CharacterProfile .tres. Empty → npc.tscn's default profile.
@export var profile_path: String = ""
## Dialogue tree id (key into GameConfig.dialogues) this NPC opens when talked to.
@export var dialogue_id: String = ""
## Quest-state-aware overrides of `dialogue_id`, evaluated at interact time; first match
## wins, `dialogue_id` is the fallback. Each entry (from game.json `dialogue_variants`):
##   {"when": "turn_in"|"active"|"complete"|"inactive", "quest": "<id>", "tree": "<id>"}
## "turn_in" = the quest is active AND its current objective is talk_to THIS npc — list
## it before "active", which also holds during turn-in.
@export var dialogue_variants: Array = []
## Placement, resolved by WorldDirector against the map AABB + a ground raycast.
## One of:
##   {"xz_frac": [0.3, 0.4]}     # fraction across the map's X/Z extent (size-agnostic)
##   {"world":   [x, y, z]}      # absolute world coordinates
##   "top_center"                # string shortcut (map centre)
@export var anchor: Variant = {}


func label() -> String:
	return display_name if display_name != "" else id
