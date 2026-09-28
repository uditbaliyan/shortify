from pathlib import Path

import pytest
import yaml

from shortify.models.config import Config


def test_default_config_is_valid():
    cfg = Config(input="video.mp4")
    assert cfg.validate() == []


def test_merge_overrides_top_level_field():
    cfg = Config()
    merged = cfg.merged_with({"duration": 60.0})
    assert merged.duration == 60.0
    assert cfg.duration != 60.0  # original untouched


def test_merge_overrides_nested_dataclass():
    cfg = Config()
    merged = cfg.merged_with({"part_label": {"enabled": False}})
    assert merged.part_label.enabled is False
    # Sibling fields on the nested dataclass are preserved.
    assert merged.part_label.position == cfg.part_label.position


def test_merge_ignores_none_values():
    cfg = Config(duration=45.0)
    merged = cfg.merged_with({"duration": None, "style": "podcast"})
    assert merged.duration == 45.0
    assert merged.style == "podcast"


def test_merge_ignores_unknown_keys():
    cfg = Config()
    merged = cfg.merged_with({"not_a_real_field": 123})
    assert not hasattr(merged, "not_a_real_field")


def test_from_yaml_roundtrip(tmp_path: Path):
    data = {
        "duration": 30,
        "style": "minimal",
        "part_label": {"position": "bottom"},
        "editing": {"speed": 1.25},
    }
    yaml_path = tmp_path / "shortify.yaml"
    yaml_path.write_text(yaml.dump(data))

    cfg = Config.from_yaml(yaml_path)
    assert cfg.duration == 30
    assert cfg.style == "minimal"
    assert cfg.part_label.position == "bottom"
    assert cfg.editing.speed == 1.25
    # Untouched nested fields keep their defaults.
    assert cfg.part_label.enabled is True


def test_validate_flags_bad_duration():
    cfg = Config(duration=-5)
    assert any("duration" in p for p in cfg.validate())


def test_validate_flags_unknown_style():
    cfg = Config(style="not-a-style")
    assert any("style" in p for p in cfg.validate())


def test_validate_flags_unknown_mode():
    cfg = Config(mode="fisheye")  # type: ignore[arg-type]
    assert any("mode" in p for p in cfg.validate())


def test_resolve_dimensions_from_width_height():
    cfg = Config(width=720, height=1280)
    assert cfg.resolve_dimensions() == (720, 1280)


def test_resolve_dimensions_from_preset_name():
    cfg = Config(aspect_ratio="tiktok")
    assert cfg.resolve_dimensions() == (1080, 1920)
