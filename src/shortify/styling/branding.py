"""Build the channel-branding overlay (logo image and/or channel-name text)."""

from __future__ import annotations

from shortify.models.config import BrandingConfig
from shortify.styling.text import escape_drawtext, overlay_position_expr, position_expr


def build_branding_filters(
    cfg: BrandingConfig,
    in_label: str,
    out_label: str,
    *,
    logo_input_label: str | None = None,
) -> list[str]:
    """Return filtergraph fragments applying branding on top of ``[in_label]``.

    If ``cfg.logo`` is set, ``logo_input_label`` must be the ffmpeg input
    pad (e.g. ``"1:v"``) for the already-added logo image input. Text is
    drawn alongside (to the right of) the logo when both are present.
    """
    if not cfg.enabled or (not cfg.channel_name and not cfg.logo):
        return [f"[{in_label}]copy[{out_label}]"]

    lines: list[str] = []
    current = in_label

    if cfg.logo and logo_input_label:
        x_expr, y_expr = overlay_position_expr(cfg.position, cfg.padding)
        lines.append(
            f"[{logo_input_label}]scale=-1:{cfg.logo_height},"
            f"format=rgba,colorchannelmixer=aa={cfg.opacity}[logo_scaled]"
        )
        lines.append(f"[{current}][logo_scaled]overlay={x_expr}:{y_expr}[branded_logo]")
        current = "branded_logo"

        if cfg.channel_name:
            text = escape_drawtext(cfg.channel_name)
            # Offset text to the right of the logo, roughly.
            text_x, text_y = _text_offset_from_logo(cfg)
            opts = [
                f"text='{text}'",
                f"fontsize={cfg.font_size}",
                f"fontcolor={cfg.font_color}@{cfg.opacity}",
                f"x={text_x}",
                f"y={text_y}",
                "shadowx=1",
                "shadowy=1",
                "shadowcolor=black@0.5",
            ]
            if cfg.font:
                opts.append(f"fontfile='{escape_drawtext(cfg.font)}'")
            lines.append(f"[{current}]drawtext={':'.join(opts)}[branded]")
            current = "branded"
    elif cfg.channel_name:
        text = escape_drawtext(cfg.channel_name)
        x_expr, y_expr = position_expr(cfg.position, cfg.padding)
        opts = [
            f"text='{text}'",
            f"fontsize={cfg.font_size}",
            f"fontcolor={cfg.font_color}@{cfg.opacity}",
            f"x={x_expr}",
            f"y={y_expr}",
            "shadowx=1",
            "shadowy=1",
            "shadowcolor=black@0.5",
        ]
        if cfg.font:
            opts.append(f"fontfile='{escape_drawtext(cfg.font)}'")
        lines.append(f"[{current}]drawtext={':'.join(opts)}[branded]")
        current = "branded"

    if current != out_label:
        lines.append(f"[{current}]copy[{out_label}]")

    return lines


def _text_offset_from_logo(cfg: BrandingConfig) -> tuple[str, str]:
    """Rough placement for channel-name text next to a logo."""
    logo_w_estimate = cfg.logo_height  # assume roughly square logo
    if "left" in cfg.position or cfg.position == "top" or cfg.position == "bottom":
        x = f"{cfg.padding + logo_w_estimate + 12}"
    else:
        x = f"W-{cfg.padding + logo_w_estimate + 12}-text_w"
    y = f"{cfg.padding + (cfg.logo_height - cfg.font_size) // 2}" if "top" in cfg.position else f"H-{cfg.padding + cfg.logo_height}"
    return x, y
