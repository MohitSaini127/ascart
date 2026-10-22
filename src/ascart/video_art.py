import math
import sys
import time
from pathlib import Path

import cv2
from PIL import Image

from ascart.converter import DEFAULT_PALETTE
from ascart.image_art import image_to_ascii


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


def play_video(
    path, width=60, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False,
    loops=1,
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
