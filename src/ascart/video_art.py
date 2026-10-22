import math
from pathlib import Path

import cv2


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
