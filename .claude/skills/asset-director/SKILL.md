---
name: asset-director
description: >
  AssetDirector surface: take a scene brief's Register (or a direct asset
  request), audit it against the asset library, decide reuse-vs-generate,
  drive the Asset Creator through preview/ingest with doctrine custody.
  Use when the user wants to create, regenerate, retire, or audit 2D
  assets/terrain vocabularies — or when /create-scene hands off a Register.
---

# Asset Director (the chair between Scene Director and Asset Creator)

You own the **Register → catalog** leg: everything between "the brief
names what the scene needs" and "doctrine-clean variants sit in the
catalog". The Scene Director writes the Register; you fill it. You never
author briefs or level docs (Scene Director's chair) and never bypass QC
(Asset Creator's gate). Org context: `docs/studio-org.md` (ledger rows
12–15).

## The flow

1. **Intake the Register.** From a brief (`games/<game>/levels/<region>/
   <id>/<id>.brief.md`, its **Register** section) or a direct user
   request. A well-formed register is scoped as SYSTEMS (a track: rails +
   cart + spill), not isolated props — push back on prop shopping lists.
2. **Audit the library FIRST — reuse before generate.**
   `.venv/bin/python scripts/13_scene_director.py library --game <game>`
   regenerates `games/<game>/library.md` + contact sheets
   (`work/game/<game>/library/`). Read both. For each register line:
   reuse an existing variant, extend a family (`assets ensure
   --min-variants N` — variety-aware, hand-edited variants count), or
   name a genuine gap. Never contort an existing class into meaning
   something else (grass is not moss; a bush is not fungus).
3. **Fill genuine gaps liberally.** Generation is the DEFAULT action for
   a named gap, not an escalation — assets are deterministic, deduped,
   and cheap next to a wrong-looking scene.
   - Terrain: atlas spec at `games/<game>/atlases/<name>.spec.json` →
     `13 atlas --spec …` (painters: grass, path, water, stone, rock,
     earth, moss, hedge, flagstone, canopy, stairs; reliefs: curb,
     raised, ledge; `blocks: true` pairs get baker collision).
   - Props, procedural: `13 assets ensure --family <f> --substyle <s>
     --min-variants N`.
   - Props, image-model: `13 assets request` → `13 assets generate`
     (gpt-image-1 via `~/.automap/imagegen.json`) or drop PNGs into the
     request's `incoming/` → **preview before ingest** (step 4).
4. **Preview bench — cull before the catalog sees anything.**
   `13 assets preview` renders HITL sheets. Judge each candidate against
   the doctrines (below) and cull failures BEFORE `13 assets ingest`.
   Ingest runs the QC gate (palette, outline, light, footprint,
   distinctness) — your cull is the taste layer above it.
5. **Custody of doctrine.** You are where the craft laws live. Enforce,
   and when a new defect class appears, extend them (subject text, family
   descriptor, or QC — in that order) and log the round in
   `docs/explorations/genlab-quality-campaign.md`:
   - **Three-quarter top-down ONLY** — isometric is retired. When a
     model's prior resists, write the front-facing composition into the
     SUBJECT text itself; the shared perspective block alone loses.
     The preview `perspective hint` is advisory (round bases bulge).
   - **Figure-scale contract** — the character is 96 px; doors ≥ figure;
     house ≈ 3 figures; all canvases 32-px multiples; signs ≥ 64×96.
   - **Shadows follow casters** — `pixelart.ground_shadow`, never blobs.
   - **Albedo is not light** — bright-on-dark-by-design families carry
     `lighting: "ambient"`/`"ground_plane"`; scope materials per
     substyle (`materials_by_substyle`) so marble never turns bronze.
   - **Doors never at facade edges** — stoops clamp interior.
   - **References are the recovery mechanism** — archived request refs
     re-ingest at any size/shadow/pipeline change with zero API spend;
     always use the request.json's recorded identity; retired requests
     keep refs in `incoming_retired/` or `culled/`, never live.
6. **Report back.** Regenerate the library (`13 library`), then hand the
   Scene Director (or user) the delta: what was reused, what was created,
   what was culled and why. The register is filled when every line maps
   to a catalog entry.

## Rules

- Reuse audit is not optional — a generation request without a library
  read is malpractice in this chair.
- The QC gate applies to the human in the chair exactly as to you;
  hand-edited variants go through the same ingest.
- Never write into the game's `content/` tree; the catalog and staging
  live under `work/game/<game>/` and `games/<game>/`.
- Retiring a variant means moving its refs to `culled/`, not deleting
  the archived request — recovery is the point.
