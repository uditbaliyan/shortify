"""Helpers for building safe ffmpeg ``drawtext`` filter fragments."""

from __future__ import annotations


def escape_drawtext(text: str) -> str:
    """Escape a string for safe interpolation into an ffmpeg drawtext filter."""
    # Order matters: escape backslashes first, then the other special chars.
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\u2019")  # avoid quoting headaches entirely
    text = text.replace("%", "\\%")
    return text


def position_expr(position: str, padding: int, text_w: str = "text_w", text_h: str = "text_h") -> tuple[str, str]:
    """Return (x_expr, y_expr) drawtext expressions for a named position."""
    positions = {
        "top": (f"(w-{text_w})/2", f"{padding}"),
        "top-left": (f"{padding}", f"{padding}"),
        "top-right": (f"w-{text_w}-{padding}", f"{padding}"),
        "center": (f"(w-{text_w})/2", f"(h-{text_h})/2"),
        "bottom": (f"(w-{text_w})/2", f"h-{text_h}-{padding}"),
        "bottom-left": (f"{padding}", f"h-{text_h}-{padding}"),
        "bottom-right": (f"w-{text_w}-{padding}", f"h-{text_h}-{padding}"),
    }
    if position not in positions:
        raise ValueError(f"Unknown position: {position!r}")
    return positions[position]


def overlay_position_expr(position: str, padding: int) -> tuple[str, str]:
    """Return (x_expr, y_expr) ``overlay`` filter expressions for a named
    position, in terms of the main-frame size (W/H) and overlay size (w/h)."""
    positions = {
        "top": ("(W-w)/2", f"{padding}"),
        "top-left": (f"{padding}", f"{padding}"),
        "top-right": (f"W-w-{padding}", f"{padding}"),
        "center": ("(W-w)/2", "(H-h)/2"),
        "bottom": ("(W-w)/2", f"H-h-{padding}"),
        "bottom-left": (f"{padding}", f"H-h-{padding}"),
        "bottom-right": (f"W-w-{padding}", f"H-h-{padding}"),
    }
    if position not in positions:
        raise ValueError(f"Unknown position: {position!r}")
    return positions[position]
