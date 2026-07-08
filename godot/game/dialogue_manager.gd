extends Node
## Dialogue playback state machine (autoload: DialogueManager).
##
## The public API + storage below is the stable seam other modules call:
##   * WorldDirector calls  register_dialogues(cfg.dialogues)  once per scene.
##   * NpcController calls   start(npc.dialogue_id)             on interaction.
##   * dialogue_ui.gd calls  advance() / choose(index)          from the panel.
## It drives the UI purely through GameEvents (dialogue_started / dialogue_line /
## dialogue_finished). No module imports this directly except by the calls above.
##
## Traversal: start() shows the tree's start node; a shown node applies its `effects`
## and emits dialogue_line(speaker, text, choices). A linear node (no choices) walks its
## `next` on advance(); a branch node walks the picked choice's `goto` on choose(index),
## applying that choice's effects first. Reaching a terminal transition ("", "end", or an
## id missing from the graph — see DialogueTree.is_end) finishes the tree, surfacing the
## terminating node's or chosen choice's `outcome` (default "") on dialogue_finished.
##
## EFFECT vocabulary (a node's/choice's `effects` is an Array of one-key dicts, applied in
## order when the node/choice is taken):
##   * {"offer_quest": "<quest_id>"} -> GameEvents.quest_offered.emit(quest_id)
## Unknown effect keys are ignored with a warning. Add new effects in _apply_effect().

## tree id -> DialogueTree, registered per scene.
var _trees: Dictionary = {}
## The tree currently playing, or null when idle.
var _active: DialogueTree = null
## Id the active tree was started under (register_dialogues key), for dialogue_finished.
var _active_id: String = ""
## Node id currently on screen while a tree plays.
var _current_node_id: String = ""


func is_active() -> bool:
	return _active != null


## Called by WorldDirector after parsing game.json. `dialogues` is {id: DialogueTree}.
func register_dialogues(dialogues: Dictionary) -> void:
	_trees = dialogues.duplicate()


func has_dialogue(tree_id: String) -> bool:
	return _trees.has(tree_id)


## Begin playing a registered dialogue tree by id. No-op if unknown or already active.
func start(tree_id: String) -> void:
	if _active != null:
		return
	if not _trees.has(tree_id):
		push_warning("[dialogue] unknown tree '%s'" % tree_id)
		return
	_active = _trees[tree_id]
	_active_id = tree_id
	_current_node_id = ""
	GameEvents.dialogue_started.emit(tree_id)
	# A tree whose start id is already terminal finishes immediately (malformed-safe).
	if _active.is_end(_active.start_id):
		_finish("")
		return
	_show_node(_active.start_id)


## Advance a linear line (no choices) by following the node's `next`. No-op when idle or
## when the current node has choices (use choose() there instead).
func advance() -> void:
	if _active == null:
		return
	var node := _active.node(_current_node_id)
	if not _node_choices(node).is_empty():
		return  # branch node — the UI should call choose(), not advance()
	var next_id := str(node.get("next", ""))
	if _active.is_end(next_id):
		_finish(str(node.get("outcome", "")))
	else:
		_show_node(next_id)


## Pick choice `index` on the current branch node. No-op when idle or index is invalid.
func choose(index: int) -> void:
	if _active == null:
		return
	var node := _active.node(_current_node_id)
	var choices := _node_choices(node)
	if index < 0 or index >= choices.size():
		return
	var choice: Dictionary = choices[index]
	GameEvents.dialogue_choice_made.emit(index)
	_apply_effects(choice.get("effects", []))
	var goto_id := str(choice.get("goto", ""))
	if _active.is_end(goto_id):
		_finish(str(choice.get("outcome", "")))
	else:
		_show_node(goto_id)


# --- traversal internals ------------------------------------------------------

## Display `node_id`: apply its effects, then emit dialogue_line with its choice texts.
func _show_node(node_id: String) -> void:
	_current_node_id = node_id
	var node := _active.node(node_id)
	_apply_effects(node.get("effects", []))
	GameEvents.dialogue_line.emit(
		str(node.get("speaker", "")), str(node.get("text", "")), _choice_texts(node)
	)


## Finish the active tree, surfacing `outcome`, and reset to idle.
func _finish(outcome: String) -> void:
	var tree_id := _active_id
	_active = null
	_active_id = ""
	_current_node_id = ""
	GameEvents.dialogue_finished.emit(tree_id, outcome)


## The raw choices Array of a node (empty when absent or malformed).
func _node_choices(node: Dictionary) -> Array:
	var choices: Variant = node.get("choices", [])
	if choices is Array:
		return choices
	return []


## The UI-facing choices: an Array of {"text": String} dicts, one per valid choice.
func _choice_texts(node: Dictionary) -> Array:
	var out: Array = []
	for choice in _node_choices(node):
		if choice is Dictionary:
			out.append({"text": str(choice.get("text", ""))})
	return out


## Apply an `effects` list (Array of one-key dicts). Robust to malformed entries.
func _apply_effects(effects: Variant) -> void:
	if not (effects is Array):
		return
	for effect in effects:
		if not (effect is Dictionary):
			continue
		for key in effect.keys():
			_apply_effect(str(key), effect[key])


## Interpret a single effect. Extend the match to grow the vocabulary.
func _apply_effect(key: String, value: Variant) -> void:
	match key:
		"offer_quest":
			GameEvents.quest_offered.emit(str(value))
		_:
			push_warning("[dialogue] unknown effect '%s' — ignored" % key)
