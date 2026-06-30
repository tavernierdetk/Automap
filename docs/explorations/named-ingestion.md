# Exploration — Named ingestion (SRT + MP4 + name → a scene)

**Status:** Exploration / brainstorm. Nothing built. Closer to buildable than the
[feature-substitution](feature-substitution.md) work — it's mostly making the
pipeline *multi-scene*, not new capability.

**Goal:** one command takes a video, its optional `.srt`, and a name, and produces
"a scene by that name."

```
ingest.py --name birch-park --video clip.mp4 --srt clip.srt
   └─ runs stages 1 → 2 → 3 against per-scene paths → birch-park.glb (+ registers it)
```

---

## What it really implies

### 1. Multi-scene namespacing
Today the pipeline is hardwired single-scene:
`input/clip.mp4 → work/frames → work/odm → work/mesh/scene.glb`. Named scenes need
per-scene paths so they coexist without clobbering:

```
work/<name>/
  frames/        # stage 1
  odm/           # stage 2
  mesh/<name>.glb  # stage 3 output
  features.json  # (later) the semantic layer
```

This is a **path-parameterization refactor** of the three existing stages — low
effort, since the stages already work. Each stage currently takes explicit
`--input/--output`; the orchestrator just supplies the namespaced ones.

### 2. It's a scoped one-button orchestrator (and that's a tension)
The design spec deliberately *deferred* one-button orchestration so intermediate
failures stay visible ("inspect between each stage"). A named ingest **is** that
orchestrator. To honor the spec's intent rather than bulldoze it:

- keep every intermediate on disk (we already do — `work/<name>/…`),
- log each stage and where its artifact landed,
- support `--from <stage>` / `--stop-after <stage>` so you can still inspect,
  resume, or re-tune one stage (e.g., re-decimate without re-running ODM).

Conscious trade: we accept some "inspect between stages" discipline loss for
convenience, now that the stages are proven.

### 3. SRT gets promoted from no-op to useful
Today `.srt` is auto-detected and otherwise ignored. In a multi-scene world it
earns its keep: GPS gives ODM faster, **metrically-scaled** solves *and* consistent
**georeferencing across scenes** — which matters if several clips should line up
in space (e.g., multiple Îles-de-la-Madeleine flights of the same area).

### 4. "A scene by that name" — the contract question
This is the one piece that touches the **playback engine** (owned separately).
Generation can cleanly produce `<name>.glb`. But "scene" most likely means
*loadable in the walking engine by name*. That needs a small shared contract:

- where named glbs live (`work/<name>/mesh/<name>.glb`, or a published
  `scenes/<name>/`),
- a manifest the engine reads (e.g. `scenes/manifest.json` listing name → glb path
  → optional `features.json`).

**This is the thing to agree on with the playback side, not decide unilaterally.**

---

## Proposed shape (for discussion)

```
python scripts/ingest.py \
    --name birch-park \
    --video /path/clip.mp4 \
    [--srt /path/clip.srt] \
    [--from frames|odm|mesh] [--stop-after frames|odm|mesh]
```

Runs stage 1 → 2 → 3 with namespaced paths, prints each artifact location, and
writes/updates the scene manifest. Pure generation; hands a named glb to playback.

---

## Effort & why this is the good "next build"

- **Effort:** low-to-moderate. Refactor stage paths to be name-parameterized +
  a thin orchestrator + the naming/manifest contract. No new algorithms.
- **Leverage:** it builds the **scene-library foundation** — each scene a named
  folder. The feature-substitution `features.json` naturally lives *inside* that
  folder, so named ingestion is the structure the ambitious work plugs into.

**Natural overall sequence:** named multi-scene ingestion → terrain-first branch →
semantic/feature layer (trees).

---

## Open questions

1. Manifest format and location — and confirming the engine will read it (playback owns this).
2. Does ingestion publish glbs to a stable `scenes/` dir, or does the engine read
   straight from `work/<name>/`?
3. How strict do we keep the inspect-between-stages discipline (default to running
   all three, or pause for confirmation)?

---

Related: [pipeline primer](../primer.md) · [feature substitution](feature-substitution.md)
