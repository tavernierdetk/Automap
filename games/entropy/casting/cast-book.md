# The cast book — game `entropy`

Owned by the **Casting Director** (docs/studio-org.md, ledger rows
5–10). The roster of who exists to be cast; per-scene casting sheets
(`<level>.json` beside this file) bind roster members to a baked
scene's `npc_slots` and are gated at publish (slots exist, creatures
built, dialogues real, regions legal per R-005, canon people admitted).

Speaking, named cast members are ALSO canon persons (the Lore Keeper
admits them); silent background archetypes only need creature
documents. Sprites may be shared across background members (the
sheet's `sprite` field) — five students walk the fair wearing two
faces, which is what school uniforms are for.

## Region: vaporis

| creature | name | archetype | canon | sprite | notes |
|---|---|---|---|---|---|
| prefect_cassia | Prefect Cassia | official | canon | own | gate duty; arc `fair_opening` b1 |
| magister_brontes | Magister Brontes | artisan | canon | own | machine show; arc b3 |
| porter_felix | Porter Felix | official | canon | own | ticket house |
| barker_vox | Vox the Barker | performer | canon | own | the promise, arc b2 |
| vendor_prisca | Prisca | vendor | canon | own | sweets stall |
| vendor_naso | Naso | vendor | canon | own | salvage stall; has the valve, arc b4 |
| operator_druso | Druso | laborer | canon | own | wheel operator; arc b5 |
| keeper_mirella | Mirella | performer | canon | own | carousel keeper |
| child_pippa | Pippa | child | canon | own | carousel court |
| cook_bassa | Bassa | artisan | canon | own | food court |
| professor_gaius | Professor Gaius | scholar | canon | own | food court, off duty |
| apprentice_tullo | Tullo | artisan | canon | own | Brontes' apprentice, graded on the boiler |
| dreamer_naia | Naia | scholar | canon | own | pond corner |
| gardener_silvo | Silvo | laborer | canon | own | hedge garden |
| student_aulus | Aulus | scholar | — | own | background |
| student_livia | Livia | scholar | — | own | background |
| student_metto | Metto | scholar | — | shares `student_aulus` | background |
| student_pella | Pella | scholar | — | shares `student_livia` | background |
| student_varro | Varro | scholar | — | shares `student_aulus` | background |
| stroller_flora | Flora | official | — | shares `student_livia` | background |

## Region: originals (imported)

Alpha, Bravo, Caden, Carmilla, Isaac, Lily, Vec, Zo — reference-frame
sprites, cast only in `originals` scenes (R-005).

## Sheets

- `vaporis_fair.json` — all 20 sockets filled (16 generated sprites,
  3 shared). First populated scene of the platform.
