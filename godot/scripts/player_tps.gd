extends CharacterBody3D
## Minimal third-person character controller for navigating the reconstructed scene.
## This is the "future-C" game seed: the scan mesh becomes set dressing you steer a
## character around. Walk mode is the default; press F for a no-clip fly to escape
## scan-artifact holes, R to respawn at the start position.
##
##   Mouse      orbit camera       WASD   move (relative to camera)
##   Shift      sprint             Space  jump (walk) / up (fly)
##   F          toggle fly/walk    Ctrl   down (fly)
##   R          respawn            Esc    free/capture the mouse cursor

@export var walk_speed := 6.0
@export var fly_speed := 25.0
@export var sprint_mult := 3.0
@export var jump_velocity := 6.0
@export var mouse_sensitivity := 0.0025
@export var turn_speed := 12.0  # how fast the body swivels to face movement

var fly := false
var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity", 9.8)
var _spawn: Transform3D

@onready var body: Node3D = $Body
@onready var pivot: Node3D = $CameraPivot
@onready var spring: SpringArm3D = $CameraPivot/SpringArm3D
@onready var collision: CollisionShape3D = $CollisionShape3D


func _ready() -> void:
	_spawn = global_transform
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if DialogueManager.is_active():
		return  # the dialogue panel owns input while a conversation is open
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		pivot.rotate_y(-event.relative.x * mouse_sensitivity)
		spring.rotation.x = clampf(
			spring.rotation.x - event.relative.y * mouse_sensitivity, -1.3, 0.4
		)
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_F:
				fly = not fly
				collision.disabled = fly  # no-clip while flying: escape scan holes
				velocity = Vector3.ZERO
				print("[game] fly mode: ", fly)
			KEY_R:
				global_transform = _spawn
				velocity = Vector3.ZERO
				print("[game] respawned")
			KEY_ESCAPE:
				Input.mouse_mode = (
					Input.MOUSE_MODE_VISIBLE
					if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
					else Input.MOUSE_MODE_CAPTURED
				)


func _physics_process(delta: float) -> void:
	if DialogueManager.is_active():
		velocity = Vector3.ZERO  # stand still while talking
		return
	# Build a move direction in the camera's horizontal frame.
	var input := Vector3.ZERO
	if Input.is_physical_key_pressed(KEY_W): input.z -= 1.0
	if Input.is_physical_key_pressed(KEY_S): input.z += 1.0
	if Input.is_physical_key_pressed(KEY_A): input.x -= 1.0
	if Input.is_physical_key_pressed(KEY_D): input.x += 1.0

	var yaw := pivot.global_transform.basis.get_euler().y
	var dir := Vector3(input.x, 0.0, input.z).rotated(Vector3.UP, yaw).normalized()

	var speed := fly_speed if fly else walk_speed
	if Input.is_physical_key_pressed(KEY_SHIFT):
		speed *= sprint_mult

	if fly:
		var vert := 0.0
		if Input.is_physical_key_pressed(KEY_SPACE): vert += 1.0
		if Input.is_physical_key_pressed(KEY_CTRL): vert -= 1.0
		velocity = (dir + Vector3.UP * vert).normalized() * speed
	else:
		velocity.x = dir.x * speed
		velocity.z = dir.z * speed
		if not is_on_floor():
			velocity.y -= _gravity * delta
		elif Input.is_physical_key_pressed(KEY_SPACE):
			velocity.y = jump_velocity

	# Swivel the visible body so its forward (-Z) faces the movement direction.
	if dir.length() > 0.01:
		var target := atan2(-dir.x, -dir.z)
		body.rotation.y = lerp_angle(body.rotation.y, target, turn_speed * delta)

	move_and_slide()
