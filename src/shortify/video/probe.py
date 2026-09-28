"""Inspect a source media file with ffprobe and build a :class:`VideoInfo`."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from shortify.ffmpeg_utils import ffprobe_json
from shortify.models.part import VideoInfo

SUPPORTED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
    ".mp3",
    ".wav",
}


def _parse_fps(rate_str: str | None) -> float:
    if not rate_str:
        return 0.0
    try:
        return float(Fraction(rate_str))
    except (ZeroDivisionError, ValueError):
        return 0.0


def probe(path: Path) -> VideoInfo:
    """Inspect ``path`` and return a populated :class:`VideoInfo`."""
    path = Path(path)
    data = ffprobe_json(path)
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

    duration = float(fmt.get("duration", 0.0) or 0.0)
    if duration == 0.0 and video_stream and "duration" in video_stream:
        duration = float(video_stream["duration"])

    width = int(video_stream.get("width", 0)) if video_stream else 0
    height = int(video_stream.get("height", 0)) if video_stream else 0
    fps = _parse_fps(video_stream.get("r_frame_rate")) if video_stream else 0.0
    video_codec = video_stream.get("codec_name", "") if video_stream else ""
    pixel_format = video_stream.get("pix_fmt") if video_stream else None

    rotation = 0
    if video_stream:
        tags = video_stream.get("tags", {}) or {}
        if "rotate" in tags:
            try:
                rotation = int(tags["rotate"])
            except ValueError:
                rotation = 0
        for side_data in video_stream.get("side_data_list", []) or []:
            if "rotation" in side_data:
                try:
                    rotation = int(side_data["rotation"])
                except (TypeError, ValueError):
                    pass

    audio_codec = audio_stream.get("codec_name") if audio_stream else None
    sample_rate = (
        int(audio_stream["sample_rate"])
        if audio_stream and "sample_rate" in audio_stream
        else None
    )
    channels = int(audio_stream["channels"]) if audio_stream and "channels" in audio_stream else None

    language = None
    if audio_stream:
        language = (audio_stream.get("tags", {}) or {}).get("language")

    bitrate = int(fmt["bit_rate"]) if "bit_rate" in fmt else None

    return VideoInfo(
        path=path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio=audio_stream is not None,
        audio_sample_rate=sample_rate,
        audio_channels=channels,
        video_codec=video_codec,
        audio_codec=audio_codec,
        bitrate=bitrate,
        pixel_format=pixel_format,
        rotation=rotation,
        num_streams=len(streams),
        subtitle_streams=len(subtitle_streams),
        language=language,
    )


def is_supported(path: Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS
