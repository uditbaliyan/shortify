"""Optional YouTube (and other yt-dlp-supported site) downloading.

Kept entirely separate from the core video-processing pipeline: if
``yt-dlp`` is not installed, everything else in shortify still works for
local files.
"""

from __future__ import annotations

from pathlib import Path

_URL_PREFIXES = ("http://", "https://")


class DownloaderUnavailableError(RuntimeError):
    pass


def is_url(source: str) -> bool:
    return source.strip().lower().startswith(_URL_PREFIXES)


_QUALITY_FORMAT_MAP = {
    "best": "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
}


def download(
    url: str,
    output_dir: Path,
    *,
    quality: str = "best",
) -> Path:
    """Download ``url`` with yt-dlp and return the path to the downloaded file."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise DownloaderUnavailableError(
            "Downloading requires the optional 'download' extra. "
            "Install it with: pip install 'shortify[download]'"
        ) from exc

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fmt = _QUALITY_FORMAT_MAP.get(quality, quality)

    ydl_opts = {
        "format": fmt,
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # merge_output_format may change the extension after muxing.
        candidate = Path(filename)
        if not candidate.exists():
            candidate = candidate.with_suffix(".mp4")
        return candidate
