# The Incident — the Weirgate Release (resolved 2026-07-18)

The prologue's fourth segment, designed and its five forks resolved by
the human. **Caden is genuinely to blame** — the darker reading. This
is the Story Director + Lore Keeper's design, recorded as PROPOSED canon
(bible R-006), to be reconciled with the rebuilt `Entropy RPG.md` (a
two-way build/reference alignment, not subordination).

## The event — the Weirgate Release

The capstone of a Gatewright education: newly-disciplined seniors (Caden,
Vec, Isaac, ~15–16) are brought to **observe a real Nudge**. The Road
predicts the ancient **Weirgate flood-locks** — above a market town
packed for the harvest fair — will fail. The Gatewrights' sanctioned
Nudge is a **controlled release**: redirect the crowd, drain the
pressure, at the cost of a small **"acceptable" number** too close to
the gates to clear in time. Among that written-off number is
**Professor Wren**, the trio's own teacher, caught at the waterline.

Caden **breaks ranks to save her.** **Vec throws himself in Caden's
path to stop him** — the two struggle in the rising water (**the
incident's combat**). Caden breaks past, reaches Wren, and pulls her
free. The disruption to the controlled release is a heartbeat too much:
the Weirgate fails **catastrophically** and the flood takes the town.
Caden saved his teacher and drowned hundreds. **He knows it.**

That is the truth, not a misframing. The fragments deepen the horror;
they do not lift the guilt.

## The nine questions, answered

1. **What physically happens?** A supervised Gatewright Nudge — a
   controlled release at the Weirgate locks — is disrupted by a
   student and becomes a catastrophic flood during a harvest fair.
2. **Who is lost?** The town — hundreds, far past the predicted cost.
   The named figure of significance, **Professor Wren**, is the one
   Caden SAVES (not lost) — she survives, bearing it, her future role
   in the story reserved.
3. **What does Caden save?** Professor Wren, his teacher, marked among
   the Nudge's "acceptable losses" at the gate. He succeeds — that is
   the tragedy.
4. **What punishment does Caden receive?** Public blame as the reckless
   student whose deviation caused the flood; **expelled, his discipline-
   mark struck**, sent away in disgrace. Here the public story and the
   truth AGREE that he caused it — the institution needs only to hide
   that it foresaw him. The Road stays trusted.
5. **What does Vec choose?** He **physically tries to restrain Caden**
   — the combat — and **fails**. He was right, he acted, and he wasn't
   ruthless enough to stop his friend. Hundreds died in the gap between
   his grip and his mercy.
6. **What does Isaac find or conceal?** As a **Weaver** (the discipline
   that assists prediction-work) he is near the Gatewright's
   **prediction-slate**. It named the flood's **true toll — the
   hundreds — before the event**, not the "acceptable few" the students
   were told. The Nudge's promised cost was a lie, or the deviation was
   foreseen. He says nothing and **pockets a copy.**
7. **Failed, successful, or off-Road Nudge?** A Nudge the Road had
   **already written to end in the true flood** — the "controlled
   release" and its "acceptable number" were the story told to the
   students. Publicly: a successful Nudge ruined by a reckless boy.
   Concealed: the outcome was foreseen and permitted, and Caden's mercy
   was its predicted trigger. He is both guilty and used.
8. **Separated afterward?** Yes, immediately. Caden exiled (disgrace →
   **redemption**), Vec retained and quietly commended for trying to
   hold the line (validation of control → **corruption**), Isaac
   graduates and begins his inquiry (obsession → **antagonist**).
9. **Hidden in the first presentation?** That the slate named the true
   toll beforehand; that the deviation was foreseen; that the "acceptable
   number" was a fiction; Wren's knowledge of any of it. The player-
   observed FACTS — Caden broke past Vec, saved Wren, the gate failed,
   the town drowned, he was cast out — are all TRUE and stay true. What
   fragments add is that it was *foreseen*, not that it was *not his*.

## Three lessons from one event

- **Caden → redemption.** He genuinely traded a town for his teacher,
  from love, and cannot undo it. His is the hardest redemption: earning
  the right to exist after real, unforgivable harm from a good impulse.
  Fragments reveal he was foreseen and used — which sharpens the horror
  without lifting the blame. *(compassion_associated_with_catastrophic_
  cost; trust_in_self_or_institutions_damaged)*
- **Vec → corruption.** He tried to stop Caden and lost the struggle;
  had he been stronger, harder, willing to truly hurt his friend, the
  town would live. Lesson: mercy toward the one who would deviate is
  paid for by the many; restraint must be absolute, control total.
  His goodwill becomes the engine of coercion. *(order_associated_with_
  prevention; autonomy_associated_with_unacceptable_risk)*
- **Isaac → antagonist.** The slate KNEW the true toll. The Road does
  not merely guide — it foresees, or is made to, and whoever reads or
  writes the prediction holds the only real power. He must learn how.
  *(uncertainty_associated_with_power_or_truth; motivation to
  investigate or exploit the Road)*

## The combat — Vec restrains Caden

The incident's mechanical centerpiece: a **story-battle at the gate** in
the rising water, Vec against Caden, fought as their chosen disciplines
(so the class choices pay off — the tutorial_policy's "the incident may
test the chosen classes"). The **outcome is fixed** — Caden breaks past
and reaches Wren, whatever the player does — a formative struggle, not a
win/lose gate. Whose side the player fights it from is the
`exact_player_control_model` decision; for the slice the player is Caden,
so the fight is Caden vs Vec from Caden's side.

**Built (2026-07-19).** The forced-outcome story-battle mode is in
`engine/combat/battle.gd`: a `story` spec on the pending battle makes it a
scripted struggle — nobody falls (hp held at ≥1), it runs a turn budget and
ends on the FIXED outcome (`caden_breaks_past`), Run *is* breaking past, and
both sides fight as their chosen discipline (class stats + ability pool).
The `formative_crisis` handler orchestrates it windowed: `the_weirgate`
setup cutscene → the Vec-vs-Caden story-battle → `the_weirgate_aftermath`
→ the segment completes with the three worldview flags. Headless drives the
state directly (`test_story_battle` proves the mode; `test_prologue` the
flow; `incident_windowed` proves the whole chain in real play).

**Weirgate backdrop — wired, image pending.** Battles now take a
per-encounter `backdrop` (`battle_ui` falls back to the default when the
named background isn't published), and the incident asks for `"weirgate"`.
The publisher publishes game-owned backgrounds from
`games/entropy/backgrounds/`. The one missing piece is the image itself:
generating it hit the **image-API billing hard limit** (raise the cap, then
run the one-off prompt → drop `weirgate.png` into
`games/entropy/backgrounds/` → publish; the battle upgrades automatically,
no code change). Until then the incident battle shows the default backdrop.

## The pruning seed (incidental now, evidence later)

Isaac's slate: the casualty list matches the **full flood (hundreds)**,
dated before the release — not the "acceptable few." First presentation:
a boy pocketing a slate — reads as evidence to defend Caden, or a
keepsake. Late-game fragment: the prediction named the true dead because
this branch was *read before it was lived* — foreknowledge that becomes
the pruning reveal. **No mechanism words are spoken** — no branch, copy,
prune — only a casualty list that is too complete, too early.

## Fragment plan (deepens, never exonerates)

- **Fragment A (Isaac's eye):** the slate's true toll, dated before the
  release — the "acceptable number" was a fiction.
- **Fragment B (the Gatewright's word):** the deviation was expected;
  Caden's mercy was the predicted trigger, permitted.
- **Fragment C (Wren):** what the professor understood as Caden pulled
  her free — the seam to her reserved future role.
Each adds material information; none contradicts a visible fact; Caden's
guilt survives every one.

## Resolved forks

1. **Caden's blame:** REAL. He caused it; the horror is that it was
   foreseen. Redemption from genuine guilt.
2. **The named figure:** Professor Wren, a Weaver-professor, SAVED by
   Caden; survives; future role reserved.
3. **The disaster:** the Weirgate flood.
4. **Vec:** physically restrains Caden — a story-battle he loses.
5. **Reconciliation:** with the rebuilt `Entropy RPG.md` (a
   build/reference doc realigned to this engine); two-way, pending
   human ratification.
