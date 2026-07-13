# Crumble engine — decrepit, not dismembered (styling slice 3)

**Status: built, 2026-07-13.** Playtest mark: "most buildings are missing
walls — postapo or bug?" Answer: **both**, and each got its fix.

## The diagnosis

1. **Bug (the big one):** `_textured_walls` had the outward-normal sign
   flipped — for a wall triangle the glTF front-face normal is
   `(-edge.z, edge.x)`, not `(edge.z, -edge.x)` — so **every textured wall
   wound inward**, and with all 579 materials single-sided, near walls were
   back-face-culled. What read as facades in renders was often the interior
   of the *far* wall. An unintended consequence of the texture slice, exactly
   as suspected. Fixed + regression-tested for both footprint orientations.
2. **Concept:** the damaged decay state removed the roof and dropped whole
   parapet corners (`top_offsets`), which even when rendered correctly reads
   as *removed geometry*, not decay.

## The replacement: `automap/crumble.py`

A **modular pattern engine** — the platform component that turns the game's
*context* (post-apoc, carried by the identity's decay dials) into *visuals*.
Deliberately geometry-free and numpy-only: it emits deterministic patterns;
renderers turn them into meshes or texels. It incubates in Automap per the
module-boundary rule and earns its own repo at the second consumer (terrain
erosion, road cracking, coastline nibbling are all the same math).

- `fbm1d(n, rng)` — smoothstep value-noise fBm, the noisy-random primitive.
- `crumble_profile(length, height, severity, rng)` — one wall's eroded top
  edge: ragged fBm parapet (≤28% × severity), corner bites (walls crumble
  from their free ends), at most one gaussian breach whose chance grows with
  severity. **Hard floor at 1.5 m: sections crumble, walls never vanish** —
  that guarantee is the module's reason to exist, and it's a test.

## Consumption (`presentation.py`)

Damaged buildings now build **segmented wall strips** whose top edges follow
per-wall crumble profiles (`_crumbled_walls`) — textured with the same
storey-tile UVs, or flat-colored when the identity has no textures block.
The old `top_offsets` hook is gone. A soot-dark debris floor sits just above
grade, visible through breaches. Identity dials arrive via the additive
`crumble` block (`visual-identity@2.2.0`): severity range, segment spacing,
breach chance; `postapo.json` pins severity 0.4–0.85.

## Verified

Winding: all faces outward for CW and CCW footprints (unit test). Crumble:
deterministic, severity-monotone, ≥1.5 m everywhere (7 engine tests). All
four walls present on damaged buildings with outward winding (integration-
style unit test). Suites: 193 Python green, both Godot headless suites ALL
PASS, plateau republished (19.3 MB) — renders show complete buildings with
eroded silhouettes, breach notches, and visible near-wall facades.

## Follow-ups

- Breach debris: rubble spill at the foot of each breach (the profile knows
  where; `rubble_parts` knows how).
- 2D crumble masks (`crumble_mask2d`) for texture-space erosion — waits for
  its consumer per the module rule.
- Remnant rubble stubs could take crumbled top profiles too (they're boxes).
- The engine's second consumer decides when `crumble` graduates to a repo.
