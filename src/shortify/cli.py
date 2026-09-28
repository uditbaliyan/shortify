"""``shortify`` command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from shortify.models.config import Config, DEFAULT_STYLE_NAMES
from shortify.pipeline import Shortify
from shortify.styling.presets import PRESETS
from shortify.utils.timefmt import format_timestamp


def _progress_printer(stage: str, done: int, total: int) -> None:
    if stage == "done":
        click.echo(f"\rRendered {total}/{total} parts.{' ' * 10}")
        return
    click.echo(f"\rRendering part {done + 1}/{total}...", nl=False)




@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("input_source")
@click.option("--config", "config_path", type=click.Path(exists=True), help="YAML config file.")
@click.option("--output-dir", default=None, help="Output root directory (default: 'output').")
@click.option("--duration", type=float, default=None, help="Target seconds per part (default: 45).")
@click.option("--aspect", "aspect_ratio", default=None, help='Aspect ratio, e.g. "9:16", or a preset name.')
@click.option("--width", type=int, default=None, help="Output width in pixels.")
@click.option("--height", type=int, default=None, help="Output height in pixels.")
@click.option(
    "--preset",
    "aspect_preset",
    type=click.Choice(["youtube-shorts", "tiktok", "instagram-reels"]),
    default=None,
    help="Shortcut for a common aspect-ratio preset.",
)
@click.option(
    "--mode",
    type=click.Choice(["crop", "fit", "blur", "black"]),
    default=None,
    help="How landscape video is converted to vertical: crop/fit/blur/black.",
)
@click.option("--style", type=click.Choice(sorted(DEFAULT_STYLE_NAMES)), default=None, help="Named style preset.")
@click.option("--part-label/--no-part-label", "part_label_enabled", default=None, help="Show/hide the PART N overlay.")
@click.option("--part-label-position", default=None, help="Position of the PART N label.")
@click.option("--channel", "channel_name", default=None, help="Channel name/handle to display as branding.")
@click.option("--logo", type=click.Path(exists=True), default=None, help="Logo image for branding.")
@click.option("--branding/--no-branding", "branding_enabled", default=None, help="Enable/disable branding overlay.")
@click.option("--captions/--no-captions", "captions_enabled", default=None, help="Enable/disable burned-in captions.")
@click.option(
    "--caption-style",
    type=click.Choice(["basic", "bold", "boxed", "highlight"]),
    default=None,
    help="Caption visual style.",
)
@click.option(
    "--caption-model",
    default=None,
    help="faster-whisper model size (tiny/base/small/medium/large-v3).",
)
@click.option("--language", default=None, help="Force a transcription language (e.g. 'en').")
@click.option("--trim-start", type=float, default=None, help="Seconds to skip at the start.")
@click.option("--trim-end", type=float, default=None, help="Seconds to skip at the end.")
@click.option("--remove-silence/--no-remove-silence", default=None, help="Auto-cut silent sections.")
@click.option("--mute/--no-mute", default=None, help="Mute all audio.")
@click.option("--volume", type=float, default=None, help="Audio volume multiplier (1.0 = unchanged).")
@click.option("--speed", type=float, default=None, help="Playback speed multiplier (1.0 = unchanged).")
@click.option("--fade-in", type=float, default=None, help="Fade-in duration in seconds.")
@click.option("--fade-out", type=float, default=None, help="Fade-out duration in seconds.")
@click.option("--brightness", type=float, default=None, help="Brightness adjustment (-1.0 to 1.0).")
@click.option("--contrast", type=float, default=None, help="Contrast multiplier (1.0 = unchanged).")
@click.option("--saturation", type=float, default=None, help="Saturation multiplier (1.0 = unchanged).")
@click.option("--intro", type=click.Path(exists=True), default=None, help="Intro video file, prepended to every part.")
@click.option("--outro", type=click.Path(exists=True), default=None, help="Outro video file, appended to every part.")
@click.option("--thumbnails/--no-thumbnails", default=None, help="Generate a thumbnail image per part.")
@click.option(
    "--download-quality",
    default=None,
    help="Quality for YouTube downloads: best/1080p/720p/480p.",
)
@click.option("--strict-coverage/--no-strict-coverage", default=None, help="Fail if any timeline gap/overlap is detected.")
@click.option("--dry-run", is_flag=True, default=False, help="Print the plan without rendering anything.")
@click.option("--overwrite/--no-overwrite", default=None, help="Overwrite existing output files.")
@click.version_option()
def main(input_source: str, config_path: str | None, dry_run: bool, **flags: Any) -> None:
    """Split INPUT_SOURCE (a local file or a URL) into sequential Shorts.

    \b
    Examples:
      shortify video.mp4
      shortify video.mp4 --duration 45 --style podcast
      shortify "https://www.youtube.com/watch?v=..." --duration 60
      shortify video.mp4 --config shortify.yaml
    """
    yaml_layer = Config.load_yaml_dict(config_path) if config_path else {}
    cli_layer = _build_overrides(flags)
    cli_layer["input"] = input_source
    if dry_run:
        cli_layer["dry_run"] = True

    try:
        # Precedence: defaults < style preset < YAML < CLI flags.
        config = Config.from_layers(yaml_layer, cli_layer)
        job = Shortify(config=config)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if job.config.dry_run:
        _print_dry_run(job)
        return

    try:
        result = job.run(progress=_progress_printer)
    except Exception as exc:  # noqa: BLE001 - CLI boundary: surface a clean error
        raise click.ClickException(str(exc)) from exc

    click.echo()
    click.echo(result.coverage.summary())
    click.echo(f"\nWrote {len(result.parts)} part(s) to: {result.output_dir}")
    if result.metadata_path:
        click.echo(f"Metadata: {result.metadata_path}")


def _print_dry_run(job: Shortify) -> None:
    from shortify import ffmpeg_utils
    from shortify.output.manager import job_name_from_source
    from shortify.video.probe import probe
    from shortify.video.split import CoverageReport, compute_parts

    ffmpeg_utils.require_binaries()
    cfg = job.config

    if cfg.input.startswith(("http://", "https://")):
        click.echo("Dry run does not download remote URLs; showing planned settings only.")
        click.echo(f"Source:           {cfg.input}")
        click.echo(f"Part duration:    {cfg.duration}s")
        click.echo(f"Output:           {Path(cfg.output_dir)}/<video-id>/")
        return

    path = Path(cfg.input)
    if not path.exists():
        raise click.ClickException(f"Input file not found: {path}")

    info = probe(path)
    parts = compute_parts(
        info.duration,
        cfg.duration,
        trim_start=cfg.editing.trim_start,
        trim_end=cfg.editing.trim_end,
    )
    coverage = CoverageReport(info.duration, parts)
    job_name = job_name_from_source(cfg.input)

    click.echo(f"Source duration:  {format_timestamp(info.duration)}")
    click.echo(f"Part duration:    {format_timestamp(cfg.duration)}")
    click.echo()
    click.echo(f"Parts to create:  {len(parts)}")
    click.echo()
    click.echo("Output:")
    click.echo(f"{cfg.output_dir}/{job_name}/")
    click.echo()
    click.echo(coverage.summary())


def _build_overrides(flags: dict[str, Any]) -> dict[str, Any]:
    """Translate flat CLI flag names into the nested Config override shape."""
    o: dict[str, Any] = {}

    def top(key: str, flag: str) -> None:
        if flags.get(flag) is not None:
            o[key] = flags[flag]

    top("output_dir", "output_dir")
    top("duration", "duration")
    top("width", "width")
    top("height", "height")
    top("style", "style")
    top("download_quality", "download_quality")
    top("strict_coverage", "strict_coverage")
    top("overwrite", "overwrite")
    top("mode", "mode")

    if flags.get("aspect_preset"):
        o["aspect_ratio"] = flags["aspect_preset"]
    elif flags.get("aspect_ratio") is not None:
        o["aspect_ratio"] = flags["aspect_ratio"]

    part_label: dict[str, Any] = {}
    if flags.get("part_label_enabled") is not None:
        part_label["enabled"] = flags["part_label_enabled"]
    if flags.get("part_label_position") is not None:
        part_label["position"] = flags["part_label_position"]
    if part_label:
        o["part_label"] = part_label

    branding: dict[str, Any] = {}
    if flags.get("channel_name") is not None:
        branding["channel_name"] = flags["channel_name"]
        branding.setdefault("enabled", True)
    if flags.get("logo") is not None:
        branding["logo"] = flags["logo"]
        branding.setdefault("enabled", True)
    if flags.get("branding_enabled") is not None:
        branding["enabled"] = flags["branding_enabled"]
    if branding:
        o["branding"] = branding

    captions: dict[str, Any] = {}
    if flags.get("captions_enabled") is not None:
        captions["enabled"] = flags["captions_enabled"]
    if flags.get("caption_style") is not None:
        captions["style"] = flags["caption_style"]
    if flags.get("caption_model") is not None:
        captions["model"] = flags["caption_model"]
    if flags.get("language") is not None:
        captions["language"] = flags["language"]
    if captions:
        o["captions"] = captions

    editing: dict[str, Any] = {}
    for key in (
        "trim_start",
        "trim_end",
        "remove_silence",
        "mute",
        "volume",
        "speed",
        "fade_in",
        "fade_out",
        "brightness",
        "contrast",
        "saturation",
    ):
        if flags.get(key) is not None:
            editing[key] = flags[key]
    if editing:
        o["editing"] = editing

    if flags.get("intro") is not None:
        o["intro"] = {"enabled": True, "file": flags["intro"]}
    if flags.get("outro") is not None:
        o["outro"] = {"enabled": True, "file": flags["outro"]}

    if flags.get("thumbnails") is not None:
        o["thumbnails"] = flags["thumbnails"]

    return o


if __name__ == "__main__":
    main()
