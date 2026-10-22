import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from ascart.video_art import inspect_video, positive_property


class VideoInspectionTests(unittest.TestCase):
    def test_real_video_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
            self.assertTrue(writer.isOpened(), "Test machine needs MJPG encoding")
            try:
                for color in ((0, 0, 255), (255, 0, 0), (0, 255, 0)):
                    writer.write(np.full((24, 32, 3), color, dtype=np.uint8))
            finally:
                writer.release()
            info = inspect_video(path)
            self.assertEqual((info["width"], info["height"]), (32, 24))
            self.assertEqual(info["frame_count"], 3)
            self.assertAlmostEqual(info["fps"], 10)
            self.assertAlmostEqual(info["duration_seconds"], 0.3)

    def test_unknown_properties(self):
        for value in (0, -1, float("nan"), float("inf")):
            capture = Mock()
            capture.get.return_value = value
            self.assertIsNone(positive_property(capture, cv2.CAP_PROP_FPS))

    def test_no_decodable_frame_releases_capture(self):
        capture = Mock()
        capture.read.return_value = (False, None)
        with patch("ascart.video_art.open_video", return_value=capture):
            with self.assertRaisesRegex(ValueError, "no frame"):
                inspect_video("unused.avi")
        capture.release.assert_called_once()

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "does not exist"):
                inspect_video(Path(folder) / "missing.mp4")


if __name__ == "__main__":
    unittest.main()
