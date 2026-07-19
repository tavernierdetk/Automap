"""Audio Director's seam — the music-generation key door.

The chair itself is still a seam (studio-org: registers reserved in
briefs, no pipeline yet), but its API access is real: the same
swappable-box pattern as GenLab's image key. The key NEVER enters the
repo and is never printed; drop it at ``~/.automap/musicgen.json``::

    {"provider": "suno", "api_key": "..."}

or export ``SUNO_API_KEY`` (or ``MUSICGEN_API_KEY``). When the music
pipeline lands (request → generate → QC → publish, mirroring
``genlab``), it starts from :func:`musicgen_config`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

KEYFILE = Path.home() / ".automap" / "musicgen.json"


def musicgen_config() -> dict:
    key = os.environ.get("SUNO_API_KEY") or os.environ.get("MUSICGEN_API_KEY")
    if key:
        return {"provider": "suno", "api_key": key}
    if KEYFILE.exists():
        cfg = json.loads(KEYFILE.read_text())
        if cfg.get("api_key"):
            return {"provider": cfg.get("provider", "suno"), **cfg}
    raise RuntimeError(
        "no music-generation key: set SUNO_API_KEY, or write "
        f"{KEYFILE} as {{\"provider\": \"suno\", \"api_key\": \"...\"}}")
