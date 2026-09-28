"""Optional auto-generated, burned-in captions.

Captions are opt-in (``--captions``). When enabled, this module:

1. Extracts the audio for a part's time window.
2. Transcribes it locally with ``faster-whisper`` (word-level timestamps).
3. Renders an ``.ass`` subtitle file styled per ``--caption-style``.
4. The renderer burns it in via ffmpeg's ``subtitles=`` filter.

``faster-whisper`` is an optional dependency (``pip install
shortify[captions]``); importing it is deferred until captions are
actually requested so the rest of the package works without it installed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from shortify.captions.transcript import TranscriptSegment, Word
from shortify.ffmpeg_utils import ffmpeg_run
from shortify.models.config import CaptionsConfig

_WHISPER_MODEL_CACHE: dict[str, object] = {}


class CaptionsUnavailableError(RuntimeError):
    pass


def _get_model(model_size: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - exercised only without extra
        raise CaptionsUnavailableError(
            "Captions require the optional 'captions' extra. "
            "Install it with: pip install 'shortify[captions]'"
        ) from exc

    if model_size not in _WHISPER_MODEL_CACHE:
        _WHISPER_MODEL_CACHE[model_size] = WhisperModel(
            model_size, device="auto", compute_type="auto"
        )
    return _WHISPER_MODEL_CACHE[model_size]


def transcribe_window(
    source: Path,
    start: float,
    end: float,
    *,
    model_size: str = "small",
    language: str | None = None,
) -> list[TranscriptSegment]:
    """Transcribe ``[start, end]`` of ``source`` with word-level timestamps.

    Returned segment/word timestamps are relative to ``start`` (i.e. 0 is
    the beginning of the window), matching the coordinate space of the
    rendered part.
    """
    duration = max(0.0, end - start)
    if duration <= 0:
        return []

    model = _get_model(model_size)

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "window.wav"
        ffmpeg_run(
            [
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(audio_path),
            ]
        )

        segments_iter, _info = model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
            vad_filter=True,
        )

        segments: list[TranscriptSegment] = []
        for seg in segments_iter:
            words = [
                Word(
                    text=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    probability=getattr(w, "probability", None),
                )
                for w in (seg.words or [])
            ]
            segments.append(
                TranscriptSegment(
                    text=seg.text.strip(), start=seg.start, end=seg.end, words=words
                )
            )
        return segments


# --- ASS rendering -----------------------------------------------------

_ALIGNMENT_BY_POSITION = {
    "top": 8,
    "top-left": 7,
    "top-right": 9,
    "center": 5,
    "bottom": 2,
    "bottom-left": 1,
    "bottom-right": 3,
}

_STYLE_PRESETS: dict[str, dict[str, str]] = {
    "basic": {
        "PrimaryColour": "&H00FFFFFF",
        "OutlineColour": "&H00000000",
        "BackColour": "&H00000000",
        "BorderStyle": "1",
        "Outline": "2",
        "Shadow": "1",
        "Bold": "0",
    },
    "bold": {
        "PrimaryColour": "&H00FFFFFF",
        "OutlineColour": "&H00000000",
        "BackColour": "&H00000000",
        "BorderStyle": "1",
        "Outline": "3",
        "Shadow": "1",
        "Bold": "1",
    },
    "boxed": {
        "PrimaryColour": "&H00FFFFFF",
        "OutlineColour": "&H00000000",
        "BackColour": "&H90000000",
        "BorderStyle": "3",
        "Outline": "1",
        "Shadow": "0",
        "Bold": "1",
    },
    "highlight": {
        # ASS karaoke: Secondary = not-yet-spoken words, Primary = spoken.
        "PrimaryColour": "&H0000D7FF",  # gold once spoken
        "SecondaryColour": "&H00FFFFFF",  # white before being spoken
        "OutlineColour": "&H00000000",
        "BackColour": "&H00000000",
        "BorderStyle": "1",
        "Outline": "2",
        "Shadow": "1",
        "Bold": "1",
    },
}


def _to_ass_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total_cs = int(round(seconds * 100))
    hours, rem = divmod(total_cs, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, cs = divmod(rem, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _wrap_text(words: list[str], max_chars: int) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for w in words:
        if current and length + 1 + len(w) > max_chars:
            lines.append(" ".join(current))
            current, length = [], 0
        current.append(w)
        length += len(w) + (1 if len(current) > 1 else 0)
    if current:
        lines.append(" ".join(current))
    return lines


def _build_style_header(cfg: CaptionsConfig, video_height: int) -> str:
    style = dict(_STYLE_PRESETS.get(cfg.style, _STYLE_PRESETS["basic"]))
    font = cfg.font or "DejaVu Sans"
    alignment = _ALIGNMENT_BY_POSITION.get(cfg.position, 2)
    margin_v = max(40, int(video_height * 0.08))
    fields = [
        "Name=Default",
        f"Fontname={font}",
        f"Fontsize={cfg.font_size}",
        f"PrimaryColour={style['PrimaryColour']}",
        f"SecondaryColour={style.get('SecondaryColour', '&H000000FF')}",
        f"OutlineColour={style['OutlineColour']}",
        f"BackColour={style['BackColour']}",
        f"Bold={style['Bold']}",
        "Italic=0",
        f"BorderStyle={style['BorderStyle']}",
        f"Outline={style['Outline']}",
        f"Shadow={style['Shadow']}",
        f"Alignment={alignment}",
        "MarginL=60",
        "MarginR=60",
        f"MarginV={margin_v}",
        "Encoding=1",
    ]
    return "Style: " + ",".join(f.split("=", 1)[1] for f in fields)


_STYLE_FORMAT = (
    "Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, "
    "MarginL, MarginR, MarginV, Encoding"
)


def render_ass(
    segments: list[TranscriptSegment],
    cfg: CaptionsConfig,
    *,
    video_width: int,
    video_height: int,
    out_path: Path,
) -> Path:
    """Render ``segments`` into an .ass subtitle file for the given style."""
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_width}\n"
        f"PlayResY: {video_height}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        f"Format: {_STYLE_FORMAT}\n"
        f"{_build_style_header(cfg, video_height)}\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    lines: list[str] = []
    for seg in segments:
        if cfg.style == "highlight" and seg.words:
            lines.append(_render_karaoke_line(seg, cfg.max_chars_per_line))
        else:
            wrapped = _wrap_text(seg.text.split(), cfg.max_chars_per_line)
            text = "\\N".join(wrapped)
            lines.append(
                f"Dialogue: 0,{_to_ass_timestamp(seg.start)},{_to_ass_timestamp(seg.end)},"
                f"Default,,0,0,0,,{text}"
            )

    out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _render_karaoke_line(seg: TranscriptSegment, max_chars: int) -> str:
    # Build \k tags (centiseconds per word) so libass sweeps the highlight
    # color across each word as it's spoken.
    pieces = []
    for w in seg.words:
        dur_cs = max(1, int(round((w.end - w.start) * 100)))
        pieces.append(f"{{\\k{dur_cs}}}{w.text} ")
    text = "".join(pieces).strip()
    return (
        f"Dialogue: 0,{_to_ass_timestamp(seg.start)},{_to_ass_timestamp(seg.end)},"
        f"Default,,0,0,0,,{text}"
    )


def escape_path_for_filter(path: Path) -> str:
    """Escape a filesystem path for embedding inside an ffmpeg filter string."""
    s = str(path)
    s = s.replace("\\", "\\\\")
    s = s.replace(":", "\\:")
    s = s.replace("'", "\u2019")
    return s


def build_captions_filter(ass_path: Path, in_label: str, out_label: str) -> str:
    escaped = escape_path_for_filter(ass_path)
    return f"[{in_label}]subtitles='{escaped}'[{out_label}]"
