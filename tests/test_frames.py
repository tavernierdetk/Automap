"""Tests for stage-1 frame extraction (sharpness, capping, end-to-end)."""
import shutil
import subprocess

import cv2
import numpy as np
import pytest

from automap.frames import (
    even_subsample,
    extract_frames,
    find_input_video,
    sharpness,
)

ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def _make_alternating_video(tmp_path, n_pairs=6, size=(320, 240)):
    """Build a near-lossless mjpeg clip alternating sharp(noise)/flat frames."""
    src = tmp_path / "src"
    src.mkdir()
    rng = np.random.default_rng(0)
    w, h = size
    idx = 1
    for _ in range(n_pairs):
        cv2.imwrite(str(src / f"f_{idx:03d}.png"),
                    rng.integers(0, 256, (h, w, 3), dtype=np.uint8)); idx += 1
        cv2.imwrite(str(src / f"f_{idx:03d}.png"),
                    np.full((h, w, 3), 127, np.uint8)); idx += 1
    video = tmp_path / "clip.mov"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-framerate", "10",
         "-i", str(src / "f_%03d.png"), "-c:v", "mjpeg", "-q:v", "1", str(video)],
        check=True,
    )
    return video


def test_even_subsample():
    items = list(range(10))
    out = even_subsample(items, 4)
    assert len(out) == 4
    assert out[0] == 0 and out[-1] == 9          # endpoints preserved
    assert even_subsample(items, 20) == items     # fewer than k -> unchanged
    assert even_subsample(items, 1) == [0]


def test_sharpness_noise_vs_flat(tmp_path):
    rng = np.random.default_rng(1)
    noise = tmp_path / "noise.png"
    flat = tmp_path / "flat.png"
    cv2.imwrite(str(noise), rng.integers(0, 256, (200, 200, 3), dtype=np.uint8))
    cv2.imwrite(str(flat), np.full((200, 200, 3), 127, np.uint8))
    assert sharpness(noise) > 100.0
    assert sharpness(flat) < 1.0
    assert sharpness(tmp_path / "does_not_exist.png") == 0.0


def test_find_input_video(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_input_video(tmp_path)
    (tmp_path / "a.mp4").write_bytes(b"x")
    assert find_input_video(tmp_path).name == "a.mp4"


@ffmpeg_required
def test_extract_culls_blurry(tmp_path):
    video = _make_alternating_video(tmp_path, n_pairs=6)
    out = tmp_path / "frames"
    # threshold between flat (~0) and noise (large) -> flats culled
    kept = extract_frames(video, out, fps=10, max_frames=999,
                          sharpness_threshold=50.0, resize=0, jpeg_quality=90)
    assert len(kept) > 0
    assert all(k["sharpness"] >= 50.0 for k in kept)
    # culling actually removed frames vs threshold disabled
    all_frames = extract_frames(video, out, fps=10, max_frames=999,
                                sharpness_threshold=0.0, resize=0, jpeg_quality=90)
    assert len(all_frames) > len(kept)


@ffmpeg_required
def test_extract_caps_and_names(tmp_path):
    video = _make_alternating_video(tmp_path, n_pairs=8)
    out = tmp_path / "frames"
    kept = extract_frames(video, out, fps=10, max_frames=4,
                          sharpness_threshold=0.0, resize=0, jpeg_quality=90)
    assert len(kept) == 4
    names = [k["name"] for k in kept]
    assert names == [f"frame_{i:05d}.jpg" for i in range(1, 5)]
    assert all((out / n).exists() for n in names)
    # times are monotonically increasing (temporal order preserved)
    times = [k["time"] for k in kept]
    assert times == sorted(times)
    # staging dir cleaned up
    assert not (out / "_stage").exists()


@ffmpeg_required
def test_extract_resizes(tmp_path):
    video = _make_alternating_video(tmp_path, n_pairs=3, size=(640, 480))
    out = tmp_path / "frames"
    kept = extract_frames(video, out, fps=10, max_frames=999,
                          sharpness_threshold=0.0, resize=160, jpeg_quality=90)
    img = cv2.imread(str(kept[0]["path"]))
    assert max(img.shape[:2]) <= 160
