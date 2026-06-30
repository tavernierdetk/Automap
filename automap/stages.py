"""Stage orchestration helpers shared by the standalone CLIs and ingest.py.

Keeps the stage-1 extract+georeference sequence and the run-ordering in one place
so 01_extract_frames.py and ingest.py can't drift apart.
"""
from __future__ import annotations

from pathlib import Path

from .config import FramesConfig
from .frames import extract_frames
from .srt import parse_dji_srt, write_geo_txt

# Generation stages, in order. Playback (Godot) is intentionally not here.
STAGE_ORDER = ["frames", "odm", "mesh"]


def select_stages(from_stage: str = "frames", stop_after: str = "mesh") -> list[str]:
    """The contiguous slice of STAGE_ORDER to run. Raises on bad/empty ranges."""
    for s in (from_stage, stop_after):
        if s not in STAGE_ORDER:
            raise ValueError(f"unknown stage {s!r}; expected one of {STAGE_ORDER}")
    i, j = STAGE_ORDER.index(from_stage), STAGE_ORDER.index(stop_after)
    if i > j:
        raise ValueError(f"--from {from_stage} is after --stop-after {stop_after}")
    return STAGE_ORDER[i : j + 1]


def run_extract(
    video: str | Path,
    out_dir: str | Path,
    *,
    cfg: FramesConfig,
    srt_path: str | Path | None = None,
    on_log=lambda _m: None,
) -> dict:
    """Stage 1: extract frames, and write an ODM geo.txt if an SRT is supplied.

    Returns {frames, georeferenced}. Writing geo.txt is a no-op when srt_path is
    absent/empty, so callers treat georeferencing as optional.
    """
    frames = extract_frames(
        video, out_dir,
        fps=cfg.fps, max_frames=cfg.max_frames,
        sharpness_threshold=cfg.sharpness_threshold,
        resize=cfg.resize, jpeg_quality=cfg.jpeg_quality,
        on_log=on_log,
    )
    georeferenced = False
    if frames and srt_path and Path(srt_path).exists():
        entries = parse_dji_srt(srt_path)
        n = write_geo_txt(frames, entries, Path(out_dir) / "geo.txt")
        georeferenced = n > 0
        if n:
            on_log(f"SRT {Path(srt_path).name}: wrote geo.txt for {n} frames")
        else:
            on_log(f"SRT {Path(srt_path).name} present but no GPS parsed")
    elif not srt_path:
        on_log("no .SRT sidecar - ODM will solve blind")
    return {"frames": len(frames), "georeferenced": georeferenced}
