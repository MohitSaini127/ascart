import contextlib
import io
import itertools
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from ascart.border import add_border
from ascart.camera_art import camera_candidates, list_cameras, play_camera
from ascart.cli import main
from ascart.video_art import video_frame_to_ascii


def fake_capture(reads, opened=True):
    capture = Mock()
    capture.isOpened.return_value = opened
    capture.read.side_effect = reads
    return capture


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.full((24, 32, 3), (10, 30, 200), dtype=np.uint8)

    def test_candidate_discovery_does_not_open_cameras(self):
        paths = [Path("/dev/video10"), Path("/dev/video2"), Path("/dev/video2"), Path("/dev/video-name")]
        with patch("ascart.camera_art.sys.platform", "linux"), patch("ascart.camera_art.Path.glob", return_value=paths), patch("ascart.camera_art.cv2.VideoCapture") as open_camera:
            self.assertEqual(camera_candidates(), [2, 10])
        open_camera.assert_not_called()
        with patch("ascart.camera_art.sys.platform", "win32"):
            self.assertEqual(camera_candidates(), list(range(10)))

    def test_default_flips_pixels_before_conversion_and_mirrored_preserves_source(self):
        frame = np.zeros((24, 32, 3), dtype=np.uint8)
        frame[:, :8] = (10, 30, 200)
        original = frame.copy()
        for mirrored in (False, True):
            with self.subTest(mirrored=mirrored):
                capture = fake_capture([(True, frame), KeyboardInterrupt()])
                output = io.StringIO()
                with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), patch("ascart.camera_art.time.sleep"), contextlib.redirect_stdout(output):
                    with self.assertRaises(KeyboardInterrupt):
                        play_camera(width=16, color=True, border=True, mirrored=mirrored)
                expected_frame = original if mirrored else cv2.flip(original, 1)
                expected = add_border(video_frame_to_ascii(expected_frame, width=16, color=True))
                self.assertIn("\033[H\033[J" + expected, output.getvalue())
                np.testing.assert_array_equal(frame, original)
                capture.release.assert_called_once()

    def test_list_requires_a_real_frame_and_releases_every_probe(self):
        captures = [fake_capture([], False), fake_capture([(False, None)]),
                    fake_capture([(True, self.frame)]), fake_capture([cv2.error("driver failed")]),
                    fake_capture([(True, None)]), fake_capture([(True, np.zeros((0, 0, 3)))])]
        with patch("ascart.camera_art.camera_candidates", return_value=range(6)), patch("ascart.camera_art.cv2.VideoCapture", side_effect=captures):
            self.assertEqual(list_cameras(), [2])
        for capture in captures:
            capture.release.assert_called_once()

    def test_list_interrupt_releases_current_camera(self):
        capture = fake_capture([KeyboardInterrupt()])
        with patch("ascart.camera_art.camera_candidates", return_value=[0, 1]), patch("ascart.camera_art.cv2.VideoCapture", return_value=capture) as open_camera:
            with self.assertRaises(KeyboardInterrupt):
                list_cameras()
        capture.release.assert_called_once()
        open_camera.assert_called_once_with(0)

    def test_unavailable_camera_does_not_touch_terminal_screen(self):
        capture = fake_capture([], False)
        output = io.StringIO()
        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, "unavailable, busy, or blocked"):
                play_camera()
        self.assertEqual(output.getvalue(), "")
        capture.release.assert_called_once()

    def test_read_failure_before_and_after_display_cleans_up(self):
        bad_frames = ((False, None), (True, None), (True, np.zeros((0, 0, 3))))
        for displayed, bad_frame in itertools.product((False, True), bad_frames):
            with self.subTest(displayed=displayed, bad_frame=bad_frame[0]):
                reads = ([(True, self.frame)] if displayed else []) + [bad_frame]
                capture = fake_capture(reads)
                output = io.StringIO()
                with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), patch("ascart.camera_art.time.sleep"), contextlib.redirect_stdout(output):
                    with self.assertRaisesRegex(ValueError, "disconnected"):
                        play_camera()
                capture.release.assert_called_once()
                self.assertEqual("\033[?25h" in output.getvalue(), displayed)

    def test_read_conversion_and_sleep_errors_restore_cursor_and_release(self):
        for failure in (OSError("device failed"), cv2.error("driver failed"), KeyboardInterrupt()):
            for location in ("read", "conversion", "sleep"):
                with self.subTest(failure=type(failure).__name__, location=location):
                    capture = fake_capture([(True, self.frame), failure] if location == "read" else [(True, self.frame)] * 2)
                    output = io.StringIO()
                    with contextlib.ExitStack() as stack:
                        stack.enter_context(patch("ascart.camera_art.cv2.VideoCapture", return_value=capture))
                        stack.enter_context(contextlib.redirect_stdout(output))
                        if location == "conversion":
                            stack.enter_context(patch("ascart.camera_art.video_frame_to_ascii", side_effect=["@", failure]))
                        stack.enter_context(patch("ascart.camera_art.time.sleep", side_effect=failure if location == "sleep" else None))
                        with self.assertRaises(type(failure)):
                            play_camera()
                    capture.release.assert_called_once()
                    self.assertIn("\033[0m\033[?25h", output.getvalue())

    def test_redraw_rate_is_capped_and_slow_frames_do_not_sleep(self):
        capture = fake_capture([(True, self.frame), (True, self.frame), KeyboardInterrupt()])
        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), \
             patch("ascart.camera_art.time.monotonic", side_effect=[10, 10.01, 11, 11.05, 12]), \
             patch("ascart.camera_art.time.sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                play_camera()
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 1 / 30 - 0.01)
        capture.release.assert_called_once()

    def test_negative_camera_and_unexpected_errors_are_not_hidden(self):
        with patch("ascart.camera_art.cv2.VideoCapture") as open_camera:
            with self.assertRaisesRegex(ValueError, "0 or greater"):
                play_camera(-1)
        open_camera.assert_not_called()
        capture = fake_capture([(True, self.frame)])
        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), patch("ascart.camera_art.video_frame_to_ascii", side_effect=TypeError("test bug")):
            with self.assertRaisesRegex(TypeError, "test bug"):
                play_camera()
        capture.release.assert_called_once()


