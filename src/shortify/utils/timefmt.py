"""Small helpers for formatting durations/timestamps for humans and ffmpeg."""

from __future__ import annotations


def format_timestamp(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS`` (or ``MM:SS`` when under an hour)."""
    seconds = max(0.0, seconds)
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp: ``HH:MM:SS,mmm``."""
    seconds = max(0.0, seconds)
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def format_ffmpeg_time(seconds: float) -> str:
    """Format seconds for use in ffmpeg ``-ss``/``-to`` arguments."""
    return f"{max(0.0, seconds):.3f}"
