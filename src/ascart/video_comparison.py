"""Stream synchronized original/ASCII video comparisons to silent MP4."""

import shutil
import sys
import tempfile
from contextlib import closing
from itertools import chain
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ascart.border import add_border
from ascart.comparison import comparison_to_png
from ascart.image_art import image_to_ascii
from ascart.video_art import open_video, positive_property, verify_video


def video_comparison_frames(path, *, width, palette, background, max_height, color, border):
    """Yield the original and artwork from the same decoded frame, plus delay."""
    capture = open_video(path)
    try:
        fps = positive_property(capture, cv2.CAP_PROP_FPS)
        if fps is None:
            fps = 30.0
            print("Video frame rate unavailable; using 30 FPS for saving.", file=sys.stderr)
        count = 0
        while True:
            success, pixels = capture.read()
            if not success:
                if not count:
                    raise ValueError("Video opened, but no frame could be decoded")
                return
            with Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)) as source:
                art = image_to_ascii(source, width, palette, background, max_height, color)
                yield source, add_border(art) if border else art, 1000 / fps
            count += 1
    finally:
        capture.release()


def save_comparison_video(frames, output, background="dark"):
    """Encode privately, verify every frame, then publish without replacement."""
    writer = None
    with closing(frames):
        try:
            first = next(frames, None)
            if first is None:
                raise ValueError("No frames to save")
            fps = 1000 / first[2]
            count = 0
            destination = Path(output)
            # Render before creating directories or temporary files, so layout
            # errors cannot create output artifacts.
            with closing(comparison_to_png(first[0], first[1], background)) as picture:
                size = picture.size
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".ascart-", dir=destination.parent) as folder:
                temporary = Path(folder) / "comparison.mp4"
                try:
                    writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
                    if not writer.isOpened():
                        raise ValueError("MP4 encoding is unavailable; this OpenCV installation needs an mp4v encoder")
                    for source, art, _ in chain((first,), frames):
                        with closing(comparison_to_png(source, art, background)) as picture:
                            if picture.size != size:
                                raise ValueError("Video comparison frame dimensions changed during conversion")
                            writer.write(cv2.cvtColor(np.asarray(picture), cv2.COLOR_RGB2BGR))
                        count += 1
                finally:
                    if writer is not None:
                        writer.release()
                        writer = None
                verify_video(temporary, count, size)
                with temporary.open("rb") as source, destination.open("xb") as output_file:
                    shutil.copyfileobj(source, output_file)
            return count
        finally:
            if writer is not None:
                writer.release()
