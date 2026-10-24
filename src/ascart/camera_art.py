"""Read local cameras and display live ASCII in the terminal."""

import math
import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import cv2

from ascart.border import add_border
from ascart.converter import DEFAULT_PALETTE
from ascart.video_art import video_frame_to_ascii


SNAPSHOT_COUNTDOWN_SECONDS = 3


@contextmanager
def camera_capture(index):
    """Open a camera only when requested, and always release its handle."""
    if index < 0:
        raise ValueError("Camera ID must be 0 or greater")
    if index > 2147483647:
        raise ValueError("Camera ID is too large; maximum is 2147483647")
    capture = cv2.VideoCapture(index)
    try:
        if not capture.isOpened():
            raise ValueError(
                f"Cannot open camera {index}; it may be unavailable, busy, or blocked by permissions. "
                "Try --list-cameras or check your operating system's camera settings"
            )
        yield capture
    finally:
        capture.release()


def camera_candidates():
    """Find Linux video-device IDs, or use a bounded probe on other systems."""
    if sys.platform.startswith("linux"):
        return sorted({int(path.name[5:]) for path in Path("/dev").glob("video*")
                       if re.fullmatch(r"video\d+", path.name)})
    return list(range(10))


def list_cameras():
    """Return IDs that open and supply a frame; probes can activate cameras."""
    available = []
    for index in camera_candidates():
        try:
            with camera_capture(index) as capture:
                success, frame = capture.read()
                if success and frame is not None and frame.size > 0:
                    available.append(index)
        except (OSError, ValueError, cv2.error):
            # A failed probe is not proof that hardware is absent.
            continue
    return available


def read_camera_frame(capture, index):
    success, frame = capture.read()
    if not success or frame is None or frame.size == 0:
        raise ValueError(
            f"Cannot read a frame from camera {index}; it may have disconnected or stopped sending frames"
        )
    return frame


def camera_frame_to_ascii(frame, width, palette, background, max_height, color, border, mirrored):
    """Apply the same orientation and visual settings to live and saved frames."""
    if not mirrored:
        frame = cv2.flip(frame, 1)
    art = video_frame_to_ascii(frame, width, palette, background, max_height, color)
    return add_border(art) if border else art


def snapshot_camera(
    index=0, width=60, palette=DEFAULT_PALETTE, background="dark",
    max_height=None, color=False, border=False, mirrored=False,
):
    """Warm up during a countdown, then convert one frame and release the camera."""
    with camera_capture(index) as capture:
        deadline = time.monotonic() + SNAPSHOT_COUNTDOWN_SECONDS
        previous = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            seconds = math.ceil(remaining)
            if seconds != previous:
                print(f"Snapshot in {seconds}... (Ctrl+C cancels)", file=sys.stderr, flush=True)
                previous = seconds
            # Read and discard warm-up frames to avoid saving the first buffered
            # picture after waiting. This also allows auto-exposure to settle.
            read_camera_frame(capture, index)
            delay = min(1 / 30, max(0, deadline - time.monotonic()))
            if delay > 0:
                time.sleep(delay)
        frame = read_camera_frame(capture, index)
        return camera_frame_to_ascii(frame, width, palette, background, max_height, color, border, mirrored)


def play_camera(
    index=0, width=60, palette=DEFAULT_PALETTE, background="dark",
    max_height=None, color=False, border=False, mirrored=False,
):
    """Display one frame at a time until interrupted; never record or upload."""
    screen_started = False
    try:
        with camera_capture(index) as capture:
            while True:
                started = time.monotonic()
                frame = read_camera_frame(capture, index)
                art = camera_frame_to_ascii(frame, width, palette, background, max_height, color, border, mirrored)
                if not screen_started:
                    screen_started = True
                    print("\033[2J\033[H\033[?25l", end="", flush=True)
                print("\033[H\033[J" + art, end="", flush=True)
                # Cap terminal redraws at 30 FPS; slower devices/processors
                # naturally run slower, without accumulating recorded frames.
                delay = 1 / 30 - (time.monotonic() - started)
                if delay > 0:
                    time.sleep(delay)
    finally:
        if screen_started:
            print("\033[0m\033[?25h", flush=True)
