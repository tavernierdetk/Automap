# The cutscene module — staged story, camera-first (2026-07-18)

A new chair: the **Cutscene Director**, under the Story Director,
interacting with the Casting Director (studio-org addendum below). The
requirement: scenes where dialogue plays on screen, NPCs move about and
interact with EACH OTHER, the camera goes where the story needs it (not
the player), the player is frozen — or absent entirely.

## The house type applied

| Piece | What |
|---|---|
| Owned document | `games/<g>/cutscenes/<id>.json` (cutscene@1.0.0) |
| Skill door | `/cutscene-director` |
| Gate | the cutscene gate (`automap/cutscenes.py`, fatal in the publisher): stage level exists; every actor's creature exists AND obeys the region law (R-005); speakers are staged actors; referenced dialogues exist; named canon persons are admitted; trigger rects sit inside the stage's pixel bounds |
| Library | the cast book (who exists to be staged) + scene briefs (where) |
| Engine reader | `engine/cutscene/` — a runner that executes the document verbatim |

## The document (cutscene@1.0.0)

```jsonc
{
  "id": "first_turn",
  "level": "vaporis_fair",              // the STAGE (any published level)
  "kind": "interstitial" | "triggered",
  "trigger": {                           // triggered kind only
    "rect": {"pos": [x,y], "size": [w,h]},
    "once_flag": "seen_gate_welcome"     // auto-set; never replays
  },
  "hide_player": true,                   // interstitial default: PC absent
  "actors": [                            // puppets spawned FOR the scene
    {"id": "druso", "creature": "operator_druso", "spawn": [x,y],
     "face": "front"}
  ],
  "steps": [                             // sequential; each awaits
    {"camera": {"pos": [x,y], "zoom": 1.2, "duration": 1.5}},
    {"move":   {"actor": "druso", "to": [x,y], "speed": 70}},
    {"face":   {"actor": "druso", "dir": "left"}},
    {"say":    {"actor": "druso", "text": "…", "auto": 2.5}},  // accept OR auto
    {"say":    {"dialogue": "some_published_doc"}},            // full doc form
    {"wait":   0.8},
    {"effects": [{"type": "flag", "key": "x", "value": true}]}, // dialogue vocab
    {"parallel": [ {"move": …}, {"camera": …} ]}               // one level deep
  ]
}
```

- **Actors are puppets**: spawned from creature sprites for the scene's
  duration, driven by the script (tween movement with facing-correct
  Walk animations — choreography ignores collision by design), freed at
  the end. Scene NPCs and wanderers FREEZE while a cutscene runs (the
  same input-lock family as dialogue/menus).
- **`say` rides the dialogue machinery**: a synthesized one-node
  dialogue-script per line → the themed box, the speaker's PORTRAIT,
  accept-to-advance (or `auto` seconds for hands-free interstitials).
  The full-doc form plays any published dialogue mid-scene.
- **Camera**: the runner's own Camera2D becomes current; pans/zooms are
  tweens; the player's camera is restored at the end.
- **Two start modes**:
  - `triggered`: BakedLocation spawns a trigger zone at load for every
    published cutscene staged on its level (a THIN READER — the baker
    is untouched); walking in fires it once (`once_flag`).
  - `interstitial`: `Cutscenes.play(id)` — from a dialogue effect
    (`{"type": "cutscene", "id": …}`, dialogue-script@1.2), from story
    code, or from tests. If the stage is a DIFFERENT level, the runner
    travels there, plays with the player hidden, and returns to the
    exact prior spot — the "PC was never there" mode.

## Org addendum (studio-org.md)

- **Cutscene Director** — new chair under the Story Director. Owns
  `games/<g>/cutscenes/`; requisitions actors from the Casting
  Director's cast book (an actor without a creature + sprite is a gate
  error, not a wish); binds to the Scene Director's stages by level id.
- Ledger rows: Story → Cutscene (a beat commissions a scene),
  Cutscene → Casting (actor requisition; cast book), Cutscene →
  publisher (★ the cutscene gate), engine trigger/interstitial rows.
- Coverage map: "Cutscenes / staged story" moves from a Story-Director
  fold to its own chair.

## Named limits (v1, deliberate)

- Choreography verbs: camera/move/face/say/wait/effects/parallel — no
  emotes, no props animation, no music cue (Audio seam), no branching
  (cutscenes are LINEAR; branching belongs to dialogue).
- Movement ignores collision (puppets walk where the script says).
- One `parallel` level; `say` never runs inside `parallel`.
- Interstitial travel restores position but not scroll-perfect camera
  history; wanderers resume fresh.
