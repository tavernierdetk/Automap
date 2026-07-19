extends Node
## Headless INTEGRATION test for the game layer — the seams the unit test can't touch.
##
## Where test_game_layer.gd drives the manager autoloads with synthetic data, this test
## loads the REAL published lighthouse scene (scenes/phare/sf_phare.tscn -> game.tscn ->
## map_loader + WorldDirector) and verifies the in-world wiring end to end:
##   * game.json resolution + anchor raycast placement on the actual terrain collider
##   * NPC / zone / UI spawning
##   * the played loop through real physics triggers: walk up to the Keeper (proximity
##     prompt), accept the quest in dialogue, physically enter the cliff zone, return and
##     report back -> quest complete
##   * the procedural fallback: game.tscn with no game.json beside its map still yields
##     a playable NPC + quest, driven to completion the same way.
##
## Run:
##   /Applications/Godot.app/Contents/MacOS/Godot --headless --path godot \
##       res://tests/test_game_integration.tscn --quit-after 2000
## (exit 0 = all pass)

const PHARE_SCENE := "res://scenes/phare/sf_phare.tscn"
const GAME_SHELL := "res://scenes/game.tscn"

var _fail := 0

# GameEvents recordings.
var _prompts: Array = []
var _lines: Array = []
var _finished: Array = []
var _objectives: Array = []
var _zones_hit: Array = []


func _ready() -> void:
	GameEvents.interact_prompt_changed.connect(func(t): _prompts.append(t))
	GameEvents.dialogue_line.connect(func(s, t, c): _lines.append({"speaker": s, "text": t, "choices": c}))
	GameEvents.dialogue_finished.connect(func(id, o): _finished.append([id, o]))
	GameEvents.objective_changed.connect(func(id, txt, pos): _objectives.append({"id": id, "text": txt, "pos": pos}))
	GameEvents.zone_reached.connect(func(id): _zones_hit.append(id))

	await _test_phare_slice()
	await _test_lagrave_populate()
	await _test_procedural_fallback()

	if _fail == 0:
		print("TEST game_integration: ALL PASS")
	else:
		printerr("TEST game_integration: %d FAILURE(S)" % _fail)
	get_tree().quit(_fail)


func _check(cond: bool, msg: String) -> void:
	if cond:
		print("  ok  | ", msg)
	else:
		_fail += 1
		printerr("  FAIL| ", msg)


# --- the authored lighthouse slice on real terrain -----------------------------

