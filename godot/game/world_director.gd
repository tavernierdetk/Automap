extends Node
## Runtime world population — the module that ties the narrative/quest layer together.
##
## map_loader.gd (the scene ROOT, node "Main") loads the pipeline .glb at runtime and adds
## it as a child "Map" with trimesh collision. WorldDirector runs a beat later, resolves the
## scene's game.json into a GameConfig (or builds a procedural one so ANY scene is playable),
## and populates the world: it spawns the UI, resolves each NPC/zone/spawn anchor onto the
## terrain (map AABB + a downward raycast), instances the other modules' scenes, and hands
## the managers their data. It owns no dialogue/quest logic — it only wires data + placement
## and speaks through the documented DialogueManager / QuestManager calls and the GameEvents
## bus. Every module asset it instances is optional (guarded), so a missing sibling module
## degrades to a log line rather than a crash.

## res:// scenes populated at runtime (built by sibling modules; may not exist yet).
const HUD_SCENE := "res://ui/hud.tscn"
const DIALOGUE_UI_SCENE := "res://ui/dialogue_ui.tscn"
const OBJECTIVE_MARKER_SCENE := "res://game/objective_marker.tscn"
const NPC_SCENE := "res://game/npc/npc.tscn"
const OBJECTIVE_ZONE_SCENE := "res://game/objective_zone.tscn"

## Vertical padding (m) above/below the AABB for the ground raycast.
const RAYCAST_MARGIN := 5.0
## Small lift applied when repositioning the player from a spawn anchor.
const PLAYER_SPAWN_LIFT := 2.0

var _map: Node3D = null


func _ready() -> void:
	# map_loader adds "Map" in ITS OWN _ready; sibling _ready order isn't guaranteed, so
	# wait a couple of frames for the map (and its trimesh colliders) to exist.
	_map = await _await_map()
	if _map == null:
		push_warning("[world] no Map node found — world population skipped")
		return

	# Let physics register the map's freshly-added trimesh colliders before we raycast.
	await get_tree().physics_frame

	# 1) The map's world-space bounds drive all anchor placement. Computed BEFORE any
	#    spawning so the objective marker / NPCs can't inflate the box.
	var aabb := _world_aabb(_map)

	# 2) UI next — spawn HUD / dialogue panel / objective marker so they are listening
	#    on the GameEvents bus BEFORE QuestManager emits its initial objective/quest signals.
	_spawn_ui()

	# 3) Resolve the scene's game.json → GameConfig, or fall back to a procedural game.
	var source := ""
	var cfg: GameConfig = null
	var dir := _scene_dir()
	if dir != "":
		cfg = GameDataLoader.from_scene_dir(dir)
	if cfg != null and not cfg.is_empty():
		source = dir.path_join("game.json")
	else:
		cfg = _procedural_config()
		source = "procedural"

	# 4) Register data + spawn actors, in the order the managers expect.
	_populate(cfg, aabb)

	print("[world] %s — %d npc(s), %d zone(s), %d quest(s)" % [
		source, cfg.npcs.size(), cfg.zones.size(), cfg.quests.size(),
	])


## Wait (up to a few frames) for map_loader to add the "Map" child of our parent (Main).
func _await_map() -> Node3D:
	var root := get_parent()
	for _i in range(4):
		var m := root.get_node_or_null("Map") if root != null else null
		if m is Node3D:
			return m as Node3D
		await get_tree().process_frame
	var m2 := root.get_node_or_null("Map") if root != null else null
	return m2 as Node3D


# --- population --------------------------------------------------------------

func _populate(cfg: GameConfig, aabb: AABB) -> void:
	# Dialogues before anything can offer/talk.
	DialogueManager.register_dialogues(cfg.dialogues)

	# NPCs: register targets, then instance the figure under the map.
	for npc in cfg.npcs:
		if npc == null or npc.id == "":
			continue
		var pos := resolve_anchor(npc.anchor, aabb)
		QuestManager.set_target_position(npc.id, pos)
		# Register EVERY tree the NPC can play (default + state variants) so a talk_to
		# objective completes off whichever variant the quest state selects.
		QuestManager.register_target_dialogue(npc.id, npc.dialogue_id)
		for v in npc.dialogue_variants:
			if typeof(v) == TYPE_DICTIONARY:
				QuestManager.register_target_dialogue(npc.id, str(v.get("tree", "")))
		_spawn_npc(npc, pos)

	# Zones: register targets, then instance the trigger volume under the map.
	for zone in cfg.zones:
		if zone == null or zone.id == "":
			continue
		var zpos := resolve_anchor(zone.anchor, aabb)
		QuestManager.set_target_position(zone.id, zpos)
		_spawn_zone(zone, zpos)

	# Quests LAST — after every target position is set, so auto_start objectives carry a
	# real world_pos when QuestManager emits their first objective_changed.
	QuestManager.register_quests(cfg.quests)

	# Optional spawn override: move the player onto the resolved anchor.
	if typeof(cfg.spawn) == TYPE_DICTIONARY and cfg.spawn.has("anchor"):
		_move_player(resolve_anchor(cfg.spawn["anchor"], aabb))


