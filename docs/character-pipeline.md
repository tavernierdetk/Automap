# Automap — Character Pipeline

A readable tour of how a **photo of a person** becomes a **recognizable character you
walk around as** — the stages, the contract that ties them together, and a step-by-step
runbook for the one stage that needs a local model.

This pipeline runs *alongside* the scene pipeline (which turns drone footage into a
walkable world). For the scene side see [the primer](primer.md); for the architectural
rationale see [the design spec](2026-06-30-automap-pipeline-design.md) §8.

---

## 1. The big picture

The character pipeline mirrors the scene pipeline's shape — **a chain of swappable
boxes** — applied to the player:

```
  input/CharacterReferences/   named traits          person.tres            Godot
   *.jpg  (a portrait)   ──▶   blonde / slim / …  ──▶  CharacterProfile  ──▶  (walk around
                               local vision model      (text, committed)      as them)
   capture / drop zone         Stage C                 the contract          Stage A
   newest photo is used        Ollama VLM              .tres resource        primitive figure
```

The goal is **recognition by high-level traits** — hair colour and style, build,
height, glasses, skin tone — *not* a photoreal face scan. That keeps it light on the
M4, private, and reproducible.

Three principles, same as the scene side:
- **The contract is a tiny text file.** A `CharacterProfile` (`.tres`) is the seam every
  stage speaks. It's committed to git; the rendered model is regenerated from it, never
  stored. No binary ever enters the repo.
- **Stages are swappable boxes.** The thing that *reads the photo* (Stage C) and the
  thing that *renders the figure* (Stage A/B) can each be replaced without touching the
  other — they only care about the profile in between.
- **Local & private.** The photo is read on this machine and sent only to a local model.
  It never leaves the Mac.

**Lettered, not numbered** (A/B/C) to keep it distinct from the scene pipeline's stages
0–4.

---

## 2. The contract — `CharacterProfile`

One schema, spoken by every stage. Defined in `godot/scripts/character_profile.gd`,
stored as text `.tres` under `godot/profiles/`.

| Field | Type | Meaning |
|---|---|---|
| `height_m` | float 1.4–2.1 | standing height in metres (the hard one — see §5) |
| `build` | float 0.8–1.3 | body width: slim → average → broad |
| `skin_color` | Color | linear RGB |
| `hair_color` | Color | linear RGB |
| `shirt_color`, `pants_color` | Color | clothing colours |
| `hairstyle` | enum | `bald` / `short` / `medium` / `long` / `ponytail` / `afro` |
| `glasses` | bool | |
| `facial_hair` | bool | |

Two samples ship in the repo: `godot/profiles/default.tres` and `example.tres`. You can
hand-write one in a text editor or the Godot inspector — Stage C just automates writing it.

---

## 3. Stage by stage

