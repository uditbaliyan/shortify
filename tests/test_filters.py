import pytest

from shortify.models.config import EditingConfig
from shortify.video.filters import (
    _atempo_chain,
    build_audio_filters,
    build_select_expression,
    build_video_filters,
    keep_segments_from_silence,
)


@pytest.mark.parametrize(
    "speed",
    [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.5],
)
def test_atempo_chain_produces_valid_factors_within_range(speed):
    chain = _atempo_chain(speed)
    for f in chain:
        value = float(f.split("=")[1])
        assert 0.5 <= value <= 2.0

    # The product of all factors should reconstruct the requested speed.
    product = 1.0
    for f in chain:
        product *= float(f.split("=")[1])
    assert product == pytest.approx(speed, rel=1e-3)


def test_build_video_filters_includes_speed_and_eq():
    cfg = EditingConfig(speed=2.0, brightness=0.1, contrast=1.2, saturation=0.9)
    filters = build_video_filters(cfg)
    joined = ",".join(filters)
    assert "setpts=PTS/2.0" in joined
    assert "brightness=0.1" in joined
    assert "contrast=1.2" in joined
    assert "saturation=0.9" in joined


def test_build_video_filters_empty_for_defaults():
    cfg = EditingConfig()
    assert build_video_filters(cfg) == []


def test_build_audio_filters_mute_wins_over_volume():
    cfg = EditingConfig(mute=True, volume=2.0)
    filters = build_audio_filters(cfg)
    assert "volume=0" in filters
    assert "volume=2.0" not in filters


def test_keep_segments_inverts_silence():
    silence = [(2.0, 4.0), (8.0, 9.0)]
    keep = keep_segments_from_silence(silence, total_duration=10.0, padding=0.0)
    assert keep == [(0.0, 2.0), (4.0, 8.0), (9.0, 10.0)]


def test_keep_segments_no_silence_keeps_everything():
    assert keep_segments_from_silence([], total_duration=15.0) == [(0.0, 15.0)]


def test_build_select_expression_combines_segments():
    expr = build_select_expression([(0.0, 2.0), (4.0, 8.0)])
    assert expr == "between(t,0.000,2.000)+between(t,4.000,8.000)"


def test_build_select_expression_empty_segments_selects_everything():
    assert build_select_expression([]) == "1"
