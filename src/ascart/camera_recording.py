"""Record bounded camera ASCII animations without replacing user files."""

import math
import shutil
import tempfile
import time
from contextlib import ExitStack, closing
from itertools import chain
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ascart.camera_art import camera_capture, camera_frame_to_ascii, read_camera_frame
from ascart.converter import DEFAULT_PALETTE
from ascart.border import COLOR_CODE
from ascart.gif_art import save_ascii_gif
from ascart.html_art import MAX_ANIMATION_FRAMES, save_animated_html
from ascart.png_art import art_to_png
from ascart.video_art import verify_video


RECORDING_FPS = 15
MAX_CAMERA_DURATION = 300
CAMERA_GIF_PIXEL_LIMIT = 64_000_000


def _grid_size(art):
    rows = COLOR_CODE.sub("", art).split("\n")
    return max(map(len, rows)), len(rows)


def _camera_animation_frames(index, duration, gif_timing=False, preview=False, **settings):
    """Yield fixed-rate ASCII slots while keeping capture and preview bounded."""
    screen_started = False
    status_width = max(1, shutil.get_terminal_size(fallback=(80, 24)).columns - 1) if preview else 0
    try:
        with ExitStack() as camera_scope:
            capture = camera_scope.enter_context(camera_capture(index))
            art = camera_frame_to_ascii(read_camera_frame(capture, index), **settings)
            grid = _grid_size(art)
            target = math.ceil(duration * RECORDING_FPS)
            started = time.monotonic()
            deadline = started + duration
            count = 0
            while count < target:
                if count and time.monotonic() < deadline:
                    art = camera_frame_to_ascii(read_camera_frame(capture, index), **settings)
                    if _grid_size(art) != grid:
                        raise ValueError("Camera frame dimensions changed during recording")
                elapsed = max(0, time.monotonic() - started)
                due = min(target, max(count + 1, math.floor(elapsed * RECORDING_FPS) + 1))
                if elapsed >= duration:
                    camera_scope.close()
                    due = target
                if preview:
                    if not screen_started:
                        screen_started = True
                        print("\033[2J\033[H\033[?25l", end="", flush=True)
                    status = f"{max(0, duration - elapsed):.1f}s left | Ctrl+C cancels"[:status_width]
                    print("\033[H\033[J" + art + "\n" + status, end="", flush=True)
                while count < due:
                    if time.monotonic() >= deadline:
                        camera_scope.close()
                    # GIF timing uses 10-ms units. Round cumulative boundaries,
                    # alternating 60/70 ms rather than truncating every frame.
                    delay = (round((count + 1) * 100 / RECORDING_FPS) - round(count * 100 / RECORDING_FPS)) * 10 if gif_timing else 1000 / RECORDING_FPS
                    count += 1
                    yield art, delay
                delay = min(deadline, started + count / RECORDING_FPS) - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            if preview:
                print("\033[H\033[J" + art, end="", flush=True)
    finally:
        if screen_started:
            print("\033[0m\033[?25h", flush=True)


def _record_camera_animation(index, output, duration, preview=False, **settings):
    output_path = Path(output)
    suffix = output_path.suffix.lower()
    count = math.ceil(duration * RECORDING_FPS)
    if suffix == ".html" and count > MAX_ANIMATION_FRAMES:
        raise ValueError("HTML animation exceeds 3000 frames; use a duration of at most 200 seconds")
    with closing(_camera_animation_frames(index, duration, gif_timing=suffix == ".gif", preview=preview, **settings)) as frames:
        first = next(frames)
        grid = _grid_size(first[0])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".ascart-", dir=output_path.parent) as folder:
            temporary = Path(folder) / ("camera" + suffix)
            entries = chain((first,), frames)
            if suffix == ".html":
                save_animated_html(entries, temporary, settings["background"], loop_control=True)
            else:
                save_ascii_gif(entries, temporary, settings["background"], smooth=True,
                               pixel_limit=CAMERA_GIF_PIXEL_LIMIT)
                total = 0
                with Image.open(temporary) as saved:
                    for frame_index in range(saved.n_frames):
                        saved.seek(frame_index)
                        saved.load()
                        if saved.size != (max(1, grid[0]) * 12 + 24, grid[1] * 22 + 24):
                            raise ValueError("Encoded GIF dimensions do not match the artwork")
                        total += saved.info.get("duration", 0)
                if total != round(count * 100 / RECORDING_FPS) * 10:
                    raise ValueError("Encoded GIF timing does not match the recording")
            with temporary.open("rb") as source, output_path.open("xb") as destination:
                shutil.copyfileobj(source, destination)
    return count


def record_camera(
    index, output, duration, width=60, palette=DEFAULT_PALETTE, background="dark",
    max_height=None, color=False, border=False, mirrored=False, preview=False,
):
    """Record wall-clock seconds at fixed FPS, repeating late frames as needed."""
    if not math.isfinite(duration) or not 0 < duration <= MAX_CAMERA_DURATION:
        raise ValueError("Camera duration must be greater than 0 and at most 300 seconds")
    suffix = Path(output).suffix.lower()
    if suffix not in (".mp4", ".gif", ".html"):
        raise ValueError("Camera recording supports only .mp4, .gif, and .html output")
    if suffix != ".mp4":
        return _record_camera_animation(
            index, output, duration, width=width, palette=palette, background=background,
            max_height=max_height, color=color, border=border, mirrored=mirrored, preview=preview,
        )
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
