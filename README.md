# shortify

Turn one long video into a **sequential series of vertical Shorts** — `part_01.mp4`, `part_02.mp4`,
… — covering the entire timeline, with a `PART N` label, optional branding, captions and simple
edits.

FFmpeg does all the video work. No AI clipping, no cloud services.

```
input.mp4 (42:17)  →  split  →  9:16  →  style  →  "PART N"  →  part_01.mp4 … part_N.mp4
```

---

## 1. Install

**Requirements:** Python 3.10+ and **FFmpeg** (with `libass` for captions) on your `PATH`.

```bash
ffmpeg -version          # check it's installed

cd shortify_project
pip install -e .                  # core
pip install -e ".[captions]"      # adds faster-whisper (for --captions)
pip install -e ".[download]"      # adds yt-dlp (for YouTube URLs)
pip install -e ".[all]"           # everything
```

---

## 2. Quick start

```bash
shortify input.mp4
```

That's it. You get 45-second parts, 1080×1920, blurred-background style, with `PART 1`, `PART 2`… at
the top:

```
output/
  input/
    part_01.mp4
    part_02.mp4
    ...
    metadata.json
```

**Preview first (renders nothing):**

```bash
shortify input.mp4 --dry-run
```

```
Source duration:  01:23:45
Part duration:    00:45

Parts to create:  112

Output:
output/input/
```

---

## 3. Common recipes

### Choose the part length

```bash
shortify input.mp4 --duration 30
shortify input.mp4 --duration 60
```

The last part is shorter if the video doesn't divide evenly.

### Choose how landscape becomes vertical

```bash
shortify input.mp4 --mode blur     # original centered over a blurred copy (default)
shortify input.mp4 --mode crop     # fill the frame, cut off the sides
shortify input.mp4 --mode fit      # whole video visible, padded
shortify input.mp4 --mode black    # whole video visible, black bars
```

### Use a style preset

```bash
shortify input.mp4 --style podcast
```

Presets: `default`, `minimal`, `black-bars`, `blur-background`, `podcast`, `clean`. (`clean` turns
off the part label and branding.)

### Output size / platform presets

```bash
shortify input.mp4 --preset tiktok            # 1080x1920
shortify input.mp4 --preset instagram-reels   # 1080x1920
shortify input.mp4 --width 720 --height 1280  # custom size
```

### Part label

```bash
shortify input.mp4 --part-label-position bottom
shortify input.mp4 --no-part-label
```

Positions: `top`, `top-left`, `top-right`, `center`, `bottom`, `bottom-left`, `bottom-right`. Custom
text, font, colors, box, etc. are set in the YAML config (section 5).

### Channel branding

```bash
shortify input.mp4 --channel "@mychannel"
shortify input.mp4 --logo logo.png
shortify input.mp4 --logo logo.png --channel "@mychannel"
```

### Basic editing

```bash
shortify input.mp4 --trim-start 10 --trim-end 30     # skip first 10s / last 30s
shortify input.mp4 --speed 1.25
shortify input.mp4 --volume 0.8
shortify input.mp4 --mute
shortify input.mp4 --fade-in 0.5 --fade-out 0.5
shortify input.mp4 --brightness 0.05 --contrast 1.1 --saturation 1.2
shortify input.mp4 --remove-silence
```

### Captions (optional)

```bash
pip install -e ".[captions]"

shortify input.mp4 --captions
shortify input.mp4 --captions --caption-style highlight
shortify input.mp4 --captions --caption-style boxed --caption-model small --language en
```

