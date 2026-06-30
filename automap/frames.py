"""Stage 1 core: extract frames from a video, cull blurry ones, cap the count.

Pipeline: ffmpeg samples candidate frames at a fixed fps (optionally downscaled
to a longest-edge limit) as lossless PNGs in a staging dir. OpenCV scores each by
variance-of-Laplacian (sharpness), culls those below threshold, then evenly
subsamples down to max_frames so temporal coverage is preserved. Survivors are
re-encoded once to JPEG and renumbered contiguously as frame_NNNNN.jpg.

Kept separate from the CLI so it is unit-testable.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2

VIDEO_GLOBS = ("*.mp4", "*.MP4", "*.mov", "*.MOV")


def find_input_video(input_dir: str | Path) -> Path:
    """First video found in input_dir. Raises FileNotFoundError if none."""
    input_dir = Path(input_dir)
    vids = sorted(p for g in VIDEO_GLOBS for p in input_dir.glob(g))
    if not vids:
        raise FileNotFoundError(
            f"No video in {input_dir} (looked for {', '.join(VIDEO_GLOBS)})"
        )
    return vids[0]


def _ffmpeg_extract(video: Path, stage_dir: Path, fps: float, resize: int) -> list[Path]:
    """Sample frames at `fps` into stage_dir as PNGs; downscale if resize > 0."""
    vf = f"fps={fps}"
    if resize and resize > 0:
        # Fit within resize x resize, preserve aspect, keep dims even.
        vf += (
            f",scale=w={resize}:h={resize}"
            ":force_original_aspect_ratio=decrease"
            ":force_divisible_by=2:flags=lanczos"
        )
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
        "-i", str(video), "-vf", vf,
        str(stage_dir / "stage_%05d.png"),
    ]
    subprocess.run(cmd, check=True)
    return sorted(stage_dir.glob("stage_*.png"))


def sharpness(path: str | Path) -> float:
    """Variance of the Laplacian — a standard focus/blur metric. Higher = sharper."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def even_subsample(items: list, k: int) -> list:
    """Keep k items evenly spaced across the sequence (preserves first/last)."""
    if k <= 0 or len(items) <= k:
        return items
    if k == 1:
        return [items[0]]
    idx = sorted({round(i * (len(items) - 1) / (k - 1)) for i in range(k)})
    return [items[i] for i in idx]


def extract_frames(
    video: str | Path,
    out_dir: str | Path,
    *,
    fps: float,
    max_frames: int,
    sharpness_threshold: float,
    resize: int,
    jpeg_quality: int,
    on_log=lambda _msg: None,
) -> list[dict]:
    """Extract -> cull -> cap -> write frame_NNNNN.jpg into out_dir.

    Returns a list of {name, path, time, sharpness} for the kept frames, in order.
    `time` is the frame's source timestamp in seconds (used for SRT georeferencing).
    """
    video = Path(video)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clean prior outputs so reruns are deterministic.
    for old in out_dir.glob("frame_*.jpg"):
        old.unlink()
    geo = out_dir / "geo.txt"
    if geo.exists():
        geo.unlink()

    stage_dir = out_dir / "_stage"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir()

    try:
        staged = _ffmpeg_extract(video, stage_dir, fps, resize)
        on_log(f"ffmpeg sampled {len(staged)} candidate frames at {fps} fps")

        scored = [(p, sharpness(p)) for p in staged]
        if sharpness_threshold and sharpness_threshold > 0:
            kept = [(p, s) for p, s in scored if s >= sharpness_threshold]
            on_log(
                f"sharpness cull (>= {sharpness_threshold}): "
                f"{len(kept)}/{len(scored)} kept"
            )
        else:
            kept = scored

        kept.sort(key=lambda ps: ps[0].name)  # temporal order by stage index

        if max_frames and len(kept) > max_frames:
            kept = even_subsample(kept, max_frames)
            on_log(f"capped to max_frames={max_frames}")

        results: list[dict] = []
        for i, (p, s) in enumerate(kept, start=1):
            stage_idx = int(p.stem.split("_")[1])
            src_time = (stage_idx - 1) / fps if fps else 0.0
            final = out_dir / f"frame_{i:05d}.jpg"
            img = cv2.imread(str(p))
            cv2.imwrite(str(final), img, [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)])
            results.append(
                {"name": final.name, "path": final, "time": src_time, "sharpness": s}
            )
        on_log(f"wrote {len(results)} frames to {out_dir}")
        return results
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
