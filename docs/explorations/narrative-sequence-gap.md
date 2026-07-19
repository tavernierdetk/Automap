# Implementing the Shared Origin prologue — gap analysis + roadmap (2026-07-18)

The sample `narrative_sequence` (Entropy prologue, `narrative.prologue.
shared_origin`) is a **new tier of artifact**: it orchestrates FOUR
playable segments, a declared state ledger, a revelation plan, and ten
directors into one prologue. Everything the platform makes today lives
one or two tiers below it (a scene, an arc's beats, a cutscene, a
casting sheet). This maps what exists against what the document
demands, names the net-new components, and proposes a phased path —
separating **platform capability** (we build), **content authoring**
(we author on the machinery), and **human design decisions** (blocked,
theirs to resolve).

## What already carries weight

| The document asks for | We have | State |
|---|---|---|
| Named canon characters (Caden, Vec, Isaac) | `games/entropy/creatures/{caden,vec,isaac}.json` (originals region, imported canon) | ✅ exist |
| Scenes (classroom, fair, specialty wings) | Scene Director: brief → level → bake | ✅ machinery; scenes to author |
| Dialogue with distinct voices | Dialogue runner + dialogue-script@1.2, portraits | ✅ |
| Staged story (opening beats, transitions) | Cutscene Director + runner (just built) = the doc's `cinematic_director` | ✅ |
| Optional tutorial combat | Encounter zones + data-skill battle | ✅ |
| Persistent choice flags | WorldState flags/vars + Save 2.0 | ✅ substrate |
| Music cues (`music.auregate_*`) | Audio Director key door (Suno seam) | ~ seam only |
| Cast + portraits + bodies | Casting chain, ULPC bodies, figure portraits | ✅ (needs age variants) |

The director roster maps cleanly onto our chairs: lore_director = Lore
Keeper, character_director = Casting/NPC, dialogue_director = Dialogue
Writer, gameplay_director = Systems, cinematic_director = Cutscene
Director, scene/encounter/asset directors as named. **Only
continuity_director is a genuinely new chair.**

## The gaps — net-new PLATFORM capability

1. **The sequence tier itself (biggest gap).** Our `arc` (beats.json)
   ≈ ONE of this document's segments. There is no artifact that
   composes segments, declares `persistent_outputs`/`hidden_outputs`,
   holds entry/exit conditions, or owns a `revelation_plan`. Need:
   `sequence@1` + `segment@1` schemas (Story Director's tier above
   arcs), and a **state ledger** — the declared named outputs
   (`caden_selected_class`, `incident_interpretation_*`) a gate
   verifies are each produced by some segment and consumed where
   referenced. WorldState is the runtime substrate; the ledger is the
   contract over it.

2. **A SequenceRunner (engine).** Drives segment → segment, checks
   entry/exit conditions, persists the declared outputs, saves
   mid-sequence. New autoload/scene; the spine everything hangs on.

3. **Segment types.** Each `segment_type` is a playable shape the
   engine must support:
   - `playable_exposition` (classroom) — light exploration + talk +
     **inspection points** (examine → exposition text). We have
     talk/teleport interactables; EXAMINE-for-text is new + small.
   - `playable_hub` (welcome_fair) — bounded exploration with
     **required stations** (visit-tracked interactables carrying a
     demo + companion reaction + foreshadowing) and an "all seen or
     exit" completion. Station abstraction is new.
   - `ritualized_player_choice` (class_choice) — a **choice ceremony**
     (enter, speak professor, take seat, confirm, irreversible). New
     interaction, and it commits to the class system (gap 4).
   - `formative_crisis` (incident) — **DESIGN-BLOCKED** (the doc marks
     it `missing_core_design`).

4. **The class/discipline system (Systems + Interface).** Five
   disciplines (shaper/steward/weaver/breaker/mentarch) as data:
   `class@1` — starting attribute bonus + initial learnable ability
   pool (skill@ ids) + visual/equipment markers. Class choice assigns
   these and persists. We have skills and stats; class BUNDLES them and
   adds a choice screen. Gates: stat-budget on the bonus, every ability
   in the pool is a real skill.

5. **Multiple protagonists + player-control model.** Caden AND Vec are
   both protagonist; the player picks classes for both; who the player
   embodies per segment is `unresolved` in the doc. Our engine has ONE
   `OverworldPlayer` and a fixed party. Substrate to build: a segment
   can name its controlled character (and swap). The MODEL itself
   (single-PC vs multi-PC) is **human-blocked** (`exact_player_
   control_model`).