func _test_phare_slice() -> void:
	print("[phare slice on real terrain]")
	var shell: Node = (load(PHARE_SCENE) as PackedScene).instantiate()
	add_child(shell)

	var npcs := await _await_npcs(shell, 2)
	_check(npcs.size() == 2, "game.json spawns 2 NPCs (got %d)" % npcs.size())
	if npcs.size() < 2:
		shell.queue_free()
		return

	var keeper: Node3D = null
	var fisher: Node3D = null
	for n in npcs:
		match str(n.get("display_name")):
			"The Keeper": keeper = n
			"Maren": fisher = n
	_check(keeper != null and fisher != null, "NPCs are The Keeper + Maren")

	var zones := _zones_under(shell.get_node("Map"))
	_check(zones.size() == 1 and str(zones[0].get("zone_id")) == "cliff_edge",
		"zone 'cliff_edge' spawned")
	var zone: Area3D = zones[0]

	var director := shell.get_node("WorldDirector")
	_check(director.get_child_count() >= 2, "HUD + dialogue UI spawned under WorldDirector")

	_check(QuestManager.state_of("light_the_way") == "inactive"
		and QuestManager.title_of("light_the_way") == "Light the Way",
		"quest 'light_the_way' registered, inactive")

	# Anchor placement: every actor must sit ON the terrain collider (raycast placement
	# worked), not at the AABB-top fallback or below the map.
	var player: CharacterBody3D = shell.get_node("Player")
	await get_tree().physics_frame
	print("      map AABB: ", _world_aabb(shell.get_node("Map")))
	print("      player spawn: %v" % player.global_position)
	for actor in [keeper, fisher, zone]:
		var label: String = str(actor.get("display_name")) if actor.get("display_name") else str(actor.get("zone_id"))
		var gap := _surface_gap(actor, [player, actor])  # NPCs carry their own body now
		print("      %s at %v (probe gap %.2f)" % [label, actor.global_position, gap])
		_check(gap < 1.0, "%s on terrain surface (gap %.2f m)" % [label, gap])
	_check(keeper.global_position.distance_to(fisher.global_position) > 1.0,
		"distinct anchors resolve to distinct world positions")

	# --- play the loop through real triggers ---
	# 1) Flavor NPC: talk to Maren, no quest side effects.
	_lines.clear(); _finished.clear()
	fisher.call("interact")
	_check(_lines.size() == 1 and _lines[0].speaker == "Maren", "Maren's flavor dialogue starts")
	DialogueManager.advance()
	_check(_finished.size() == 1 and _finished[0][0] == "fisher_flavor", "Maren's dialogue finishes")
	_check(QuestManager.state_of("light_the_way") == "inactive", "flavor talk offers no quest")

	# 2) Proximity prompt: physically move the player next to the Keeper. The player may
	#    already START inside the Keeper's area (both default to the map centre), so step
	#    well outside first — body_entered only fires on a fresh entry.
	_teleport(player, keeper.global_position + Vector3(50.0, 10.0, 50.0))
	await _physics_frames(4)
	_prompts.clear()
	_teleport(player, keeper.global_position + Vector3(1.0, 0.5, 0))
	await _physics_frames(4)
	_check(_prompts.any(func(p): return "The Keeper" in str(p)),
		"walking up to the Keeper raises the interaction prompt")

	# 3) Accept the quest through the dialogue choice.
	_lines.clear(); _finished.clear(); _objectives.clear()
	keeper.call("interact")
	_check(_lines.size() == 1 and _lines[0].choices.size() == 2, "Keeper intro shows 2 choices")
	DialogueManager.choose(0)  # "I'll go."  -> offer_quest light_the_way
	DialogueManager.advance()  # grateful -> end
	_check(QuestManager.state_of("light_the_way") == "active", "choice activates the quest")
	var obj := _last_objective_for("light_the_way")
	_check(obj.get("text", "") == "Check the cliff-edge beacon", "objective 0 announced")
	var opos: Vector3 = obj.get("pos", Vector3.INF)
	_check(opos.is_finite() and opos.distance_to(zone.global_position) < 0.5,
		"objective carries the zone's world position (marker target)")
	_check(_finished.size() == 1 and _finished[0][1] == "accepted",
		"dialogue finish (talk_to Keeper pending later) does NOT skip the zone objective"
		if QuestManager.state_of("light_the_way") == "active" else "quest survived dialogue end")

	# 3b) Quest-state-aware dialogue: talking again mid-quest plays the REMINDER, not the
	#     intro — and finishing it must not touch the reach_zone objective.
	_lines.clear(); _finished.clear()
	keeper.call("interact")
	_check(_lines.size() == 1 and "beacon still waits" in str(_lines[0].text)
		and (_lines[0].choices as Array).is_empty(),
		"mid-quest talk plays the reminder variant (no intro replay)")
	DialogueManager.advance()
	_check(_finished.size() == 1 and _finished[0][0] == "keeper_reminder",
		"reminder tree finishes")
	_check(QuestManager.state_of("light_the_way") == "active"
		and _last_objective_for("light_the_way").get("text", "") == "Check the cliff-edge beacon",
		"reminder does not advance or complete the quest")

	# 4) Physically walk into the cliff-edge zone.
	_objectives.clear()
	_teleport(player, zone.global_position + Vector3(0, 1.0, 0))
	await _physics_frames(4)
	_check(_zones_hit.has("cliff_edge"), "entering the zone fires zone_reached")
	_check(_last_objective_for("light_the_way").get("text", "") == "Report back to the Keeper",
		"objective advances to the report-back step")

	# 5) Return and report back: the TURN-IN variant plays and completes the quest.
	_teleport(player, keeper.global_position + Vector3(1.0, 0.5, 0))
	await _physics_frames(4)
	_lines.clear(); _objectives.clear()
	keeper.call("interact")
	_check(_lines.size() == 1 and "You saw it dark" in str(_lines[0].text),
		"turn-in variant plays on report-back")
	DialogueManager.advance()
	_check(QuestManager.state_of("light_the_way") == "complete",
		"reporting back completes 'Light the Way'")
	_check(_last_objective_for("light_the_way").get("text", "-") == "",
		"completion clears the HUD objective")

	# 6) Post-quest epilogues: both NPCs switch to their 'complete' variants.
	_lines.clear()
	keeper.call("interact")
	_check(_lines.size() == 1 and "light burns true" in str(_lines[0].text),
		"Keeper plays his post-quest epilogue")
	DialogueManager.advance()
	_lines.clear()
	fisher.call("interact")
	_check(_lines.size() == 1 and "Knew you had it in you" in str(_lines[0].text),
		"Maren reacts to the completed quest")
	DialogueManager.advance()

	shell.queue_free()
	await _physics_frames(2)


