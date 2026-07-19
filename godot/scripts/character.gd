extends Node3D
## Parametric, procedurally-animated primitive figure — Phase A of the character pipeline.
## This is `figure-2`, the platform's out-of-the-box character tier (see
## docs/explorations/character-runtime-stack.md; acceptance renders come from
## tests/character_gallery.tscn).
##
## Reads a CharacterProfile (high-level physical attributes: height, build, colours,
## hairstyle, glasses) and configures this primitive rig to match. The profile is the
## stable contract the whole pipeline targets: today a hand-written .tres, later the
## JSON a local vision model emits from a photo. The render backend (these primitives)
## is a swappable box — a real rigged model can replace it without touching the
## controller, which only ever rotates this node to face movement.
##
## Animation is pure-visual and two-layered: a walk gait (two-segment limbs with knee
## and elbow flexion, hip/shoulder counter-rotation, body bob and lean) scaled by the
## ancestor CharacterBody3D's speed, plus an idle layer (breathing, blinking, weight
## shifts, slow head wander) that keeps stationary figures — every NPC — alive.

const DEFAULT_PROFILE := "res://profiles/default.tres"
const BASE_HEIGHT := 1.8  # the rig is modelled ~1.8 m tall; profile.height_m scales it

@export var profile: CharacterProfile

@export var stride_freq := 2.2
@export var max_swing := 0.55
@export var reference_speed := 6.0
@export var blend_speed := 10.0

var _phase := 0.0
var _amp := 0.0
var _breathe := 0.0
var _body: CharacterBody3D
var _blink_wait := 2.0
var _blink_left := 0.0
var _base_scales := {}  # MeshInstance3D -> its authored scale (build multiplies it)

@onready var _rig: Node3D = $Rig
@onready var _hips: Node3D = $Rig/Hips
@onready var _spine: Node3D = $Rig/Spine
@onready var _chest: MeshInstance3D = $Rig/Spine/Chest
@onready var _head: Node3D = $Rig/Spine/Head
@onready var _leg_l: Node3D = $Rig/Hips/LegL
@onready var _leg_r: Node3D = $Rig/Hips/LegR
@onready var _knee_l: Node3D = $Rig/Hips/LegL/Knee
@onready var _knee_r: Node3D = $Rig/Hips/LegR/Knee
@onready var _foot_l: MeshInstance3D = $Rig/Hips/LegL/Knee/Foot
@onready var _foot_r: MeshInstance3D = $Rig/Hips/LegR/Knee/Foot
@onready var _arm_l: Node3D = $Rig/Spine/ArmL
@onready var _arm_r: Node3D = $Rig/Spine/ArmR
@onready var _elbow_l: Node3D = $Rig/Spine/ArmL/Elbow
@onready var _elbow_r: Node3D = $Rig/Spine/ArmR/Elbow
@onready var _eye_l: MeshInstance3D = $Rig/Spine/Head/EyeL
@onready var _eye_r: MeshInstance3D = $Rig/Spine/Head/EyeR


func _ready() -> void:
	var n: Node = get_parent()
	while n != null and not (n is CharacterBody3D):
		n = n.get_parent()
	_body = n as CharacterBody3D

	if profile == null and ResourceLoader.exists(DEFAULT_PROFILE):
		profile = load(DEFAULT_PROFILE)
	if profile == null:
		profile = CharacterProfile.new()  # sane defaults so we never crash

	for m in find_children("*", "MeshInstance3D", true, false):
		_base_scales[m] = m.scale

	_apply_profile()


func _apply_profile() -> void:
	# Height: scale the whole rig (feet stay on the origin, so it grows upward).
	scale = Vector3.ONE * (profile.height_m / BASE_HEIGHT)

	# Build: widen torso + limbs on X/Z without changing their length. Meshes carry
	# authored non-uniform scales, so build multiplies the base instead of replacing it.
	var w := profile.build
	for m in [_chest, $Rig/Hips/Pelvis, $Rig/Spine/ShoulderL, $Rig/Spine/ShoulderR,
			$Rig/Spine/ArmL/UpperArm, $Rig/Spine/ArmR/UpperArm,
			$Rig/Spine/ArmL/Elbow/Forearm, $Rig/Spine/ArmR/Elbow/Forearm,
			$Rig/Hips/LegL/Thigh, $Rig/Hips/LegR/Thigh,
			$Rig/Hips/LegL/Knee/Shin, $Rig/Hips/LegR/Knee/Shin]:
		var base: Vector3 = _base_scales.get(m, Vector3.ONE)
		m.scale = Vector3(base.x * w, base.y, base.z * w)

	# Colours — one material per body group, applied via material_override.
	var skin := profile.skin_color
	_paint([$Rig/Spine/Head/Skull, $Rig/Spine/Head/Nose, $Rig/Spine/Head/EarL,
			$Rig/Spine/Head/EarR, $Rig/Spine/Neck,
			$Rig/Spine/ArmL/Elbow/Forearm, $Rig/Spine/ArmR/Elbow/Forearm,
			$Rig/Spine/ArmL/Elbow/Hand, $Rig/Spine/ArmR/Elbow/Hand], skin)
	_paint([_chest, $Rig/Spine/ShoulderL, $Rig/Spine/ShoulderR,
			$Rig/Spine/ArmL/UpperArm, $Rig/Spine/ArmR/UpperArm], profile.shirt_color)
	_paint([$Rig/Hips/Pelvis, $Rig/Hips/LegL/Thigh, $Rig/Hips/LegR/Thigh,
			$Rig/Hips/LegL/Knee/Shin, $Rig/Hips/LegR/Knee/Shin], profile.pants_color)
	_paint([_foot_l, _foot_r], Color(0.12, 0.12, 0.14))

	# Face: near-white eyes with a glossy dark pupil (the catchlight sells it),
	# mouth a muted darker skin tone so it reads without turning into lipstick.
	_paint([_eye_l, _eye_r], Color(0.93, 0.93, 0.92), 0.25)
	_paint([$Rig/Spine/Head/EyeL/Pupil, $Rig/Spine/Head/EyeR/Pupil],
			Color(0.08, 0.06, 0.05), 0.2)
	_paint([$Rig/Spine/Head/Mouth], Color(skin.r * 0.75, skin.g * 0.5, skin.b * 0.5))
	_paint_recursive($Rig/Spine/Head/Glasses, Color(0.05, 0.05, 0.08), 0.4)

	# Hair: hide every style, show the matching one, tint hair + brows + facial hair.
	for style in _head.get_node("Hair").get_children():
		style.visible = (style.name == profile.hairstyle)
	_paint_recursive(_head.get_node("Hair"), profile.hair_color, 0.75)
	_paint([$Rig/Spine/Head/BrowL, $Rig/Spine/Head/BrowR,
			$Rig/Spine/Head/FacialHair], profile.hair_color, 0.75)

	_head.get_node("Glasses").visible = profile.glasses
	_head.get_node("FacialHair").visible = profile.facial_hair

	print("[character] %.2fm, build %.2f, hair=%s glasses=%s" % [
		profile.height_m, profile.build, profile.hairstyle, profile.glasses])


