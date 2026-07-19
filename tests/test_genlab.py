"""GenLab: prompt composer, drop lifecycle, repixel through the shared gate.

The reference image is SELF-GENERATED (a smooth, anti-aliased, decidedly
non-pixel-art tree painted with gradients) — same philosophy as stage 1's
synthetic clip: the suite proves the pipeline without any network or any
committed binary.
"""
import json

import numpy as np
import pytest
from PIL import Image

from automap import asset_creator, asset_qc, genlab, pixelart, repixel, trees_px

IDENTITY = {"name": "t", "canopy_color": (0.22, 0.42, 0.2),
            "trunk_color": (0.34, 0.26, 0.18), "cliff_color": (0.47, 0.45, 0.43),
            "water_color": (0.16, 0.36, 0.44), "path_color": (0.56, 0.45, 0.31)}
FAM = asset_creator.FAMILIES["tree"]


@pytest.fixture(scope="module")
def pal():
    return pixelart.master_palette(IDENTITY)


def synthetic_reference(w=384, h=512) -> Image.Image:
    """A smooth gradient-shaded tree on flat magenta — everything pixel art
    is NOT: anti-aliased edges, continuous shading, off-palette colors."""
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = (255, 0, 255)
    # trunk: vertical gradient brown column with flare
    cx = w / 2
    trunk_top, trunk_base = h * 0.42, h * 0.94
    t = np.clip((yy - trunk_top) / (trunk_base - trunk_top), 0, 1)
    half = 14 + 16 * t ** 2
    trunk = (np.abs(xx - cx) < half) & (yy >= trunk_top) & (yy <= trunk_base)
    shade_t = np.clip((xx - cx) / 40 + 0.5, 0, 1)
    for c, base, spread in ((0, 96, -50), (1, 70, -40), (2, 46, -26)):
        img[..., c] = np.where(trunk, base + spread * shade_t, img[..., c])
    # canopy: big radial-gradient green ball of overlapping lobes
    rng = np.random.default_rng(7)
    canopy = np.zeros((h, w), bool)
    for i in range(7):
        a = 2 * np.pi * i / 7
        lx = cx + np.cos(a) * w * 0.16
        ly = h * 0.30 + np.sin(a) * h * 0.10
        r = w * 0.20 * rng.uniform(0.8, 1.1)
        canopy |= ((xx - lx) ** 2 + (yy - ly) ** 2) < r * r
    d = np.hypot(xx - cx * 0.82, yy - h * 0.22)
    lit = np.clip(1.0 - d / (w * 0.55), 0, 1)
    for c, lo, hi in ((0, 30, 110), (1, 70, 190), (2, 26, 90)):
        img[..., c] = np.where(canopy, lo + (hi - lo) * lit, img[..., c])
    return Image.fromarray(img, "RGB")


# --- prompt composer ---------------------------------------------------------------

def test_prompt_is_deterministic_and_rich(pal):
    kw = dict(identity=IDENTITY, family="tree", substyle="deciduous",
              size_class="large", pal=pal, descriptor=FAM["descriptor"],
              materials=FAM["materials"])
    p1, p2 = genlab.compose_prompt(**kw), genlab.compose_prompt(**kw)
    assert p1 == p2
    for hexes in (pal["materials"]["foliage"]["ramp"],
                  pal["materials"]["wood"]["ramp"]):
        assert ("#%02x%02x%02x" % tuple(hexes[0])) in p1   # explicit palette
    assert "three-quarter" in p1                            # from descriptor
    assert "96x128" in p1                                   # target canvas
    assert "TOP-LEFT" in p1                                 # fixed key light
    assert "NO ground/cast shadow" in p1                    # pipeline adds it


def test_prompt_perspective_and_subject_vary(pal):
    a = genlab.compose_prompt(IDENTITY, "tree", "pine", "medium", pal,
                              FAM["descriptor"], FAM["materials"])
    b = genlab.compose_prompt(IDENTITY, "tree", "dead", "medium", pal,
                              FAM["descriptor"], FAM["materials"])
    assert "conifer" in a and "leafless" in b and a != b


