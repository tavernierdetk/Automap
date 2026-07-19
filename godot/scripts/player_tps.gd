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

@export var fly_speed := 25.0
@export var sprint_mult := 3.0
@export var mouse_sensitivity := 0.0025

var fly := false
var _spawn: Transform3D
var _loco: Locomotion  # walking is the movement module's job (input adapter here)

@onready var body: Node3D = $Body
@onready var pivot: Node3D = $CameraPivot
@onready var spring: SpringArm3D = $CameraPivot/SpringArm3D
@onready var collision: CollisionShape3D = $CollisionShape3D


func _ready() -> void:
	_spawn = global_transform
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	# The mover: params come from the Body's CharacterProfile (stage 10 derives
	# them from the character's stats), so who you play as changes how you move.
	_loco = Locomotion.new()
	_loco.visual = body
	add_child(_loco)
	_loco.sprint_mult = sprint_mult
	_loco.configure_from_profile(body.get("profile"))


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
	var sprint := Input.is_physical_key_pressed(KEY_SHIFT)

	if fly:
		# No-clip dev mode stays outside the movement module on purpose: it is a
		# tool for escaping scan holes, not a character verb.
		var speed := fly_speed * (sprint_mult if sprint else 1.0)
		var vert := 0.0
		if Input.is_physical_key_pressed(KEY_SPACE): vert += 1.0
		if Input.is_physical_key_pressed(KEY_CTRL): vert -= 1.0
		velocity = (dir + Vector3.UP * vert).normalized() * speed
		if dir.length() > 0.01:
			var target := atan2(-dir.x, -dir.z)
			body.rotation.y = lerp_angle(body.rotation.y, target, _loco.turn_speed * delta)
		move_and_slide()
	else:
		_loco.move(dir, delta, sprint, Input.is_physical_key_pressed(KEY_SPACE))
