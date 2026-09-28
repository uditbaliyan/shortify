"""The main :class:`Shortify` pipeline: the Python-API entry point.

    from shortify import Shortify

    job = Shortify(input="input.mp4", duration=45, style="podcast")
    result = job.run()
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from shortify import ffmpeg_utils
from shortify.cache import Cache, cache_key, fingerprint_file
from shortify.downloader import download, is_url
from shortify.models.config import Config
from shortify.models.part import Part, VideoInfo
from shortify.output.manager import OutputManager, job_name_from_source
from shortify.output.thumbnails import generate_thumbnail
from shortify.styling.presets import PRESETS, get_preset
from shortify.video.filters import detect_silence, keep_segments_from_silence
from shortify.video.probe import probe
from shortify.video.render import attach_intro_outro, render_part
from shortify.video.split import CoverageReport, compute_parts

ProgressCallback = Callable[[str, int, int], None]


@dataclass
class ShortifyResult:
    job_name: str
    source: Path
    video_info: VideoInfo
    parts: list[Part]
    coverage: CoverageReport
    metadata_path: Path | None = None
    output_dir: Path | None = None


class Shortify:
    """Programmatic entry point mirroring the CLI's behavior."""

    def __init__(self, config: Config | None = None, **overrides: Any) -> None:
        """Create a job.

        * ``Shortify(input=..., style=...)``: defaults < style preset < kwargs.
        * ``Shortify(config=cfg, **kw)``: ``cfg`` is used as-is; kwargs are
          applied on top (a new ``style`` kwarg re-applies that preset
          beneath the kwargs, but over ``cfg``).
        """
        if config is None:
            self.config = Config.from_layers(overrides)
        else:
            style = overrides.get("style")
            if style and style != config.style:
                preset = {**get_preset(style), "style": style} if style in PRESETS else {}
                config = config.merged_with(preset)
            self.config = config.merged_with(overrides)

        problems = self.config.validate()
        if problems:
            raise ValueError("Invalid configuration:\n- " + "\n- ".join(problems))

    def run(self, progress: ProgressCallback | None = None) -> ShortifyResult:
        cfg = self.config
        ffmpeg_utils.require_binaries()

        source = self._resolve_source(cfg.input)
        video_info = probe(source)

        job_name = job_name_from_source(cfg.input if not is_url(cfg.input) else source)
        cache = Cache(Path(cfg.output_dir) / job_name / ".cache")

        parts = compute_parts(
            video_info.duration,
            cfg.duration,
            trim_start=cfg.editing.trim_start,
            trim_end=cfg.editing.trim_end,
        )
        coverage = CoverageReport(
            video_info.duration,
            parts,
            trim_start=cfg.editing.trim_start,
            trim_end=cfg.editing.trim_end,
        )

        if cfg.strict_coverage and (coverage.gap_count or coverage.overlap_count):
            raise RuntimeError(
                "strict_coverage is enabled but the computed parts contain "
                f"{coverage.gap_count} gap(s) and {coverage.overlap_count} "
                "overlap(s). This indicates a bug in split logic."
            )

        manager = OutputManager(cfg, job_name)

        if cfg.dry_run:
            manager_dir = manager.job_dir
            return ShortifyResult(
                job_name=job_name,
                source=source,
                video_info=video_info,
                parts=parts,
                coverage=coverage,
                output_dir=manager_dir,
            )

        manager.prepare()

        total = len(parts)
        for i, part in enumerate(parts):
            if progress:
                progress("rendering", i, total)
            self._render_one_part(source, part, video_info, manager, cache)

        metadata_path = manager.write_metadata(source, video_info, parts, coverage)

        if progress:
            progress("done", total, total)

        return ShortifyResult(
            job_name=job_name,
            source=source,
            video_info=video_info,
            parts=parts,
            coverage=coverage,
            metadata_path=metadata_path,
            output_dir=manager.job_dir,
        )

    # -- internals --------------------------------------------------

    def _resolve_source(self, source: str) -> Path:
        if is_url(source):
            download_dir = Path(self.config.output_dir) / ".downloads"
            return download(source, download_dir, quality=self.config.download_quality)
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        return path

    def _render_one_part(
        self,
        source: Path,
        part: Part,
        video_info: VideoInfo,
        manager: OutputManager,
        cache: Cache,
    ) -> None:
        cfg = self.config
        out_path = manager.path_for(part)
        part.output_path = out_path

        keep_segments = None
        if cfg.editing.remove_silence and video_info.has_audio:
            fp = fingerprint_file(source)
            key = cache_key(
                fp,
                {
                    "part": part.index,
                    "threshold": cfg.editing.silence_threshold_db,
                    "min_duration": cfg.editing.silence_min_duration,
                    "start": part.start,
                    "end": part.end,
                },
            )
            cached = cache.get("silence", key)
            if cached is not None:
                keep_segments = [tuple(seg) for seg in cached]
            else:
                silence_pairs = detect_silence(
                    source,
                    start=part.start,
                    end=part.end,
                    threshold_db=cfg.editing.silence_threshold_db,
                    min_duration=cfg.editing.silence_min_duration,
                )
                keep_segments = keep_segments_from_silence(
                    silence_pairs, part.duration
                )
                cache.set("silence", key, keep_segments)

        ass_path = None
        if cfg.captions.enabled:
            ass_path = self._build_captions_for_part(source, part)

        if cfg.intro.enabled or cfg.outro.enabled:
            with tempfile.TemporaryDirectory() as tmp:
                raw_part_path = Path(tmp) / "raw_part.mp4"
                render_part(
                    source,
                    part,
                    cfg,
                    video_info,
                    raw_part_path,
                    ass_path=ass_path,
                    keep_segments=keep_segments,
                )
                out_w, out_h = cfg.resolve_dimensions()
                attach_intro_outro(
                    raw_part_path,
                    out_path,
                    out_w=out_w,
                    out_h=out_h,
                    intro_path=Path(cfg.intro.file) if cfg.intro.enabled and cfg.intro.file else None,
                    outro_path=Path(cfg.outro.file) if cfg.outro.enabled and cfg.outro.file else None,
                    video_codec=cfg.video_codec,
                    audio_codec=cfg.audio_codec,
                    crf=cfg.crf,
                    preset=cfg.preset,
                )
        else:
            render_part(
                source,
                part,
                cfg,
                video_info,
                out_path,
                ass_path=ass_path,
                keep_segments=keep_segments,
            )

        if cfg.thumbnails:
            thumb_path = manager.thumbnail_path_for(part)
            generate_thumbnail(out_path, part, thumb_path)
            part.thumbnail_path = thumb_path

    def _build_captions_for_part(self, source: Path, part: Part) -> Path:
        from shortify.captions.captions import render_ass, transcribe_window

        cfg = self.config
        out_w, out_h = cfg.resolve_dimensions()
        segments = transcribe_window(
            source,
            part.start,
            part.end,
            model_size=cfg.captions.model,
            language=cfg.captions.language,
        )
        ass_dir = Path(cfg.output_dir) / ".tmp_captions"
        ass_dir.mkdir(parents=True, exist_ok=True)
        ass_path = ass_dir / f"part_{part.number:03d}.ass"
        return render_ass(
            segments, cfg.captions, video_width=out_w, video_height=out_h, out_path=ass_path
        )
