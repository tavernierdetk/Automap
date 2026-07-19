class_name CharacterProfile
extends Resource
## High-level physical attributes of a character — the stable contract for the whole
## character pipeline. A photo (later, via a local VLM) produces one of these; the
## parametric build (now: primitives; later: MakeHuman/MPFB2) consumes it.
##
## Deliberately "recognizable by traits", not a face scan: hair, build, height, glasses.
## Saved as a text .tres so it is git-clean, human-editable, and fully reproducible —
## no binary ever needs to be committed.

@export_range(1.4, 2.1, 0.01) var height_m := 1.8
## Body width multiplier: 0.8 slim … 1.0 average … 1.3 broad.
@export_range(0.8, 1.3, 0.01) var build := 1.0

@export var skin_color := Color(0.86, 0.66, 0.52)
@export var hair_color := Color(0.18, 0.12, 0.08)
@export var shirt_color := Color(0.25, 0.45, 0.85)
@export var pants_color := Color(0.20, 0.22, 0.28)

@export_enum("bald", "short", "medium", "long", "ponytail", "afro") var hairstyle := "short"
@export var glasses := false
@export var facial_hair := false

## Locomotion params — derived from the five attributes by the mechanics module
## (automap/balance.derive_movement) and projected here by stage 10. Never
## hand-set on admitted characters; the defaults are the all-average baseline
## so hand-written/photo profiles keep the engine's historical feel.
@export var walk_speed := 6.0
@export var jump_velocity := 6.0
@export var turn_speed := 12.0
