# Minimap — a modular UI component fed by the world model

**Status: built, 2026-07-13.** The engine's UI kit gains its first
self-contained module, and the pipeline gains one more world-model consumer.

## Two halves, one contract

**Pipeline half (`automap/minimap.py`):** the minimap is *not a screenshot* —
it's a cartographic render of `features.json` in the visual identity's
colors (ground = grass tone, water, width-true roads, building footprints in
wall color). The identity keeps being the context→visuals link: the postapo
Plateau's map is dead-olive and brick-dark; a madelinot map is postcard
bright. Stage 6 emits `<stem>.minimap.png/.json` beside the styled glb;
stage 7 publishes them as `minimap.png`/`minimap.json` next to the scene —
the env.json pattern. The JSON is the contract: origin_x/origin_z, m_per_px,
width/height (north-up; +z is map-down).

**Runtime half (`godot/ui/minimap.tscn|gd`):** a single Control instanced in
the game shell (so every published scene inherits it). Its modularity rules:

- resolves whatever `map_loader` loaded (new `loaded_dir` property — the
  generic sidecar seam env.json already used implicitly);
- **hides itself when a scene ships no minimap** — drop it in any shell and
  it works or stays out of the way;
- no hard game-layer dependency: it connects to `GameEvents` only if the
  autoload exists, then shows the active objective as a rim-clamped dot.

Rendering: north-up scrolling crop centered on the player
(`draw_texture_rect_region`), view-direction arrow from the active camera's
yaw, ~80 m view radius.

## Verified

Pixel-exact color/transform unit tests (identity colors land where features
are; resolution capped for huge scenes). Integration: minimap visible on
lagrave, texture loaded, player position maps inside bounds — ALL PASS. Live
capture on plateau shows map + arrow + the fallback quest's objective dot.

## Follow-ups

- Ruins on the map: collapsed buildings could draw as rubble outlines
  (the world model knows; the renderer currently draws all footprints alike).
- NPC dots (world director knows the spawns; needs a GameEvents signal or
  group scan — keep the bus discipline).
- Fog-of-war / explored mask, full-map overlay on a key — later, when a
  game asks for them.
- `minimap.json` graduates to platform-specs when a second consumer reads it.
