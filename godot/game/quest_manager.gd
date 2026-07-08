extends Node
## Quest state machine (autoload: QuestManager).
##
## The public API + storage below is the stable seam other modules call:
##   * WorldDirector calls  register_quests(cfg.quests)              once per scene.
##   * WorldDirector calls  set_target_position(id, world_pos)       per spawned zone/NPC,
##       so this manager can attach a world location to each objective it tracks.
##   * WorldDirector calls  register_target_dialogue(npc_id, tree)   per NPC, so a
##       "talk_to" objective can complete off dialogue_finished (which carries a tree id).
## It listens to GameEvents (quest_offered / zone_reached / dialogue_finished) and drives
## the HUD/marker purely through GameEvents (quest_state_changed / objective_changed).
##
## State machine: inactive -> active -> complete. A quest walks its QuestDef.objectives
## one at a time. Activating emits quest_state_changed("active") + objective_changed for
## objectives[0]. Advancing bumps the current index; completing the last objective emits
## quest_state_changed("complete") and a cleared objective_changed. _target_pos fills each
## objective_changed's world_pos (Vector3.INF when the target has no known position).

const STATE_INACTIVE := "inactive"
const STATE_ACTIVE := "active"
const STATE_COMPLETE := "complete"

## quest id -> QuestDef.
var _defs: Dictionary = {}
## quest id -> state String.
var _states: Dictionary = {}
## quest id -> current objective index (int).
var _progress: Dictionary = {}
## target id (zone/npc) -> world position, populated by WorldDirector.
var _target_pos: Dictionary = {}
## npc id -> Array of dialogue tree ids, populated by WorldDirector — lets a "talk_to"
## objective complete when ANY of that NPC's dialogues finishes (dialogue_finished
## carries only a tree_id, and a quest-state-aware NPC plays a different tree per state).
var _target_dialogue: Dictionary = {}


func _ready() -> void:
	GameEvents.quest_offered.connect(_on_quest_offered)
	GameEvents.zone_reached.connect(_on_zone_reached)
	GameEvents.dialogue_finished.connect(_on_dialogue_finished)


## Called by WorldDirector after parsing game.json.
func register_quests(quests: Array) -> void:
	for q in quests:
		if q is QuestDef and q.id != "":
			_defs[q.id] = q
			_states[q.id] = STATE_INACTIVE
			_progress[q.id] = 0
	# Defer initial auto_start activation: the HUD listener is spawned around the same
	# time and WorldDirector's set_target_position() calls may run after this — deferring
	# lets those land first so our objective_changed emits carry real world positions and
	# reach a live listener.
	_activate_auto_start_quests.call_deferred()


func _activate_auto_start_quests() -> void:
	for id in _defs:
		var d: QuestDef = _defs[id]
		if d.auto_start and _states.get(id, STATE_INACTIVE) == STATE_INACTIVE:
			_activate(id)


## Called by WorldDirector once a zone/NPC is placed, so objectives can point at it.
func set_target_position(target_id: String, world_pos: Vector3) -> void:
	_target_pos[target_id] = world_pos


## Called by WorldDirector per NPC dialogue tree (the default AND every quest-state
## variant), so a "talk_to" objective can complete off dialogue_finished (which carries
## only the tree id, not the NPC id). Additive: one NPC may own several trees.
func register_target_dialogue(npc_id: String, dialogue_id: String) -> void:
	if dialogue_id == "":
		return
	var trees: Array = _target_dialogue.get(npc_id, [])
	if not trees.has(dialogue_id):
		trees.append(dialogue_id)
	_target_dialogue[npc_id] = trees


func state_of(quest_id: String) -> String:
	return _states.get(quest_id, STATE_INACTIVE)


## Human-readable title for a quest id (for the HUD tracker). "" if unknown.
func title_of(quest_id: String) -> String:
	var d: QuestDef = _defs.get(quest_id, null)
	return d.title if d != null else ""


## The objective dict a quest is currently on, or {} if unknown/finished.
func current_objective(quest_id: String) -> Dictionary:
	var d: QuestDef = _defs.get(quest_id, null)
	if d == null:
		return {}
	return d.objective(_progress.get(quest_id, 0))