6. **Fragmented revelation / flashback.** Replayable segments/cutscenes
   that ADD information on replay, keyed to player-knowledge flags,
   preferring "withheld camera framing / missing dialogue" over false
   narration. Our cutscene runner plays a FIXED doc. Need a **fragment
   layer**: variant reveals gated by knowledge flags + a fragment-order
   policy. Mechanism is buildable; the specific `fragment_release_
   order` is **human-blocked**.

7. **Continuity Director (new chair).** The doc's `continuity_rules` +
   `validation.narrative_checks`. Mechanical ones are gate-able
   (equal_starting_status = no wealth/status gap in the relationship
   model; isaac fixed weaver; arc-independent-of-class; output
   completeness). Judgment ones (isaac_not_telegraphed, fragment_
   fairness) are skill-level. Need `automap/continuity.py` +
   `/continuity-director`.

8. **Richer quest objectives.** game@ quests are `reach_zone`/`talk_to`
   only. The prologue wants visit-station, choose-class, confirm
   triggers. A Systems/Quest extension (new objective types).

9. **Inspection + codex (small).** `inspect_*`, `journal_or_codex` — an
   examine interactable feeding an optional codex UI (Interface).

10. **Age variants (Asset/Casting content).** `caden.age11` /
    `caden.age15` etc. Creatures are single-age; ULPC child/teen/adult
    body types already exist — needs a per-age build-spec convention.

## The gaps — CONTENT to author (on existing/new machinery)

- Auregate scenes: classroom (age 11), welcome fair (age 11), five
  specialty-wing rooms (age 15), the incident scene (blocked).
- Cast: the professor; Caden/Vec/Isaac at ages 11 and 15 (age variants).
- Dialogue sets (7 named, `unwritten`): peer banter, professor
  instruction, five station reactions, three class-choice scripts, the
  incident (blocked).
- The prologue itself transcribed into `sequence@1`/`segment@1`.

## HUMAN-BLOCKED (design decisions the platform cannot invent)

The document flags these itself (`validation.completeness.blocked`,
`human_review_required: true`). They gate ~half the sequence:

- **The incident** (`prologue.incident`, `missing_core_design`) — the
  9 `unresolved_design_questions` (what happens, who is lost, Caden's
  punishment, Vec's choice, Isaac's evidence, failed vs successful
  Nudge…). The whole 4th segment and its dialogue are blocked on this.
- **Protagonist naming strategy** (immediate vs relational labels vs
  late reveal).
- **Player-control model** (single-PC vs multi-PC swap across segments).
- **Character voice profiles** (Caden/Vec/Isaac `to_define`).
- **Fragment release order** (which fragment reveals what, when).

## Proposed phases (each ends runnable; capability before content)

- **NS0 — Ratify the contract (names before machinery).** `sequence@1`
  + `segment@1` schemas; a Story-Director-tier "sequence" chair;
  transcribe the prologue into a VALIDATED platform document (blocked
  segments become `to_author`/`unresolved` fields). Structural gate:
  every participant is castable, every referenced scene/dialogue/class
  exists or is marked to-author. Mirrors the R1 move. No engine changes.
- **NS1 — State ledger + SequenceRunner.** The runtime spine: segment
  transitions, declared-output persistence, entry/exit conditions,
  save mid-sequence. Verified on a 2-segment toy sequence headless.
- **NS2 — The class/discipline system.** `class@1` (five disciplines),
  the choice ceremony, persistence — unblocks `class_choice` and is a
  real game system standalone.
- **NS3 — Segment types 1 & 2 + the Auregate content.** Inspection
  points, station abstraction, completion triggers; author classroom +
  welcome_fair with age-11 cast and scenes (needs NS4 age variants in
  parallel).
- **NS4 — Age variants + Auregate cast/scenes (content).** Caden/Vec/
  Isaac × {11,15}, the professor, the six+ environments — mostly
  authoring on existing machinery.
- **NS5 — Continuity Director + fragment mechanism.** The continuity
  gate + skill; the replayable-fragment layer (mechanism only —
  ordering deferred to the human decision).
- **BLOCKED — the incident.** Not a build task until the human answers
  the incident design questions, the control model, and voice profiles.

## Recommendation

Start at **NS0** regardless of the blocked decisions: transcribing the
prologue into a validated `sequence@1` document is "names before
machinery," depends on none of the blocked items (they become explicit
`unresolved` fields), and the gate immediately tells us exactly what's
missing — turning this analysis into a living checklist. It also lets
the human make the blocked design calls against a concrete artifact
instead of prose.

Note the strategic shift this represents: the vaporis/fair world was
the **proving ground**; the Shared Origin prologue is the **actual
game** (its characters are already canon in the originals region). The
sandbox stays as the test bed; the prologue is the first real product.
