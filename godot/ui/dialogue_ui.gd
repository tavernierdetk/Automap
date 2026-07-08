extends CanvasLayer
## Bottom-anchored dialogue panel — the only view onto DialogueManager's playback.
##
## Self-contained scene (res://ui/dialogue_ui.tscn), instantiated at runtime by another
## module; it is NOT added to any existing scene by hand. It self-registers on the
## GameEvents bus in _ready() and consumes only these signals:
##   * dialogue_started  -> show the panel, free the mouse cursor for clicking choices
##   * dialogue_line      -> render speaker + text; build a Button per choice, or show a
##                           "continue" affordance for a linear line
##   * dialogue_finished  -> hide the panel, restore the captured mouse cursor
##
## It never touches DialogueManager's state directly beyond the documented calls
## advance() / choose(index). A separate integrator freezes the player controller while
## DialogueManager.is_active(); this panel only owns its own input consumption so
## E-to-advance doesn't leak through to the world.

const CONTINUE_HINT := "▸ continue (E)"

## True while the panel is on screen (a tree is playing).
var _shown := false
## True when the current line offers choices (advance() is suppressed then).
var _has_choices := false

@onready var _panel: PanelContainer = $Panel
@onready var _speaker: Label = $Panel/Margin/VBox/Speaker
@onready var _text: Label = $Panel/Margin/VBox/Text
@onready var _choices: VBoxContainer = $Panel/Margin/VBox/Choices
@onready var _continue: Label = $Panel/Margin/VBox/Continue


func _ready() -> void:
	_panel.visible = false
	_continue.text = CONTINUE_HINT
	GameEvents.dialogue_started.connect(_on_dialogue_started)
	GameEvents.dialogue_line.connect(_on_dialogue_line)
	GameEvents.dialogue_finished.connect(_on_dialogue_finished)


func _on_dialogue_started(_tree_id: String) -> void:
	_shown = true
	_panel.visible = true
	# Free the cursor so the player can click choice buttons.
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _on_dialogue_line(speaker: String, text: String, choices: Array) -> void:
	_speaker.text = speaker
	_speaker.visible = speaker != ""
	_text.text = text
	_rebuild_choices(choices)


func _on_dialogue_finished(_tree_id: String, _outcome: String) -> void:
	_shown = false
	_has_choices = false
	_panel.visible = false
	_clear_choices()
	# Hand control back to the third-person controller (its default cursor mode).
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


## Replace the choice buttons for the current line, or show the continue hint if linear.
func _rebuild_choices(choices: Array) -> void:
	_clear_choices()
	_has_choices = not choices.is_empty()
	_choices.visible = _has_choices
	_continue.visible = not _has_choices
	if not _has_choices:
		return
	for i in choices.size():
		var choice: Dictionary = choices[i] if choices[i] is Dictionary else {}
		var button := Button.new()
		button.text = str(choice.get("text", ""))
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.focus_mode = Control.FOCUS_ALL
		# Bind the index so every button routes to the right choice.
		button.pressed.connect(_on_choice_pressed.bind(i))
		_choices.add_child(button)
	# Focus the first choice so keyboard/controller users can pick without a mouse.
	if _choices.get_child_count() > 0:
		(_choices.get_child(0) as Button).grab_focus()


func _clear_choices() -> void:
	for child in _choices.get_children():
		child.queue_free()


func _on_choice_pressed(index: int) -> void:
	DialogueManager.choose(index)


func _unhandled_input(event: InputEvent) -> void:
	if not _shown:
		return
	# E (physical) or a left-click on empty panel space advances a linear line. When the
	# line has choices, the Buttons handle input; we still swallow E so it can't leak.
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_E:
			if not _has_choices:
				DialogueManager.advance()
			get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		if not _has_choices:
			DialogueManager.advance()
			get_viewport().set_input_as_handled()
