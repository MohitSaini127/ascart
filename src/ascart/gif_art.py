import math
import time
from contextlib import ExitStack, closing
from pathlib import Path

from PIL import GifImagePlugin, Image

from ascart.converter import DEFAULT_PALETTE
from ascart.image_art import image_to_ascii
from ascart.png_art import art_to_png


def save_streaming_ascii_gif(frames, path, background="dark", *, smooth=True):
    """Encode full frames incrementally into a new GIF, without repeat metadata.

    Camera callers supply a private temporary path and verify the completed
    file before publishing it. Only the current picture is retained here.
    """
    size = None
    output = None
    with ExitStack() as resources:
        for art, duration in frames:
            if not math.isfinite(duration) or not 10 <= duration <= 655350:
                raise ValueError("GIF frame duration must be between 10 and 655350 milliseconds")
            with closing(art_to_png(art, background, smooth=smooth)) as picture:
                if any(side > 65535 for side in picture.size):
                    raise ValueError("GIF dimensions must not exceed 65535 pixels per side; use a smaller --width")
                if size is not None and picture.size != size:
                    raise ValueError("GIF frames must have matching dimensions")
                with closing(picture.convert(
                    "P", palette=Image.Palette.ADAPTIVE, colors=256,
                    dither=Image.Dither.NONE,
                )) as paletted:
                    if output is None:
                        size = picture.size
                        output_path = Path(path)
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output = resources.enter_context(output_path.open("xb"))
                        # A duration selects the GIF89a header. No loop field
                        # means the exported animation requests one playback.
                        header, _ = GifImagePlugin.getheader(
                            paletted, info={"duration": duration, "optimize": False},
                        )
                        output.writelines(header)
                    # Each frame has its own palette and fills the whole
                    # canvas, including repeated frames and their delays.
                    output.writelines(GifImagePlugin.getdata(
                        paletted, duration=duration, disposal=2,
                        include_color_table=True,
                    ))
        if output is None:
            raise ValueError("No frames to save")
        output.write(b";")  # GIF trailer, written only after every frame succeeds.


def save_ascii_gif(frames, path, background="dark", *, smooth=False):
    """Save one pass of ASCII frames, without adding GIF repeat metadata."""
    if not frames:
        raise ValueError("No frames to save")
    pictures = []
    durations = []
    try:
        for art, duration in frames:
            with art_to_png(art, background, smooth=smooth) as picture:
                # GIF allows up to 256 colors per frame. Avoid dithering so
                # plain character strokes do not acquire speckled patterns.
                pictures.append(picture.convert(
                    "P", palette=Image.Palette.ADAPTIVE, colors=256,
                    dither=Image.Dither.NONE,
                ))
            durations.append(duration if duration > 0 else 100)
        if any(picture.size != pictures[0].size for picture in pictures):
            raise ValueError("GIF frames must have matching dimensions")
        if any(side > 65535 for side in pictures[0].size):
            raise ValueError("GIF dimensions must not exceed 65535 pixels per side; use a smaller --width")
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("xb") as file:
            try:
                pictures[0].save(
                    file, format="GIF", save_all=True, append_images=pictures[1:],
                    duration=durations, disposal=2, optimize=False,
                )
            except OverflowError:
                # Pillow merges identical consecutive pictures and adds their
                # delays. That sum can exceed GIF's 16-bit delay field.
                raise ValueError(
                    "GIF frame timing exceeds 655.35 seconds, possibly after merging "
                    "identical ASCII frames; use a shorter animation"
                ) from None
        # No loop option is passed above: omitting GIF loop metadata requests
        # one playback, even when the input GIF repeats continuously.
    finally:
        for picture in pictures:
            picture.close()


def play_gif(frames, loops=1):
    if not frames:
        return
    try:
        print("\033[2J\033[H\033[?25l", end="", flush=True)
        completed = 0
        while loops == 0 or completed < loops:
            for art, duration in frames:
                print("\033[H\033[J" + art, end="", flush=True)
                delay = duration / 1000 if duration > 0 else 0.1
                time.sleep(delay)
            completed += 1
    finally:
        print("\033[0m\033[?25h", flush=True)


def gif_to_ascii(
    path, width=80, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False
):
    return list(gif_ascii_frames(path, width, palette, background, max_height, color))


def gif_ascii_frames(
    path, width=80, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False
):
    """Yield decoded ASCII frames without collecting an unbounded animation."""
    with Image.open(path) as gif:
        if gif.format != "GIF":
            raise ValueError("Expected a GIF file")

        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            duration = gif.info.get("duration", 0)
            with gif.convert("RGB") as frame:
                art = image_to_ascii(frame, width, palette, background, max_height, color)
            yield art, duration


def inspect_gif(path):
    with Image.open(path) as gif:
        if gif.format != "GIF":
            raise ValueError("Expected a GIF file")

        print("Frame count:", gif.n_frames)

        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            duration = gif.info.get("duration", 0)
            print(f"Frame {frame_index + 1}: {duration} ms")
