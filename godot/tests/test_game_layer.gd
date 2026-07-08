extends Node
## Headless smoke/unit test for the game layer's two logic cores: DialogueManager
## traversal and the QuestManager state machine. Drives the real autoloads through the
## GameEvents bus and asserts the emitted signals, then quits with the failure count as
## exit code (0 = all pass).
##
## Run:
##   /Applications/Godot.app/Contents/MacOS/Godot --headless --path godot \
##       res://tests/test_game_layer.tscn --quit-after 600
## (Runs as a SCENE, not `--script`, so the autoloads GameEvents/DialogueManager/
## QuestManager are present.)

var _fail := 0
var _lines: Array = []
var _finished: Array = []
var _offered: Array = []
var _qstate: Array = []
var _objectives: Array = []


func _ready() -> void:
	GameEvents.dialogue_line.connect(func(s, t, c): _lines.append({"speaker": s, "text": t, "choices": c}))
	GameEvents.dialogue_finished.connect(func(id, o): _finished.append([id, o]))
	GameEvents.quest_offered.connect(func(id): _offered.append(id))
	GameEvents.quest_state_changed.connect(func(id, st): _qstate.append([id, st]))
	GameEvents.objective_changed.connect(func(id, txt, _pos): _objectives.append([id, txt]))

	await _run()

	if _fail == 0:
		print("TEST game_layer: ALL PASS")
	else:
		printerr("TEST game_layer: %d FAILURE(S)" % _fail)
	get_tree().quit(_fail)


func _check(cond: bool, msg: String) -> void:
	if cond:
		print("  ok  | ", msg)
	else:
		_fail += 1
		printerr("  FAIL| ", msg)


func _run() -> void:
	_test_dialogue()
	await get_tree().process_frame
	_test_quest()
	await get_tree().process_frame


func _test_dialogue() -> void:
	print("[dialogue traversal]")
	var cfg := GameDataLoader.parse({
		"dialogue": {"t": {"start": "a", "nodes": {
			"a": {"speaker": "K", "text": "hi", "choices": [
				{"text": "yes", "goto": "b", "effects": [{"offer_quest": "q"}]},
				{"text": "no", "goto": "end", "outcome": "declined"}]},
			"b": {"speaker": "K", "text": "thanks", "next": "end", "outcome": "accepted"},
		}}},
	})
	DialogueManager.register_dialogues(cfg.dialogues)
	_lines.clear(); _finished.clear(); _offered.clear()

	DialogueManager.start("t")
	_check(_lines.size() == 1 and _lines[0].text == "hi" and _lines[0].choices.size() == 2,
		"start() shows node 'a' with 2 choices")
	_check(DialogueManager.is_active(), "manager active during a tree")

	DialogueManager.choose(0)
	_check(_offered.has("q"), "choose(0) fires effect offer_quest 'q'")
	_check(_lines.size() == 2 and _lines[1].text == "thanks", "choose(0) advances to node 'b'")

	DialogueManager.advance()
	_check(_finished.size() == 1 and _finished[0][0] == "t" and _finished[0][1] == "accepted",
		"advance() finishes tree with outcome 'accepted'")
	_check(not DialogueManager.is_active(), "manager idle after finish")


func _test_quest() -> void:
	print("[quest state machine]")
	var cfg := GameDataLoader.parse({
		"quests": [{"id": "q", "title": "Q", "objectives": [
			{"type": "reach_zone", "zone": "z", "text": "go to z"},
			{"type": "talk_to", "npc": "n", "text": "talk to n"}]}],
	})
	QuestManager.set_target_position("z", Vector3(1, 2, 3))
	QuestManager.set_target_position("n", Vector3(4, 5, 6))
	QuestManager.register_target_dialogue("n", "tn")
	QuestManager.register_quests(cfg.quests)
	await get_tree().process_frame
	_qstate.clear(); _objectives.clear()

	GameEvents.quest_offered.emit("q")
	_check(QuestManager.state_of("q") == "active", "offer activates the quest")
	_check(_objectives.size() >= 1 and _objectives[-1][1] == "go to z", "objective 0 announced")

	GameEvents.zone_reached.emit("z")
	_check(_objectives.size() >= 2 and _objectives[-1][1] == "talk to n",
		"reach_zone 'z' advances to objective 1")

	GameEvents.dialogue_finished.emit("tn", "")
	_check(QuestManager.state_of("q") == "complete",
		"talk_to 'n' (via registered tree 'tn') completes the quest")
	_check(_objectives.size() >= 3 and _objectives[-1][1] == "", "completion clears the objective")
