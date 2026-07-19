extends Node
## Waypoint adapter for NPCs — the movement module's second driver (R2).
##
## Follows a route of world-space points through the sibling Locomotion
## component; with no route it just settles the body onto the terrain
## (gravity through Locomotion.halt). Movement pauses while the player is in
## interaction range or any dialogue is open, so the talk loop always wins
## over the walk loop and the controller's face-the-player swivel is never
## fought.
##
## Runtime API only: routes arrive via `set_route()` (tests, future
## behaviors) — the generation-side route baker that authors `route` into
## game.json is the living-behavior slice (C3), not this one.

@export var route: Array[Vector3] = []
@export var loop := true
@export var arrive_distance := 0.6

var _i := 0
var _body: CharacterBody3D

@onready var _loco: Locomotion = get_node_or_null("../Locomotion")
@onready var _controller: Node = get_parent()


func _ready() -> void:
	_body = get_parent() as CharacterBody3D


## Replace the route (world-space points). `looped` loops forever; otherwise
## the NPC stops at the last point and the route clears.
func set_route(points: Array, looped := true) -> void:
	route = []
	for p in points:
		route.append(p as Vector3)
	loop = looped
	_i = 0


func _physics_process(delta: float) -> void:
	if _body == null or _loco == null:
		return
	if route.is_empty() or _paused():
		_loco.halt(delta)
		return
	var to := route[_i] - _body.global_position
	to.y = 0.0
	if to.length() <= arrive_distance:
		_i += 1
		if _i >= route.size():
			if loop:
				_i = 0
			else:
				route = []
				_loco.halt(delta)
				return
		to = route[_i] - _body.global_position
		to.y = 0.0
	_loco.move(to, delta)


func _paused() -> bool:
	if DialogueManager.is_active():
		return true
	return _controller != null and _controller.has_method("player_in_range") \
			and _controller.call("player_in_range")