### Stage A — Build the figure · `godot/scenes/character.tscn` + `character.gd`  ✅ built
| | |
|---|---|
| **Reads** | a `CharacterProfile` (assigned on the player's `Body` node) |
| **Writes** | the visible, animated character in-engine |
| **Tool** | Godot 4.4 |

`character.gd` reads the profile and configures a primitive rig: scales by `height_m`,
widens by `build`, colours skin/hair/clothes, shows the matching hairstyle, toggles
glasses and facial hair — then animates it.

**This rig is `figure-2` — the platform's out-of-the-box character tier.** Every
game the studio produces gets it for free; richer tiers (`skeletal-3`: Skeleton3D
on Godot's humanoid bone profile; styled/skinned bodies from asset-factory) are
future opt-ins, and `figure-1` (the box-torso original) is retired. The tier enum
enters the game spec only when a second live tier exists to select on; until then
this scene is the tier's reference implementation and the gallery renders below
are its acceptance images. Rationale and roadmap:
[character-runtime-stack](explorations/character-runtime-stack.md).

The v2 rig (2026-07-15) is articulated
and has a face: human 7.5-head proportions, tapered chest/pelvis, two-segment limbs
with knee/elbow flexion in the gait, hip/shoulder counter-rotation, body bob and
lean while walking, plus an idle layer (breathing, blinking, weight shifts, slow
head wander) that keeps stationary NPCs alive. Eyes/brows/nose/mouth/ears are part
of the face; glasses are torus frames. Still all procedural primitives — no binary
assets — and the body remains a swap-point: a real rigged model can replace it
without the controller changing.

**Inspect:** open `godot/scenes/game.tscn`, press **F6**. Edit `profiles/default.tres`
in the inspector and watch the figure rebuild. For a quick render of several
profiles (front / three-quarter / portrait to `work/character_gallery/*.png`):
`/Applications/Godot.app/Contents/MacOS/Godot --path godot res://tests/character_gallery.tscn`
(needs a window; the headless driver renders nothing).

### Stage C — Read traits from a photo · `scripts/char_photo_to_profile.py`  ✅ built & working
| | |
|---|---|
| **Reads** | newest image in `input/CharacterReferences/` (or a path); read locally, never uploaded |
| **Writes** | `godot/profiles/<name>.tres` |
| **Tool** | Ollama + a vision model (`qwen2.5vl:3b` by default) |
| **Logic** | `automap/character.py` (schema, mapping, `.tres` rendering) |

The model is asked for **categorical** traits — a build category and *named* colours
(`blonde`, `red`, `fair`…) rather than raw numbers, because small vision models pick
from a list reliably but invent poor RGB/floats. `automap/character.py` maps those names
to Colors/floats, so the Godot contract stays numeric. The response is validated (a
sloppy answer can't produce a broken profile) and written as a `.tres`. **See §4.**

### Stage B — Upgrade the fidelity  · *designed, not built*
Swap the render backend behind the same profile: **MakeHuman/MPFB2** headless in Blender
(reuses the scene pipeline's Blender) for a rigged parametric human, and/or **Mixamo** as
a retargeted animation library. The controller and the contract don't change.

---

## 4. Runbook — the Stage C spike

The spike is **done** — `qwen2.5vl:3b` reads all the categorical traits correctly
(build, skin tone, hair colour, hairstyle, garment colours, glasses, facial hair).
Height isn't asked of the model (a single photo has no scale); it defaults to a standard
**1.75 m (5'9")** unless you pass `--height`. This is the path to a profile from any photo.

### Step 1 — Install Ollama and pull the model  *(one-time)*
```sh
brew install ollama
ollama serve                 # leave running in its own terminal (or: brew services start ollama)
ollama pull qwen2.5vl:3b     # ~3.2 GB
```
Sanity check the server is up: `curl -s http://localhost:11434/api/tags` should return JSON.

### Step 2 — Dry-run a photo *(inspect, write nothing)*
Drop a clear, roughly front-facing photo in `input/CharacterReferences/`, then:
```sh
.venv/bin/python scripts/char_photo_to_profile.py --dry-run   # uses the newest photo there
# or name one:  ... scripts/char_photo_to_profile.py input/CharacterReferences/me.jpg --dry-run
```
This prints the parsed summary **and the exact profile that would be written** — but
touches no files. This is your iteration loop.

### Step 3 — Assess the attributes
Eyeball the printed profile against the photo:

| Trait | Good sign | If it's off |
|---|---|---|
| `hairstyle` | nearest of the 6 styles | tune the prompt; styles are coarse by design |
| `hair_color` / `skin_tone` | correct named colour (`blonde`, `fair`…) | lighting skews it — try an evenly-lit shot, or edit the map in `character.py` |
| `build` | slim/average/broad reads right | tune the prompt wording |
| garment colours | main top/bottom colour named | strong patterns confuse it; pick the dominant |
| `glasses` / `facial_hair` | true/false correct | usually reliable; a clearer face helps |
| `height_m` | defaults to 1.75 m (5'9") | not read from the photo — pass `--height` if known |

Run a few photos to get a feel for consistency.

### Step 4 — Tune if needed
Levers, all in `automap/character.py`:
- **`_PROMPT`** — sharpen wording for whatever it gets wrong.
- **`PROFILE_SCHEMA`** — the categorical enums the model must choose from.
- **`HAIR_COLORS` / `SKIN_TONES` / `BASIC_COLORS` / `BUILDS`** — the name→value maps.
  Adjust a colour by editing its RGB, or add a category (also add it to the schema enum).

If 3B is too weak on some trait, pull a bigger model: `ollama pull qwen2.5vl:7b`
(now that disk allows) then pass `--model qwen2.5vl:7b`.

The hairstyle set lives in **two places that must stay in sync**: `HAIRSTYLES` in
`automap/character.py` and the `hairstyle` enum in `godot/scripts/character_profile.gd`.

### Step 5 — Generate the profile
Drop `--dry-run` to write it, and set height by hand (a single photo has no scale):
```sh
.venv/bin/python scripts/char_photo_to_profile.py --height 1.68
# -> godot/profiles/<image>.tres
```

### Step 6 — Walk as them
In Godot, assign the generated `.tres` to the player's `Body.profile` (in
`godot/scenes/game.tscn`), then **F6**. You're navigating the scene as that character.

---

## 5. Known limits

- **Height is a guess.** A single photo carries no scale — the same problem stage 3 owns
  for scenes. The model gives a rough estimate; pass `--height <m>` to set it precisely.
- **Stylized, not a likeness.** Six hairstyles, primitive geometry, trait-level colour.
  Recognition comes from the *combination* of traits, not facial detail. Higher fidelity
  is Stage B's job.
- **Model-dependent quality.** A 7B vision model is good at coarse traits (hair, glasses,
  build) and weaker at subtle ones. The validation layer guarantees a *usable* profile
  regardless, falling back to averages for anything missing or out of range.

---

## 6. Verify the glue (no model needed)
The parsing/validation/rendering is unit-tested independently of Ollama:
```sh
.venv/bin/python -m pytest -q tests/test_character.py
```
These cover clamping out-of-range values, hairstyle fallback, `.tres` rendering, the
end-to-end write with a height override, and the dry-run (writes nothing) path.
