extends Interactable
## A talkable NPC: a visible primitive figure (reused `character.tscn`) plus a proximity
## volume that offers a "Press E to talk" prompt and hands off to `DialogueManager`.
##
## WorldDirector instances `res://game/npc/npc.tscn`, sets `dialogue_id` / `display_name`,
## calls `apply_profile()` with an optional `CharacterProfile`, positions the node and
## adds it to the world. Everything else is self-contained. The NPC only ever emits
## *intent* on the `GameEvents` bus (a prompt request) and calls the documented
## `DialogueManager` API — it owns no dialogue or quest logic itself.

## Dialogue tree to play on interaction. Keys into the scene's `game.json` `dialogue{}`.
## Empty means this NPC has nothing to say (interaction becomes a no-op).
@export var dialogue_id: String = ""
## NpcSpawn id, set by WorldDirector — needed to ask QuestManager turn-in questions.
@export var npc_id: String = ""
## Quest-state-aware overrides of `dialogue_id` (see NpcSpawn.dialogue_variants).
## Evaluated top-down at interact time; first matching entry wins.
@export var dialogue_variants: Array = []
## Human-readable name used in the interaction prompt and the floating label.
@export var display_name: String = ""

## How fast the body swivels to face the player while in range (rad/s-ish factor).
@export var turn_speed := 8.0

var _player: Node3D = null      # the player node while it is inside the volume
var _character: Node3D = null   # the inner character.tscn instance (may hold `profile`)

@onready var _area: Area3D = $InteractionArea
@onready var _label: Label3D = $NameLabel


func _ready() -> void:
	_character = get_node_or_null("Character")
	_refresh_label()

	_area.body_entered.connect(_on_body_entered)
	_area.body_exited.connect(_on_body_exited)


## Assign a CharacterProfile to the inner character figure and make it take effect.
## `p == null` leaves the character's own default profile untouched. Safe to call before
## or after the NPC enters the tree: if the character node is already live we re-run its
## profile application, otherwise setting `profile` lets its own `_ready` pick it up.
func apply_profile(p: CharacterProfile) -> void:
	if p == null:
		return
	if _character == null:
		_character = get_node_or_null("Character")
	if _character == null:
		return
	_character.set("profile", p)
	# character.gd applies the profile in _ready via _apply_profile(); if it has already
	# run (node live in tree) re-apply now so the new profile is reflected immediately.
	if _character.is_inside_tree() and _character.has_method("_apply_profile"):
		_character.call("_apply_profile")


## Interactable seam: talking to this NPC starts its dialogue tree.
func interact() -> void:
	_start_dialogue()


func prompt_text() -> String:
	return "Press E to talk to %s" % _name()


func _process(delta: float) -> void:
	# Face the player on the Y axis while they are in range (purely cosmetic).
	if _player == null or _character == null:
		return
	var to := _player.global_position - _character.global_position
	to.y = 0.0
	if to.length_squared() < 0.0001:
		return
	var target := atan2(to.x, to.z)  # character figure faces +Z of its own basis
	_character.rotation.y = lerp_angle(_character.rotation.y, target, turn_speed * delta)


func _unhandled_input(event: InputEvent) -> void:
	# Physical-key idiom (matches player_tps.gd): one clean press = one dialogue start.
	if _player == null:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_E:
			_start_dialogue()


func _start_dialogue() -> void:
	var tree := _dialogue_for_state()
	if tree.is_empty():
		return
	if DialogueManager.is_active():
		return
	DialogueManager.start(tree)


## The dialogue tree this NPC should play RIGHT NOW: the first `dialogue_variants` entry
## whose quest condition holds, else the default `dialogue_id`. Conditions:
##   "turn_in"  — quest active and its current objective is talk_to this npc
##   "active" / "complete" / "inactive" — plain quest state
## ("active" also holds during turn-in; authors list "turn_in" first — first match wins.)
func _dialogue_for_state() -> String:
	for v in dialogue_variants:
		if typeof(v) != TYPE_DICTIONARY:
			continue
		var quest := str(v.get("quest", ""))
		var tree := str(v.get("tree", ""))
		if quest == "" or tree == "":
			continue
		var matched := false
		match str(v.get("when", "active")):
			"turn_in":
				matched = QuestManager.is_turn_in(quest, npc_id)
			"active":
				matched = QuestManager.state_of(quest) == "active"
			"complete":
				matched = QuestManager.state_of(quest) == "complete"
			"inactive":
				matched = QuestManager.state_of(quest) == "inactive"
			_:
				push_warning("[npc] %s: unknown dialogue_variants when '%s'" % [_name(), v.get("when")])
		if matched:
			return tree
	return dialogue_id


func _on_body_entered(body: Node3D) -> void:
	if not body.is_in_group("player"):
		return
	_player = body
	GameEvents.interact_prompt_changed.emit(prompt_text())


func _on_body_exited(body: Node3D) -> void:
	if body != _player:
		return
	_player = null
	GameEvents.interact_prompt_changed.emit("")


func _name() -> String:
	return display_name if not display_name.is_empty() else "the stranger"


func _refresh_label() -> void:
	if _label != null:
		_label.text = _name()
		_label.visible = not display_name.is_empty()
