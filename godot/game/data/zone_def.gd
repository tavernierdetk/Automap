class_name ZoneDef
extends Resource
## A world-space objective zone — WorldDirector spawns an ObjectiveZone (Area3D) for
## each of these; entering it emits GameEvents.zone_reached(id), which QuestManager
## uses to advance "reach_zone" objectives.
##
## (Added alongside the plan's four data classes: zones are first-class in game.json,
## so they get a typed def for parity with NpcSpawn/QuestDef.)

@export var id: String = ""
## Placement — same vocabulary as NpcSpawn.anchor (xz_frac / world / "top_center"),
## resolved by WorldDirector against the map AABB + a ground raycast.
@export var anchor: Variant = {}
## Trigger radius in metres.
@export var radius: float = 8.0
