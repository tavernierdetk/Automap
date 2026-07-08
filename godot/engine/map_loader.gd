extends Node3D
## Walking-engine map loader — the seam between the pipeline and playback.
##
## The engine is a standalone component: it loads ANY pipeline-generated .glb at
## runtime by path and never touches scene generation (stages 0-3). Scene files
## (main.tscn / game.tscn) carry no baked mesh; they just host this loader + a player.
##
## The map is resolved in order:
##   1. launch arg   Godot --path godot -- --scene <path>
##   2. env var      AUTOMAP_SCENE=<path>
##   3. map_scene    an in-scene PackedScene set in the editor (see below)
##   4. res://assets/scene.glb   (opt-in fallback, gitignored)
##   5. procedural flat ground   (so the engine always launches, binary-free)
##
## <path> may be an absolute OS path (e.g. work/mesh/scene.glb) or a res:// path.
## map_scene lets a *published* scene play straight from the editor's Play button
## (which passes no launch arg): stage 7 writes each scene as an inherited game.tscn
## with map_scene assigned to its glb. A CLI --scene / AUTOMAP_SCENE still overrides.

const FALLBACK_RES := "res://assets/scene.glb"

@export var map_scene: PackedScene


func _ready() -> void:
	var path := _resolve_scene_path()
	var map: Node3D = null
	var source := ""
	if path != "":
		map = _load_map(path)
		source = path
	elif map_scene != null:
		map = map_scene.instantiate() as Node3D
		source = map_scene.resource_path
	elif ResourceLoader.exists(FALLBACK_RES) or FileAccess.file_exists(FALLBACK_RES):
		map = _load_map(FALLBACK_RES)
		source = FALLBACK_RES

	if map != null:
		map.name = "Map"
		add_child(map)
		var count := _add_trimesh_collision(map)
		print("[engine] loaded %s (%d mesh collider(s))" % [source, count])
		_place_player(map)
	else:
		_build_procedural_ground()
		print("[engine] no scene found — procedural ground")


func _resolve_scene_path() -> String:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--scene="):
			return arg.trim_prefix("--scene=")
	var args := OS.get_cmdline_user_args()
	var i := args.find("--scene")
	if i != -1 and i + 1 < args.size():
		return args[i + 1]

	var env := OS.get_environment("AUTOMAP_SCENE")
	if env != "":
		return env

	return ""


## Loads a map at runtime. Accepts two shapes so generation stays decoupled:
##   * a PackedScene (.tscn/.scn) — the pipeline's published hand-off, referencing
##     an imported glb by res:// (see scripts/07_publish_godot_scenes.py); and
##   * a raw glb/gltf by res:// or external OS path (work/<name>/mesh/…), parsed
##     on the fly with GLTFDocument.
func _load_map(path: String) -> Node3D:
	if path == "":
		return null
	if not (path.begins_with("res://") or FileAccess.file_exists(path)):
		push_warning("[engine] scene not found: %s" % path)
		return null

	var lower := path.to_lower()
	if lower.ends_with(".tscn") or lower.ends_with(".scn"):
		var packed := ResourceLoader.load(path) as PackedScene
		if packed == null:
			push_warning("[engine] failed to load scene %s" % path)
			return null
		var inst := packed.instantiate() as Node3D
		# A published scene is itself a runnable shell (inherited game.tscn whose root
		# runs THIS script). Nesting one as a map would make its own loader re-resolve
		# the same --scene launch arg and recurse forever — refuse instead.
		if inst != null and inst.get_script() == get_script():
			push_warning("[engine] %s is a runnable shell scene — launch it directly (positional arg / editor Play), not via --scene=" % path)
			inst.free()
			return null
		return inst

	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		push_warning("[engine] failed to parse %s (err %d)" % [path, err])
		return null
	return doc.generate_scene(state)


## Moved verbatim from the former world.gd: static trimesh collision for every mesh
## so the player can walk on the terrain.
func _add_trimesh_collision(node: Node) -> int:
	if node == null:
		return 0
	var n := 0
	if node is MeshInstance3D and node.mesh != null:
		node.create_trimesh_collision()  # adds a StaticBody3D + ConcavePolygonShape3D
		n += 1
	for child in node.get_children():
		n += _add_trimesh_collision(child)
	return n


## Drop the player at the centre of the scene, standing on the surface. We raycast
## straight down through the middle of the map footprint to find the ground height
## there, so the start point is sensible on any scale of scene (not hovering high
## above a peak, nor dropped into a valley off-centre). Falls back to hovering just
## above the centre — physics settles it — if the ray misses (e.g. a hole at the
## exact centre). The player node opts in via the "player" group.
func _place_player(map: Node3D) -> void:
	var players := get_tree().get_nodes_in_group("player")
	if players.is_empty():
		return
	var aabb := _world_aabb(map)
	if aabb.size == Vector3.ZERO:
		return
	var cx := aabb.position.x + aabb.size.x * 0.5
	var cz := aabb.position.z + aabb.size.z * 0.5
	var top := aabb.position.y + aabb.size.y

	# Trimesh colliders only become queryable after a physics step has run.
	await get_tree().physics_frame
	var spawn := Vector3(cx, top + 5.0, cz)
	var hit := get_world_3d().direct_space_state.intersect_ray(
		PhysicsRayQueryParameters3D.create(
			Vector3(cx, top + 10.0, cz), Vector3(cx, aabb.position.y - 10.0, cz)))
	if hit:
		spawn = hit.position + Vector3(0.0, 1.5, 0.0)  # stand just above the surface

	for p in players:
		if p is Node3D:
			p.global_position = spawn
			if p is CharacterBody3D:
				p.velocity = Vector3.ZERO
	print("[engine] player spawn %v (%s)" % [spawn, "on surface" if hit else "above centre"])


## Combined world-space AABB of every MeshInstance3D under the map.
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


func _build_procedural_ground() -> void:
	var ground := StaticBody3D.new()
	ground.name = "Map"
	var mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(200, 200)
	mesh.mesh = plane
	ground.add_child(mesh)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(200, 0.1, 200)
	shape.shape = box
	ground.add_child(shape)
	add_child(ground)
