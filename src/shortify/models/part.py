from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoInfo:
    """Metadata about a source media file, as reported by ffprobe."""

    path: Path
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    audio_sample_rate: int | None
    audio_channels: int | None
    video_codec: str
    audio_codec: str | None
    bitrate: int | None = None
    pixel_format: str | None = None
    rotation: int = 0
    num_streams: int = 0
    subtitle_streams: int = 0
    language: str | None = None

    @property
    def aspect_ratio(self) -> float:
        if self.height == 0:
            return 0.0
        return self.width / self.height

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["path"] = str(self.path)
        return d


@dataclass
class Part:
    """A single output segment of the source video."""

    index: int
    start: float
    end: float
    output_path: Path | None = None
    thumbnail_path: Path | None = None

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    @property
    def number(self) -> int:
        """1-based part number, for display/filenames."""
        return self.index + 1

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "number": self.number,
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "output_path": str(self.output_path) if self.output_path else None,
            "thumbnail_path": str(self.thumbnail_path)
            if self.thumbnail_path
            else None,
        }
