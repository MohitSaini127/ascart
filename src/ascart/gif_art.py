import time

from PIL import Image

from ascart.converter import DEFAULT_PALETTE
from ascart.image_art import image_to_ascii


def play_gif(frames):
    try:
        print("\033[2J\033[H\033[?25l", end="", flush=True)
        for art, duration in frames:
            print("\033[H\033[J" + art, end="", flush=True)
            delay = duration / 1000 if duration > 0 else 0.1
            time.sleep(delay)
    finally:
        print("\033[0m\033[?25h", flush=True)


def gif_to_ascii(
    path, width=80, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False
):
    frames = []
    with Image.open(path) as gif:
        if gif.format != "GIF":
            raise ValueError("Expected a GIF file")

        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            duration = gif.info.get("duration", 0)
            frame = gif.convert("RGB")
            art = image_to_ascii(frame, width, palette, background, max_height, color)
            frames.append((art, duration))

    return frames


def inspect_gif(path):
    with Image.open(path) as gif:
        if gif.format != "GIF":
            raise ValueError("Expected a GIF file")

        print("Frame count:", gif.n_frames)

        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            duration = gif.info.get("duration", 0)
            print(f"Frame {frame_index + 1}: {duration} ms")
