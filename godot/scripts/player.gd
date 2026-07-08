extends CharacterBody3D
## Minimal fly/walk controller for inspecting the reconstructed scene.
## Starts in FLY mode (free 6-DoF, no gravity) so you never get stuck in a scan
## hole; press F to toggle WALK mode (gravity + jump, collides with the terrain).
##
##   Mouse      look          WASD   move
##   Shift      sprint        Space  up (fly) / jump (walk)
##   Ctrl       down (fly)    F      toggle fly/walk
##   Esc        free/capture the mouse cursor

@export var walk_speed := 8.0
@export var fly_speed := 25.0
@export var sprint_mult := 3.0
@export var jump_velocity := 6.0
@export var mouse_sensitivity := 0.0025

var fly := true
var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity", 9.8)

@onready var cam: Camera3D = $Camera3D


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotate_y(-event.relative.x * mouse_sensitivity)
		cam.rotate_x(-event.relative.y * mouse_sensitivity)
		cam.rotation.x = clampf(cam.rotation.x, -1.4, 1.4)
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_F:
				fly = not fly
				velocity = Vector3.ZERO
				print("[viewer] fly mode: ", fly)
			KEY_ESCAPE:
				Input.mouse_mode = (
					Input.MOUSE_MODE_VISIBLE
					if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
					else Input.MOUSE_MODE_CAPTURED
				)


func _physics_process(delta: float) -> void:
	var basis := cam.global_transform.basis if fly else global_transform.basis
	var dir := Vector3.ZERO
	if Input.is_physical_key_pressed(KEY_W): dir -= basis.z
	if Input.is_physical_key_pressed(KEY_S): dir += basis.z
	if Input.is_physical_key_pressed(KEY_A): dir -= basis.x
	if Input.is_physical_key_pressed(KEY_D): dir += basis.x

	var speed := fly_speed if fly else walk_speed
	if Input.is_physical_key_pressed(KEY_SHIFT):
		speed *= sprint_mult

	if fly:
		if Input.is_physical_key_pressed(KEY_SPACE): dir += Vector3.UP
		if Input.is_physical_key_pressed(KEY_CTRL): dir -= Vector3.UP
		velocity = dir.normalized() * speed
	else:
		var horiz := Vector3(dir.x, 0.0, dir.z).normalized() * speed
		velocity.x = horiz.x
		velocity.z = horiz.z
		if not is_on_floor():
			velocity.y -= _gravity * delta
		elif Input.is_physical_key_pressed(KEY_SPACE):
			velocity.y = jump_velocity

	move_and_slide()
