extends Node3D
## Visual check for the parametric rig — NOT part of the headless test suite.
##
## Spawns a row of profiles (two idle, two mid-walk), renders a front and a
## three-quarter view to work/character_gallery/*.png, then quits. Needs a real
## window (the headless driver renders nothing): run
##   /Applications/Godot.app/Contents/MacOS/Godot --path godot res://tests/character_gallery.tscn

const PROFILES := [
	"res://profiles/default.tres",
	"res://profiles/marguerite_a_theodore.tres",
	"res://profiles/fisher.tres",
	"res://profiles/example.tres",
]
const WALKING := [false, false, true, true]  # which figures pose mid-stride
const SPACING := 1.1

@onready var _cam: Camera3D = $Camera3D


func _ready() -> void:
	for i in PROFILES.size():
		var body := CharacterBody3D.new()  # rig reads its velocity for the gait
		body.position.x = (i - (PROFILES.size() - 1) * 0.5) * SPACING
		add_child(body)
		var figure: Node3D = load("res://scenes/character.tscn").instantiate()
		figure.set("profile", load(PROFILES[i]))
		body.add_child(figure)
		if WALKING[i]:
			body.velocity = Vector3(0, 0, -3.0)

	await get_tree().create_timer(1.2).timeout  # let gait/blend settle
	var out := ProjectSettings.globalize_path("res://").path_join("../work/character_gallery")
	DirAccess.make_dir_recursive_absolute(out)

	await _shoot(out.path_join("front.png"), Vector3(0, 1.25, -3.6), Vector3(0, 1.0, 0))
	await _shoot(out.path_join("three_quarter.png"), Vector3(2.6, 1.7, -2.9), Vector3(0, 1.0, 0))
	# Head-and-shoulders on figure 2 (marguerite: glasses + medium hair).
	await _shoot(out.path_join("portrait.png"), Vector3(-0.35, 1.55, -0.85), Vector3(-0.55, 1.42, 0))
	print("[gallery] wrote front/three_quarter/portrait to ", out)
	get_tree().quit(0)


func _shoot(path: String, cam_pos: Vector3, target: Vector3) -> void:
	_cam.position = cam_pos
	_cam.look_at(target)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