class CameraCliTests(unittest.TestCase):
    def run_cli(self, *args, terminal=True):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, args)]), patch.object(output, "isatty", return_value=terminal), \
             patch.dict(os.environ, {"COLORFGBG": "0;15"}), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_default_and_explicit_camera_selection_and_stop(self):
        for options, index, mirrored in ((["--camera"], 0, False), (["--camera", "2"], 2, False), (["--camera=12"], 12, False), (["--camera-mirrored"], 0, True), (["--camera-mirrored", "2"], 2, True)):
            with patch("ascart.cli.play_camera", side_effect=KeyboardInterrupt) as play:
                code, output, errors = self.run_cli(*options)
            self.assertEqual(code, 0, errors)
            self.assertEqual(play.call_args.args, (index,))
            self.assertEqual(play.call_args.kwargs["width"], 60)
            self.assertEqual(play.call_args.kwargs["mirrored"], mirrored)
            self.assertIn("Camera stopped.", output)

    def test_rendering_option_matrix_uses_existing_converter(self):
        frame = np.full((24, 32, 3), (10, 30, 200), dtype=np.uint8)
        cases = itertools.product((False, True), (False, True), ("dark", "light", "auto"), (False, True), (False, True), (False, True))
        for color, border, background, custom, fitted, mirrored in cases:
            with self.subTest(color=color, border=border, background=background, custom=custom, fitted=fitted, mirrored=mirrored):
                options = ["--camera-mirrored" if mirrored else "--camera", "--background", background]
                options += ["--color"] if color else []
                options += ["--border"] if border else []
                options += ["--chars= .:@"] if custom else []
                options += ["--fit"] if fitted else ["--width=10"]
                capture = fake_capture([(True, frame), KeyboardInterrupt()])
                with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture) as open_camera, patch("ascart.camera_art.time.sleep"), patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((18, 10))):
                    code, output, errors = self.run_cli(*options)
                self.assertEqual(code, 0, errors)
                palette = " .:@" if custom else ("#%@" if color else " .:-=+*#%@")
                width = (15 if border else 17) if fitted else 10
                height = (6 if border else 8) if fitted else None
                art = video_frame_to_ascii(frame if mirrored else cv2.flip(frame, 1), width, palette, "dark" if background == "dark" else "light", height, color)
                if border:
                    art = add_border(art)
                self.assertIn("\033[H\033[J" + art, output)
                self.assertIn("\033[?25h", output)
                open_camera.assert_called_once_with(0)
                capture.release.assert_called_once()

    def test_invalid_commands_never_open_camera_or_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "not-created" / "camera.mp4"
            keep = Path(directory) / "keep.txt"
            keep.write_text("user file")
            cases = [[], ["--camera", "-1"], ["--camera", "999999999999999"], ["--camera", "abc"], ["--camera", "--list-cameras"],
                     ["--camera", "--text", "hello"], ["--camera", "photo.png"], ["--list-cameras", "photo.png"],
                     ["--camera", "--output", target], ["--list-cameras", "--output", keep],
                     ["--camera", "--loop"], ["--camera", "--loop-4"], ["--list-cameras", "--loop-count", "2"],
                     ["--camera", "--width", "0"], ["--camera", "--chars="], ["--camera", "--chars=☃"],
                     ["--camera", "--width", "10", "--fit"], ["--list-cameras", "--color"],
                     ["--list-cameras", "--fit"], ["--camera", "--fit", "--border"]]
            cases += [["--camera", "--camera-mirrored"], ["--camera-mirrored", "-1"],
                      ["--camera-mirrored", "999999999999999"], ["--camera-mirrored", "--list-cameras"],
                      ["--camera-mirrored", "--text", "hi"], ["--camera-mirrored", "--output", target],
                      ["--camera-mirrored", "--loop"]]
            for options in cases:
                with self.subTest(options=options), patch("ascart.camera_art.cv2.VideoCapture") as open_camera, patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((3, 4))):
                    code, output, errors = self.run_cli(*options)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertNotIn("Traceback", errors)
                open_camera.assert_not_called()
            self.assertFalse(target.parent.exists())
            self.assertEqual(keep.read_text(), "user file")

    def test_noninteractive_camera_rejected_before_opening(self):
        with patch("ascart.camera_art.cv2.VideoCapture") as open_camera:
            code, output, errors = self.run_cli("--camera", terminal=False)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("interactive terminal", errors)
        open_camera.assert_not_called()

    def test_list_output_empty_result_interrupt_and_errors(self):
        for result, expected in (([0, 2], "Camera 2: readable"), ([], "No readable cameras")):
            with patch("ascart.cli.list_cameras", return_value=result):
                code, output, errors = self.run_cli("--list-cameras", terminal=False)
            self.assertEqual(code, 0, errors)
            self.assertIn("briefly activate", output)
            self.assertIn(expected, output)
        with patch("ascart.cli.list_cameras", side_effect=KeyboardInterrupt):
            self.assertIn("Camera check stopped.", self.run_cli("--list-cameras")[1])
        with patch("ascart.cli.list_cameras", side_effect=OSError("cannot inspect devices")):
            code, output, errors = self.run_cli("--list-cameras")
        self.assertEqual(code, 2)
        self.assertIn("cannot inspect devices", errors)

    def test_camera_errors_and_unexpected_bugs(self):
        for error in (OSError("device busy"), ValueError("no frame"), cv2.error("driver failed")):
            with patch("ascart.cli.play_camera", side_effect=error):
                code, output, errors = self.run_cli("--camera")
            self.assertEqual(code, 2)
            self.assertIn("Cannot use camera 0", errors)
            self.assertNotIn("Traceback", errors)
        with patch("ascart.cli.play_camera", side_effect=TypeError("test bug")):
            with self.assertRaisesRegex(TypeError, "test bug"):
                self.run_cli("--camera")

    def test_existing_commands_help_and_version_never_access_camera(self):
        with patch("ascart.camera_art.cv2.VideoCapture") as open_camera:
            for options in (("--help",), ("--version",), ("-t", "hello"), ("examples/image1.png",)):
                code, output, errors = self.run_cli(*options)
                self.assertEqual(code, 0, errors)
            self.assertEqual(self.run_cli("-t", "--camera")[0], 2)
            self.assertEqual(self.run_cli("--text=--camera")[0], 0)
        open_camera.assert_not_called()
