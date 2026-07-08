extends Node
## The game layer's signal BUS — the single cross-module seam (autoload: GameEvents).
##
## The narrative/quest game is built as several decoupled modules (dialogue, quests,
## NPCs, world population, HUD). Rather than importing each other, they all speak
## through this one autoload's FROZEN signal list. Managers own logic and emit/consume;
## UI only consumes; NPCs only emit intent. This mirrors how CharacterProfile is the
## stable contract for the character pipeline.
##
## FROZEN CONTRACT — do not rename, retype, or remove these signals. Add new ones only
## by extending this list (append), never by changing existing signatures.

## Interaction prompt text changed. "" means hide the prompt (player left the volume).
signal interact_prompt_changed(text: String)

## A dialogue tree began playing.
signal dialogue_started(tree_id: String)
## A single dialogue line to display. `choices` is an Array of {text: String} dicts
## (empty for a linear line — the UI shows a "continue" affordance instead).
signal dialogue_line(speaker: String, text: String, choices: Array)
## The player picked choice `index` in the current line's choices array.
signal dialogue_choice_made(index: int)
## The dialogue tree finished. `outcome` is a free-form tag a tree can set on its
## terminal node (e.g. "accepted", "declined", ""), for quests to branch on.
signal dialogue_finished(tree_id: String, outcome: String)

## A dialogue (or other trigger) offered a quest to the player.
signal quest_offered(quest_id: String)
## A quest changed state. `state` is one of: "inactive", "active", "complete".
signal quest_state_changed(quest_id: String, state: String)
## The tracked objective changed. `text` is the HUD/marker label; `world_pos` is where
## the objective is in world space (Vector3.INF when it has no world location).
signal objective_changed(quest_id: String, text: String, world_pos: Vector3)

## The player entered an objective zone with this id.
signal zone_reached(zone_id: String)