# --- the populated B-world: an ADMITTED character as NPC (lagrave) --------------
# The character-creator seam: godot/scenes/lagrave/game.json places Marguerite —
# a stage-10-admitted CharacterProfile — on the geodata-built scene, with a
# quest hung on her v2 `goal`. Asserts the profile on the spawned figure IS the
# admitted .tres, then plays her loop through the same real triggers as phare.

func _test_lagrave_populate() -> void:
	print("[lagrave populate (admitted character as NPC)]")
	var shell: Node = (load("res://scenes/lagrave/sf_lagrave.tscn") as PackedScene).instantiate()
	add_child(shell)

	var npcs := await _await_npcs(shell, 1)
	_check(npcs.size() == 1 and str(npcs[0].get("display_name")) == "Marguerite à Théodore",
		"game.json spawns Marguerite (got %d npc(s))" % npcs.size())
	if npcs.is_empty():
		shell.queue_free()
		return
	var marguerite: Node3D = npcs[0]

	# The figure wears the ADMITTED profile — the stage-10 projection, not a default.
	var figure: Node = marguerite.get_node("Character")
	var prof: Resource = figure.get("profile")
	_check(prof != null and prof.resource_path == "res://profiles/marguerite_a_theodore.tres",
		"NPC wears the admitted character's .tres")
	_check(prof != null and str(prof.get("hairstyle")) == "medium" and bool(prof.get("glasses")),
		"profile traits survive the projection (hairstyle/glasses)")

	var zones := _zones_under(shell.get_node("Map"))
	_check(zones.size() == 1 and str(zones[0].get("zone_id")) == "quay", "zone 'quay' spawned")
	var zone: Area3D = zones[0]
	_check(QuestManager.state_of("old_quay") == "inactive"
		and QuestManager.title_of("old_quay") == "Who moors at the old quay?",
		"quest 'old_quay' registered, inactive")

	var player: CharacterBody3D = shell.get_node("Player")
	await get_tree().physics_frame
	for actor in [marguerite, zone]:
		var gap := _surface_gap(actor, [player, actor])  # NPCs carry their own body now
		_check(gap < 1.0, "%s on terrain surface (gap %.2f m)"
			% [str(actor.get("display_name")) if actor.get("display_name") else "zone", gap])

	# Accept her quest: intro is two linear nodes, then the choice.
	_lines.clear(); _finished.clear()
	marguerite.call("interact")
	_check(_lines.size() == 1 and "wrong side of the jetty" in str(_lines[0].text),
		"intro opens in her voice (the dialogue_seed line)")
	DialogueManager.advance()  # -> who
	DialogueManager.advance()  # -> ask (choices)
	_check(_lines.size() == 3 and (_lines[2].choices as Array).size() == 2, "ask node shows 2 choices")
	DialogueManager.choose(0)  # "I'll go look." -> offer_quest old_quay
	DialogueManager.advance()  # thanks -> end
	_check(QuestManager.state_of("old_quay") == "active", "choice activates 'old_quay'")

	# Walk to the quay, then report back through the turn-in variant.
	_teleport(player, zone.global_position + Vector3(0, 1.0, 0))
	await _physics_frames(4)
	_check(_zones_hit.has("quay"), "entering the quay fires zone_reached")
	_check(_last_objective_for("old_quay").get("text", "") == "Tell Marguerite what you saw",
		"objective advances to the report-back step")

	_teleport(player, marguerite.global_position + Vector3(1.0, 0.5, 0))
	await _physics_frames(4)
	_lines.clear()
	marguerite.call("interact")
	_check(_lines.size() == 1 and "read it on your face" in str(_lines[0].text),
		"turn-in variant plays on report-back")
	DialogueManager.advance()  # -> read
	DialogueManager.advance()  # -> end (outcome reported)
	_check(QuestManager.state_of("old_quay") == "complete", "reporting back completes the quest")

	_lines.clear()
	marguerite.call("interact")
	_check(_lines.size() == 1 and "Ovila" in str(_lines[0].text), "post-quest epilogue plays")
	DialogueManager.advance()

	# --- minimap module: published map picked up, player tracked --------------
	var mm := shell.get_node_or_null("Minimap")
	_check(mm != null and mm.visible, "minimap is visible on a scene that ships one")
	if mm != null and mm.visible:
		_check(mm.get("_tex") != null, "minimap loaded the published texture")
		var uv: Vector2 = mm.call("_world_to_map", player.global_position.x, player.global_position.z)
		_check(uv.x > 0.0 and uv.y > 0.0
			and uv.x < float(mm.get("_meta").width) and uv.y < float(mm.get("_meta").height),
			"player maps inside the minimap bounds (%s)" % uv)

	# --- decoration convention: roads/weeds/water get NO colliders ------------
	# (the road-blocking fix: the terrain below carries the player, so a road
	# is walked through — there is nothing to jump onto or be stopped by)
	var deco_meshes: Array = []
	var deco_with_collider := 0
	_collect_deco(shell.get_node("Map"), deco_meshes)
	for m in deco_meshes:
		for ch in m.get_children():
			if ch is StaticBody3D:
				deco_with_collider += 1
	_check(deco_meshes.size() > 0, "deco_ meshes exist in the published scene (%d)" % deco_meshes.size())
	_check(deco_with_collider == 0, "no deco_ mesh carries a collider (%d did)" % deco_with_collider)

	var road: MeshInstance3D = null
	for m in deco_meshes:
		if str(m.name).begins_with("deco_road"):
			road = m
			break
	if road != null:
		# a ray dropped through the road must land on the TERRAIN below the
		# ribbon, proving the ribbon itself stops nothing
		var raabb: AABB = road.global_transform * road.get_aabb()
		var over := raabb.get_center() + Vector3(0, 20.0, 0)
		var hit := get_tree().root.world_3d.direct_space_state.intersect_ray(
			PhysicsRayQueryParameters3D.create(over, over + Vector3(0, -60, 0)))
		_check(hit.size() > 0 and hit.position.y < raabb.get_center().y - 0.02,
			"ray passes through the road and lands on terrain (no road collider)")

	shell.queue_free()
	await _physics_frames(2)


