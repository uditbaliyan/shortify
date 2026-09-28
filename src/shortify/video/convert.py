"""Build the FFmpeg filter graph fragment that converts a clip to a target
aspect ratio using one of four modes: crop, fit, blur, black.

Each function returns ``(filter_lines, output_label)`` where
``filter_lines`` is a list of filtergraph fragments (to be joined with
``;``) that can be spliced into a larger ``-filter_complex`` graph, and
``output_label`` is the pad name (e.g. ``"vaspect"``) carrying the
converted, ``out_w``x``out_h`` video.
"""

from __future__ import annotations


def _scale_cover(label_in: str, label_out: str, w: int, h: int) -> str:
    return (
        f"[{label_in}]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h}[{label_out}]"
    )


def _scale_fit(label_in: str, label_out: str, w: int, h: int) -> str:
    return f"[{label_in}]scale={w}:{h}:force_original_aspect_ratio=decrease[{label_out}]"


def build_aspect_chain(
    mode: str,
    in_label: str,
    out_w: int,
    out_h: int,
    *,
    pad_color: str = "black",
    blur_strength: int = 25,
) -> tuple[list[str], str]:
    """Return filtergraph fragments converting ``[in_label]`` to ``out_w``x``out_h``.

    Args:
        mode: One of "crop", "fit", "blur", "black".
        in_label: The input pad label (without brackets), e.g. "0:v".
        out_w, out_h: Target output resolution.
        pad_color: Background color used by "fit"/"black" modes.
        blur_strength: Gaussian blur sigma used by "blur" mode.
    """
    lines: list[str] = []

    if mode == "crop":
        lines.append(_scale_cover(in_label, "vaspect", out_w, out_h))
        return lines, "vaspect"

    if mode in ("fit", "black"):
        color = "black" if mode == "black" else pad_color
        lines.append(_scale_fit(in_label, "vfit", out_w, out_h))
        lines.append(
            f"[vfit]pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color={color}[vaspect]"
        )
        return lines, "vaspect"

    if mode == "blur":
        # Split the source into a background branch (blurred, filling the
        # frame) and a foreground branch (the original video, letterboxed
        # to fit, centered on top of the blurred background).
        lines.append(f"[{in_label}]split=2[vbg_src][vfg_src]")
        lines.append(_scale_cover("vbg_src", "vbg_cover", out_w, out_h))
        lines.append(f"[vbg_cover]gblur=sigma={blur_strength}[vbg]")
        lines.append(_scale_fit("vfg_src", "vfg", out_w, out_h))
        lines.append("[vbg][vfg]overlay=(W-w)/2:(H-h)/2[vaspect]")
        return lines, "vaspect"

    raise ValueError(f"Unknown aspect mode: {mode!r}")