def test_prompt_anatomy_is_per_family(pal):
    """Tree language must never leak into another family's prompt — the
    mine_hall arch failure (correction plan S4): the timber-frame prompt
    told the image model about canopy masses and trunk widths."""
    from automap.asset_creator import FAMILIES
    sup = FAMILIES["support"]
    p = genlab.compose_prompt(IDENTITY, "support", "timber", "large", pal,
                              sup["descriptor"], sup["materials"])
    for tree_word in ("canopy", "trunk", "leaf clumps", "bark"):
        assert tree_word not in p
    assert "wood grain" in p                      # its own texture motifs
    assert "posts clearly wider" in p             # its own anchor
    assert "NEGATIVE SPACE" in p                  # its prompt note
    # tree prompts keep their anatomy
    t = genlab.compose_prompt(IDENTITY, "tree", "deciduous", "large", pal,
                              FAM["descriptor"], FAM["materials"])
    assert "leaf clumps" in t and "trunk clearly wider" in t


def test_prompt_notes_key_by_substyle(pal):
    from automap.asset_creator import FAMILIES
    por = FAMILIES["portal"]
    arch = genlab.compose_prompt(IDENTITY, "portal", "arch", "large", pal,
                                 por["descriptor"], por["materials"])
    bricked = genlab.compose_prompt(IDENTITY, "portal", "bricked", "large",
                                    pal, por["descriptor"], por["materials"])
    assert "NEGATIVE SPACE" in arch
    assert "NEGATIVE SPACE" not in bricked        # a sealed mouth stays sealed


def test_cart_carries_no_track():
    """Rails are a GROUND class; a cart with a baked-in track stub floats
    on any floor that isn't that stub."""
    assert "track" not in genlab.SUBJECTS["machine"]["cart"]


# --- request lifecycle ---------------------------------------------------------------

def test_create_request_writes_drop_contract(tmp_path):
    req = genlab.create_request(tmp_path, IDENTITY, "identities/x.json",
                                "tree", "deciduous", "large", 2,
                                FAM["descriptor"], FAM["materials"])
    assert (req / "prompt.md").exists() and (req / "incoming").is_dir()
    doc = json.loads((req / "request.json").read_text())
    assert doc["schema"] == genlab.REQUEST_SCHEMA and doc["mode"] == "drop"
    assert len(doc["prompt_sha12"]) == 12
    req2 = genlab.create_request(tmp_path, IDENTITY, "identities/x.json",
                                 "tree", "deciduous", "large", 2,
                                 FAM["descriptor"], FAM["materials"])
    assert req2.name != req.name                     # ids never collide


def test_api_mode_generates_into_incoming(tmp_path, monkeypatch):
    """API mode fills incoming/ exactly like a human drop — same contract."""
    import base64, io
    req = genlab.create_request(tmp_path, IDENTITY, "id.json",
                                "tree", "deciduous", "large", 2,
                                FAM["descriptor"], FAM["materials"])
    calls = {}

    def fake_post(url, payload, headers, timeout=300):
        calls.update(url=url, payload=payload, headers=headers)
        buf = io.BytesIO()
        synthetic_reference(64, 96).save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"data": [{"b64_json": b64}] * payload["n"]}

    monkeypatch.setattr(genlab, "_post_json", fake_post)
    monkeypatch.setenv("IMAGEGEN_API_KEY", "sk-test")
    saved = genlab.generate_via_api(req, log=lambda m: None)
    assert [p.name for p in saved] == ["gen_0.png", "gen_1.png"]
    assert all(p.exists() for p in saved)
    assert calls["payload"]["model"] == "gpt-image-1"
    assert calls["payload"]["size"] == "1024x1536"      # 96x128 -> portrait
    assert "sk-test" in calls["headers"]["Authorization"]
    assert calls["payload"]["prompt"] == (req / "prompt.md").read_text()
    gen = json.loads((req / "generation.json").read_text())
    assert gen["saved"] == ["gen_0.png", "gen_1.png"]
    # idempotent naming: a second run appends, never overwrites
    saved2 = genlab.generate_via_api(req, log=lambda m: None)
    assert [p.name for p in saved2] == ["gen_2.png", "gen_3.png"]


def test_api_mode_requires_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGEGEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(genlab, "KEYFILE", tmp_path / "nope.json")
    with pytest.raises(RuntimeError, match="imagegen.json|IMAGEGEN_API_KEY"):
        genlab.imagegen_config()


def test_keyfile_configures_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGEGEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    kf = tmp_path / "imagegen.json"
    kf.write_text(json.dumps({"api_key": "sk-file", "quality": "medium"}))
    monkeypatch.setattr(genlab, "KEYFILE", kf)
    cfg = genlab.imagegen_config()
    assert cfg["api_key"] == "sk-file" and cfg["provider"] == "openai"
    assert cfg["quality"] == "medium"