func _collect_deco(node: Node, out: Array) -> void:
	if node is MeshInstance3D and str(node.name).begins_with("deco_"):
		out.append(node)
	for child in node.get_children():
		_collect_deco(child, out)


# --- the procedural fallback on a game.json-less map ---------------------------

func _test_procedural_fallback() -> void:
	print("[procedural fallback (no game.json)]")
	var shell: Node = (load(GAME_SHELL) as PackedScene).instantiate()
	add_child(shell)  # no map_scene -> assets/scene.glb -> no res:// dir -> procedural

	var npcs := await _await_npcs(shell, 1)
	_check(npcs.size() == 1 and str(npcs[0].get("display_name")) == "Guide",
		"fallback spawns the Guide NPC")
	if npcs.is_empty():
		shell.queue_free()
		return
	var guide: Node3D = npcs[0]

	var zones := _zones_under(shell.get_node("Map"))
	_check(zones.size() == 1 and str(zones[0].get("zone_id")) == "waypoint",
		"fallback spawns the waypoint zone")

	# auto_start quest activates by itself (deferred), no dialogue needed.
	await _physics_frames(2)
	_check(QuestManager.state_of("explore") == "active", "'explore' auto-starts")

	var player: CharacterBody3D = shell.get_node("Player")
	_teleport(player, (zones[0] as Node3D).global_position + Vector3(0, 1.0, 0))
	await _physics_frames(4)
	_check(_zones_hit.has("waypoint"), "waypoint zone fires on entry")
	_check(_last_objective_for("explore").get("text", "") == "Return to the guide",
		"objective advances to the return step")

	_teleport(player, guide.global_position + Vector3(1.0, 0.5, 0))
	await _physics_frames(4)
	_lines.clear()
	guide.call("interact")
	_check(_lines.size() == 1 and "There and back" in str(_lines[0].text),
		"Guide plays the turn-in variant on return")
	DialogueManager.advance()
	_check(QuestManager.state_of("explore") == "complete",
		"talking to the Guide completes the fallback quest")
	_lines.clear()
	guide.call("interact")
	_check(_lines.size() == 1 and "site is yours" in str(_lines[0].text),
		"Guide switches to his post-quest line")
	DialogueManager.advance()

	shell.queue_free()
	await _physics_frames(2)


