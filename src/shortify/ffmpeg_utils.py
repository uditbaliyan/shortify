"""Thin, well-behaved wrappers around the ``ffmpeg``/``ffprobe`` binaries.

shortify orchestrates FFmpeg rather than re-implementing video processing
in Python. Every function here shells out to a real binary and raises a
:class:`FFmpegError` with the captured stderr on failure, so problems are
never swallowed silently.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    """Raised when an ffmpeg/ffprobe invocation fails."""

    def __init__(self, command: list[str], returncode: int, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        pretty = " ".join(command)
        super().__init__(
            f"Command failed ({returncode}): {pretty}\n--- stderr (tail) ---\n"
            f"{stderr[-4000:]}"
        )


def require_binaries() -> None:
    """Raise a clear error early if ffmpeg/ffprobe are not installed."""
    missing = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if missing:
        raise RuntimeError(
            "Missing required binaries: "
            + ", ".join(missing)
            + ". Install FFmpeg (which provides both) and ensure it is on PATH."
        )


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess command, capturing output as text."""
    proc = subprocess.run(command, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise FFmpegError(command, proc.returncode, proc.stderr)
    return proc


def ffprobe_json(path: Path) -> dict:
    """Run ffprobe and return the parsed JSON stream/format description."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = run(cmd)
    return json.loads(proc.stdout)


def ffmpeg_run(
    args: list[str],
    *,
    overwrite: bool = True,
    quiet: bool = True,
) -> subprocess.CompletedProcess:
    """Run ffmpeg with sensible default flags.

    ``args`` should be the arguments *after* the ``ffmpeg`` binary name and
    excluding the ``-y``/``-n`` overwrite flag and log-level flags, which
    are added automatically.
    """
    cmd = ["ffmpeg"]
    cmd.append("-y" if overwrite else "-n")
    if quiet:
        cmd += ["-hide_banner", "-loglevel", "error"]
    cmd += args
    return run(cmd)


def probe_duration(path: Path) -> float:
    data = ffprobe_json(path)
    fmt = data.get("format", {})
    if "duration" in fmt:
        return float(fmt["duration"])
    # Fall back to the longest stream duration.
    durations = [
        float(s["duration"]) for s in data.get("streams", []) if "duration" in s
    ]
    return max(durations) if durations else 0.0


def extract_frame(
    src: Path,
    timestamp: float,
    out_path: Path,
    *,
    width: int | None = None,
) -> None:
    """Grab a single frame at ``timestamp`` seconds and save it as an image."""
    args = ["-ss", f"{timestamp:.3f}", "-i", str(src), "-frames:v", "1"]
    if width:
        args += ["-vf", f"scale={width}:-2"]
    args += [str(out_path)]
    ffmpeg_run(args)
