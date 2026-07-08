# Capture guide — filming drone footage that reconstructs well

The pipeline can only rebuild what the footage actually saw from enough angles.
Map quality is decided at capture time far more than by any pipeline knob. This
guide is the field recipe; read it before the next shoot.

## The one idea
Photogrammetry recovers 3D by triangulating the **same surface point seen in many
overlapping images from different positions**. So every surface you want in the
map must be:
1. **textured** (matchable detail, not blank), and
2. **seen from many viewpoints** with high overlap between consecutive frames.

Everything below serves those two requirements.

## Post-mortem: why the `phare` clip reconstructed poorly
It was a cinematic flyby, not a mapping mission. The numbers show it:

- **~394 features/image** (healthy is thousands+). Each frame was ~40% sky and
  ~30% moving sea — textureless, unmatchable pixels. Water changes every frame.
- **2,796 sparse tie points / 106 of 120 images** registered — a thin, weak solve.
- **Single-pass, single-sided trajectory** (a straight descent toward the
  lighthouse). ODM fell back to a "single-line → vertical prior" alignment. The
  tower was only ever seen from one side, so its other faces can't exist.
- **Huge scale jump** — from a km-wide aerial coast view to a ground-level
  close-up on a deck. Fusing those viewpoints is what split the model.

None of that is fixable in post. The fix is how you fly.

## Rules for the next flight

**Overlap — the non-negotiable.**
- **70–80% front overlap** (successive frames) and **60–70% side overlap** (between
  passes). In practice: fly slow, and if you're extracting ~1–2 frames/sec, keep
  ground speed low enough that the view barely changes frame to frame.

**Choose a pattern for the subject:**
- **Terrain / area** (fields, coastline, a site) → **nadir grid ("lawnmower")**:
  camera pointing straight down, parallel passes with side overlap, constant
  altitude. Feeds the **terrain-first** path (`--terrain` / `--style`).
- **A structure / object** (lighthouse, building, monument) → **orbit rings**:
  circle the subject at a constant radius with the camera locked on it, then do
  **2–3 rings at different heights** (e.g. low, mid, high) and radii, plus a few
  higher oblique/near-nadir passes over the top. Feeds the **mesh-first** path
  (default `sraw`, styling off). This is what `phare` needed and never got.

**Framing:**
- **Keep sky, horizon, and open water out of the frame.** Fill it with the
  textured surface you're mapping. A frame that is half sky is half wasted.
- Use **oblique angles (~45°) as well as nadir** for anything with vertical faces —
  nadir alone never sees walls.

**Consistency:**
- Hold **one altitude band** per mission; don't mix a wide aerial with a ground
  close-up in the same clip. Do those as separate captures/scenes.
- **Even, diffuse light.** Overcast is fine (no harsh shadows); avoid changing
  exposure and avoid direct sun glare off water.
- Keep moving subjects (waves, traffic, people) to a minimum — they can't match.

**Coverage:**
- Get **all sides** of a structure and overshoot the edges of your area — the
  reconstruction thins out at the margins.

## Feeding the pipeline
- Aim for a clip that yields **~150–400 usable frames** of the subject after
  culling. More well-overlapped views ≈ better, up to the M4 memory ceiling.
- The DJI telemetry (embedded subtitle track or `.srt` sidecar) is auto-used for
  georeferencing — good GPS spread (an orbit, not a line) also helps the solve.
- Extraction rate lives in `config.toml [frames]` (`fps`, `max_frames`); ODM
  quality knobs in `[odm]`. Higher quality = more memory/time (16 GB is the ceiling).

## Pre-flight checklist
- [ ] Overlap: slow ground speed, 70–80% between frames
- [ ] Pattern chosen: nadir grid (terrain) **or** orbit rings (structure)
- [ ] Camera angle: nadir for ground, +45° obliques for anything vertical
- [ ] Frame is full of textured surface — **no sky / horizon / open sea**
- [ ] All sides of the subject covered; area edges overshot
- [ ] One altitude band; consistent exposure; diffuse light
- [ ] Right pipeline mode: `--style`/`--terrain` for terrain, plain mesh-first for structures
