"""Build the "PART N" text overlay filter fragment."""

from __future__ import annotations

from shortify.models.config import PartLabelConfig
from shortify.styling.text import escape_drawtext, position_expr


def build_part_label_filter(
    cfg: PartLabelConfig,
    part_number: int,
    in_label: str,
    out_label: str,
) -> str | None:
    """Return a single drawtext filtergraph fragment, or ``None`` if disabled."""
    if not cfg.enabled:
        return None

    text = cfg.text.format(part=part_number)
    text = escape_drawtext(text)
    x_expr, y_expr = position_expr(cfg.position, cfg.padding)

    opts = [
        f"text='{text}'",
        f"fontsize={cfg.font_size}",
        f"fontcolor={cfg.font_color}@{cfg.opacity}",
        f"x={x_expr}",
        f"y={y_expr}",
    ]
    if cfg.font:
        opts.append(f"fontfile='{escape_drawtext(cfg.font)}'")
    if cfg.outline_width > 0:
        opts.append(f"borderw={cfg.outline_width}")
        opts.append(f"bordercolor={cfg.outline_color}@{cfg.opacity}")
    if cfg.shadow:
        opts.append("shadowx=2")
        opts.append("shadowy=2")
        opts.append("shadowcolor=black@0.6")
    if cfg.background_box:
        opts.append("box=1")
        opts.append(f"boxcolor={cfg.box_color}")
        opts.append(f"boxborderw={max(8, cfg.padding // 2)}")

    return f"[{in_label}]drawtext={':'.join(opts)}[{out_label}]"
