extends Node3D
## World-space objective marker — a bright floating beam that marks where the tracked
## quest objective is. Instantiated at runtime (res://game/objective_marker.tscn) by the
## world module and added to the scene; it is NOT part of any authored scene.
##
## It listens on the GameEvents bus for objective_changed(quest_id, text, world_pos):
##   * finite world_pos -> jump to that spot and show the marker,
##   * Vector3.INF       -> hide (objective cleared / quest done / no world location).
## The beam gently bobs and spins so it reads as a live waypoint from a distance.

## How high the bobbing head rides above the marker's base, in metres.
@export var bob_height := 1.2
## Vertical bob amplitude in metres.
@export var bob_amplitude := 0.35
## Bob cycles per second.
@export var bob_speed := 1.5
## Spin rate of the marker head, radians per second.
@export var spin_speed := 1.5

@onready var _head: Node3D = $Head

var _t := 0.0


func _ready() -> void:
	GameEvents.objective_changed.connect(_on_objective_changed)
	# Start hidden until an objective with a real world position arrives.
	visible = false


func _process(delta: float) -> void:
	if not visible:
		return
	_t += delta
	if _head != null:
		_head.position.y = bob_height + sin(_t * TAU * bob_speed) * bob_amplitude
		_head.rotate_y(spin_speed * delta)


## Track the current objective: move to and show a finite position, hide otherwise.
func _on_objective_changed(_quest_id: String, _text: String, world_pos: Vector3) -> void:
	if world_pos.is_finite():
		global_position = world_pos
		visible = true
	else:
		visible = false
