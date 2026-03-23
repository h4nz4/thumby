import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.text import Text

from . import __version__
from .thumbnailer import MAX_ANIM_FRAMES, Thumbnailer, ThumbnailerParams

ASCII_LOGO = r"""

 ████████╗ ██╗  ██╗ ██╗   ██╗ ███╗   ███╗ ██████╗  ██╗   ██╗
 ╚══██╔══╝ ██║  ██║ ██║   ██║ ████╗ ████║ ██╔══██╗ ╚██╗ ██╔╝
    ██║    ███████║ ██║   ██║ ██╔████╔██║ ██████╔╝  ╚████╔╝
    ██║    ██╔══██║ ██║   ██║ ██║╚██╔╝██║ ██╔══██╗   ╚██╔╝
    ██║    ██║  ██║ ╚██████╔╝ ██║ ╚═╝ ██║ ██████╔╝    ██║
    ╚═╝    ╚═╝  ╚═╝  ╚═════╝  ╚═╝     ╚═╝ ╚═════╝     ╚═╝


"""


def print_logo():
    console = Console()
    lines = ASCII_LOGO.strip("\n").split("\n")
    # Mint palette colors from oh-my-logo: #00d2ff -> #3a7bd5
    start_color = (0, 210, 255)
    end_color = (58, 123, 213)

    # empty line padding on top
    console.print(Text("\n"))

    for i, line in enumerate(lines):
        t = i / (len(lines) - 1) if len(lines) > 1 else 0
        r = int(start_color[0] + (end_color[0] - start_color[0]) * t)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * t)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * t)

        color = f"rgb({r},{g},{b})"
        console.print(Text(line, style=color))


app = typer.Typer(
    help="Create video thumbnail sheets or animated GIF/WebP previews from a video file.",
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)


def version_callback(value: bool) -> None:
    if not value:
        return
    print_logo()
    typer.echo(f"thumby {__version__}")
    raise typer.Exit()


@app.command()
def main(
    video_path: Path = typer.Argument(
        ..., help="Path to the video file.", exists=True, file_okay=True, dir_okay=False
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (.jpg sheet, or .gif / .webp when --gif / --webp).",
    ),
    rows: int = typer.Option(9, "--rows", "-r", help="Number of rows in the grid."),
    cols: int = typer.Option(3, "--cols", "-c", help="Number of columns in the grid."),
    width: int = typer.Option(
        400, "--width", "-w", help="Width of each tile in pixels."
    ),
    skip: float = typer.Option(
        10.0, "--skip", "-s", help="Seconds to skip from the start."
    ),
    quality: int = typer.Option(95, "--quality", "-q", help="JPEG quality (1-100)."),
    as_gif: bool = typer.Option(
        False,
        "--gif",
        help="Write an animated GIF instead of a JPEG thumbnail sheet.",
    ),
    as_webp: bool = typer.Option(
        False,
        "--webp",
        help="Write an animated WebP instead of a JPEG thumbnail sheet.",
    ),
    gif_duration: float = typer.Option(
        2.0,
        "--gif-duration",
        help="Animated clip length in seconds for --gif / --webp (clamped after --skip).",
    ),
    gif_fps: float = typer.Option(
        10.0,
        "--gif-fps",
        help=f"Frames per second for --gif / --webp (max {MAX_ANIM_FRAMES} frames).",
    ),
    webp_quality: int = typer.Option(
        80,
        "--webp-quality",
        help="WebP quality 0-100 (--webp only; ignored when --webp-lossless).",
    ),
    webp_lossless: bool = typer.Option(
        False,
        "--webp-lossless",
        help="Lossless WebP (--webp only).",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    Generate a thumbnail sheet (preview) or an animated GIF/WebP for a video file.
    """
    print_logo()
    if as_gif and as_webp:
        typer.secho("Error: use only one of --gif or --webp.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if output is None:
        if as_gif:
            output = video_path.with_name(f"{video_path.stem}_preview.gif")
        elif as_webp:
            output = video_path.with_name(f"{video_path.stem}_preview.webp")
        else:
            output = video_path.with_name(f"{video_path.stem}_preview.jpg")

    params = ThumbnailerParams(
        columns=cols,
        rows=rows,
        tile_width=width,
        skip_seconds=skip,
        jpeg_quality=quality,
    )

    thumbnailer = Thumbnailer(params)

    try:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total} frames)"),
        ) as progress:
            if as_gif or as_webp:
                est_frames = min(
                    MAX_ANIM_FRAMES,
                    max(1, int(gif_duration * gif_fps + 1)),
                )
                if as_gif:
                    label = "Extracting GIF frames"
                else:
                    label = "Extracting WebP frames"
                task_id = progress.add_task(label, total=est_frames)

                def progress_callback(done: int, total: int) -> None:
                    progress.update(task_id, completed=done, total=total)

                if as_gif:
                    thumbnailer.create_and_save_animated_gif(
                        video_path,
                        output,
                        gif_duration_seconds=gif_duration,
                        gif_fps=gif_fps,
                        progress_callback=progress_callback,
                    )
                else:
                    wq = max(0, min(100, webp_quality))
                    thumbnailer.create_and_save_animated_webp(
                        video_path,
                        output,
                        anim_duration_seconds=gif_duration,
                        anim_fps=gif_fps,
                        quality=wq,
                        lossless=webp_lossless,
                        progress_callback=progress_callback,
                    )
            else:
                task_id = progress.add_task("Extracting frames", total=rows * cols)

                def progress_callback(done: int, total: int) -> None:
                    progress.update(task_id, completed=done, total=total)

                thumbnailer.create_and_save_preview_thumbnails_for(
                    video_path,
                    output,
                    progress_callback=progress_callback,
                )

        if as_gif:
            typer.secho(
                f"\nSuccess! Animated GIF saved to: {output}",
                fg=typer.colors.GREEN,
            )
        elif as_webp:
            typer.secho(
                f"\nSuccess! Animated WebP saved to: {output}",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                f"\nSuccess! Thumbnail sheet saved to: {output}",
                fg=typer.colors.GREEN,
            )
    except Exception as exc:
        typer.secho(f"\nError: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def run() -> None:
    # Show logo if it's the help command
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print_logo()
    app()


if __name__ == "__main__":
    run()
