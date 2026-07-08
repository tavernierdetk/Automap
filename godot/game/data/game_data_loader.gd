class_name GameDataLoader
extends RefCounted
## Parses a scene's game.json into a typed GameConfig (npcs / quests / zones / dialogue).
##
## Mirrors the pipeline's features.json data-layer pattern: a git-clean JSON file sitting
## beside a scene, tolerant of absence and malformation. Every failure mode returns null
## so WorldDirector can fall back to procedural population — parsing NEVER crashes the game.
##
## Usage:
##   var cfg := GameDataLoader.from_scene_dir("res://scenes/phare")   # or an OS dir path
##   if cfg == null: cfg = <procedural fallback>   # WorldDirector's job

const FILENAME := "game.json"


## Load the game.json next to a running scene. `scene_res_path` is any file inside the
## scene dir (e.g. the .tscn/.glb res:// path); we look for game.json in that directory.
## Returns null when the file is absent or unparseable.
static func from_scene_path(scene_res_path: String) -> GameConfig:
	if scene_res_path == "":
		return null
	var dir := scene_res_path.get_base_dir()
	return from_scene_dir(dir)


## Load <dir>/game.json. `dir` may be a res:// path or an absolute OS path.
static func from_scene_dir(dir: String) -> GameConfig:
	if dir == "":
		return null
	var path := dir.path_join(FILENAME)
	return from_file(path)


## Parse a specific game.json path. Returns null if missing/invalid.
static func from_file(path: String) -> GameConfig:
	if not FileAccess.file_exists(path):
		return null
	var text := FileAccess.get_file_as_string(path)
	if text == "":
		push_warning("[game] %s is empty" % path)
		return null
	var json := JSON.new()
	if json.parse(text) != OK:
		push_warning("[game] %s parse error line %d: %s" % [path, json.get_error_line(), json.get_error_message()])
		return null
	if typeof(json.data) != TYPE_DICTIONARY:
		push_warning("[game] %s is not a JSON object" % path)
		return null
	return parse(json.data)


## Build a GameConfig from an already-decoded dictionary. Unknown keys are ignored;
## missing keys use sane defaults. Never returns null (an empty dict → empty config).
static func parse(data: Dictionary) -> GameConfig:
	var cfg := GameConfig.new()
	cfg.spawn = data.get("spawn", {})

	for raw in _as_array(data.get("npcs", [])):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var n := NpcSpawn.new()
		n.id = raw.get("id", "")
		n.display_name = raw.get("name", raw.get("display_name", ""))
		n.profile_path = raw.get("profile", raw.get("profile_path", ""))
		n.dialogue_id = raw.get("dialogue", raw.get("dialogue_id", ""))
		for v in _as_array(raw.get("dialogue_variants", [])):
			if typeof(v) == TYPE_DICTIONARY and str(v.get("tree", "")) != "":
				n.dialogue_variants.append(v)
		n.anchor = raw.get("anchor", {})
		cfg.npcs.append(n)

	for raw in _as_array(data.get("quests", [])):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var q := QuestDef.new()
		q.id = raw.get("id", "")
		q.title = raw.get("title", "")
		q.objectives = _as_array(raw.get("objectives", []))
		q.auto_start = raw.get("auto_start", false)
		cfg.quests.append(q)

	for raw in _as_array(data.get("zones", [])):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var z := ZoneDef.new()
		z.id = raw.get("id", "")
		z.anchor = raw.get("anchor", {})
		z.radius = float(raw.get("radius", 8.0))
		cfg.zones.append(z)

	var dialogues: Dictionary = data.get("dialogue", data.get("dialogues", {}))
	if typeof(dialogues) == TYPE_DICTIONARY:
		for tree_id in dialogues:
			var tree := _parse_dialogue(String(tree_id), dialogues[tree_id])
			if tree != null:
				cfg.dialogues[String(tree_id)] = tree

	return cfg


## One dialogue tree: {"start": "...", "nodes": { id: {...} }} — or, as a shorthand,
## the bare nodes dict itself (start defaults to "start").
static func _parse_dialogue(tree_id: String, raw: Variant) -> DialogueTree:
	if typeof(raw) != TYPE_DICTIONARY:
		return null
	var tree := DialogueTree.new()
	tree.id = tree_id
	if raw.has("nodes"):
		tree.start_id = raw.get("start", "start")
		tree.nodes = raw.get("nodes", {})
	else:
		tree.start_id = raw.get("start", "start")
		tree.nodes = raw
	return tree


static func _as_array(v: Variant) -> Array:
	return v if typeof(v) == TYPE_ARRAY else []
