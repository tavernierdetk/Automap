"""Tests for the DJI .SRT parser and ODM geo.txt writer."""
import shutil
import subprocess

import pytest

from automap.srt import extract_embedded_srt, interpolate, parse_dji_srt, write_geo_txt

_HAS_FFMPEG = shutil.which("ffmpeg") is not None

# Bracketed DJI format (newer firmware).
BRACKETED = """1
00:00:00,000 --> 00:00:01,000
<font size="28">SrtCnt : 1, DiffTime : 1000ms
2026-06-30 12:00:00.000
[latitude: 47.100000] [longitude: -63.200000] [rel_alt: 30.000 abs_alt: 50.000]</font>

2
00:00:02,000 --> 00:00:03,000
<font size="28">SrtCnt : 2, DiffTime : 1000ms
2026-06-30 12:00:02.000
[latitude: 47.100200] [longitude: -63.200400] [rel_alt: 31.000 abs_alt: 51.000]</font>
"""

# Legacy GPS(long,lat,alt) format.
LEGACY = """1
00:00:00,000 --> 00:00:01,000
HOME(-63.2,47.1) GPS(-63.200000,47.100000,40) BAROMETER:30.0

2
00:00:01,000 --> 00:00:02,000
HOME(-63.2,47.1) GPS(-63.201000,47.101000,41) BAROMETER:31.0
"""


def test_parse_bracketed(tmp_path):
    p = tmp_path / "clip.srt"
    p.write_text(BRACKETED)
    e = parse_dji_srt(p)
    assert len(e) == 2
    assert e[0]["time"] == 0.0
    assert e[0]["lat"] == 47.1 and e[0]["lon"] == -63.2
    assert e[0]["alt"] == 50.0  # abs_alt preferred
    assert e[1]["time"] == 2.0


def test_parse_legacy(tmp_path):
    p = tmp_path / "clip.srt"
    p.write_text(LEGACY)
    e = parse_dji_srt(p)
    assert len(e) == 2
    assert e[0]["lon"] == -63.2 and e[0]["lat"] == 47.1 and e[0]["alt"] == 40.0


def test_parse_empty(tmp_path):
    p = tmp_path / "clip.srt"
    p.write_text("not a subtitle file\n")
    assert parse_dji_srt(p) == []


def test_interpolate_midpoint():
    e = [
        {"time": 0.0, "lat": 0.0, "lon": 0.0, "alt": 0.0},
        {"time": 2.0, "lat": 2.0, "lon": -4.0, "alt": 10.0},
    ]
    mid = interpolate(e, 1.0)
    assert mid["lat"] == 1.0 and mid["lon"] == -2.0 and mid["alt"] == 5.0
    # clamps outside range
    assert interpolate(e, -5.0)["lat"] == 0.0
    assert interpolate(e, 99.0)["lat"] == 2.0
    assert interpolate([], 1.0) is None


def test_write_geo_txt(tmp_path):
    frames = [{"name": "frame_00001.jpg", "time": 0.0},
              {"name": "frame_00002.jpg", "time": 2.0}]
    entries = parse_dji_srt_from(BRACKETED, tmp_path)
    out = tmp_path / "geo.txt"
    n = write_geo_txt(frames, entries, out)
    assert n == 2
    lines = out.read_text().splitlines()
    assert lines[0] == "EPSG:4326"
    # image_name lon lat alt  (lon first for EPSG:4326)
    assert lines[1].startswith("frame_00001.jpg -63.2")
    assert lines[2].startswith("frame_00002.jpg -63.2004")


def test_write_geo_txt_noop_when_no_srt(tmp_path):
    out = tmp_path / "geo.txt"
    assert write_geo_txt([{"name": "frame_00001.jpg", "time": 0.0}], [], out) == 0
    assert not out.exists()  # absent sidecar -> no file at all


def _synth_video(path, *, with_subs: bool):
    """A 2s black clip, optionally carrying a mov_text telemetry subtitle track."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "color=c=black:s=64x64:d=2", "-c:v", "libx264", str(path)],
        check=True,
    )
    if not with_subs:
        return
    srt = path.with_suffix(".tmp.srt")
    srt.write_text(LEGACY)
    muxed = path.with_name("muxed.mp4")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-i", str(srt),
         "-c", "copy", "-c:s", "mov_text", str(muxed)],
        check=True,
    )
    muxed.replace(path)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg not installed")
def test_extract_embedded_srt_roundtrip(tmp_path):
    video = tmp_path / "clip.mp4"
    _synth_video(video, with_subs=True)
    out = extract_embedded_srt(video, tmp_path / "embedded.srt")
    assert out is not None and out.exists()
    e = parse_dji_srt(out)
    assert len(e) == 2 and e[0]["lat"] == 47.1 and e[0]["lon"] == -63.2


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg not installed")
def test_extract_embedded_srt_noop_without_track(tmp_path):
    video = tmp_path / "clip.mp4"
    _synth_video(video, with_subs=False)
    out = tmp_path / "embedded.srt"
    assert extract_embedded_srt(video, out) is None
    assert not out.exists()  # no subtitle stream -> no leftover file


def test_extract_embedded_srt_missing_video(tmp_path):
    assert extract_embedded_srt(tmp_path / "nope.mp4", tmp_path / "out.srt") is None


def parse_dji_srt_from(text: str, tmp_path) -> list[dict]:
    p = tmp_path / "_tmp.srt"
    p.write_text(text)
    return parse_dji_srt(p)
