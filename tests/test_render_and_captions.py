from pathlib import Path

from shortify import Shortify
from shortify.captions.captions import build_captions_filter, render_ass
from shortify.captions.transcript import TranscriptSegment, Word
from shortify.models.config import CaptionsConfig, Config
from shortify.models.part import Part, VideoInfo
from shortify.video.render import build_render_plan


def _info(has_audio=True):
    return VideoInfo(
        path=Path("in.mp4"), duration=60, width=1920, height=1080, fps=30,
        has_audio=has_audio, audio_sample_rate=48000, audio_channels=2,
        video_codec="h264", audio_codec="aac",
    )


def test_precedence_preset_then_yaml_then_cli():
    cfg = Config.from_layers(
        {"style": "clean", "part_label": {"enabled": True}},  # yaml
        {"duration": 20},  # cli
    )
    assert cfg.part_label.enabled is True  # explicit beats preset (clean=False)
    assert cfg.mode == "fit"  # preset value survives where not overridden
    assert cfg.duration == 20


def test_python_api_applies_style_preset():
    job = Shortify(input="x.mp4", style="black-bars")
    assert job.config.mode == "black"


def test_map_uses_unbracketed_raw_audio_stream():
    plan = build_render_plan(Path("in.mp4"), Part(0, 0, 10), Config(), _info())
    assert "0:a" in plan.map_args and "[0:a]" not in plan.map_args


def test_no_audio_source_disables_audio():
    plan = build_render_plan(Path("in.mp4"), Part(0, 0, 10), Config(), _info(False))
    assert "-an" in plan.map_args


def test_part_label_number_in_filter():
    plan = build_render_plan(Path("in.mp4"), Part(2, 20, 30), Config(), _info())
    assert "PART 3" in plan.filter_complex


def test_render_ass_highlight_uses_karaoke_tags(tmp_path):
    seg = TranscriptSegment("hello world", 0.0, 1.0,
                            [Word("hello", 0.0, 0.5), Word("world", 0.5, 1.0)])
    out = render_ass([seg], CaptionsConfig(style="highlight"),
                     video_width=1080, video_height=1920, out_path=tmp_path / "a.ass")
    text = out.read_text()
    assert "\\k50" in text and "PlayResX: 1080" in text


def test_render_ass_boxed_uses_opaque_box_border_style(tmp_path):
    seg = TranscriptSegment("hi there", 0.0, 1.0, [])
    out = render_ass([seg], CaptionsConfig(style="boxed"),
                     video_width=1080, video_height=1920, out_path=tmp_path / "b.ass")
    assert ",3,1,0,2," in out.read_text()  # BorderStyle=3


def test_captions_filter_escapes_colons():
    assert "C\\:" in build_captions_filter(Path("C:/x/a.ass"), "v", "o")