func _paint(nodes: Array, color: Color, roughness := 0.9) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = roughness
	for node in nodes:
		if node is MeshInstance3D:
			node.material_override = mat


func _paint_recursive(root: Node, color: Color, roughness := 0.9) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = roughness
	for node in root.find_children("*", "MeshInstance3D", true, false):
		node.material_override = mat


func _process(delta: float) -> void:
	var speed := 0.0
	if _body != null:
		speed = Vector2(_body.velocity.x, _body.velocity.z).length()

	var move := clampf(speed / reference_speed, 0.0, 1.0)
	_amp = lerpf(_amp, move * max_swing, clampf(blend_speed * delta, 0.0, 1.0))
	_phase += delta * stride_freq * maxf(speed, 0.0)
	_breathe += delta
	var idle := 1.0 - move

	# --- gait --------------------------------------------------------------
	var s := sin(_phase)
	var c := cos(_phase)

	# Legs: hips swing; the knee flexes mid-swing (when the hip crosses centre
	# moving forward) and straightens for the plant — that trailing shin is most
	# of what separates a walk from a puppet swing.
	var hip_l := s * _amp
	var hip_r := -s * _amp
	var knee_l := -(0.06 + maxf(0.0, c) * _amp * 1.1)
	var knee_r := -(0.06 + maxf(0.0, -c) * _amp * 1.1)
	_leg_l.rotation.x = hip_l
	_leg_r.rotation.x = hip_r
	_knee_l.rotation.x = knee_l
	_knee_r.rotation.x = knee_r
	# Ankles mostly keep the foot level instead of letting toes stab the ground.
	_foot_l.rotation.x = -(hip_l + knee_l) * 0.75
	_foot_r.rotation.x = -(hip_r + knee_r) * 0.75

	# Arms: counter-swing to the legs, always slightly bent at the elbow, bending
	# further as the arm comes forward; held a touch away from the torso.
	var sway := sin(_breathe * 1.5) * 0.02 * idle
	_arm_l.rotation.x = -s * _amp * 0.75 + sway
	_arm_r.rotation.x = s * _amp * 0.75 - sway
	_arm_l.rotation.z = 0.07
	_arm_r.rotation.z = -0.07
	_elbow_l.rotation.x = 0.22 + maxf(0.0, -s) * _amp * 0.6
	_elbow_r.rotation.x = 0.22 + maxf(0.0, s) * _amp * 0.6

	# Trunk: shoulders counter-rotate the pelvis, weight rolls over the stance
	# leg, the whole rig bobs twice a stride and leans into the movement.
	_spine.rotation.y = -s * 0.1 * move
	_hips.rotation.y = s * 0.07 * move
	_hips.rotation.z = c * 0.03 * move
	_rig.position.y = (0.5 - 0.5 * cos(_phase * 2.0)) * 0.035 * move
	_rig.rotation.x = -0.05 * move

	# --- idle life ----------------------------------------------------------
	# Breathing (chest), a slow weight shift, and a lazy head wander; the head
	# also counters the shoulder yaw while walking so the gaze stays forward.
	var chest_base: Vector3 = _base_scales.get(_chest, Vector3.ONE)
	var breath := 1.0 + sin(_breathe * 1.5) * 0.015 * idle
	_chest.scale = Vector3(chest_base.x * profile.build * breath, chest_base.y * breath,
			chest_base.z * profile.build * breath)
	_rig.rotation.z = sin(_breathe * 0.4) * 0.015 * idle
	_head.rotation.y = s * 0.06 * move \
			+ (sin(_breathe * 0.23) * 0.18 + sin(_breathe * 0.11) * 0.1) * idle
	_head.position.y = 0.56 + sin(_phase * 2.0) * 0.008 * move

	# Blink: hold, snap shut for ~0.13 s, reopen. Cheap, and it reads as alive
	# even on a perfectly still NPC.
	if _blink_left > 0.0:
		_blink_left -= delta
		var lid := 0.12 if _blink_left > 0.0 else 1.0
		_eye_l.scale.y = _base_scales[_eye_l].y * lid
		_eye_r.scale.y = _base_scales[_eye_r].y * lid
	else:
		_blink_wait -= delta
		if _blink_wait <= 0.0:
			_blink_left = 0.13
			_blink_wait = 2.0 + randf() * 3.5
