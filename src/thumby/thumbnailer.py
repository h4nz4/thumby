from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable
from typing import cast

import av
from PIL import Image, ImageColor, ImageDraw, ImageFont, features
from pymediainfo import MediaInfo

MAX_ANIM_FRAMES = 120
MAX_GIF_FRAMES = MAX_ANIM_FRAMES


@dataclass(slots=True)
class ThumbnailerParams:
    columns: int = 3
    rows: int = 9
    tile_width: int = 400
    spacing: int = 2
    background_color: str = "black"
    header_font_color: str = "white"
    timestamp_font_color: str = "white"
    timestamp_shadow_color: str = "black"
    skip_seconds: float = 10.0
    jpeg_quality: int = 95
    fast_keyframes: bool = True


class Thumbnailer:
    def __init__(self, params: ThumbnailerParams) -> None:
        self.params = params
        self.background_rgb = ImageColor.getrgb(params.background_color)
        self.header_font_rgb = ImageColor.getrgb(params.header_font_color)
        self.timestamp_font_rgb = ImageColor.getrgb(params.timestamp_font_color)
        self.timestamp_shadow_rgb = ImageColor.getrgb(params.timestamp_shadow_color)
        self.header_font = ImageFont.load_default()
        self.timestamp_font = ImageFont.load_default()

    def create_and_save_preview_thumbnails_for(
        self,
        video_path: Path,
        output_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        image = self.create_preview_thumbnails_for(
            video_path,
            progress_callback=progress_callback,
        )
        image.save(output_path, quality=self.params.jpeg_quality)

    def create_and_save_animated_gif(
        self,
        video_path: Path,
        output_path: Path,
        gif_duration_seconds: float,
        gif_fps: float,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        targets = self._read_animation_targets(
            video_path, gif_duration_seconds, gif_fps
        )
        frames_rgb = self._capture_animation_frames(
            video_path,
            targets,
            progress_callback=progress_callback,
        )
        if not frames_rgb:
            raise ValueError(f"Could not capture frames for GIF from: {video_path}")

        palette_frames = self._frames_to_gif_palette(frames_rgb)
        duration_ms = max(1, round(1000.0 / gif_fps))
        palette_frames[0].save(
            output_path,
            format="GIF",
            save_all=True,
            append_images=palette_frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=True,
        )

    def create_and_save_animated_webp(
        self,
        video_path: Path,
        output_path: Path,
        anim_duration_seconds: float,
        anim_fps: float,
        quality: int = 80,
        lossless: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        if not features.check("webp"):
            raise ValueError(
                "WebP is not supported by this Pillow build (libwebp). "
                "Install a Pillow wheel with WebP support, or use --gif instead."
            )

        targets = self._read_animation_targets(
            video_path, anim_duration_seconds, anim_fps
        )
        frames_rgb = self._capture_animation_frames(
            video_path,
            targets,
            progress_callback=progress_callback,
        )
        if not frames_rgb:
            raise ValueError(f"Could not capture frames for WebP from: {video_path}")

        q = max(0, min(100, quality))
        rgb = [f.convert("RGB") for f in frames_rgb]
        duration_ms = max(1, round(1000.0 / anim_fps))
        save_kw: dict[str, Any] = {
            "format": "WEBP",
            "save_all": True,
            "append_images": rgb[1:],
            "duration": duration_ms,
            "loop": 0,
            "lossless": lossless,
            "method": 4,
        }
        if not lossless:
            save_kw["quality"] = q
        try:
            rgb[0].save(output_path, **save_kw)
        except OSError as exc:
            raise ValueError(
                f"Could not write animated WebP ({exc}). "
                "Try --gif, or reinstall Pillow with full WebP support."
            ) from exc

    def _read_animation_targets(
        self,
        video_path: Path,
        anim_duration_seconds: float,
        anim_fps: float,
    ) -> list[float]:
        metadata = self._read_metadata(video_path)
        duration_seconds = float(cast(float, metadata["duration_seconds"]))
        if duration_seconds <= 0:
            raise ValueError(f"Video has no valid duration: {video_path}")

        if anim_fps <= 0:
            raise ValueError("Animation fps must be positive")
        if anim_duration_seconds <= 0:
            raise ValueError("Animation duration must be positive")

        skip = min(
            max(self.params.skip_seconds, 0.0), max(duration_seconds - 0.001, 0.0)
        )
        timeline = duration_seconds - skip
        if timeline <= 0:
            skip = 0.0
            timeline = duration_seconds

        clip_end = min(skip + anim_duration_seconds, duration_seconds - 1e-6)
        clip_len = clip_end - skip
        if clip_len <= 0:
            raise ValueError("No time left in video after skip for animated clip")

        n_frames = min(
            MAX_ANIM_FRAMES,
            max(1, math.ceil(clip_len * anim_fps - 1e-9)),
        )
        return [
            min(skip + (i + 0.5) / anim_fps, clip_end - 1e-9) for i in range(n_frames)
        ]

    def create_preview_thumbnails_for(
        self,
        video_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Image.Image:
        metadata = self._read_metadata(video_path)
        duration_seconds = float(cast(float, metadata["duration_seconds"]))
        if duration_seconds <= 0:
            raise ValueError(f"Video has no valid duration: {video_path}")

        tile_count = self.params.columns * self.params.rows
        if tile_count <= 0:
            raise ValueError("rows and columns must produce at least one thumbnail")

        skip = min(
            max(self.params.skip_seconds, 0.0), max(duration_seconds - 0.001, 0.0)
        )
        timeline = duration_seconds - skip
        if timeline <= 0:
            skip = 0.0
            timeline = duration_seconds

        step = timeline / tile_count
        timestamps = [skip + ((i + 0.5) * step) for i in range(tile_count)]

        thumbnails = self._capture_thumbnails(
            video_path,
            timestamps,
            progress_callback=progress_callback,
        )
        if not thumbnails:
            raise ValueError(f"Could not capture thumbnails from: {video_path}")

        first_width, first_height = thumbnails[0].size
        if first_width <= 0 or first_height <= 0:
            raise ValueError("Captured thumbnail has invalid dimensions")

        aspect_ratio = first_width / first_height
        thumb_width = self.params.tile_width
        thumb_height = max(1, int(thumb_width / aspect_ratio))
        image_width = thumb_width * self.params.columns + self.params.spacing * (
            self.params.columns + 1
        )

        header_lines = self._build_header_lines(video_path, metadata)
        text_line_spacing = 2
        header_height = self.params.spacing
        for line in header_lines:
            header_height += self._font_height(line, self.header_font)
            header_height += text_line_spacing
        if header_lines:
            header_height -= text_line_spacing

        image_height = (
            header_height
            + thumb_height * self.params.rows
            + self.params.spacing * (self.params.rows + 1)
        )

        output = Image.new(
            "RGB", (image_width, image_height), color=self.background_rgb
        )
        draw = ImageDraw.Draw(output)

        x = self.params.spacing
        y = self.params.spacing
        for line in header_lines:
            draw.text((x, y), line, fill=self.header_font_rgb, font=self.header_font)
            y += self._font_height(line, self.header_font) + text_line_spacing

        y = header_height + self.params.spacing
        idx = 0
        for _ in range(self.params.rows):
            x = self.params.spacing
            for _ in range(self.params.columns):
                if idx >= len(thumbnails):
                    break
                resized = thumbnails[idx].resize((thumb_width, thumb_height))
                output.paste(resized, (x, y))
                timestamp_label = self._format_time(timestamps[idx])
                self._draw_timestamp(draw, x, y, thumb_height, timestamp_label)
                x += thumb_width + self.params.spacing
                idx += 1
            y += thumb_height + self.params.spacing

        return output

    def _capture_thumbnails(
        self,
        video_path: Path,
        timestamps: list[float],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Image.Image]:
        images: list[Image.Image] = []
        total = len(timestamps)
        captured = 0

        if progress_callback is not None:
            progress_callback(0, total)

        with av.open(str(video_path)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            stream.thread_count = 0
            filter_graph, graph_src, graph_sink = self._build_scale_filter_graph(stream)

            for target_second in timestamps:
                image = self._capture_frame(
                    container,
                    stream,
                    filter_graph,
                    graph_src,
                    graph_sink,
                    target_second,
                )
                if image is not None:
                    images.append(image)
                captured += 1
                if progress_callback is not None:
                    progress_callback(captured, total)

        if images and len(images) < len(timestamps):
            last = images[-1]
            images.extend(last.copy() for _ in range(len(timestamps) - len(images)))

        return images

    def _capture_animation_frames(
        self,
        video_path: Path,
        targets: list[float],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Image.Image]:
        total = len(targets)
        if progress_callback is not None:
            progress_callback(0, total)

        images: list[Image.Image] = []
        start_seek = max(0.0, targets[0])

        with av.open(str(video_path)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            stream.thread_count = 0
            filter_graph, graph_src, graph_sink = self._build_scale_filter_graph(stream)

            time_base = float(stream.time_base) if stream.time_base is not None else 0.0
            if time_base <= 0.0:
                return []

            seek_position = int(start_seek / time_base)
            if stream.start_time is not None:
                seek_position += int(stream.start_time)

            try:
                container.seek(
                    seek_position, stream=stream, any_frame=False, backward=True
                )
                codec_context = getattr(stream, "codec_context", None)
                if codec_context is not None:
                    codec_context.flush_buffers()
            except Exception:
                return []

            t_idx = 0
            prev_t: float | None = None
            prev_img: Image.Image | None = None
            done = 0

            try:
                for frame in container.decode(video=stream.index):
                    if frame.pts is None:
                        continue
                    t = float(frame.pts * stream.time_base)
                    img = self._filter_frame(
                        frame, filter_graph, graph_src, graph_sink
                    )

                    if prev_t is None:
                        while t_idx < len(targets) and targets[t_idx] <= t:
                            images.append(img.copy())
                            t_idx += 1
                            done += 1
                            if progress_callback is not None:
                                progress_callback(done, total)
                        prev_t, prev_img = t, img
                        if t_idx >= len(targets):
                            break
                    else:
                        while t_idx < len(targets) and targets[t_idx] <= t:
                            d_prev = abs(targets[t_idx] - prev_t)
                            d_cur = abs(targets[t_idx] - t)
                            chosen = (
                                prev_img.copy()
                                if d_prev <= d_cur
                                else img.copy()
                            )
                            images.append(chosen)
                            t_idx += 1
                            done += 1
                            if progress_callback is not None:
                                progress_callback(done, total)

                        prev_t, prev_img = t, img
                        if t_idx >= len(targets):
                            break
            except Exception:
                return images

            while t_idx < len(targets) and prev_img is not None:
                images.append(prev_img.copy())
                t_idx += 1
                done += 1
                if progress_callback is not None:
                    progress_callback(done, total)

        if images and len(images) < len(targets):
            last = images[-1]
            images.extend(last.copy() for _ in range(len(targets) - len(images)))

        return images

    def _frames_to_gif_palette(self, frames: list[Image.Image]) -> list[Image.Image]:
        rgb = [f.convert("RGB") for f in frames]
        base = rgb[0].quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        out: list[Image.Image] = [base]
        for f in rgb[1:]:
            out.append(
                f.quantize(palette=base, dither=Image.Dither.FLOYDSTEINBERG)
            )
        return out

    def _build_scale_filter_graph(
        self,
        stream: av.video.stream.VideoStream,
    ) -> tuple[av.filter.Graph, Any, Any]:
        graph = av.filter.Graph()
        graph_src = cast(Any, graph.add_buffer(template=stream))
        graph_scale = graph.add("scale", args=f"{self.params.tile_width}:-1")
        graph_sink = cast(Any, graph.add("buffersink"))
        graph_src.link_to(graph_scale)
        graph_scale.link_to(graph_sink)
        graph.configure()
        return graph, graph_src, graph_sink

    def _capture_frame(
        self,
        container: av.container.input.InputContainer,
        stream: av.video.stream.VideoStream,
        filter_graph: av.filter.Graph,
        graph_src: Any,
        graph_sink: Any,
        target_second: float,
    ) -> Image.Image | None:
        seek_second = max(0.0, target_second)
        time_base = float(stream.time_base) if stream.time_base is not None else 0.0
        if time_base <= 0.0:
            return None

        seek_position = int(seek_second / time_base)
        if stream.start_time is not None:
            seek_position += int(stream.start_time)

        try:
            container.seek(seek_position, stream=stream, any_frame=False, backward=True)
            codec_context = getattr(stream, "codec_context", None)
            if codec_context is not None:
                codec_context.flush_buffers()
        except Exception:
            return None

        try:
            fallback: Image.Image | None = None
            for frame in container.decode(video=stream.index):
                if frame.pts is None:
                    continue

                if self.params.fast_keyframes:
                    return self._filter_frame(
                        frame, filter_graph, graph_src, graph_sink
                    )

                frame_second = float(frame.pts * stream.time_base)
                filtered = self._filter_frame(
                    frame, filter_graph, graph_src, graph_sink
                )
                if fallback is None:
                    fallback = filtered
                if frame_second >= target_second:
                    return filtered
                if frame_second > target_second + 5.0:
                    break

            return fallback
        except Exception:
            return None

    def _filter_frame(
        self,
        frame: av.VideoFrame,
        filter_graph: av.filter.Graph,
        graph_src: Any,
        graph_sink: Any,
    ) -> Image.Image:
        graph_src.push(frame)
        filtered_frame = graph_sink.pull()
        return filtered_frame.to_image()

    def _build_header_lines(
        self, video_path: Path, metadata: dict[str, object]
    ) -> list[str]:
        duration_seconds = float(cast(float, metadata["duration_seconds"]))
        file_size = int(cast(int, metadata["file_size"]))
        width = int(cast(int, metadata["width"]))
        height = int(cast(int, metadata["height"]))
        video_format = str(metadata.get("video_format", "unknown"))
        frame_rate = self._first_numeric(metadata.get("frame_rate"), default=None)
        video_bit_rate = self._first_numeric(
            metadata.get("video_bit_rate"), default=None
        )
        audio_format = metadata.get("audio_format")
        audio_bit_rate = self._first_numeric(
            metadata.get("audio_bit_rate"), default=None
        )
        audio_sampling_rate = self._first_numeric(
            metadata.get("audio_sampling_rate"), default=None
        )
        audio_channels = self._first_numeric(
            metadata.get("audio_channels"), default=None
        )

        lines = [f"File: {video_path.name}"]
        lines.append(
            f"Size: {file_size} B ({self._format_size(file_size)}), Duration: {self._format_time(duration_seconds)}"
        )

        video_parts = [video_format, f"{width}x{height}"]
        if width > 0 and height > 0:
            video_parts.append(f"({width / height:.2f}:1)")
        if frame_rate:
            video_parts.append(f"{float(frame_rate):.2f} fps")
        if video_bit_rate:
            video_parts.append(self._format_bit_rate(int(video_bit_rate)))
        lines.append(f"Video: {', '.join(video_parts)}")

        if not audio_format:
            lines.append("Audio: None")
        else:
            audio_parts = [str(audio_format)]
            if audio_sampling_rate:
                audio_parts.append(f"{int(audio_sampling_rate)} Hz")
            if audio_channels:
                channel_count = int(audio_channels)
                if channel_count == 1:
                    audio_parts.append("mono")
                elif channel_count == 2:
                    audio_parts.append("stereo")
                else:
                    audio_parts.append(f"{channel_count} channels")
            if audio_bit_rate:
                audio_parts.append(self._format_bit_rate(int(audio_bit_rate)))
            lines.append(f"Audio: {', '.join(audio_parts)}")

        return lines

    def _read_metadata(self, video_path: Path) -> dict[str, object]:
        general_track = None
        video_track = None
        audio_track = None

        for track in MediaInfo.parse(str(video_path)).tracks:
            if track.track_type == "General" and general_track is None:
                general_track = track.to_data()
            elif track.track_type == "Video" and video_track is None:
                video_track = track.to_data()
            elif track.track_type == "Audio" and audio_track is None:
                audio_track = track.to_data()

        if video_track is None:
            raise ValueError(f"Unable to read video metadata: {video_path}")

        duration_ms = self._first_numeric(
            video_track.get("duration") if video_track else None,
            general_track.get("duration") if general_track else None,
            default=0.0,
        )
        duration_seconds = (duration_ms or 0.0) / 1000.0

        width = int(self._first_numeric(video_track.get("width"), default=0.0) or 0)
        height = int(self._first_numeric(video_track.get("height"), default=0.0) or 0)
        if width <= 0 or height <= 0:
            with av.open(str(video_path)) as container:
                stream = container.streams.video[0]
                width = int(stream.width or 0)
                height = int(stream.height or 0)

        file_size = int(
            self._first_numeric(
                general_track.get("file_size") if general_track else None,
                default=float(video_path.stat().st_size),
            )
            or 0
        )

        return {
            "duration_seconds": duration_seconds,
            "file_size": file_size,
            "width": width,
            "height": height,
            "video_format": video_track.get("format", "unknown"),
            "frame_rate": self._first_numeric(
                video_track.get("frame_rate"), default=None
            ),
            "video_bit_rate": self._first_numeric(
                video_track.get("bit_rate"), default=None
            ),
            "audio_format": audio_track.get("format") if audio_track else None,
            "audio_sampling_rate": self._first_numeric(
                audio_track.get("sampling_rate") if audio_track else None,
                default=None,
            ),
            "audio_channels": self._first_numeric(
                audio_track.get("channel_s") if audio_track else None,
                default=None,
            ),
            "audio_bit_rate": self._first_numeric(
                audio_track.get("bit_rate") if audio_track else None,
                default=None,
            ),
        }

    @staticmethod
    def _first_numeric(*values: object, default: float | None = None) -> float | None:
        for value in values:
            if value is None:
                continue
            if isinstance(value, (int, float)):
                return float(value)
            if not isinstance(value, str):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return default

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if value < 1024.0 or unit == "TiB":
                return f"{value:.2f} {unit}"
            value /= 1024.0
        return f"{value:.2f} TiB"

    @staticmethod
    def _format_time(duration_in_seconds: float) -> str:
        duration = max(0, int(duration_in_seconds))
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _format_bit_rate(bits_per_second: int) -> str:
        return f"{int(round(bits_per_second / 1000.0, 0))} kb/s"

    @staticmethod
    def _font_height(text: str, font: ImageFont.ImageFont) -> int:
        bbox = font.getbbox(text)
        return int(bbox[3] - bbox[1]) + 1

    def _draw_timestamp(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        thumb_height: int,
        text: str,
    ) -> None:
        text_x = x + 6
        text_y = y + thumb_height - self._font_height(text, self.timestamp_font) - 6
        draw.text(
            (text_x + 1, text_y + 1),
            text,
            fill=self.timestamp_shadow_rgb,
            font=self.timestamp_font,
        )
        draw.text(
            (text_x, text_y),
            text,
            fill=self.timestamp_font_rgb,
            font=self.timestamp_font,
        )