def test_keyfile_configures_genserver_provider(tmp_path, monkeypatch):
    """A self-hosted node is a keyless provider — the LAN transport reaches it."""
    monkeypatch.delenv("IMAGEGEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    kf = tmp_path / "imagegen.json"
    kf.write_text(json.dumps({"provider": "genserver", "target": "gpu1"}))
    monkeypatch.setattr(genlab, "KEYFILE", kf)
    cfg = genlab.imagegen_config()
    assert cfg["provider"] == "genserver" and cfg["target"] == "gpu1"
    assert "api_key" not in cfg


def test_genserver_provider_runs_node_and_fills_incoming(tmp_path, monkeypatch):
    """genserver mode drops PNGs into incoming/ exactly like the OpenAI path —
    same downstream contract, just from the self-hosted SDXL node."""
    import subprocess
    req = genlab.create_request(tmp_path, IDENTITY, "id.json",
                                "tree", "deciduous", "large", 2,
                                FAM["descriptor"], FAM["materials"])
    seen = {}

    def fake_run(cmd, capture_output=True, text=True):
        import pathlib
        seen["cmd"] = cmd
        # the prompt was staged as a --input dir with prompt.txt == prompt.md
        idir = next(c.split("=", 1)[1] for c in cmd if c.startswith("prompt="))
        seen["prompt"] = (pathlib.Path(idir) / "prompt.txt").read_text()
        out = tmp_path / "store" / "outputs"
        out.mkdir(parents=True, exist_ok=True)
        for i in range(2):
            synthetic_reference(64, 96).save(out / f"gen_{i}.png")
        return subprocess.CompletedProcess(
            cmd, 0, stdout=f"[genserver] imagegen abc123: ran on gpu1\n"
            f"[genserver] outputs: {out}\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    kf = tmp_path / "imagegen.json"
    kf.write_text(json.dumps({"provider": "genserver", "target": "gpu1",
                              "steps": 24, "seed": 5}))
    monkeypatch.setattr(genlab, "KEYFILE", kf)

    saved = genlab.generate_via_api(req, log=lambda m: None)
    assert [p.name for p in saved] == ["gen_0.png", "gen_1.png"]
    assert all(p.exists() for p in saved)
    joined = " ".join(seen["cmd"])
    assert "run imagegen" in joined and "--target gpu1" in joined
    assert "n=2" in joined and "steps=24" in joined and "seed=5" in joined
    assert "width=1024" in joined and "height=1536" in joined  # large tree -> portrait
    assert seen["prompt"] == (req / "prompt.md").read_text()   # prompt staged verbatim
    gen = json.loads((req / "generation.json").read_text())
    assert gen["provider"] == "genserver" and gen["saved"] == ["gen_0.png", "gen_1.png"]
    # append, never overwrite — same as the API path
    saved2 = genlab.generate_via_api(req, log=lambda m: None)
    assert [p.name for p in saved2] == ["gen_2.png", "gen_3.png"]


# --- repixel ------------------------------------------------------------------------

def test_repixel_passes_the_full_qc_gate(pal):
    sprite, material, band, names = repixel.repixelize(
        synthetic_reference(), pal, trees_px.SIZES["large"],
        FAM["descriptor"], FAM["materials"])
    arr = np.asarray(sprite)
    assert arr.shape == (128, 96, 4)
    wood_idx = next(i for i, m in names.items() if m == "wood")
    outline_min = min(i for i, m in names.items() if m.startswith("outline:"))
    subject = (material > 0) & (material < outline_min)
    meta = trees_px.measure_tree_meta(subject, material == wood_idx)
    checks = asset_qc.run_qc(arr, meta, pal, FAM["descriptor"])
    bad = [f"{c.name} ({c.detail})" for c in checks if not c.ok]
    assert not bad, bad


def test_repixel_is_deterministic(pal):
    ref = synthetic_reference()
    a = repixel.repixelize(ref, pal, trees_px.SIZES["medium"],
                           FAM["descriptor"], FAM["materials"])
    b = repixel.repixelize(ref, pal, trees_px.SIZES["medium"],
                           FAM["descriptor"], FAM["materials"])
    assert np.array_equal(np.asarray(a[0]), np.asarray(b[0]))


def test_repixel_masks_alpha_references(pal):
    """A reference that already carries alpha skips background keying."""
    ref = synthetic_reference().convert("RGBA")
    arr = np.array(ref)
    bg = (arr[:, :, 0] > 200) & (arr[:, :, 1] < 60) & (arr[:, :, 2] > 200)
    arr[bg] = 0
    sprite, *_ = repixel.repixelize(Image.fromarray(arr, "RGBA"), pal,
                                    trees_px.SIZES["small"],
                                    FAM["descriptor"], FAM["materials"])
    a = np.asarray(sprite)
    assert set(np.unique(a[:, :, 3])) <= {0, 255} and (a[:, :, 3] > 0).any()


# --- ingest through the shared gate ---------------------------------------------------

def test_ingest_stages_catalog_and_provenance(tmp_path):
    game = tmp_path / "game"
    (game / "content" / "props").mkdir(parents=True)
    req = genlab.create_request(tmp_path / "genlab", IDENTITY, "id.json",
                                "tree", "deciduous", "large", 1,
                                FAM["descriptor"], FAM["materials"])
    synthetic_reference().save(req / "incoming" / "ref_a.png")
    staging = tmp_path / "work" / "props"
    out = genlab.ingest(req, game, staging, IDENTITY, log=lambda m: None)
    assert out["staged"] == ["deciduous_0"] and not out["skipped"]
    cat = json.loads((staging / "props.json").read_text())
    e = cat["props"]["deciduous_0"]
    assert e["style"] == "gen1" and e["generator"] == "genlab/1"
    assert e["provenance"] == "generated" and e["footprint"]["r"] >= 4
    prov = json.loads((req / "provenance" / "deciduous_0.json").read_text())
    assert prov["intent_qc"]["status"] == "skipped"     # optional gate, stubbed
    maps = np.load(req / "provenance" / "deciduous_0.npz")
    assert maps["material"].shape == (128, 96)          # animation substrate
    # sprite is palette-member by construction
    arr = np.asarray(Image.open(staging / "deciduous_0.png").convert("RGBA"))
    used = {tuple(c) for c in arr[arr[:, :, 3] > 0][:, :3]}
    assert used <= pixelart.palette_colors(pixelart.master_palette(IDENTITY))


# --- second family: rocks (the family-agnostic proof) --------------------------------

def synthetic_boulder(w=420, h=380) -> Image.Image:
    """A smooth faceted gray boulder on flat magenta, lit from the top-left."""
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = (255, 0, 255)
    cx, cy = w / 2, h * 0.55
    rng = np.random.default_rng(11)
    mass = np.zeros((h, w), bool)
    for i in range(6):
        a = 2 * np.pi * i / 6
        lx = cx + np.cos(a) * w * 0.14
        ly = cy + np.sin(a) * h * 0.10
        r = w * 0.24 * rng.uniform(0.85, 1.1)
        mass |= ((xx - lx) ** 2 + (yy - ly) ** 2) < r * r
    mass &= yy < h * 0.92
    # faceted shading: light from up-left + angular facet bands
    d = ((xx - cx * 0.72) + (yy - cy * 0.65)) / (w * 0.9)
    lit = np.clip(1.0 - d, 0, 1)
    facets = ((np.floor((xx * 0.7 + yy * 0.35) / 34)) % 3) * 0.09
    v = np.clip(lit - facets, 0, 1)
    for c, lo, hi in ((0, 58, 190), (1, 56, 186), (2, 60, 182)):
        img[..., c] = np.where(mass, lo + (hi - lo) * v, img[..., c])
    return Image.fromarray(img, "RGB")


ROCK = asset_creator.FAMILIES["rock"]


def test_rock_family_repixels_through_the_gate(pal):
    sprite, material, band, names = repixel.repixelize(
        synthetic_boulder(), pal, ROCK["sizes"]["large"],
        ROCK["descriptor"], ROCK["materials"])
    arr = np.asarray(sprite)
    assert arr.shape == (64, 64, 4)
    outline_min = min(i for i, m in names.items() if m.startswith("outline:"))
    subject = (material > 0) & (material < outline_min)
    meta = pixelart.measure_prop_meta(subject, subject, r_min=4.0, r_max=26.0)
    checks = asset_qc.run_qc(arr, meta, pal, ROCK["descriptor"])
    bad = [f"{c.name} ({c.detail})" for c in checks if not c.ok]
    assert not bad, bad
    assert meta["footprint"]["r"] >= 12          # blocks its WHOLE base


def test_rock_ingest_and_variant_numbering_skips_blobs(tmp_path):
    game = tmp_path / "game"
    (game / "content" / "props").mkdir(parents=True)
    # legacy blob rocks live in the catalog: numbering must continue past them
    (game / "content" / "props" / "props.json").write_text(json.dumps(
        {"props": {f"rock_{i}": {"file": f"rock_{i}.png"} for i in range(3)}}))
    req = genlab.create_request(tmp_path / "genlab", IDENTITY, "id.json",
                                "rock", "rock", "large", 1,
                                ROCK["descriptor"], ROCK["materials"])
    assert "boulder" not in (req / "prompt.md").read_text()
    assert "granite" not in (req / "prompt.md").read_text()
    synthetic_boulder().save(req / "incoming" / "ref.png")
    out = genlab.ingest(req, game, tmp_path / "staging", IDENTITY,
                        log=lambda m: None)
    assert out["staged"] == ["rock_3"]           # blobs 0-2 untouched
    cat = json.loads((tmp_path / "staging" / "props.json").read_text())
    e = cat["props"]["rock_3"]
    assert e["family"] == "rock" and e["frames"] == 1    # rocks don't animate
    assert not (tmp_path / "staging" / "rock_3.f1.png").exists()


def test_rock_ensure_points_to_genlab(tmp_path):
    game = tmp_path / "game"
    (game / "content" / "props").mkdir(parents=True)
    msgs = []
    report = asset_creator.ensure(game, tmp_path / "staging", IDENTITY,
                                  "rock", "boulder", 2, log=msgs.append)
    assert report["gap"] == 2 and "generated" not in report
    assert any("genlab" in m for m in msgs)      # guidance, not a crash


def test_gen1_assets_count_as_fit(tmp_path):
    game = tmp_path / "game"
    (game / "content" / "props").mkdir(parents=True)
    (game / "content" / "props" / "props.json").write_text(json.dumps(
        {"props": {"deciduous_0": {
            "family": "tree", "substyle": "deciduous", "identity_name": "t",
            "style": "gen1", "file": "deciduous_0.png"}}}))
    r = asset_creator.resolve(game, "tree", "t", "deciduous", 1)
    assert r["fit"] and r["have"] == ["deciduous_0"]


# --- preview: the human-in-the-loop dry run -------------------------------------------

def test_preview_writes_sheet_and_stages_nothing(tmp_path):
    req = genlab.create_request(tmp_path / "genlab", IDENTITY, "id.json",
                                "tree", "deciduous", "large", 1,
                                FAM["descriptor"], FAM["materials"])
    synthetic_reference().save(req / "incoming" / "ref_a.png")
    out = genlab.preview(req, IDENTITY, log=lambda m: None)
    assert out == req / "preview.png" and out.exists()
    sheet = Image.open(out)
    assert sheet.width > 256 and sheet.height >= 256   # ref + sprite side by side
    # dry run: no staging, no catalog, no provenance
    assert not (req / "provenance").exists()
    assert not list(tmp_path.glob("work/**/*.png"))


def test_preview_empty_incoming_is_a_noop(tmp_path):
    req = genlab.create_request(tmp_path / "genlab", IDENTITY, "id.json",
                                "tree", "deciduous", "large", 1,
                                FAM["descriptor"], FAM["materials"])
    assert genlab.preview(req, IDENTITY, log=lambda m: None) is None


# --- scene concepts --------------------------------------------------------------

def test_scene_concept_prompt_distills_the_brief(pal):
    brief = """# Scene brief — X
## The place
A festival lawn under a great wheel.
## Light & air
Full daylight, warm.
## Zones, walked south to north
- **The entrance (S):** columns and lanterns.
- **The wheel plaza (NE):** the ferris wheel.
## Register
stuff that must NOT leak into the prompt
"""
    p1 = genlab.compose_scene_prompt(brief, pal)
    p2 = genlab.compose_scene_prompt(brief, pal)
    assert p1 == p2
    assert "festival lawn" in p1 and "Full daylight" in p1
    assert "wheel plaza" in p1 and "NOT a tile map" in p1
    assert "must NOT leak" not in p1          # register stays out


def test_scene_concept_generates_and_archives(tmp_path, monkeypatch):
    import base64, io
    brief = tmp_path / "x.brief.md"
    brief.write_text("## The place\nA lawn.\n## Light & air\nDay.\n")

    def fake_post(url, payload, headers, timeout=300):
        assert payload["size"] == "1536x1024"
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), (10, 120, 40)).save(buf, format="PNG")
        return {"data": [{"b64_json": base64.b64encode(buf.getvalue()).decode()}]}

    monkeypatch.setattr(genlab, "_post_json", fake_post)
    monkeypatch.setenv("IMAGEGEN_API_KEY", "sk-test")
    saved = genlab.generate_scene_concept(brief, IDENTITY, tmp_path / "c",
                                          count=1, log=lambda m: None)
    assert [p.name for p in saved] == ["concept_0.png"]
    assert (tmp_path / "c" / "prompt.md").exists()
    assert (tmp_path / "c" / "generation.json").exists()
