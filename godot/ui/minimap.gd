extends Control
## Minimap — a self-contained UI module of the engine's kit.
##
## Reads the cartographic map the pipeline publishes beside every scene
## (`minimap.png` + `minimap.json`, drawn from the world model in the visual
## identity's colors — see automap/minimap.py). North-up, scrolling crop
## centered on the player, view-direction arrow, and an objective dot when
## the game layer broadcasts one.
##
## Modularity rules it obeys: no hard dependency on the game layer (it
## connects to GameEvents only if that autoload exists), no dependency on any
## particular map (it resolves whatever map_loader loaded), and it hides
## itself entirely when a scene ships no minimap. Drop the node in any shell
## scene and it either works or stays out of the way.

const VIEW_RADIUS_M := 80.0        # world meters from center to panel edge
const ARROW := 7.0                 # player arrow half-size, px

var _tex: Texture2D
var _meta: Dictionary = {}
var _player: Node3D
var _objective := Vector3.INF


func _ready() -> void:
	clip_contents = true
	visible = false
	var ge := get_node_or_null("/root/GameEvents")
	if ge != null and ge.has_signal("objective_changed"):
		ge.connect("objective_changed", _on_objective)
	_resolve.call_deferred()


func _resolve() -> void:
	# the shell root (map_loader) knows where the map came from
	var host := get_parent()
	var dir := str(host.get("loaded_dir")) if host != null and host.get("loaded_dir") != null else ""
	if dir == "":
		return
	var png := dir + "/minimap.png"
	var meta_path := dir + "/minimap.json"
	if not FileAccess.file_exists(meta_path):
		return
	if ResourceLoader.exists(png):
		_tex = load(png)                              # imported resource
	elif FileAccess.file_exists(png):
		var img := Image.load_from_file(png)          # OS path (work/ scenes)
		if img != null:
			_tex = ImageTexture.create_from_image(img)
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(meta_path))
	if _tex == null or typeof(parsed) != TYPE_DICTIONARY:
		return
	_meta = parsed
	var players := get_tree().get_nodes_in_group("player")
	_player = players[0] if not players.is_empty() else null
	visible = _player != null
	if visible:
		print("[minimap] %s (%dx%d @ %s m/px)"
			% [png, int(_meta.width), int(_meta.height), str(_meta.m_per_px)])


func _on_objective(_id: String, text: String, pos: Vector3) -> void:
	_objective = Vector3.INF if text == "" or not pos.is_finite() else pos


func _process(_dt: float) -> void:
	if visible:
		queue_redraw()


func _world_to_map(x: float, z: float) -> Vector2:
	return Vector2((x - float(_meta.origin_x)) / float(_meta.m_per_px),
	               (z - float(_meta.origin_z)) / float(_meta.m_per_px))


func _draw() -> void:
	if _tex == null or _player == null or not is_instance_valid(_player):
		return
	var half := size / 2.0
	var scale_px := half.x / VIEW_RADIUS_M            # screen px per world m
	var map_scale := scale_px * float(_meta.m_per_px)  # screen px per map px
	var p := _player.global_position
	var centre_uv := _world_to_map(p.x, p.z)
	var src_half := half / map_scale
	draw_texture_rect_region(
		_tex, Rect2(Vector2.ZERO, size),
		Rect2(centre_uv - src_half, src_half * 2.0))

	# objective dot (game layer optional)
	if _objective.is_finite():
		var d := (_world_to_map(_objective.x, _objective.z) - centre_uv) * map_scale
		var r := minf(d.length(), half.x - 8.0)       # clamp to the rim
		draw_circle(half + d.normalized() * r if d.length() > 0.01 else half,
			5.0, Color(1.0, 0.85, 0.25))

	# view-direction arrow (north-up map: -z is up)
	var cam := get_viewport().get_camera_3d()
	var yaw := 0.0
	if cam != null:
		var fwd := -cam.global_transform.basis.z
		yaw = atan2(fwd.x, -fwd.z)
	var pts := PackedVector2Array()
	for v in [Vector2(0, -ARROW * 1.4), Vector2(ARROW, ARROW), Vector2(-ARROW, ARROW)]:
		pts.append(half + v.rotated(yaw))
	draw_colored_polygon(pts, Color(0.95, 0.97, 1.0))
	draw_polyline(pts + PackedVector2Array([pts[0]]), Color(0.1, 0.12, 0.15, 0.9), 1.5)

	# frame
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0, 0, 0, 0)
	box.set_border_width_all(2)
	box.border_color = Color(0.08, 0.09, 0.1, 0.85)
	box.set_corner_radius_all(6)
	draw_style_box(box, Rect2(Vector2.ZERO, size))