func _spawn_ui() -> void:
	var hud := _instance(HUD_SCENE)
	if hud != null:
		add_child(hud)
	var dlg := _instance(DIALOGUE_UI_SCENE)
	if dlg != null:
		add_child(dlg)
	var marker := _instance(OBJECTIVE_MARKER_SCENE)
	if marker != null:
		_map.add_child(marker)


func _spawn_npc(npc: NpcSpawn, pos: Vector3) -> void:
	var node := _instance(NPC_SCENE)
	if node == null:
		return
	# Set identity before add_child so the NPC's _ready sees it (label, prompt).
	node.set("npc_id", npc.id)
	node.set("dialogue_id", npc.dialogue_id)
	node.set("dialogue_variants", npc.dialogue_variants)
	node.set("display_name", npc.label())
	_map.add_child(node)
	# Profile is optional — apply_profile(null) is a documented no-op.
	var profile: Resource = null
	if npc.profile_path != "" and ResourceLoader.exists(npc.profile_path):
		profile = load(npc.profile_path)
	if node.has_method("apply_profile"):
		node.call("apply_profile", profile)
	if node is Node3D:
		node.global_position = pos


func _spawn_zone(zone: ZoneDef, pos: Vector3) -> void:
	var node := _instance(OBJECTIVE_ZONE_SCENE)
	if node == null:
		return
	node.set("zone_id", zone.id)
	node.set("radius", zone.radius)
	_map.add_child(node)
	if node is Node3D:
		node.global_position = pos


func _move_player(pos: Vector3) -> void:
	for p in get_tree().get_nodes_in_group("player"):
		if p is Node3D:
			p.global_position = pos + Vector3(0.0, PLAYER_SPAWN_LIFT, 0.0)
			if p is CharacterBody3D:
				p.velocity = Vector3.ZERO


## Instance a res:// scene, guarding against a sibling module not being built yet.
func _instance(path: String) -> Node:
	if not ResourceLoader.exists(path):
		push_warning("[world] asset not available: %s" % path)
		return null
	var packed := load(path) as PackedScene
	if packed == null:
		push_warning("[world] failed to load %s" % path)
		return null
	return packed.instantiate()


# --- anchor resolution -------------------------------------------------------

## Resolve a game.json anchor to a world position on the terrain.
##   "top_center"            -> map centre, dropped to the ground
##   {"xz_frac": [fx, fz]}   -> fraction across X/Z extent, dropped to the ground
##   {"world":   [x, y, z]}  -> absolute coordinates (no raycast)
## Except for explicit "world", a downward raycast lands the point on the map collider.
## The scan's footprint rarely fills its axis-aligned AABB (rotated flights, ragged
## edges), so an anchor near a fraction extreme can sit over empty air; when the ray
## misses, the point is walked toward the map centre until terrain is found — a
## reachable spot near the authored one beats an exact spot the player can't reach.
func resolve_anchor(anchor: Variant, aabb: AABB) -> Vector3:
	var pos := aabb.position
	var size := aabb.size
	var cx := pos.x + size.x * 0.5
	var cz := pos.z + size.z * 0.5
	var x := cx
	var z := cz

	if typeof(anchor) == TYPE_DICTIONARY:
		if anchor.has("world"):
			var w = anchor["world"]
			if typeof(w) == TYPE_ARRAY and w.size() >= 3:
				return Vector3(float(w[0]), float(w[1]), float(w[2]))
		elif anchor.has("xz_frac"):
			var f = anchor["xz_frac"]
			if typeof(f) == TYPE_ARRAY and f.size() >= 2:
				x = pos.x + float(f[0]) * size.x
				z = pos.z + float(f[1]) * size.z
	# else: string "top_center" (or anything unrecognised) keeps the centre defaults.

	# Try the anchor point first, then progressively closer to the centre.
	const STEPS := 8
	for i in range(STEPS):
		var t := float(i) / float(STEPS - 1)
		var px := lerpf(x, cx, t)
		var pz := lerpf(z, cz, t)
		var y := _ground_y(px, pz, aabb)
		if not is_nan(y):
			if i > 0:
				push_warning("[world] anchor (%.1f, %.1f) is off the terrain — moved to (%.1f, %.1f)"
					% [x, z, px, pz])
			return Vector3(px, y, pz)
	# No terrain anywhere along the path (degenerate map): centre, AABB top.
	return Vector3(cx, pos.y + size.y, cz)


