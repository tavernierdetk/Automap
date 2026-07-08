#!/usr/bin/env python
"""Character pipeline, Stage C - turn a photo into a Godot CharacterProfile.

A local Ollama vision model reads the portrait and emits high-level traits (hair,
build, glasses, colours, an estimated height); we write them as a .tres profile that
Stage A renders unchanged. Runs entirely on this machine — the photo never leaves it.

Prereqs (one-time):
    brew install ollama && ollama serve        # in another terminal
    ollama pull qwen2.5vl:3b

Drop reference photos in input/CharacterReferences/. With no path, the newest one there
is used.

Usage:
    python scripts/char_photo_to_profile.py                          # newest reference photo
    python scripts/char_photo_to_profile.py input/CharacterReferences/me.jpg
    python scripts/char_photo_to_profile.py me.jpg --out godot/profiles/me.tres --height 1.68
    python scripts/char_photo_to_profile.py me.jpg --dry-run         # inspect, write nothing

Then point game.tscn's Body.profile at the generated .tres (or pass it however you load
profiles) and walk around as that character.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

# Allow running the script directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automap.character import (  # noqa: E402
    DEFAULT_HOST,
    DEFAULT_MODEL,
    PROFILE_OUT_DIR,
    REFERENCE_DIR,
    attributes_to_tres,
    newest_reference,
    photo_to_profile,
)

app = typer.Typer(add_completion=False)


@app.command()
def main(
    image: Optional[Path] = typer.Argument(None, help=f"Portrait photo (default: newest in {REFERENCE_DIR}/)"),
    out: Optional[Path] = typer.Option(None, "--out", help=f"Output .tres (default {PROFILE_OUT_DIR}/<image>.tres)"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="Ollama vision model"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Ollama server URL"),
    height: Optional[float] = typer.Option(None, "--height", help="Override the height estimate (metres)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Read traits and print the profile, but write nothing"),
):
    if image is None:
        image = newest_reference()
        if image is None:
            typer.echo(f"[char stage C] no photo given and none found in {REFERENCE_DIR}/")
            raise typer.Exit(code=1)
        typer.echo(f"[char stage C] using newest reference: {image}")
    if not image.exists():
        typer.echo(f"[char stage C] photo not found: {image}")
        raise typer.Exit(code=1)

    out_path = out or Path(PROFILE_OUT_DIR) / f"{image.stem}.tres"
    log = lambda m: typer.echo(f"[char stage C] {m}")

    try:
        attrs = photo_to_profile(
            image, out_path, model=model, host=host,
            height_override=height, write=not dry_run, on_log=log,
        )
    except (ConnectionError, ValueError, FileNotFoundError) as e:
        log(f"failed: {e}")
        raise typer.Exit(code=1)

    if dry_run:
        typer.echo("\n# --- profile that would be written to " + str(out_path) + " ---")
        typer.echo(attributes_to_tres(attrs))
    else:
        log("done. Assign this profile on the character's Body node in Godot.")


if __name__ == "__main__":
    app()
