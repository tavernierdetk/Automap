class_name Interactable
extends Node3D
## Tiny uniform seam for anything the player can interact with (talk, read, open, …).
##
## Concrete interactables (NPCs, later signs/doors/loot) extend this and override the two
## virtual-ish methods below. The player-side interaction driver only ever needs to ask
## for `prompt_text()` and call `interact()`; it never reaches into a subclass. Keeping
## the base this small mirrors how CharacterProfile stays a stable contract while its
## backend swaps out.

## Short call-to-action shown in the HUD prompt while the player is in range.
## Override to return e.g. "Press E to talk to The Keeper". "" means no prompt.
func prompt_text() -> String:
	return ""


## Perform the interaction. Override to do the actual thing (start a dialogue, open a
## door, …). The base is a no-op so a bare Interactable is harmless.
func interact() -> void:
	pass