## Raycast straight down through the map collider to find the ground y at (x, z).
## Bodies in the "player" group are excluded — the player often stands exactly on an
## anchor (both default to the map centre) and must never become the "ground".
## Returns NAN when nothing is hit.
func _ground_y(x: float, z: float, aabb: AABB) -> float:
	if _map == null:
		return NAN
	var space := _map.get_world_3d().direct_space_state
	if space == null:
		return NAN
	var from := Vector3(x, aabb.position.y + aabb.size.y + RAYCAST_MARGIN, z)
	var to := Vector3(x, aabb.position.y - RAYCAST_MARGIN, z)
	var query := PhysicsRayQueryParameters3D.create(from, to)
	var excl: Array[RID] = []
	for p in get_tree().get_nodes_in_group("player"):
		if p is CollisionObject3D:
			excl.append((p as CollisionObject3D).get_rid())
	query.exclude = excl
	var hit := space.intersect_ray(query)
	if hit.has("position"):
		return (hit["position"] as Vector3).y
	return NAN


# --- scene / config resolution ----------------------------------------------

## The res:// directory of the running scene — prefer the root's assigned map_scene,
## then the loaded map's own scene_file_path. "" when neither is a res:// path.
func _scene_dir() -> String:
	var root := get_parent()
	if root != null:
		var ps = root.get("map_scene")
		if ps is PackedScene and (ps as PackedScene).resource_path != "":
			return (ps as PackedScene).resource_path.get_base_dir()
	if _map != null and _map.scene_file_path != "":
		return _map.scene_file_path.get_base_dir()
	return ""


## Combined world-space AABB of every MeshInstance3D under the map (mirrors map_loader).
func _world_aabb(node: Node, acc := AABB(), seeded := [false]) -> AABB:
	if node is MeshInstance3D and node.mesh != null:
		var box: AABB = node.global_transform * node.get_aabb()
		if not seeded[0]:
			acc = box
			seeded[0] = true
		else:
			acc = acc.merge(box)
	for child in node.get_children():
		acc = _world_aabb(child, acc, seeded)
	return acc


# --- procedural fallback -----------------------------------------------------

## A minimal, self-contained game built in code, so the loop works on ANY scene that
## ships no (or an empty/invalid) game.json: one guide NPC, one waypoint zone, and a
## two-step auto-starting "explore" quest wired to a tiny intro dialogue.
func _procedural_config() -> GameConfig:
	var cfg := GameConfig.new()

	var npc := NpcSpawn.new()
	npc.id = "guide"
	npc.display_name = "Guide"
	npc.dialogue_id = "intro"
	npc.dialogue_variants = [
		{"when": "turn_in", "quest": "explore", "tree": "guide_return"},
		{"when": "complete", "quest": "explore", "tree": "guide_done"},
	]
	npc.anchor = {"xz_frac": [0.5, 0.55]}
	cfg.npcs.append(npc)

	var zone := ZoneDef.new()
	zone.id = "waypoint"
	zone.anchor = {"xz_frac": [0.82, 0.2]}
	zone.radius = 8.0
	cfg.zones.append(zone)

	var quest := QuestDef.new()
	quest.id = "explore"
	quest.title = "Explore the site"
	quest.auto_start = true
	quest.objectives = [
		{"type": "reach_zone", "zone": "waypoint", "text": "Reach the waypoint"},
		{"type": "talk_to", "npc": "guide", "text": "Return to the guide"},
	]
	cfg.quests.append(quest)

	var intro := DialogueTree.new()
	intro.id = "intro"
	intro.start_id = "start"
	intro.nodes = {
		"start": {
			"speaker": "Guide",
			"text": "Welcome, traveller. This whole site is yours to wander.",
			"next": "hint",
		},
		"hint": {
			"speaker": "Guide",
			"text": "Make for the waypoint marker, then find your way back to me.",
			"next": "end",
			"outcome": "greeted",
		},
	}
	var back := DialogueTree.new()
	back.id = "guide_return"
	back.start_id = "start"
	back.nodes = {
		"start": {
			"speaker": "Guide",
			"text": "There and back again — you have the lay of the land now.",
			"next": "end",
			"outcome": "returned",
		},
	}

	var done := DialogueTree.new()
	done.id = "guide_done"
	done.start_id = "start"
	done.nodes = {
		"start": {
			"speaker": "Guide",
			"text": "Off you go, wanderer. The site is yours.",
			"next": "end",
		},
	}

	cfg.dialogues = {"intro": intro, "guide_return": back, "guide_done": done}

	return cfg
