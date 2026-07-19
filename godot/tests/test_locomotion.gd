extends Node3D
## Headless unit test for the movement module (R2): the Locomotion component
## through its NPC waypoint adapter — settling, route following, profile-driven
## params, arrival. The player adapter is exercised by the integration test
## (same component, input-fed).
##
##   Godot --headless --path godot res://tests/test_locomotion.tscn --quit-after 4000
##
## Exit code 0 = all assertions passed.

var _fails := 0


func _check(cond: bool, label: String) -> void:
	print(("  ok  | " if cond else "  FAIL| ") + label)
	if not cond:
		_fails += 1


func _physics_frames(n: int) -> void:
	for _i in range(n):
		await get_tree().physics_frame


func _ready() -> void:
	print("TEST locomotion")
	# A 200x200 m floor with its top face at y = 0.
	var floor_body := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(200, 1, 200)
	cs.shape = box
	floor_body.add_child(cs)
	add_child(floor_body)
	floor_body.position.y = -0.5

	var npc: CharacterBody3D = (load("res://game/npc/npc.tscn") as PackedScene).instantiate()
	add_child(npc)
	npc.global_position = Vector3(0, 0.05, 0)

	# No route: the body settles onto the terrain and stands still.
	await _physics_frames(30)
	_check(absf(npc.global_position.y) < 0.05,
		"idle NPC settles onto the floor (y=%.3f)" % npc.global_position.y)
	_check(npc.velocity.length() < 0.1, "idle NPC stands still")

	# A route moves the NPC at the profile's walk speed.
	var mover: Node = npc.get_node("Mover")
	mover.call("set_route", [Vector3(30, 0, 0)], false)
	var x0: float = npc.global_position.x
	await _physics_frames(60)
	var moved: float = npc.global_position.x - x0
	_check(moved > 3.0, "route moves the NPC (+%.2f m in ~1 s)" % moved)
	_check(absf(npc.velocity.length() - 6.0) < 0.5,
		"cruise speed ~ baseline walk_speed (%.2f m/s)" % npc.velocity.length())

	# Movement params travel with the profile (mechanics regiments the mover).
	var slow := CharacterProfile.new()
	slow.walk_speed = 2.0
	npc.call("apply_profile", slow)
	await _physics_frames(30)
	_check(absf(npc.velocity.length() - 2.0) < 0.3,
		"profile walk_speed regiments the mover (%.2f m/s)" % npc.velocity.length())

	# A non-looped route clears on arrival and the NPC halts.
	mover.call("set_route", [npc.global_position + Vector3(1.0, 0, 0)], false)
	await _physics_frames(150)
	var route: Array = mover.get("route")
	_check(route.is_empty(), "non-looped route clears on arrival")
	_check(npc.velocity.length() < 0.1, "NPC halts at the last waypoint")

	print("TEST locomotion: %s" % ("ALL PASS" if _fails == 0 else "%d FAIL(S)" % _fails))
	get_tree().quit(1 if _fails > 0 else 0)
