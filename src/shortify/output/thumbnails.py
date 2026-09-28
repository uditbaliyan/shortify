"""Generate a representative thumbnail image for a rendered part."""

from __future__ import annotations

from pathlib import Path

from shortify.ffmpeg_utils import extract_frame
from shortify.models.part import Part


def generate_thumbnail(rendered_part_path: Path, part: Part, out_path: Path) -> Path:
    """Grab a frame from the middle of the rendered clip as its thumbnail."""
    midpoint = part.duration / 2.0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    extract_frame(rendered_part_path, midpoint, out_path)
    return out_path
