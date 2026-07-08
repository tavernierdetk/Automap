extends CanvasLayer
## Display-only HUD overlay for the narrative/quest game layer.
##
## Instantiated at runtime (res://ui/hud.tscn) by another module; it is NOT added to
## any authored scene. Like every game-layer UI, it ONLY consumes the frozen GameEvents
## signal bus (plus the two read-only QuestManager getters) — it owns no game logic and
## never emits. The root Control ignores the mouse so clicks pass through to the world.
##
## Two elements:
##   • an interaction prompt (bottom-center) driven by `interact_prompt_changed`;
##   • a quest tracker (top-right) driven by `quest_state_changed` + `objective_changed`.

## How long the "✓ … — complete" flash stays up before the tracker hides.
const COMPLETE_FLASH_SECONDS := 2.0

## Active quests we're aware of, keyed by quest id → { "title": String, "objective": String }.
## Kept small; lets us fall back to another quest when the tracked one finishes.
var _active: Dictionary = {}
## The quest currently shown in the tracker (most-recently activated / updated).
var _tracked_id: String = ""
## Bumped on every state change so a pending complete-flash timer knows if it's stale.
var _flash_token: int = 0

@onready var _prompt_panel: PanelContainer = $Root/InteractPrompt
@onready var _prompt_label: Label = $Root/InteractPrompt/Margin/PromptLabel
@onready var _tracker_panel: PanelContainer = $Root/QuestTracker
@onready var _title_label: Label = $Root/QuestTracker/Margin/VBox/TitleLabel
@onready var _objective_label: Label = $Root/QuestTracker/Margin/VBox/ObjectiveLabel


func _ready() -> void:
	# Start clean; only signals reveal anything.
	_prompt_panel.hide()
	_tracker_panel.hide()

	GameEvents.interact_prompt_changed.connect(_on_interact_prompt_changed)
	GameEvents.quest_state_changed.connect(_on_quest_state_changed)
	GameEvents.objective_changed.connect(_on_objective_changed)


# --- Interaction prompt (bottom-center) ---------------------------------------------

func _on_interact_prompt_changed(text: String) -> void:
	if text == "":
		_prompt_panel.hide()
	else:
		_prompt_label.text = text
		_prompt_panel.show()


# --- Quest tracker (top-right) -------------------------------------------------------

func _on_quest_state_changed(quest_id: String, state: String) -> void:
	_flash_token += 1
	match state:
		"active":
			var title := QuestManager.title_of(quest_id)
			if title == "":
				title = quest_id
			# Preserve any objective we already know for this quest.
			var objective: String = ""
			if _active.has(quest_id):
				objective = _active[quest_id].get("objective", "")
			_active[quest_id] = { "title": title, "objective": objective }
			_tracked_id = quest_id
			_refresh_tracker()
		"complete":
			_flash_complete(quest_id, _flash_token)
		"inactive":
			_forget_quest(quest_id)
		_:
			# Unknown state — ignore rather than crash.
			pass


func _on_objective_changed(quest_id: String, text: String, _world_pos: Vector3) -> void:
	# We may hear about a quest's objective before (or without) an "active" state.
	if not _active.has(quest_id):
		var title := QuestManager.title_of(quest_id)
		if title == "":
			title = quest_id
		_active[quest_id] = { "title": title, "objective": "" }

	_active[quest_id]["objective"] = text
	# An objective update means this quest is the one worth showing.
	_tracked_id = quest_id
	_flash_token += 1  # cancel any stale complete-flash for a different quest
	_refresh_tracker()


# --- Internals -----------------------------------------------------------------------

## Show the currently tracked quest, or hide the tracker if nothing is active.
func _refresh_tracker() -> void:
	if _tracked_id == "" or not _active.has(_tracked_id):
		# Fall back to any remaining active quest, else hide.
		if _active.is_empty():
			_tracker_panel.hide()
			return
		_tracked_id = _active.keys()[0]

	var q: Dictionary = _active[_tracked_id]
	_title_label.text = q.get("title", _tracked_id)
	var objective: String = q.get("objective", "")
	if objective == "":
		_objective_label.text = ""
		_objective_label.hide()
	else:
		_objective_label.text = "• " + objective
		_objective_label.show()
	_tracker_panel.show()


## Drop a quest we no longer care about, then re-pick what to show.
func _forget_quest(quest_id: String) -> void:
	_active.erase(quest_id)
	if _tracked_id == quest_id:
		_tracked_id = ""
	_refresh_tracker()


## Briefly show a completion banner for `quest_id`, then hide the tracker if idle.
## `token` guards against a newer signal superseding this flash while we await.
func _flash_complete(quest_id: String, token: int) -> void:
	var title := QuestManager.title_of(quest_id)
	if title == "":
		title = _active.get(quest_id, {}).get("title", quest_id)

	_tracked_id = quest_id
	_title_label.text = "✓ " + title + " — complete"
	_objective_label.text = ""
	_objective_label.hide()
	_tracker_panel.show()

	await get_tree().create_timer(COMPLETE_FLASH_SECONDS).timeout

	# A newer state/objective change happened during the wait — let it own the tracker.
	if token != _flash_token:
		return

	_forget_quest(quest_id)
