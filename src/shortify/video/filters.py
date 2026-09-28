"""Simple, automated editing filters: color adjustments, speed, volume,
fades, and silence detection/removal.

This module is intentionally small in scope (per the project brief this is
not meant to become a full video editor).
"""

from __future__ import annotations

import re
from pathlib import Path

from shortify.ffmpeg_utils import ffmpeg_run
from shortify.models.config import EditingConfig

_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")


def build_video_filters(cfg: EditingConfig) -> list[str]:
    """Return a list of video-filter fragments (unlabeled, chained with commas)."""
    filters: list[str] = []

    if cfg.speed != 1.0:
        filters.append(f"setpts=PTS/{cfg.speed}")

    eq_parts = []
    if cfg.brightness != 0.0:
        eq_parts.append(f"brightness={cfg.brightness}")
    if cfg.contrast != 1.0:
        eq_parts.append(f"contrast={cfg.contrast}")
    if cfg.saturation != 1.0:
        eq_parts.append(f"saturation={cfg.saturation}")
    if eq_parts:
        filters.append("eq=" + ":".join(eq_parts))

    if cfg.fade_in > 0:
        filters.append(f"fade=t=in:st=0:d={cfg.fade_in}")

    return filters


def build_fade_out_video_filter(cfg: EditingConfig, clip_duration: float) -> str | None:
    if cfg.fade_out <= 0:
        return None
    start = max(0.0, clip_duration - cfg.fade_out)
    return f"fade=t=out:st={start:.3f}:d={cfg.fade_out}"


def _atempo_chain(speed: float) -> list[str]:
    """ffmpeg's ``atempo`` filter only accepts [0.5, 2.0]; chain it for
    speeds outside that range."""
    if speed <= 0:
        raise ValueError("speed must be > 0")
    filters: list[str] = []
    remaining = speed
    # Repeatedly apply the largest valid factor until we reach the target.
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    if abs(remaining - 1.0) > 1e-9:
        filters.append(f"atempo={remaining:.6f}")
    return filters or ["atempo=1.0"]


def build_audio_filters(cfg: EditingConfig) -> list[str]:
    """Return a list of audio-filter fragments (unlabeled, chained with commas)."""
    filters: list[str] = []

    if cfg.speed != 1.0:
        filters.extend(_atempo_chain(cfg.speed))

    if cfg.mute:
        filters.append("volume=0")
    elif cfg.volume != 1.0:
        filters.append(f"volume={cfg.volume}")

    if cfg.fade_in > 0:
        filters.append(f"afade=t=in:st=0:d={cfg.fade_in}")

    return filters


def build_fade_out_audio_filter(cfg: EditingConfig, clip_duration: float) -> str | None:
    if cfg.fade_out <= 0:
        return None
    start = max(0.0, clip_duration - cfg.fade_out)
    return f"afade=t=out:st={start:.3f}:d={cfg.fade_out}"


def detect_silence(
    path: Path,
    *,
    start: float,
    end: float,
    threshold_db: float = -35.0,
    min_duration: float = 0.6,
) -> list[tuple[float, float]]:
    """Run ffmpeg's ``silencedetect`` over ``[start, end]`` of ``path``.

    Returns a list of ``(silence_start, silence_end)`` tuples, relative to
    ``start`` (i.e. 0 == the start of the analyzed window).
    """
    duration = max(0.0, end - start)
    if duration <= 0:
        return []

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(path),
        "-af",
        f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f",
        "null",
        "-",
    ]
    import subprocess

    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = proc.stderr

    starts = [float(m) for m in _SILENCE_START_RE.findall(log)]
    ends = [float(m) for m in _SILENCE_END_RE.findall(log)]

    # silencedetect may report a trailing silence_start with no matching
    # silence_end if the window ends while still silent.
    pairs: list[tuple[float, float]] = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration
        pairs.append((max(0.0, s), min(duration, e)))
    return pairs


def keep_segments_from_silence(
    silence_pairs: list[tuple[float, float]],
    total_duration: float,
    *,
    padding: float = 0.08,
) -> list[tuple[float, float]]:
    """Invert silence intervals into "speaking" (keep) intervals.

    ``padding`` seconds are preserved around each cut so words are not
    clipped at the boundary.
    """
    if not silence_pairs:
        return [(0.0, total_duration)]

    silence_pairs = sorted(silence_pairs)
    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for s_start, s_end in silence_pairs:
        s_start = max(0.0, s_start + padding)
        s_end = min(total_duration, s_end - padding)
        if s_start > cursor:
            keep.append((cursor, min(s_start, total_duration)))
        cursor = max(cursor, s_end)
    if cursor < total_duration:
        keep.append((cursor, total_duration))

    # Drop degenerate/negative-length segments produced by padding overlap.
    return [(a, b) for a, b in keep if b - a > 0.02]


def build_select_expression(segments: list[tuple[float, float]]) -> str:
    """Build a ``select``/``aselect`` boolean expression for ``segments``."""
    if not segments:
        return "1"
    parts = [f"between(t,{a:.3f},{b:.3f})" for a, b in segments]
    return "+".join(parts)
