#!/usr/bin/env python
"""Named ingestion - one command turns a clip into a named, walkable scene.

Runs the generation pipeline (stage 1 frames -> 2 ODM -> 3 glb) against
per-scene namespaced paths (work/<name>/...), so multiple scenes coexist, and
registers the result in scenes/manifest.json (the hand-off to playback).

    python scripts/ingest.py --name birch-park --video clip.mp4
    python scripts/ingest.py --name birch-park --video clip.mp4 --srt clip.srt
    python scripts/ingest.py --name birch-park --video clip.mp4 --stop-after frames
    python scripts/ingest.py --name birch-park --from mesh        # re-run stage 3 only

A sibling .srt next to the video is auto-detected; SRT is never required.
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
from automap.stages import run_extract, select_stages  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
app = typer.Typer(add_completion=False)


def _auto_srt(video: Path) -> Optional[Path]:
    """A DJI sidecar sitting next to the video (clip.mp4 -> clip.srt)."""
    for cand in (video.with_suffix(".srt"), video.with_suffix(".SRT")):
        if cand.exists():
            return cand
    return None


@app.command()
def main(
    name: str = typer.Option(..., "--name", help="Scene name (folder + manifest key)"),
    video: Optional[Path] = typer.Option(None, "--video", help="Source clip (.mp4/.mov)"),
    srt: Optional[Path] = typer.Option(None, "--srt", help="GPS sidecar (else sibling auto-detect)"),
    from_stage: str = typer.Option("frames", "--from", help="Start at: frames|odm|mesh"),
    stop_after: str = typer.Option("mesh", "--stop-after", help="Stop after: frames|odm|mesh"),
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
    log(f"stages: {' -> '.join(stages)}  ->  {sp.base.relative_to(ROOT)}/")

    frame_count: Optional[int] = None
    georeferenced = False

    # --- Stage 1: frames ---
    if "frames" in stages:
        if video is None:
            raise typer.BadParameter("--video is required to run the frames stage")
        if not video.exists():
            raise typer.BadParameter(f"video not found: {video}")
        srt_path = srt or _auto_srt(video)
        if srt and not srt.exists():
            raise typer.BadParameter(f"srt not found: {srt}")
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
        log("stage 2: OpenDroneMap (this is the slow one)")
        r = subprocess.run(
            ["bash", str(ROOT / "scripts" / "02_run_odm.sh"),
             "--frames", str(sp.frames), "--output", str(sp.odm), "--config", str(config)],
            check=False,
        )
        if r.returncode != 0:
            raise typer.Exit(code=r.returncode)

    # --- Stage 3: mesh -> glb ---
    if "mesh" in stages:
        if not sp.obj.exists():
            raise typer.BadParameter(f"ODM mesh missing: {sp.obj} - run the odm stage first")
        sp.mesh_dir.mkdir(parents=True, exist_ok=True)
        log("stage 3: Blender mesh cleanup -> glb")
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "03_mesh_to_glb.py"),
             "--input", str(sp.obj), "--output", str(sp.glb)],
            check=False,
        )
        if r.returncode != 0:
            raise typer.Exit(code=r.returncode)

    # --- Register in the manifest ---
    entry = {"updated": datetime.now().isoformat(timespec="seconds")}
    if video is not None:
        entry["source_video"] = str(video)
    if frame_count is not None:
        entry["frames"] = frame_count
        entry["georeferenced"] = georeferenced
    if sp.glb.exists():
        entry["glb"] = os.path.relpath(sp.glb, ROOT)
    upsert_scene(ROOT, name, entry)

    if entry.get("glb"):
        log(f"done -> {entry['glb']}  (registered in scenes/manifest.json)")
    else:
        log("done (partial run; glb not produced yet)")


if __name__ == "__main__":
    app()
