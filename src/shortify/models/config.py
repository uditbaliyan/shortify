"""Typed configuration models for shortify.

Configuration can come from three layers, applied in increasing priority:

    1. built-in defaults (this module)
    2. a YAML config file (``--config shortify.yaml``)
    3. explicit CLI flags

Layer 3 always wins over layer 2, which always wins over layer 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

AspectMode = Literal["crop", "fit", "blur", "black"]
Position = Literal[
    "top",
    "top-left",
    "top-right",
    "center",
    "bottom",
    "bottom-left",
    "bottom-right",
]

# Aspect-ratio presets: (width, height)
PRESETS: dict[str, tuple[int, int]] = {
    "youtube-shorts": (1080, 1920),
    "tiktok": (1080, 1920),
    "instagram-reels": (1080, 1920),
}

DEFAULT_STYLE_NAMES = (
    "default",
    "minimal",
    "black-bars",
    "blur-background",
    "podcast",
    "clean",
)


def _merge_dataclass(instance: Any, overrides: dict[str, Any]) -> Any:
    """Return a copy of a dataclass instance with ``overrides`` applied.

    Nested dataclasses are merged recursively. ``None`` values in
    ``overrides`` are treated as "not provided" and are skipped, so CLI
    flags that default to ``None`` never clobber a YAML-provided value.
    """
    if not is_dataclass(instance):
        return overrides if overrides is not None else instance

    updates: dict[str, Any] = {}
    field_names = {f.name for f in fields(instance)}
    for key, value in overrides.items():
        if key not in field_names:
            continue
        if value is None:
            continue
        current = getattr(instance, key)
        if is_dataclass(current) and isinstance(value, dict):
            updates[key] = _merge_dataclass(current, value)
        else:
            updates[key] = value
    return _replace(instance, **updates)


def _replace(instance: Any, **updates: Any) -> Any:
    from dataclasses import replace

    return replace(instance, **updates)


@dataclass
class PartLabelConfig:
    """Controls the "PART N" overlay burned into each clip."""

    enabled: bool = True
    text: str = "PART {part}"
    position: Position = "top"
    font: str | None = None
    font_size: int = 72
    font_color: str = "white"
    outline_color: str = "black"
    outline_width: int = 3
    shadow: bool = True
    background_box: bool = True
    box_color: str = "black@0.45"
    rounded: bool = True
    opacity: float = 1.0
    padding: int = 24


@dataclass
class BrandingConfig:
    """Controls channel-name / logo watermark overlay."""

    enabled: bool = False
    channel_name: str | None = None
    logo: str | None = None
    position: Position = "top-left"
    opacity: float = 0.9
    font: str | None = None
    font_size: int = 42
    font_color: str = "white"
    logo_height: int = 72
    padding: int = 24


@dataclass
class CaptionsConfig:
    """Controls optional auto-generated burned-in captions."""

    enabled: bool = False
    style: Literal["basic", "bold", "boxed", "highlight"] = "basic"
    model: str = "small"
    language: str | None = None
    font: str | None = None
    font_size: int = 56
    max_chars_per_line: int = 30
    position: Position = "bottom"


@dataclass
class IntroOutroConfig:
    enabled: bool = False
    file: str | None = None


@dataclass
class EditingConfig:
    """Simple, non-destructive editing knobs applied to every part."""

    trim_start: float = 0.0
    trim_end: float = 0.0
    remove_silence: bool = False
    silence_threshold_db: float = -35.0
    silence_min_duration: float = 0.6
    mute: bool = False
    volume: float = 1.0
    speed: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0


@dataclass
class Config:
    """Top-level configuration for a shortify job."""

    input: str = ""
    output_dir: str = "output"

    duration: float = 45.0
    strict_coverage: bool = True

    aspect_ratio: str = "9:16"
    width: int = 1080
    height: int = 1920
    mode: AspectMode = "blur"

    style: str = "default"

    part_label: PartLabelConfig = field(default_factory=PartLabelConfig)
    branding: BrandingConfig = field(default_factory=BrandingConfig)
    captions: CaptionsConfig = field(default_factory=CaptionsConfig)
    editing: EditingConfig = field(default_factory=EditingConfig)
    intro: IntroOutroConfig = field(default_factory=IntroOutroConfig)
    outro: IntroOutroConfig = field(default_factory=IntroOutroConfig)

    filename_template: str = "part_{part:02d}"
    thumbnails: bool = False

    download_quality: str = "best"

    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 20
    preset: str = "veryfast"

    dry_run: bool = False
    overwrite: bool = True

    def resolve_dimensions(self) -> tuple[int, int]:
        """Resolve the final (width, height) output resolution.

        A named preset (``preset``/``style`` is not used here; that's a
        different concept from an aspect-ratio preset) takes precedence
        if explicitly requested via ``aspect_ratio`` matching a preset
        name, otherwise explicit width/height win, falling back to the
        ``aspect_ratio`` string (e.g. "9:16") scaled from height.
        """
        if self.aspect_ratio in PRESETS:
            return PRESETS[self.aspect_ratio]
        return self.width, self.height

    @classmethod
    def from_layers(cls, *layers: dict[str, Any]) -> Config:
        """Build a Config from ordered override layers (later layers win).

        The style preset named by the *last* layer that sets ``style`` is
        applied first, so precedence is always:
        defaults < style preset < each layer in order.
        """
        from shortify.styling.presets import PRESETS as STYLE_PRESETS

        style = "default"
        for layer in layers:
            if layer.get("style"):
                style = layer["style"]
        cfg = cls()
        if style in STYLE_PRESETS:
            cfg = _merge_dataclass(cfg, STYLE_PRESETS[style])
        for layer in layers:
            cfg = _merge_dataclass(cfg, layer)
        return cfg

    @classmethod
    def load_yaml_dict(cls, path: str | Path) -> dict[str, Any]:
        return yaml.safe_load(Path(path).read_text()) or {}

    @classmethod
    def from_yaml(cls, path: str | Path) -> Config:
        return cls.from_layers(cls.load_yaml_dict(path))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        return cls.from_layers(data)

    def merged_with(self, overrides: dict[str, Any]) -> Config:
        """Return a new Config with non-None ``overrides`` applied on top."""
        return _merge_dataclass(self, overrides)

    def validate(self) -> list[str]:
        """Return a list of human-readable validation problems, if any."""
        problems: list[str] = []
        if self.duration <= 0:
            problems.append("duration must be > 0")
        if self.width <= 0 or self.height <= 0:
            problems.append("width/height must be > 0")
        if self.mode not in ("crop", "fit", "blur", "black"):
            problems.append(f"unknown mode: {self.mode!r}")
        if self.style not in DEFAULT_STYLE_NAMES:
            problems.append(
                f"unknown style: {self.style!r} "
                f"(expected one of {', '.join(DEFAULT_STYLE_NAMES)})"
            )
        if self.editing.speed <= 0:
            problems.append("editing.speed must be > 0")
        if self.editing.volume < 0:
            problems.append("editing.volume must be >= 0")
        if not (0.0 <= self.part_label.opacity <= 1.0):
            problems.append("part_label.opacity must be within [0, 1]")
        if not (0.0 <= self.branding.opacity <= 1.0):
            problems.append("branding.opacity must be within [0, 1]")
        return problems
