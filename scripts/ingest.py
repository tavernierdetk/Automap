#!/usr/bin/env python
"""Named ingestion - one command turns a clip into a named, walkable scene.

Runs the generation pipeline (stage 1 frames -> 2 ODM -> 3 glb) against
per-scene namespaced paths (work/<name>/...), so multiple scenes coexist, and
registers the result in scenes/manifest.json (the hand-off to playback).

    python scripts/ingest.py --name birch-park --video clip.mp4
    python scripts/ingest.py --name birch-park --video clip.mp4 --srt clip.srt
    python scripts/ingest.py --name birch-park --video clip.mp4 --stop-after frames
    python scripts/ingest.py --name birch-park --from mesh        # re-run stage 3 only

A sibling .srt next to the video is auto-detected; failing that, an embedded
subtitle track inside the video (DJI mov_text telemetry) is extracted. Either way
SRT is never required.
Intermediates are kept on disk and each stage is logged, so you can still inspect
between stages or resume with --from / --stop-after.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automap.config import load_config  # noqa: E402
from automap.scenes import scene_paths, upsert_scene  # noqa: E402
from automap.srt import extract_embedded_srt  # noqa: E402
from automap.stages import run_extract, select_stages  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
app = typer.Typer(add_completion=False)


def _auto_srt(video: Path) -> Optional[Path]:
    """A DJI sidecar sitting next to the video (clip.mp4 -> clip.srt)."""
    for cand in (video.with_suffix(".srt"), video.with_suffix(".SRT")):
        if cand.exists():
            return cand
    return None


def _require(*paths: Path, msg: str) -> None:
    for p in paths:
        if not Path(p).exists():
            raise typer.BadParameter(f"missing input: {p} - {msg}")


def _run(cmd: list) -> None:
    r = subprocess.run(cmd, check=False)
    if r.returncode != 0:
        raise typer.Exit(code=r.returncode)


@app.command()
def main(
    name: str = typer.Option(..., "--name", help="Scene name (folder + manifest key)"),
    video: Optional[Path] = typer.Option(None, "--video", help="Source clip (.mp4/.mov)"),
    srt: Optional[Path] = typer.Option(None, "--srt", help="GPS sidecar (else sibling auto-detect)"),
    from_stage: str = typer.Option("frames", "--from", help="Start at: frames|odm|mesh"),
    stop_after: str = typer.Option("mesh", "--stop-after", help="Stop after: frames|odm|mesh"),
    terrain: bool = typer.Option(False, "--terrain", help="Raw output is terrain-first (2.5D) instead of the scan mesh"),
    style: bool = typer.Option(False, "--style", help="Also produce sf_<name>.glb: terrain + detected features (implies terrain-mode ODM)"),
    identity: str = typer.Option("placeholder", "--identity", help="Visual identity for the styled glb (see 06_style_scene.py)"),
    godot: bool = typer.Option(True, "--godot/--no-godot", help="Publish the glbs into the Godot project as walkable .tscn (stage 7)"),
    config: Path = typer.Option(ROOT / "config.toml", "--config", help="Tunables"),
    fps: Optional[float] = typer.Option(None, help="Override extraction fps"),
    max_frames: Optional[int] = typer.Option(None, help="Override frame cap"),
    sharpness_threshold: Optional[float] = typer.Option(None, help="Override sharpness cull (0 disables)"),
    resize: Optional[int] = typer.Option(None, help="Override longest-edge px (0 = native)"),
):
    log = lambda m: typer.echo(f"[ingest:{name}] {m}")
    try:
        stages = select_stages(from_stage, stop_after)
    except ValueError as e:
        raise typer.BadParameter(str(e))

    sp = scene_paths(ROOT, name)
    cfg = load_config(config)
    if fps is not None:
        cfg.frames.fps = fps
    if max_frames is not None:
        cfg.frames.max_frames = max_frames
    if sharpness_threshold is not None:
        cfg.frames.sharpness_threshold = sharpness_threshold
    if resize is not None:
        cfg.frames.resize = resize
    need_dem = terrain or style   # terrain glb and feature detection both need the DEM/ortho
    outputs = "sraw" + (" + sf" if style else "")
    log(f"stages: {' -> '.join(stages)}{' (+style)' if style else ''}  ->  {sp.base.relative_to(ROOT)}/  [{outputs}]")

    frame_count: Optional[int] = None
    georeferenced = False

    # --- Stage 1: frames ---
    if "frames" in stages:
        if video is None:
            raise typer.BadParameter("--video is required to run the frames stage")
        if not video.exists():
            raise typer.BadParameter(f"video not found: {video}")
        if srt and not srt.exists():
            raise typer.BadParameter(f"srt not found: {srt}")
        srt_path = srt or _auto_srt(video)
        # No sidecar? DJI clips may embed the telemetry as a subtitle track.
        if srt_path is None:
            sp.base.mkdir(parents=True, exist_ok=True)
            srt_path = extract_embedded_srt(video, sp.base / "embedded.srt")
            if srt_path:
                log(f"telemetry: extracted embedded subtitle track -> {srt_path.name}")
        log(f"stage 1: extracting frames from {video.name}"
            + (f" (+SRT {srt_path.name})" if srt_path else " (no SRT)"))
        res = run_extract(video, sp.frames, cfg=cfg.frames, srt_path=srt_path, on_log=log)
        frame_count, georeferenced = res["frames"], res["georeferenced"]
        if not frame_count:
            raise typer.Exit(code=1)

    # --- Stage 2: ODM ---
    if "odm" in stages:
        if not list(sp.frames.glob("*.jpg")):
            raise typer.BadParameter(f"no frames in {sp.frames} - run the frames stage first")
        log(f"stage 2: OpenDroneMap{' (+DEM/ortho)' if need_dem else ''} (this is the slow one)")
        cmd = ["bash", str(SCRIPTS / "02_run_odm.sh"),
               "--frames", str(sp.frames), "--output", str(sp.odm), "--config", str(config)]
        if need_dem:
            cmd.append("--terrain")
        _run(cmd)

    # --- Stage 3: raw geometry -> sraw_<name>.glb ---
    if "mesh" in stages:
        sp.mesh_dir.mkdir(parents=True, exist_ok=True)
        if terrain:
            _require(sp.dtm, sp.ortho, msg="run the odm stage with --terrain first")
            log("stage 3b: DEM -> terrain glb (raw)")
            _run([sys.executable, str(SCRIPTS / "03b_dem_to_terrain.py"),
                  "--dtm", str(sp.dtm), "--ortho", str(sp.ortho),
                  "--output", str(sp.raw_glb), "--config", str(config)])
        else:
            _require(sp.obj, msg="run the odm stage first")
            log("stage 3: Blender mesh cleanup -> glb (raw)")
            _run([sys.executable, str(SCRIPTS / "03_mesh_to_glb.py"),
                  "--input", str(sp.obj), "--output", str(sp.raw_glb)])

    # --- Styled + feature scene -> sf_<name>.glb (parallel representation) ---
    if style and "mesh" in stages:
        _require(sp.dsm, sp.dtm, sp.ortho,
                 msg="styling needs terrain outputs (--style runs terrain-mode ODM)")
        # terrain base for styling: reuse the raw terrain glb, else build one
        base = sp.raw_glb if terrain else sp.base_glb
        if not terrain:
            log("stage 3b: DEM -> terrain base (for styling)")
            _run([sys.executable, str(SCRIPTS / "03b_dem_to_terrain.py"),
                  "--dtm", str(sp.dtm), "--ortho", str(sp.ortho),
                  "--output", str(base), "--config", str(config)])
        log("stage 5: detect features")
        _run([sys.executable, str(SCRIPTS / "05_detect_features.py"),
              "--dsm", str(sp.dsm), "--dtm", str(sp.dtm), "--ortho", str(sp.ortho),
              "--output", str(sp.features), "--config", str(config)])
        log("stage 6: style scene -> sf glb")
        _run([sys.executable, str(SCRIPTS / "06_style_scene.py"),
              "--source", str(base), "--features", str(sp.features),
              "--output", str(sp.styled_glb), "--identity", identity])

    # --- Register in the manifest ---
    entry = {"updated": datetime.now().isoformat(timespec="seconds"),
             "raw_kind": "terrain" if terrain else "mesh"}
    if video is not None:
        entry["source_video"] = str(video)
    if frame_count is not None:
        entry["frames"] = frame_count
        entry["georeferenced"] = georeferenced
    if sp.raw_glb.exists():
        entry["raw"] = os.path.relpath(sp.raw_glb, ROOT)
    if sp.styled_glb.exists():
        entry["styled"] = os.path.relpath(sp.styled_glb, ROOT)
    upsert_scene(ROOT, name, entry)

    # --- Stage 7: publish walkable .tscn into the Godot project ---
    if godot and (sp.raw_glb.exists() or sp.styled_glb.exists()):
        log("stage 7: publishing .tscn into the Godot project")
        _run([sys.executable, str(SCRIPTS / "07_publish_godot_scenes.py"), "--name", name])

    outs = [v for v in (entry.get("raw"), entry.get("styled")) if v]
    log(f"done -> {', '.join(outs) if outs else '(partial run)'}  (scenes/manifest.json)")


if __name__ == "__main__":
    app()