## True when a quest is active AND its current objective is talk_to `npc_id` — i.e.
## talking to that NPC right now turns the quest in. Drives NPC dialogue selection
## (an NpcSpawn "turn_in" variant) so the giver can react instead of replaying its intro.
func is_turn_in(quest_id: String, npc_id: String) -> bool:
	if npc_id == "" or _states.get(quest_id, STATE_INACTIVE) != STATE_ACTIVE:
		return false
	var obj := current_objective(quest_id)
	return obj.get("type", "") == "talk_to" and obj.get("npc", "") == npc_id


# --- state transitions --------------------------------------------------------

## Set a quest active, reset progress, and announce its first objective.
func _activate(quest_id: String) -> void:
	var d: QuestDef = _defs.get(quest_id, null)
	if d == null:
		return
	_states[quest_id] = STATE_ACTIVE
	_progress[quest_id] = 0
	GameEvents.quest_state_changed.emit(quest_id, STATE_ACTIVE)
	_announce_current_objective(quest_id)


## Emit objective_changed for the quest's current objective (or a cleared one if none).
func _announce_current_objective(quest_id: String) -> void:
	var obj := current_objective(quest_id)
	if obj.is_empty():
		GameEvents.objective_changed.emit(quest_id, "", Vector3.INF)
		return
	var text: String = obj.get("text", "")
	GameEvents.objective_changed.emit(quest_id, text, _world_pos_of(obj))


## Advance an active quest by one objective; complete it if none remain.
func _advance(quest_id: String) -> void:
	if _states.get(quest_id, STATE_INACTIVE) != STATE_ACTIVE:
		return
	var d: QuestDef = _defs.get(quest_id, null)
	if d == null:
		return
	var next_index: int = int(_progress.get(quest_id, 0)) + 1
	_progress[quest_id] = next_index
	if next_index < d.objectives.size():
		_announce_current_objective(quest_id)
	else:
		_states[quest_id] = STATE_COMPLETE
		GameEvents.quest_state_changed.emit(quest_id, STATE_COMPLETE)
		# Clear the tracker/marker: empty text + non-finite position.
		GameEvents.objective_changed.emit(quest_id, "", Vector3.INF)


## World position for an objective's target (zone/npc), or Vector3.INF if unknown.
func _world_pos_of(objective: Dictionary) -> Vector3:
	var target_id := ""
	match objective.get("type", ""):
		"reach_zone":
			target_id = objective.get("zone", "")
		"talk_to":
			target_id = objective.get("npc", "")
	return _target_pos.get(target_id, Vector3.INF)


# --- signal handlers ----------------------------------------------------------

func _on_quest_offered(quest_id: String) -> void:
	# Only inactive, known quests activate on offer; ignore re-offers of live/done quests.
	if _defs.has(quest_id) and _states.get(quest_id, STATE_INACTIVE) == STATE_INACTIVE:
		_activate(quest_id)


func _on_zone_reached(zone_id: String) -> void:
	for quest_id in _defs:
		if _states.get(quest_id, STATE_INACTIVE) != STATE_ACTIVE:
			continue
		var obj := current_objective(quest_id)
		if obj.get("type", "") == "reach_zone" and obj.get("zone", "") == zone_id:
			_advance(quest_id)


func _on_dialogue_finished(tree_id: String, _outcome: String) -> void:
	for quest_id in _defs:
		if _states.get(quest_id, STATE_INACTIVE) != STATE_ACTIVE:
			continue
		var obj := current_objective(quest_id)
		if obj.get("type", "") != "talk_to":
			continue
		var npc_id: String = obj.get("npc", "")
		# The objective names an npc; dialogue_finished carries a tree id. Match through
		# the npc -> trees map WorldDirector registered (any of the NPC's trees counts:
		# "talk to X" is satisfied by whichever state-variant conversation X gave).
		if npc_id != "" and (_target_dialogue.get(npc_id, []) as Array).has(tree_id):
			_advance(quest_id)
