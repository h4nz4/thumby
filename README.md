![Thumby logo](logo.png)
# thumby

**thumby** is a high-performance media utility designed to create beautiful video thumbnail sheets from a provided video file. It extracts frames at regular intervals and arranges them into a grid with a technical header.

![Python >=3.10](https://img.shields.io/badge/python-3.10%2B-blue)
![FFmpeg required](https://img.shields.io/badge/ffmpeg-required-orange)

---

## ✨ Features

- 🖼️ **Professional Layout**: Creates a grid of thumbnails with a full technical metadata header (size, duration, resolution, codecs).
- ⚡ **High Performance**: Uses `PyAV` (FFmpeg bindings) for fast frame extraction and `Pillow` for image processing.
- 📊 **Progress Bar**: Real-time progress tracking while extracting frames.
- 🛠️ **Customizable**: Control rows, columns, tile width, skip time, and JPEG quality.
- 🎞️ **Animated GIF / WebP**: Optional `--gif` or `--webp` writes a short looping preview (same `--skip`, `--width`, `--gif-duration`, and `--gif-fps` as for GIF). WebP needs Pillow with **libwebp** (usual wheels include it).

---

## 🚀 Quick Start

### 1. Installation

Install **thumby** as a global tool using [uv](https://github.com/astral-sh/uv):

```bash
uv tool install thumby-cli
```

### 2. Usage

Generate a thumbnail sheet for a video:

```bash
thumby "my_video.mp4"
```

This will create `my_video_preview.jpg` in the same directory.

Animated GIF (starts after `--skip`, default 2 s clip at 10 fps, max 120 frames):

```bash
thumby "my_video.mp4" --gif
```

Writes `my_video_preview.gif` by default. Use `-o` for a custom path. Grid options (`--rows`, `--cols`, `--quality`) only apply to JPEG sheets, not `--gif` / `--webp`.

Animated WebP (same timing options as GIF; default quality 80, optional `--webp-lossless`):

```bash
thumby "my_video.mp4" --webp
```

Writes `my_video_preview.webp`. If saving fails, your Pillow build may lack WebP—reinstall from PyPI wheels or use `--gif`.

### 3. Options

```bash
# Custom grid and tile width
thumby "video.mp4" --rows 5 --cols 5 --width 300

# Specify output path
thumby "video.mp4" --output "preview.jpg"

# Skip the first 30 seconds
thumby "video.mp4" --skip 30

# GIF: 3 s clip at 15 fps from 5 s into the video
thumby "video.mp4" --gif --skip 5 --gif-duration 3 --gif-fps 15 -o preview.gif

# WebP: same clip settings, higher compression control
thumby "video.mp4" --webp --skip 5 --gif-duration 3 --gif-fps 15 --webp-quality 75 -o preview.webp
```

---

## 🛠️ Configuration

| Option | Shorthand | Default | Description |
|--------|-----------|---------|-------------|
| `--output` | `-o` | `auto` | Output path (`.jpg`, `.gif`, or `.webp` depending on mode). |
| `--rows` | `-r` | `9` | Number of rows in the grid. |
| `--cols` | `-c` | `3` | Number of columns in the grid. |
| `--width` | `-w` | `400` | Width of each tile in pixels. |
| `--skip` | `-s` | `10.0` | Seconds to skip from the start. |
| `--quality` | `-q` | `95` | JPEG quality (1-100). Sheet mode only; ignored with `--gif` / `--webp`. |
| `--gif` | | `off` | Write an animated GIF instead of a JPEG sheet. |
| `--webp` | | `off` | Write an animated WebP instead of a JPEG sheet (not with `--gif`). |
| `--gif-duration` | | `2.0` | Animated clip length for `--gif` / `--webp` (clamped after `--skip`). |
| `--gif-fps` | | `10.0` | Frames per second for `--gif` / `--webp` (max 120 frames). |
| `--webp-quality` | | `80` | WebP quality 0–100 (`--webp` only; ignored with `--webp-lossless`). |
| `--webp-lossless` | | `off` | Lossless WebP (`--webp` only). |

---

## 📝 Requirements

- **Python 3.10+**
- **FFmpeg**: Must be installed and available in your system `PATH`.
- **WebP**: Animated WebP uses Pillow’s WebP encoder (**libwebp**). Standard Pillow wheels on Windows/macOS/Linux usually support it; if `--webp` errors, try reinstalling Pillow or use `--gif`.
