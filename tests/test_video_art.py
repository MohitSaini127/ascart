import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from ascart.video_art import inspect_video, play_video, positive_property, video_frame_to_ascii


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
            with contextlib.redirect_stdout(io.StringIO()), patch("ascart.video_art.time.sleep"):
                self.assertEqual(play_video(path, width=8), 3)
                self.assertEqual(play_video(path, width=8, loops=4), 12)

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


class VideoPlaybackTests(unittest.TestCase):
    def capture(self, fps=10):
        capture = Mock()
        capture.get.return_value = fps
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        capture.read.side_effect = [(True, frame), (True, frame), (False, None)]
        return capture

    def test_bgr_colors_and_dimensions(self):
        frame = np.full((8, 8, 3), (0, 0, 255), dtype=np.uint8)
        art = video_frame_to_ascii(frame, width=4, palette="#", color=True)
        self.assertEqual(len(art.splitlines()), 2)
        self.assertEqual(art.count("\033[38;2;255;0;0m#"), 8)

    def test_processing_time_subtracted_and_capture_released(self):
        capture = self.capture()
        output = io.StringIO()
        with patch("ascart.video_art.open_video", return_value=capture), \
             patch("ascart.video_art.time.monotonic", side_effect=[0, 0.04, 0.1, 0.25, 0.25]), \
             patch("ascart.video_art.time.sleep") as sleep, contextlib.redirect_stdout(output):
            self.assertEqual(play_video("unused", width=4), 2)
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 0.06)
        capture.release.assert_called_once()
        self.assertTrue(output.getvalue().endswith("\033[0m\033[?25h\n"))

    def test_unknown_fps_fallback(self):
        captures = [self.capture(fps=float("nan")) for _ in range(2)]
        with patch("ascart.video_art.open_video", side_effect=captures), \
             patch("ascart.video_art.time.monotonic", return_value=0), \
             patch("ascart.video_art.time.sleep") as sleep, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
            play_video("unused", width=4, loops=2)
        self.assertEqual(sleep.call_count, 4)
        self.assertAlmostEqual(sleep.call_args.args[0], 1 / 30)
        self.assertEqual(errors.getvalue().count("using 30 FPS"), 1)

    def test_counted_playback_reopens_after_releasing_previous_reader(self):
        captures = [self.capture() for _ in range(4)]
        opened = []

        def open_next(path):
            if opened:
                opened[-1].release.assert_called_once()
            capture = captures[len(opened)]
            opened.append(capture)
            return capture

        output = io.StringIO()
        with patch("ascart.video_art.open_video", side_effect=open_next), \
             patch("ascart.video_art.time.sleep"), contextlib.redirect_stdout(output):
            self.assertEqual(play_video("unused", width=4, loops=4), 8)
        self.assertEqual(len(opened), 4)
        for capture in captures:
            capture.release.assert_called_once()
        self.assertEqual(output.getvalue().count("\033[H\033[J"), 8)
        self.assertEqual(output.getvalue().count("\033[?25l"), 1)
        self.assertEqual(output.getvalue().count("\033[?25h"), 1)

    def test_continuous_playback_stops_on_interrupt(self):
        captures = [self.capture() for _ in range(3)]
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        captures[-1].read.side_effect = [(True, frame), KeyboardInterrupt]
        output = io.StringIO()
        with patch("ascart.video_art.open_video", side_effect=captures) as open_mock, \
             patch("ascart.video_art.time.sleep"), contextlib.redirect_stdout(output):
            with self.assertRaises(KeyboardInterrupt):
                play_video("unused", width=4, loops=0)
        self.assertEqual(open_mock.call_count, 3)
        self.assertEqual(output.getvalue().count("\033[H\033[J"), 5)
        for capture in captures:
            capture.release.assert_called_once()
        self.assertTrue(output.getvalue().endswith("\033[0m\033[?25h\n"))

    def test_cleanup_if_reopening_fails_or_is_interrupted(self):
        for error in (ValueError("Cannot reopen video"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                capture = self.capture()
                output = io.StringIO()
                with patch("ascart.video_art.open_video", side_effect=[capture, error]) as open_mock, \
                     patch("ascart.video_art.time.sleep"), contextlib.redirect_stdout(output):
                    with self.assertRaises(type(error)):
                        play_video("unused", width=4, loops=4)
                self.assertEqual(open_mock.call_count, 2)
                capture.release.assert_called_once()
                self.assertTrue(output.getvalue().endswith("\033[0m\033[?25h\n"))

    def test_empty_second_pass_stops_continuous_playback(self):
        captures = [self.capture(), self.capture()]
        captures[-1].read.side_effect = [(False, None)]
        output = io.StringIO()
        with patch("ascart.video_art.open_video", side_effect=captures) as open_mock, \
             patch("ascart.video_art.time.sleep"), contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, "no frame"):
                play_video("unused", width=4, loops=0)
        self.assertEqual(open_mock.call_count, 2)
        for capture in captures:
            capture.release.assert_called_once()
        self.assertTrue(output.getvalue().endswith("\033[0m\033[?25h\n"))

    def test_negative_loop_count_rejected_before_opening(self):
        with patch("ascart.video_art.open_video") as open_mock:
            with self.assertRaisesRegex(ValueError, "Loop count"):
                play_video("unused", loops=-1)
        open_mock.assert_not_called()

    def test_cleanup_after_interrupt_or_decode_error(self):
        for error in (KeyboardInterrupt, RuntimeError):
            capture = self.capture()
            frame = np.zeros((8, 8, 3), dtype=np.uint8)
            capture.read.side_effect = [(True, frame), error("stop")]
            output = io.StringIO()
            with patch("ascart.video_art.open_video", return_value=capture), \
                 patch("ascart.video_art.time.sleep"), contextlib.redirect_stdout(output):
                with self.assertRaises(error):
                    play_video("unused", width=4)
            capture.release.assert_called_once()
            self.assertTrue(output.getvalue().endswith("\033[0m\033[?25h\n"))

    def test_no_frame_does_not_clear_terminal(self):
        capture = self.capture()
        capture.read.side_effect = [(False, None)]
        output = io.StringIO()
        with patch("ascart.video_art.open_video", return_value=capture), contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, "no frame"):
                play_video("unused")
        self.assertEqual(output.getvalue(), "")
        capture.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
