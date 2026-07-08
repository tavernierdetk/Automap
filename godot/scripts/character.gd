extends Node3D
## Parametric, procedurally-animated primitive figure — Phase A of the character pipeline.
##
## Reads a CharacterProfile (high-level physical attributes: height, build, colours,
## hairstyle, glasses) and configures this primitive rig to match. The profile is the
## stable contract the whole pipeline targets: today a hand-written .tres, later the
## JSON a local vision model emits from a photo. The render backend (these primitives)
## is a swappable box — a real rigged model can replace it without touching the
## controller, which only ever rotates this node to face movement.
##
## Animation is pure-visual: limb swing + head-bob scale with the ancestor
## CharacterBody3D's speed; idle breathing keeps it alive when standing still.

const DEFAULT_PROFILE := "res://profiles/default.tres"
const BASE_HEIGHT := 1.8  # the rig is modelled ~1.8 m tall; profile.height_m scales it

@export var profile: CharacterProfile

@export var stride_freq := 2.2
@export var max_swing := 0.6
@export var reference_speed := 6.0
@export var blend_speed := 10.0

var _phase := 0.0
var _amp := 0.0
var _breathe := 0.0
var _body: CharacterBody3D
var _head_base_y := 0.0

@onready var _torso: MeshInstance3D = $Torso
@onready var _head: MeshInstance3D = $Head
@onready var _arm_l: Node3D = $ArmL
@onready var _arm_r: Node3D = $ArmR
@onready var _leg_l: Node3D = $LegL
@onready var _leg_r: Node3D = $LegR


func _ready() -> void:
	var n: Node = get_parent()
	while n != null and not (n is CharacterBody3D):
		n = n.get_parent()
	_body = n as CharacterBody3D

	if profile == null and ResourceLoader.exists(DEFAULT_PROFILE):
		profile = load(DEFAULT_PROFILE)
	if profile == null:
		profile = CharacterProfile.new()  # sane defaults so we never crash

	_head_base_y = _head.position.y
	_apply_profile()


func _apply_profile() -> void:
	# Height: scale the whole rig (feet stay on the origin, so it grows upward).
	scale = Vector3.ONE * (profile.height_m / BASE_HEIGHT)

	# Build: widen torso + limbs on X/Z without changing their length.
	var w := profile.build
	for m in [_torso, $ArmL/Mesh, $ArmR/Mesh, $LegL/Mesh, $LegR/Mesh]:
		m.scale = Vector3(w, m.scale.y, w)

	# Colours — one material per body group, applied via material_override.
	_paint([_head, $Head/Nose, $Neck, $ArmL/Hand, $ArmR/Hand], profile.skin_color)
	_paint([_torso, $ArmL/Mesh, $ArmR/Mesh], profile.shirt_color)
	_paint([$LegL/Mesh, $LegR/Mesh], profile.pants_color)
	_paint([$LegL/Foot, $LegR/Foot], Color(0.12, 0.12, 0.14))
	_paint([$Head/Glasses], Color(0.05, 0.05, 0.08))

	# Hair: hide every style, show the matching one, and tint hair + facial hair.
	for style in $Head/Hair.get_children():
		style.visible = (style.name == profile.hairstyle)
	_paint_recursive($Head/Hair, profile.hair_color)
	_paint([$Head/FacialHair], profile.hair_color)

	$Head/Glasses.visible = profile.glasses
	$Head/FacialHair.visible = profile.facial_hair

	print("[character] %.2fm, build %.2f, hair=%s glasses=%s" % [
		profile.height_m, profile.build, profile.hairstyle, profile.glasses])


func _paint(nodes: Array, color: Color) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	for node in nodes:
		if node is MeshInstance3D:
			node.material_override = mat


func _paint_recursive(root: Node, color: Color) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	for node in root.find_children("*", "MeshInstance3D", true, false):
		node.material_override = mat


func _process(delta: float) -> void:
	var speed := 0.0
	if _body != null:
		speed = Vector2(_body.velocity.x, _body.velocity.z).length()

	var move_norm := clampf(speed / reference_speed, 0.0, 1.0)
	var target_amp := move_norm * max_swing
	_amp = lerpf(_amp, target_amp, clampf(blend_speed * delta, 0.0, 1.0))
	_phase += delta * stride_freq * maxf(speed, 0.0)
	_breathe += delta

	# Limbs: arms opposite to legs, left/right out of phase.
	var swing := sin(_phase) * _amp
	_leg_l.rotation.x = swing
	_leg_r.rotation.x = -swing
	_arm_l.rotation.x = -swing
	_arm_r.rotation.x = swing

	# Walk: subtle head-bob at twice stride frequency, scaled by movement.
	_head.position.y = _head_base_y + sin(_phase * 2.0) * 0.015 * move_norm

	# Idle: gentle breathing in the torso when nearly still.
	var idle := 1.0 - move_norm
	_torso.scale.y = 1.0 + sin(_breathe * 1.6) * 0.02 * idle
