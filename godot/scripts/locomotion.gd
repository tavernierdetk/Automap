class_name Locomotion
extends Node
## The shared mover — movement module v1 (character-runtime-stack R2).
##
## Turns a movement INTENT (a world-space horizontal direction + sprint/jump
## flags) into CharacterBody3D velocity: speed cap, gravity, jump, and
## swivelling the visible figure to face travel. Two adapters drive it — player
## input (scripts/player_tps.gd) and the NPC waypoint follower
## (game/npc/npc_mover.gd) — and the rig animates from the resulting velocity,
## never from the adapter. Must sit as a direct child of the CharacterBody3D
## it moves.
##
## Params default to the all-average baseline and are overwritten from a
## CharacterProfile: stage 10 derives them from the five attributes
## (automap/balance.derive_movement — the mechanics module's mapping; movement
## params are derived, never hand-set).

@export var walk_speed := 6.0
@export var sprint_mult := 3.0
@export var jump_velocity := 6.0
@export var turn_speed := 12.0
## Optional visible figure swivelled so its forward (-Z) faces the movement.
@export var visual: Node3D

var _body: CharacterBody3D
var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity", 9.8)


func _ready() -> void:
	_body = get_parent() as CharacterBody3D
	assert(_body != null, "Locomotion must be a direct child of a CharacterBody3D")


## Pull movement params off a CharacterProfile; absent fields keep defaults.
func configure_from_profile(p: Resource) -> void:
	if p == null:
		return
	for key in ["walk_speed", "jump_velocity", "turn_speed"]:
		var v = p.get(key)
		if v != null:
			set(key, v)


## One physics tick of movement intent. `dir` may be any length (normalized
## here); pass Vector3.ZERO to stand still. Runs move_and_slide.
func move(dir: Vector3, delta: float, sprint := false, jump := false) -> void:
	dir.y = 0.0
	var moving := dir.length() > 0.01
	dir = dir.normalized() if moving else Vector3.ZERO
	var speed := walk_speed * (sprint_mult if sprint else 1.0)
	_body.velocity.x = dir.x * speed
	_body.velocity.z = dir.z * speed
	if not _body.is_on_floor():
		_body.velocity.y -= _gravity * delta
	elif jump:
		_body.velocity.y = jump_velocity
	if visual != null and moving:
		var target := atan2(-dir.x, -dir.z)
		visual.rotation.y = lerp_angle(visual.rotation.y, target, turn_speed * delta)
	_body.move_and_slide()


## Stand still but keep physics honest (gravity, settling onto the floor).
func halt(delta: float) -> void:
	move(Vector3.ZERO, delta)
