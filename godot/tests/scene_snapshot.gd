extends Node3D
## Render snapshots of a scene glb — NOT part of the headless suite (needs a
## window). Used to eyeball styling changes (e.g. before/after an identity
## edit) without launching the full game shell.
##
##   GLB=/abs/path/to/scene.glb LABEL=after \
##     /Applications/Godot.app/Contents/MacOS/Godot --path godot res://tests/scene_snapshot.tscn
##
## Writes work/scene_snapshots/<LABEL>_aerial.png and _street.png.

@onready var _cam: Camera3D = $Camera3D


func _ready() -> void:
	var glb := OS.get_environment("GLB")
	var label := OS.get_environment("LABEL")
	if label.is_empty():
		label = "snapshot"
	if glb.is_empty():
		push_error("[snapshot] set GLB=/abs/path/to.glb")
		get_tree().quit(1)
		return

	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(glb, state) != OK:
		push_error("[snapshot] could not read " + glb)
		get_tree().quit(1)
		return
	var map: Node3D = doc.generate_scene(state)
	add_child(map)

	var aabb := _world_aabb(map)
	var c := aabb.get_center()
	await get_tree().process_frame

	var out := ProjectSettings.globalize_path("res://").path_join("../work/scene_snapshots")
	DirAccess.make_dir_recursive_absolute(out)
	# aerial 3/4: high and off-corner, looking at the centre
	await _shoot(out.path_join(label + "_aerial.png"),
		c + Vector3(aabb.size.x * 0.28, maxf(aabb.size.y * 6.0, 120.0), aabb.size.z * 0.34), c)
	# street level: near the centre, low, looking across
	await _shoot(out.path_join(label + "_street.png"),
		c + Vector3(-40, 3.0, 25), c + Vector3(60, 2.0, -45))
	print("[snapshot] wrote ", label, "_aerial/_street to ", out)
	get_tree().quit(0)


func _shoot(path: String, cam_pos: Vector3, target: Vector3) -> void:
	_cam.position = cam_pos
	_cam.look_at(target)
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)


func _world_aabb(root: Node3D) -> AABB:
	var aabb := AABB()
	var first := true
	for m in root.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = (m as MeshInstance3D).global_transform * (m as MeshInstance3D).get_aabb()
		aabb = b if first else aabb.merge(b)
		first = false
	return aabb
