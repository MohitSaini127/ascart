import math
import shutil
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ascart.border import add_border
from ascart.converter import DEFAULT_PALETTE
from ascart.image_art import image_to_ascii
from ascart.png_art import art_to_png


def open_video(path):
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Video file does not exist or is not a regular file: {path}")
    capture = cv2.VideoCapture(str(source.resolve()))
    if not capture.isOpened():
        capture.release()
        raise ValueError("Cannot open video; the file or its codec may be unsupported")
    return capture


def positive_property(capture, property_id):
    value = capture.get(property_id)
    return value if math.isfinite(value) and value > 0 else None


def inspect_video(path):
    capture = open_video(path)
    try:
        success, frame = capture.read()
        if not success:
            raise ValueError("Video opened, but no frame could be decoded")
        height, width = frame.shape[:2]
        fps = positive_property(capture, cv2.CAP_PROP_FPS)
        count = positive_property(capture, cv2.CAP_PROP_FRAME_COUNT)
        return {
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": int(count) if count is not None else None,
            "duration_seconds": count / fps if count is not None and fps is not None else None,
        }
    finally:
        capture.release()


def video_frame_to_ascii(
    frame, width=60, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False
):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    with Image.fromarray(rgb) as image:
        return image_to_ascii(image, width, palette, background, max_height, color)


def video_frame_to_picture(frame, width, palette, background, max_height, color, border):
    """Render one decoded video frame into the BGR pixels OpenCV writes."""
    art = video_frame_to_ascii(frame, width, palette, background, max_height, color)
    if border:
        art = add_border(art)
    with art_to_png(art, background, smooth=False) as picture:
        return cv2.cvtColor(np.asarray(picture), cv2.COLOR_RGB2BGR)


def video_ascii_frames(
    path, width=60, palette=DEFAULT_PALETTE, background="dark", max_height=None,
    color=False, border=False,
):
    """Yield one pass of ASCII frames and millisecond timings for HTML export."""
    capture = open_video(path)
    try:
        fps = positive_property(capture, cv2.CAP_PROP_FPS)
        if fps is None:
            fps = 30.0
            print("Video frame rate unavailable; using 30 FPS for saving.", file=sys.stderr)
        count = 0
        while True:
            success, frame = capture.read()
            if not success:
                if not count:
                    raise ValueError("Video opened, but no frame could be decoded")
                break
            art = video_frame_to_ascii(frame, width, palette, background, max_height, color)
            yield (add_border(art) if border else art), 1000 / fps
            count += 1
    finally:
        capture.release()


def verify_video(path, expected_frames, expected_size):
    """Read back every encoded frame because VideoWriter.write has no status."""
    capture = open_video(path)
    try:
        count = 0
        while True:
            success, frame = capture.read()
            if not success:
                break
            if (frame.shape[1], frame.shape[0]) != expected_size:
                raise ValueError("Encoded MP4 dimensions do not match the artwork")
            count += 1
        if count != expected_frames:
            raise ValueError(f"Incomplete MP4 encoding: expected {expected_frames} frames, decoded {count}")
    finally:
        capture.release()


def save_ascii_video(
    path, output, width=60, palette=DEFAULT_PALETTE, background="dark", max_height=None,
    color=False, border=False,
):
    """Stream one silent ASCII video to a new MP4 file, independently of loops."""
    capture = open_video(path)
    writer = None
    try:
        fps = positive_property(capture, cv2.CAP_PROP_FPS)
        if fps is None:
            fps = 30.0
            print("Video frame rate unavailable; using 30 FPS for saving.", file=sys.stderr)
        success, frame = capture.read()
        if not success:
            raise ValueError("Video opened, but no frame could be decoded")
        picture = video_frame_to_picture(frame, width, palette, background, max_height, color, border)
        size = (picture.shape[1], picture.shape[0])
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # OpenCV cannot write to an exclusively opened Python file. Encode in
        # our own private folder, then copy to an exclusively created output.
        with tempfile.TemporaryDirectory(prefix=".ascart-", dir=output_path.parent) as folder:
            temporary = Path(folder) / "video.mp4"
            writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
            try:
                if not writer.isOpened():
                    raise ValueError("MP4 encoding is unavailable; this OpenCV installation needs an mp4v encoder")
                count = 0
                while success:
                    if (picture.shape[1], picture.shape[0]) != size:
                        raise ValueError("Video frame dimensions changed during conversion")
                    writer.write(picture)
                    count += 1
                    success, frame = capture.read()
                    if success:
                        picture = video_frame_to_picture(frame, width, palette, background, max_height, color, border)
            finally:
                # Close the codec before TemporaryDirectory removes its file,
                # including on systems that cannot remove open files.
                writer.release()
                writer = None
            verify_video(temporary, count, size)
            with temporary.open("rb") as source, output_path.open("xb") as destination:
                shutil.copyfileobj(source, destination)
        return count
    finally:
        if writer is not None:
            writer.release()
        capture.release()


def play_video(
    path, width=60, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False,
    loops=1, border=False,
):
    """Play a total number of passes; loops=0 repeats until interrupted."""
    if loops < 0:
        raise ValueError("Loop count must be 0 or greater")
    screen_started = False
    displayed = 0
    completed = 0
    try:
        while loops == 0 or completed < loops:
            capture = open_video(path)
            try:
                fps = positive_property(capture, cv2.CAP_PROP_FPS)
                if fps is None:
                    fps = 30.0
                    if completed == 0:
                        print("Video frame rate unavailable; using 30 FPS.", file=sys.stderr)
                frame_interval = 1 / fps
                frames_in_pass = 0
                while True:
                    started = time.monotonic()
                    success, frame = capture.read()
                    if not success:
                        if frames_in_pass == 0:
                            raise ValueError("Video opened, but no frame could be decoded")
                        break
                    art = video_frame_to_ascii(frame, width, palette, background, max_height, color)
                    if border:
                        art = add_border(art)
                    if not screen_started:
                        screen_started = True
                        print("\033[2J\033[H\033[?25l", end="", flush=True)
                    print("\033[H\033[J" + art, end="", flush=True)
                    displayed += 1
                    frames_in_pass += 1
                    elapsed = time.monotonic() - started
                    delay = frame_interval - elapsed
                    if delay > 0:
                        time.sleep(delay)
            finally:
                capture.release()
            completed += 1
        return displayed
    finally:
        if screen_started:
            print("\033[0m\033[?25h", flush=True)
