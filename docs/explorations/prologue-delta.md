# The prologue delta — now vs. a fully-implemented Shared Origin (2026-07-18)

Where we stand against the `narrative_sequence` prologue
(`prologue_shared_origin`), segment by segment and capability by
capability. The **spine is done and one segment is genuinely playable**;
the rest is additive. Companion to `narrative-sequence-gap.md` (the
original roadmap) — this is the current, precise delta.

## What runs today (done)

- **The sequence tier**: sequence@1 schema + gate, the SequenceRunner
  (segment→segment, entry/`requires` gates), the **state ledger** in
  WorldState (valued outputs like `caden_selected_class`), save/resume
  mid-sequence. (NS0 + NS1)
- **One segment type playable**: `ritualized_player_choice` — the class
  ceremony runs, produces the ledger outputs, advances the runner to
  the incident. (NS2)
- **The five disciplines** as data (class@1, stat-budget gated) + the
  choice ceremony UI.
- **The incident DESIGNED** (the Weirgate Release; all five forks
  resolved; proposed canon). No longer design-blocked.
- **The three protagonists** have overworld ULPC bodies + stat sheets
  (adult).
- **General engine**: dialogue (+ portraits + effects), combat (layouts,
  Attack/Skills/Items/Run, flee, enemy HP bars, separate modals),
  cutscenes, menus, persistent saves, the party-follow chain, the
  casting/ULPC pipeline.

The sequence gate reports **0 contradictions, 18 to-author warnings** —
the content checklist below.

## The delta — PLATFORM capability (what the gate can't see)

| # | Capability | For | State |
|---|---|---|---|
| 1 | `playable_exposition` handler + **inspection points** (examine→text) + optional codex | classroom | none |
| 2 | `playable_hub` handler + **station abstraction** (visit-tracked, companion reactions, "all seen or exit") | welcome_fair | none |
| 3 | **In-scene staging** of the class ceremony (enter room, speak professor, take a seat) | class_choice | mechanic works UI-only; not staged in a scene |
| 4 | `formative_crisis` handler — crowd, player agency at the gate, the flood, the scattering, the slate-seed | incident | none (the hardest segment) |
| 5 | **Forced-outcome story-battle mode** (Vec vs Caden, scripted result) | incident | battle does win/lose only |
| 6 | **Age variants** — Caden/Vec/Isaac at 11 and 15 (ULPC child/teen bodies + a per-age slug convention) | all segments | adult sprites only |
| 7 | **Fragmented-revelation / flashback layer** — replays that add info (the incident's fragments A/B/C) | the whole "fragmented prologue" framing | none |
| 8 | **Multi-protagonist control model** — who the player embodies per segment | class_choice, the incident battle | HUMAN-BLOCKED |
| 9 | **Continuity gate** (equal-status, isaac=weaver, arc-independent-of-class, ledger completeness) | validation | seam only (Continuity Director named, unbuilt) |
| 10 | **Dialogue portraits** for Caden/Vec/Isaac (figure_px faces) | all dialogue | none (they have bodies, no portraits) |
| 11 | **Music/ambience pipeline** (request→generate→publish; Suno key door exists) | the 3 tracks + 2 ambiences | seam only |

Items 1–4 are the NS3 "segment types" work; 6 is NS4; 7 + 9 are NS5.

## The delta — CONTENT (the gate's checklist)

- **Scenes (none built)**: the Auregate classroom (age 11), the welcome
  fair (age 11 — a DISTINCT Auregate scene, not the steampunk
  vaporis_fair), the specialty wing (age 15, five specialty rooms), the
  **Weirgate** (the incident). ~4 scene documents + briefs + bakes.
- **Dialogue (7 unwritten)**: classroom peer_banter + professor_
  instruction; fair.station_reactions; class_choice.{isaac,caden,vec};
  the incident. All need the voice profiles (below) to write well.
- **Cast (2 tbd)**: `auregate_professor` (the teacher) and
  `professor_wren` (proposed canon, saved by Caden — needs a creature
  doc + ULPC body). Plus ambient crowds (students, demonstrators,
  visitors).
- **Age variants** of the three protagonists (6 sprite sets: ×{11,15}).
- **Portraits** for the cast (dialogue).
- **Audio**: `music.auregate_childhood / _welcoming / _incident`,
  `ambience.classroom / .fair`.

## The delta — HUMAN decisions (still gating)

The incident design is now RESOLVED. Still open (from the doc's
`validation.completeness.blocked`, minus incident_design):

- **Player-control model** — single-PC vs multi-PC swap across
  segments. Load-bearing: the incident's Vec-vs-Caden battle needs a
  side, and the class choice picks for two protagonists.
- **Protagonist naming strategy** — immediate vs relational labels vs
  late reveal (affects every dialogue and UI label).
- **Character voice profiles** (Caden / Vec / Isaac) — needed before the
  seven dialogue sets can be written with distinct voices.
- **Fragment release order** — which fragment reveals what, when
  (gates NS5's fragment layer).

## Suggested order to close it

1. **NS3 — segment handlers** (exposition, hub, in-scene class choice):
   makes classroom/fair/class-choice playable as scenes. Biggest unlock;
   depends on nothing blocked.
2. **NS4 — age variants + the Auregate cast & the three early scenes**:
   age-11/15 protagonists, the professor + Wren, classroom/fair/wing.
   Content on the NS3 machinery.
3. **The incident** — the Weirgate scene, the formative_crisis handler,
   the forced-outcome story-battle, the slate-seed. *Needs the
   control-model decision first.*
4. **NS5 — fragments + continuity**: the fragmented-revelation layer
   (needs the fragment-order decision) + the continuity gate.
5. **The writing/art/audio pass**: the seven dialogue sets (needs voice
   profiles), portraits, music.

Rough shape: comparable to several of the rounds already done — but
additive, because the spine and one segment are proven. The two nearest,
unblocked pieces are **NS3** (platform) and the **Auregate scenes +
age variants** (content); the incident and fragments wait on two human
decisions (control model, fragment order) and one writing input (voice
profiles).
