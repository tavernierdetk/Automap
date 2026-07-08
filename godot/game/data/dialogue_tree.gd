class_name DialogueTree
extends Resource
## A parsed dialogue graph — the data DialogueManager plays back.
##
## A tree is a set of NODES keyed by id. Playback starts at `start_id` and follows
## each node's `next` (linear) or a chosen choice's `goto` (branch) until it reaches
## a node whose transition is "" or "end".
##
## Node shape (a plain Dictionary; see godot/game/data/GAME_JSON_SCHEMA.md):
##   {
##     "speaker": "Keeper",              # who is talking (HUD label)
##     "text": "Storm's coming in.",     # the line
##     "choices": [                       # optional; omit/empty for a linear line
##       {"text": "Can I help?", "goto": "task", "effects": [ ... ]},
##       {"text": "Not now.",    "goto": "end",  "outcome": "declined"}
##     ],
##     "next": "node_id",                 # linear successor when there are no choices
##     "effects": [ {"offer_quest": "reach_light"} ],  # applied when the node is shown
##     "outcome": "accepted"              # optional tag surfaced on dialogue_finished
##   }
##
## `effects` is a list of one-key dicts the DialogueManager interprets, e.g.
## {"offer_quest": "<id>"}. The full effect vocabulary lives with DialogueManager.

@export var id: String = ""
## Node id playback begins at. Defaults to "start" if unset.
@export var start_id: String = "start"
## id (String) -> node (Dictionary), shapes as documented above.
@export var nodes: Dictionary = {}


## The node dict for `node_id`, or an empty dict if it doesn't exist.
func node(node_id: String) -> Dictionary:
	return nodes.get(node_id, {})


## The starting node dict (empty if the tree is malformed).
func start() -> Dictionary:
	return node(start_id)


## True when `node_id` is a terminator ("", "end", or missing from the graph).
func is_end(node_id: String) -> bool:
	return node_id == "" or node_id == "end" or not nodes.has(node_id)
