"""Named style presets.

A preset is just a dict of :class:`~shortify.models.config.Config`
overrides, applied before any explicit CLI flags or YAML config values
(so CLI/YAML always win over the preset). Keeping presets as plain dicts
keeps the styling system simple and easy to extend.
"""

from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "default": {
        "mode": "blur",
        "part_label": {
            "enabled": True,
            "position": "top",
            "background_box": True,
            "shadow": True,
        },
    },
    "minimal": {
        "mode": "fit",
        "part_label": {
            "enabled": True,
            "position": "top",
            "background_box": False,
            "shadow": False,
            "outline_width": 2,
        },
        "branding": {"enabled": False},
    },
    "black-bars": {
        "mode": "black",
        "part_label": {
            "enabled": True,
            "position": "bottom",
            "background_box": False,
        },
    },
    "blur-background": {
        "mode": "blur",
        "part_label": {
            "enabled": True,
            "position": "top",
            "background_box": True,
        },
    },
    "podcast": {
        "mode": "blur",
        "part_label": {
            "enabled": True,
            "position": "bottom",
            "background_box": True,
            "rounded": True,
        },
        "captions": {"style": "boxed", "position": "bottom"},
    },
    "clean": {
        "mode": "fit",
        "part_label": {"enabled": False},
        "branding": {"enabled": False},
    },
}


def get_preset(name: str) -> dict[str, Any]:
    if name not in PRESETS:
        raise KeyError(
            f"Unknown style preset: {name!r}. "
            f"Available: {', '.join(sorted(PRESETS))}"
        )
    return PRESETS[name]
