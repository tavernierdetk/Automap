extends Area3D
## A soft trigger volume that fires `GameEvents.zone_reached(zone_id)` the first time the
## player walks into it. Quests listen for that id to advance "reach_zone" objectives.
##
## WorldDirector instances `res://game/objective_zone.tscn`, sets `zone_id` / `radius`,
## positions it on the terrain and adds it to the world — so it must work purely from the
## exported properties, with no scene editing required.

## Id emitted on entry; matches a `zones[].id` / objective `zone` in the scene's game.json.
@export var zone_id: String = ""
## Trigger sphere radius in metres. Applied to the shape in `_ready`.
@export var radius: float = 8.0

var _fired := false

@onready var _shape: CollisionShape3D = $CollisionShape3D


func _ready() -> void:
	# Size the sphere from the exported radius so one .tscn serves every zone.
	if _shape != null and _shape.shape is SphereShape3D:
		var sphere := _shape.shape as SphereShape3D
		# Duplicate so runtime resizing never mutates the shared packed-scene resource.
		sphere = sphere.duplicate() as SphereShape3D
		sphere.radius = radius
		_shape.shape = sphere

	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node3D) -> void:
	if _fired:
		return
	if not body.is_in_group("player"):
		return
	_fired = true
	GameEvents.zone_reached.emit(zone_id)
