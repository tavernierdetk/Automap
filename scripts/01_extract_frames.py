#!/usr/bin/env python
"""Stage 1 - extract frames from a drone clip.

ffmpeg samples frames at a fixed fps (downscaled to a longest-edge cap), OpenCV
culls blurry ones, and the count is capped for ODM's sake. A DJI .SRT GPS sidecar
is auto-detected and turned into an ODM geo.txt; if absent it's a silent no-op and
ODM solves structure-from-motion blind.

    python scripts/01_extract_frames.py                 # uses config.toml defaults
    python scripts/01_extract_frames.py --fps 0.5 --max-frames 60
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

# Allow running the script directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automap.config import load_config  # noqa: E402
from automap.frames import find_input_video  # noqa: E402
from automap.stages import run_extract  # noqa: E402

app = typer.Typer(add_completion=False)


@app.command()
def main(
    input_dir: Path = typer.Option(Path("input"), "--input", help="Folder with the clip (+ optional .srt)"),
    output_dir: Path = typer.Option(Path("work/frames"), "--output", help="Where frames + geo.txt go"),
    config: Path = typer.Option(Path("config.toml"), "--config", help="Tunables file"),
    fps: Optional[float] = typer.Option(None, help="Override extraction fps"),
    max_frames: Optional[int] = typer.Option(None, help="Override frame cap"),
    sharpness_threshold: Optional[float] = typer.Option(None, help="Override sharpness cull (0 disables)"),
    resize: Optional[int] = typer.Option(None, help="Override longest-edge px (0 = native)"),
):
    cfg = load_config(config).frames
    if fps is not None:
        cfg.fps = fps
    if max_frames is not None:
        cfg.max_frames = max_frames
    if sharpness_threshold is not None:
        cfg.sharpness_threshold = sharpness_threshold
    if resize is not None:
        cfg.resize = resize

    log = lambda m: typer.echo(f"[stage 1] {m}")

    video = find_input_video(input_dir)
    log(f"input video: {video}")

    # SRT auto-detect in the input folder (never required).
    srts = sorted(list(input_dir.glob("*.srt")) + list(input_dir.glob("*.SRT")))
    res = run_extract(video, output_dir, cfg=cfg, srt_path=srts[0] if srts else None, on_log=log)
    if not res["frames"]:
        log("WARNING: no frames survived the cull. Lower sharpness_threshold or check the clip.")
        raise typer.Exit(code=1)

    log(f"done: {res['frames']} frames in {output_dir}")


if __name__ == "__main__":
    app()
