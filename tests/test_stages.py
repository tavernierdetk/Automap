"""Tests for stage ordering and the shared stage-1 runner."""
import shutil
import subprocess

import pytest

from automap.config import FramesConfig
from automap.stages import run_extract, select_stages

ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def test_select_stages_full():
    assert select_stages() == ["frames", "odm", "mesh"]


def test_select_stages_partial():
    assert select_stages("odm", "mesh") == ["odm", "mesh"]
    assert select_stages("mesh", "mesh") == ["mesh"]
    assert select_stages("frames", "odm") == ["frames", "odm"]


def test_select_stages_invalid():
    with pytest.raises(ValueError):
        select_stages("mesh", "frames")   # from after stop
    with pytest.raises(ValueError):
        select_stages("bogus", "mesh")    # unknown stage


SRT = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    "[latitude: 47.1] [longitude: -63.2] [abs_alt: 50]\n\n"
    "2\n00:00:02,000 --> 00:00:03,000\n"
    "[latitude: 47.2] [longitude: -63.3] [abs_alt: 60]\n"
)


@ffmpeg_required
def test_run_extract_with_and_without_srt(tmp_path):
    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=duration=3:size=320x240:rate=4", str(video)],
        check=True,
    )
    cfg = FramesConfig(fps=2, max_frames=5, sharpness_threshold=0.0, resize=0, jpeg_quality=85)

    srt = tmp_path / "clip.srt"
    srt.write_text(SRT)
    out = tmp_path / "frames"
    res = run_extract(video, out, cfg=cfg, srt_path=srt)
    assert res["frames"] > 0 and res["georeferenced"]
    assert (out / "geo.txt").exists()

    out2 = tmp_path / "frames_nogeo"
    res2 = run_extract(video, out2, cfg=cfg, srt_path=None)
    assert res2["frames"] > 0 and not res2["georeferenced"]
    assert not (out2 / "geo.txt").exists()
