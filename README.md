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

### 3. Options

```bash
# Custom grid and tile width
thumby "video.mp4" --rows 5 --cols 5 --width 300

# Specify output path
thumby "video.mp4" --output "preview.jpg"

# Skip the first 30 seconds
thumby "video.mp4" --skip 30
```

---

## 🛠️ Configuration

| Option | Shorthand | Default | Description |
|--------|-----------|---------|-------------|
| `--output` | `-o` | `auto` | Output path for the JPEG image. |
| `--rows` | `-r` | `9` | Number of rows in the grid. |
| `--cols` | `-c` | `3` | Number of columns in the grid. |
| `--width` | `-w` | `400` | Width of each tile in pixels. |
| `--skip` | `-s` | `10.0` | Seconds to skip from the start. |
| `--quality` | `-q` | `95` | JPEG quality (1-100). |

---

## 📝 Requirements

- **Python 3.10+**
- **FFmpeg**: Must be installed and available in your system `PATH`.
