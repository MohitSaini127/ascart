"""Record a bounded, silent camera ASCII MP4 without replacing user files."""

import math
import shutil
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

import cv2
import numpy as np

from ascart.camera_art import camera_capture, camera_frame_to_ascii, read_camera_frame
from ascart.converter import DEFAULT_PALETTE
from ascart.png_art import art_to_png
from ascart.video_art import verify_video


RECORDING_FPS = 15
MAX_CAMERA_DURATION = 300


def record_camera(
    index, output, duration, width=60, palette=DEFAULT_PALETTE, background="dark",
    max_height=None, color=False, border=False, mirrored=False, preview=False,
):
    """Record wall-clock seconds at fixed FPS, repeating late frames as needed."""
    if not math.isfinite(duration) or not 0 < duration <= MAX_CAMERA_DURATION:
        raise ValueError("Camera duration must be greater than 0 and at most 300 seconds")
    screen_started = False
    status_width = max(1, shutil.get_terminal_size(fallback=(80, 24)).columns - 1) if preview else 0

    def render(frame):
        art = camera_frame_to_ascii(frame, width, palette, background, max_height, color, border, mirrored)
        with art_to_png(art, background) as picture:
            pixels = cv2.cvtColor(np.asarray(picture), cv2.COLOR_RGB2BGR)
        return art, pixels

    try:
        with ExitStack() as camera_scope:
            capture = camera_scope.enter_context(camera_capture(index))
            art, pixels = render(read_camera_frame(capture, index))
            size = (pixels.shape[1], pixels.shape[0])
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".ascart-", dir=output_path.parent) as folder:
                temporary = Path(folder) / "camera.mp4"
                writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), RECORDING_FPS, size)
                try:
                    if not writer.isOpened():
                        raise ValueError("MP4 encoding is unavailable; this OpenCV installation needs an mp4v encoder")
                    target_frames = math.ceil(duration * RECORDING_FPS)
                    started = time.monotonic()
                    deadline = started + duration
                    count = 0
                    while count < target_frames:
                        now = time.monotonic()
                        if count and now < deadline:
                            art, pixels = render(read_camera_frame(capture, index))
                            if (pixels.shape[1], pixels.shape[0]) != size:
                                raise ValueError("Camera frame dimensions changed during recording")
                        elapsed = max(0, time.monotonic() - started)
                        due = min(target_frames, max(count + 1, math.floor(elapsed * RECORDING_FPS) + 1))
                        if elapsed >= duration:
                            # Close the device at the cutoff before finishing
                            # any overdue frames from the last decoded picture.
                            camera_scope.close()
                            due = target_frames
                        while count < due:
                            writer.write(pixels)
                            count += 1
                        if preview:
                            if not screen_started:
                                screen_started = True
                                print("\033[2J\033[H\033[?25l", end="", flush=True)
                            status = f"{max(0, duration - elapsed):.1f}s left | Ctrl+C cancels"[:status_width]
                            print("\033[H\033[J" + art + "\n" + status, end="", flush=True)
                        wake = min(deadline, started + count / RECORDING_FPS)
                        delay = wake - time.monotonic()
                        if delay > 0:
                            time.sleep(delay)
                    if preview:
                        print("\033[H\033[J" + art, end="", flush=True)
                finally:
                    # Release the camera before readback/copying and close the
                    # encoder before its private temporary directory is removed.
                    try:
                        camera_scope.close()
                    finally:
                        writer.release()
                verify_video(temporary, count, size)
                with temporary.open("rb") as source, output_path.open("xb") as destination:
                    shutil.copyfileobj(source, destination)
                return count
    finally:
        if screen_started:
            print("\033[0m\033[?25h", flush=True)
