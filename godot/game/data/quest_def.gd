class_name QuestDef
extends Resource
## Definition of one quest — the data QuestManager tracks state against.
##
## A quest is a short ordered list of objectives. QuestManager walks them one at a
## time; completing the last objective completes the quest. Runtime state
## (inactive/active/complete + current objective index) lives in QuestManager, NOT
## here — this is the immutable definition parsed from game.json.
##
## Objective shape (a plain Dictionary; see GAME_JSON_SCHEMA.md):
##   {"type": "reach_zone", "zone": "light", "text": "Reach the lighthouse"}
##   {"type": "talk_to",    "npc":  "keeper", "text": "Report back to the keeper"}
## `type` is one of "reach_zone" | "talk_to". `text` is the HUD/marker label.

@export var id: String = ""
@export var title: String = ""
## Ordered Array of objective Dictionaries (shapes above).
@export var objectives: Array = []
## If true, the quest starts active on load instead of waiting to be offered.
@export var auto_start: bool = false


## The objective dict at `index`, or an empty dict if out of range.
func objective(index: int) -> Dictionary:
	if index < 0 or index >= objectives.size():
		return {}
	return objectives[index]