# --- helpers -------------------------------------------------------------------

## Wait until WorldDirector has populated the shell's Map with `want` NPCs (or time out).
func _await_npcs(shell: Node, want: int, timeout_frames := 240) -> Array:
	for _i in range(timeout_frames):
		var map := shell.get_node_or_null("Map")
		if map != null:
			var npcs := _npcs_under(map)
			if npcs.size() >= want:
				await get_tree().physics_frame
				return npcs
		await get_tree().process_frame
	var map2 := shell.get_node_or_null("Map")
	return _npcs_under(map2) if map2 != null else []


func _npcs_under(map: Node) -> Array:
	var out: Array = []
	for c in map.get_children():
		if c.has_method("interact") and c.get("dialogue_id") != null:
			out.append(c)
	return out


func _zones_under(map: Node) -> Array:
	var out: Array = []
	for c in map.get_children():
		if c is Area3D and c.get("zone_id") != null:
			out.append(c)
	return out


func _teleport(player: CharacterBody3D, pos: Vector3) -> void:
	player.global_position = pos
	player.velocity = Vector3.ZERO


func _physics_frames(n: int) -> void:
	for _i in range(n):
		await get_tree().physics_frame


## Vertical distance from a node to the terrain collider directly beneath/around it.
## The probe reaches 300 m down so a floating actor reports its real height above ground;
## INF only when there is NO collider under it at all (off the mesh / fell through).
func _surface_gap(n: Node3D, exclude: Array = []) -> float:
	var space := n.get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(
		n.global_position + Vector3(0, 2.0, 0), n.global_position - Vector3(0, 300.0, 0))
	var rids: Array[RID] = []
	for e in exclude:
		if e is CollisionObject3D:
			rids.append(e.get_rid())
	q.exclude = rids
	var hit := space.intersect_ray(q)
	if hit.has("position"):
		return absf((hit["position"] as Vector3).y - n.global_position.y)
	return INF


## Combined world-space AABB of every MeshInstance3D under a node (mirrors the engine's).
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


func _last_objective_for(quest_id: String) -> Dictionary:
	for i in range(_objectives.size() - 1, -1, -1):
		if _objectives[i]["id"] == quest_id:
			return _objectives[i]
	return {}