Styles: `basic`, `bold`, `boxed`, `highlight` (words light up as they're spoken). Models: `tiny`,
`base`, `small`, `medium`, `large-v3`. Model weights download on first use.

### Intro / outro

```bash
shortify input.mp4 --intro intro.mp4
shortify input.mp4 --outro outro.mp4
shortify input.mp4 --intro intro.mp4 --outro outro.mp4
```

### Thumbnails

```bash
shortify input.mp4 --thumbnails
```

Creates `output/input/thumbnails/part_01.png`, …

### YouTube URL

```bash
pip install -e ".[download]"

shortify "https://www.youtube.com/watch?v=XXXXXXXXXXX"
shortify "https://www.youtube.com/watch?v=XXXXXXXXXXX" --download-quality 720p
```

Qualities: `best`, `1080p`, `720p`, `480p`.

### Choose where output goes

```bash
shortify input.mp4 --output-dir ~/Videos/shorts
```

### Everything at once

```bash
shortify podcast.mp4 \
  --duration 60 \
  --style podcast \
  --mode blur \
  --channel "@mychannel" --logo logo.png \
  --captions --caption-style highlight \
  --fade-in 0.3 --fade-out 0.3 \
  --thumbnails
```

---

## 4. Python API

```python
from shortify import Shortify

job = Shortify(
    input="input.mp4",
    duration=45,
    style="podcast",
)
result = job.run()

for part in result.parts:
    print(part.number, part.start, part.end, part.output_path)

print(result.coverage.summary())
print(result.output_dir)
```

**Nested options** are passed as dicts:

```python
Shortify(
    input="input.mp4",
    duration=60,
    part_label={"text": "EP {part}", "position": "top-right"},
    branding={"enabled": True, "channel_name": "@mychannel", "logo": "logo.png"},
    editing={"fade_in": 0.3, "fade_out": 0.3, "speed": 1.1},
    captions={"enabled": True, "style": "boxed"},
    thumbnails=True,
).run()
```

**Progress callback:**

```python
def on_progress(stage, done, total):
    print(stage, done, total)

Shortify(input="input.mp4").run(progress=on_progress)
```

**Dry run (no rendering):**

```python
result = Shortify(input="input.mp4", duration=45, dry_run=True).run()
print(len(result.parts), "parts")
```

---

## 5. Config file

```bash
shortify input.mp4 --config shortify.yaml
```

Example `shortify.yaml`:

```yaml
duration: 45
style: podcast
mode: blur
thumbnails: true
filename_template: "{title}_part_{part:02d}" # e.g. my-video_part_01.mp4

part_label:
  enabled: true
  text: "PART {part}"
  position: top
  font: /path/to/font.ttf # optional
  font_size: 72
  font_color: white
  outline_color: black
  outline_width: 3
  shadow: true
  background_box: true
  box_color: "black@0.45"
  opacity: 1.0
  padding: 24

branding:
  enabled: true
  channel_name: "@mychannel"
  logo: logo.png
  position: top-left
  opacity: 0.9

captions:
  enabled: false
  style: highlight
  model: small
  font_size: 56
  position: bottom

editing:
  fade_in: 0.3
  fade_out: 0.3
  speed: 1.0
  volume: 1.0

intro:
  enabled: false
  file: intro.mp4

outro:
  enabled: false
  file: outro.mp4
```

**Precedence** (later wins): built-in defaults → style preset → YAML file → CLI flags. So
`--duration 30` on the command line beats `duration: 45` in the YAML.

---

## 6. What you get

```
output/<video-name>/
    part_01.mp4
    part_02.mp4
    ...
    thumbnails/          (only with --thumbnails)
        part_01.png
    metadata.json
```

`metadata.json` records the source, part count, output size, and per-part start/end times, plus a
coverage report:

```
Source duration:    42:17
Generated coverage: 42:17
Discarded:          00:00
Coverage:           100.00%
Gaps:               0
Overlaps:           0
```

Parts are always contiguous. Only `--trim-start` / `--trim-end` remove content.

---

## 7. All CLI flags

| Flag                                               | Purpose                                                                   |
| -------------------------------------------------- | ------------------------------------------------------------------------- |
| `--config FILE`                                    | YAML config                                                               |
| `--output-dir DIR`                                 | Output root (default `output`)                                            |
| `--duration SEC`                                   | Seconds per part (default 45)                                             |
| `--preset NAME`                                    | `youtube-shorts`, `tiktok`, `instagram-reels`                             |
| `--width` / `--height`                             | Custom output size                                                        |
| `--mode`                                           | `crop`, `fit`, `blur`, `black`                                            |
| `--style`                                          | `default`, `minimal`, `black-bars`, `blur-background`, `podcast`, `clean` |
| `--part-label` / `--no-part-label`                 | Show/hide `PART N`                                                        |
| `--part-label-position`                            | Where the label goes                                                      |
| `--channel`, `--logo`                              | Branding                                                                  |
| `--branding` / `--no-branding`                     | Force branding on/off                                                     |
| `--captions` / `--no-captions`                     | Burned-in captions                                                        |
| `--caption-style`, `--caption-model`, `--language` | Caption options                                                           |
| `--trim-start`, `--trim-end`                       | Skip seconds at start/end                                                 |
| `--remove-silence`                                 | Cut silent stretches                                                      |
| `--mute`, `--volume`, `--speed`                    | Audio/speed                                                               |
| `--fade-in`, `--fade-out`                          | Fades (seconds)                                                           |
| `--brightness`, `--contrast`, `--saturation`       | Color adjustments                                                         |
| `--intro`, `--outro`                               | Clips added around every part                                             |
| `--thumbnails`                                     | Generate thumbnails                                                       |
| `--download-quality`                               | For URL input                                                             |
| `--strict-coverage` / `--no-strict-coverage`       | Fail on any gap/overlap (default on)                                      |
| `--dry-run`                                        | Show the plan only                                                        |
| `--overwrite` / `--no-overwrite`                   | Overwrite existing files                                                  |

Run `shortify --help` for the full list.

---

## 8. Troubleshooting

| Problem                                              | Fix                                                                                            |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `Missing required binaries: ffmpeg`                  | Install FFmpeg and make sure it's on your `PATH`.                                              |
| `Captions require the optional 'captions' extra`     | `pip install -e ".[captions]"`                                                                 |
| `Downloading requires the optional 'download' extra` | `pip install -e ".[download]"`                                                                 |
| Caption text looks wrong / missing font              | Set `captions.font` in the YAML to a font installed on your system.                            |
| Part label font looks wrong                          | Set `part_label.font` to a `.ttf` path.                                                        |
| Output is slow                                       | Renders are re-encoded H.264. Use a shorter test clip first, or `--dry-run` to check the plan. |

## 9. Known limitations

- `part_label.rounded` is accepted but has no visual effect (FFmpeg text boxes are rectangular).
- With `--remove-silence`, parts are shorter than `--duration`, since silence is removed.
- Every part is re-encoded (H.264 / AAC), not stream-copied.
- Dry run can't show a part count for URLs (it doesn't download).
- Captions and YouTube download need network access (model weights / YouTube).

## 10. Development

```bash
pip install -e ".[dev]"
pytest
```
