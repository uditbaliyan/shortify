"""Assemble the full FFmpeg filter graph for a single part and render it.

This is where every other piece (aspect conversion, editing filters,
overlays, branding, captions) is stitched together into one
``-filter_complex`` graph and executed as a single ffmpeg invocation per
part (keeping quality high, since we only re-encode once).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shortify.captions.captions import build_captions_filter
from shortify.ffmpeg_utils import ffmpeg_run
from shortify.models.config import Config
from shortify.models.part import Part, VideoInfo
from shortify.styling.branding import build_branding_filters
from shortify.styling.overlays import build_part_label_filter
from shortify.video.convert import build_aspect_chain
from shortify.video.filters import (
    build_audio_filters,
    build_fade_out_audio_filter,
    build_fade_out_video_filter,
    build_select_expression,
    build_video_filters,
)


def _is_raw_stream_ref(label: str) -> bool:
    """True for labels like "0:a"/"0:v" that reference an input directly
    rather than naming a filtergraph pad produced by -filter_complex."""
    import re

    return bool(re.fullmatch(r"\d+:[av]", label))


@dataclass
class RenderPlan:
    """A fully-built ffmpeg command, exposed for testing/inspection."""

    inputs: list[str]
    filter_complex: str
    map_args: list[str]
    output_args: list[str]

    def to_args(self, output_path: Path, *, overwrite: bool = True) -> list[str]:
        args = list(self.inputs)
        if self.filter_complex:
            args += ["-filter_complex", self.filter_complex]
        args += self.map_args
        args += self.output_args
        args += [str(output_path)]
        return args


def build_render_plan(
    source: Path,
    part: Part,
    config: Config,
    video_info: VideoInfo,
    *,
    ass_path: Path | None = None,
    keep_segments: list[tuple[float, float]] | None = None,
) -> RenderPlan:
    """Build (but do not execute) the ffmpeg command for one part."""
    out_w, out_h = config.resolve_dimensions()
    inputs: list[str] = [
        "-ss",
        f"{part.start:.3f}",
        "-t",
        f"{part.duration:.3f}",
        "-i",
        str(source),
    ]

    next_input_index = 1
    logo_input_label: str | None = None
    if config.branding.enabled and config.branding.logo:
        inputs += ["-i", str(config.branding.logo)]
        logo_input_label = f"{next_input_index}:v"
        next_input_index += 1

    filter_lines: list[str] = []

    v_label = "0:v"
    a_label = "0:a" if video_info.has_audio else None

    # 1. Optional silence removal (applied first, on the raw decoded
    #    stream, before any scaling/overlay work).
    if keep_segments is not None:
        expr = build_select_expression(keep_segments)
        filter_lines.append(f"[{v_label}]select='{expr}',setpts=N/FRAME_RATE/TB[vsel]")
        v_label = "vsel"
        if a_label:
            filter_lines.append(
                f"[{a_label}]aselect='{expr}',asetpts=N/SR/TB[asel]"
            )
            a_label = "asel"

    # 2. Aspect-ratio conversion.
    aspect_lines, v_label = build_aspect_chain(config.mode, v_label, out_w, out_h)
    filter_lines.extend(aspect_lines)

    # 3. Editing filters (color, speed, fade-in).
    video_filters = build_video_filters(config.editing)
    if video_filters:
        filter_lines.append(f"[{v_label}]{','.join(video_filters)}[vedit]")
        v_label = "vedit"

    fade_out = build_fade_out_video_filter(config.editing, part.duration)
    if fade_out:
        filter_lines.append(f"[{v_label}]{fade_out}[vfade]")
        v_label = "vfade"

    # 4. Part-number label.
    label_filter = build_part_label_filter(config.part_label, part.number, v_label, "vlabel")
    if label_filter:
        filter_lines.append(label_filter)
        v_label = "vlabel"

    # 5. Channel branding.
    branding_lines = build_branding_filters(
        config.branding, v_label, "vbrand", logo_input_label=logo_input_label
    )
    if config.branding.enabled and (config.branding.channel_name or config.branding.logo):
        filter_lines.extend(branding_lines)
        v_label = "vbrand"

    # 6. Burned-in captions.
    if ass_path is not None:
        filter_lines.append(build_captions_filter(ass_path, v_label, "vcap"))
        v_label = "vcap"

    # --- audio chain ---
    audio_filters = build_audio_filters(config.editing)
    fade_out_audio = build_fade_out_audio_filter(config.editing, part.duration)
    if a_label and (audio_filters or fade_out_audio):
        chain = list(audio_filters)
        if fade_out_audio:
            chain.append(fade_out_audio)
        filter_lines.append(f"[{a_label}]{','.join(chain)}[aout]")
        a_label = "aout"

    filter_complex = ";".join(filter_lines)

    def _map_ref(label: str) -> str:
        # Raw stream specifiers like "0:a" refer directly to an input and
        # must NOT be bracketed; only actual filtergraph pad labels are.
        return label if _is_raw_stream_ref(label) else f"[{label}]"

    map_args = ["-map", _map_ref(v_label)]
    if a_label:
        map_args += ["-map", _map_ref(a_label)]
    else:
        map_args += ["-an"]

    output_args = [
        "-c:v",
        config.video_codec,
        "-preset",
        config.preset,
        "-crf",
        str(config.crf),
        "-pix_fmt",
        "yuv420p",
    ]
    if a_label:
        output_args += ["-c:a", config.audio_codec, "-b:a", "192k"]
    output_args += ["-movflags", "+faststart"]

    return RenderPlan(
        inputs=inputs,
        filter_complex=filter_complex,
        map_args=map_args,
        output_args=output_args,
    )


def attach_intro_outro(
    part_path: Path,
    output_path: Path,
    *,
    out_w: int,
    out_h: int,
    intro_path: Path | None = None,
    outro_path: Path | None = None,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    crf: int = 20,
    preset: str = "veryfast",
) -> None:
    """Concatenate an optional intro/outro around an already-rendered part.

    Each input is independently scaled/padded to ``out_w``x``out_h`` and
    given a silent audio track if it lacks one, then joined with the
    ``concat`` filter so mismatched source resolutions/codecs never cause
    a failed concatenation.
    """
    from shortify.video.probe import probe as _probe

    clips = [p for p in (intro_path, part_path, outro_path) if p is not None]
    inputs: list[str] = []
    prep_lines: list[str] = []
    concat_pads: list[str] = []
    next_index = len(clips)
    silent_inputs: list[str] = []

    for i, clip in enumerate(clips):
        inputs += ["-i", str(clip)]
        prep_lines.append(
            f"[{i}:v]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
            f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30[v{i}]"
        )
        info = _probe(clip)
        if info.has_audio:
            prep_lines.append(
                f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{i}]"
            )
        else:
            # Generate matching-length silence so concat always gets A/V pairs.
            silent_inputs += [
                "-f", "lavfi", "-t", f"{info.duration:.3f}",
                "-i", "anullsrc=r=48000:cl=stereo",
            ]
            prep_lines.append(f"[{next_index}:a]anull[a{i}]")
            next_index += 1
        # concat requires interleaved video/audio pads per segment.
        concat_pads.append(f"[v{i}][a{i}]")

    inputs += silent_inputs
    n = len(clips)
    filter_complex = ";".join(prep_lines)
    filter_complex += f";{''.join(concat_pads)}concat=n={n}:v=1:a=1[vout][aout]"

    args = inputs + [
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        video_codec,
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        audio_codec,
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_run(args + [str(output_path)])


def render_part(
    source: Path,
    part: Part,
    config: Config,
    video_info: VideoInfo,
    output_path: Path,
    *,
    ass_path: Path | None = None,
    keep_segments: list[tuple[float, float]] | None = None,
) -> None:
    """Build the render plan for ``part`` and execute it with ffmpeg."""
    plan = build_render_plan(
        source, part, config, video_info, ass_path=ass_path, keep_segments=keep_segments
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = plan.to_args(output_path, overwrite=config.overwrite)
    ffmpeg_run(args, overwrite=config.overwrite)
