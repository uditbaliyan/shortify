"""Output directory layout, filename resolution, and metadata writing.

Layout::

    output/
        <job-name>/
            part_01.mp4
            part_02.mp4
            ...
            thumbnails/
                part_01.png
                ...
            metadata.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from shortify.models.config import Config
from shortify.models.part import Part, VideoInfo
from shortify.video.split import CoverageReport


def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name or "output"


def job_name_from_source(source: Path | str) -> str:
    stem = Path(str(source)).stem
    return slugify(stem)


class OutputManager:
    def __init__(self, config: Config, job_name: str) -> None:
        self.config = config
        self.job_name = job_name
        self.job_dir = Path(config.output_dir) / job_name
        self.thumbnails_dir = self.job_dir / "thumbnails"

    def prepare(self) -> None:
        self.job_dir.mkdir(parents=True, exist_ok=True)
        if self.config.thumbnails:
            self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    def filename_for(self, part: Part) -> str:
        name = self.config.filename_template.format(
            part=part.number, title=self.job_name, index=part.index
        )
        if not name.endswith(".mp4"):
            name += ".mp4"
        return name

    def path_for(self, part: Part) -> Path:
        return self.job_dir / self.filename_for(part)

    def thumbnail_path_for(self, part: Part) -> Path:
        stem = Path(self.filename_for(part)).stem
        return self.thumbnails_dir / f"{stem}.png"

    def write_metadata(
        self,
        source: Path,
        video_info: VideoInfo,
        parts: list[Part],
        coverage: CoverageReport,
    ) -> Path:
        out_w, out_h = self.config.resolve_dimensions()
        metadata = {
            "source": str(source),
            "job_name": self.job_name,
            "duration": video_info.duration,
            "parts": len(parts),
            "part_duration": self.config.duration,
            "aspect_ratio": self.config.aspect_ratio,
            "output_resolution": {"width": out_w, "height": out_h},
            "mode": self.config.mode,
            "style": self.config.style,
            "coverage": coverage.to_dict(),
            "clips": [p.to_dict() for p in parts],
        }
        path = self.job_dir / "metadata.json"
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return path
