from PIL import Image

from ascart.converter import DEFAULT_PALETTE
from ascart.image_art import image_to_ascii


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
