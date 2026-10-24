import contextlib
import errno
import io
import itertools
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from ascart.camera_recording import RECORDING_FPS, record_camera
from ascart.cli import main


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, delay):
        self.now += delay


class CameraRecordingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.target = self.root / "new folder" / "camera.mp4"
        self.frame = np.zeros((24, 32, 3), dtype=np.uint8)
        self.frame[:, :16] = (0, 0, 255)
        self.frame[:, 16:] = (255, 0, 0)
        self.original = self.frame.copy()
        self.capture = Mock()
        self.capture.read.return_value = (True, self.frame)
        self.clock = Clock()

    @contextlib.contextmanager
    def simulated_camera(self, index):
        try:
            yield self.capture
        finally:
            self.capture.release()

    @contextlib.contextmanager
    def simulation(self):
        with patch("ascart.camera_recording.camera_capture", side_effect=self.simulated_camera) as opened, \
             patch("ascart.camera_recording.time.monotonic", side_effect=self.clock.monotonic), \
             patch("ascart.camera_recording.time.sleep", side_effect=self.clock.sleep):
            yield opened

    def run_cli(self, *args, terminal=False):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, args)]), \
             patch.object(output, "isatty", return_value=terminal), \
             patch.dict(os.environ, {"COLORFGBG": "0;15"}), \
             patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((22, 12))), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def read_output(self, target, expected_count):
        reader = cv2.VideoCapture(str(target))
        self.assertTrue(reader.isOpened())
        frames = []
        try:
            self.assertAlmostEqual(reader.get(cv2.CAP_PROP_FPS), RECORDING_FPS)
            while True:
                success, frame = reader.read()
                if not success:
                    break
                frames.append(frame)
        finally:
            reader.release()
        self.assertEqual(len(frames), expected_count)
        self.assertFalse(list(target.parent.glob(".ascart-*")))
        np.testing.assert_array_equal(self.frame, self.original)
        return frames

    def test_real_recording_color_orientation_duration_and_terminal_cleanup(self):
        for mirrored in (False, True):
            self.clock.now = 0
            self.capture.reset_mock()
            target = self.root / f"orientation-{mirrored}.MP4"
            option = "--camera-mirrored" if mirrored else "--camera"
            with self.simulation() as opened:
                code, output, errors = self.run_cli(option, "2", "--camera-duration", "0.2", "--width=10", "--chars=@", "--color", "--border", "--background=dark", "--output", target, terminal=True)
            self.assertEqual(code, 0, errors)
            opened.assert_called_once_with(2)
            self.capture.release.assert_called_once()
            self.assertAlmostEqual(self.clock.now, 0.2)
            self.assertIn("\033[?25h", output)
            self.assertTrue(output.endswith(f"Saved ASCII camera recording to {target}\n"))
            frames = self.read_output(target, 3)
            self.assertEqual(frames[0].shape[:2], (134, 168))
            middle = frames[0][34:100, 24:144].astype(np.int16)
            left = middle[:, :48]
            red_minus_blue = float((left[:, :, 2] - left[:, :, 0]).mean())
            self.assertGreater(red_minus_blue if mirrored else -red_minus_blue, 10)

    def test_visual_option_matrix_and_noninteractive_saving(self):
        cases = itertools.product((False, True), (False, True), ("dark", "light", "auto"), (False, True), (False, True), (False, True))
        for index, (color, border, background, custom, fitted, mirrored) in enumerate(cases):
            with self.subTest(case=index):
                self.clock.now = 0
                self.capture.reset_mock()
                target = self.root / f"combination-{index}.mp4"
                options = ["--camera-mirrored" if mirrored else "--camera", "--camera-duration=0.2", "--background", background]
                options += ["--color"] if color else []
                options += ["--border"] if border else []
                options += ["--chars= .:@"] if custom else []
                options += ["--fit"] if fitted else ["--width=10"]
                with self.simulation():
                    code, output, errors = self.run_cli(*options, "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertEqual(output, f"Saved ASCII camera recording to {target}\n")
                self.assertIn("Recording camera", errors)
                self.assertNotIn("\033", output)
                frames = self.read_output(target, 3)
                canvas = 0 if background == "dark" else 255
                self.assertLess(abs(float(frames[0][:8, :8].mean()) - canvas), 15)
                if fitted:
                    self.assertLessEqual(frames[0].shape[1], 21 * 12 + 24)
                    self.assertLessEqual(frames[0].shape[0], 10 * 22 + 24)
                self.capture.release.assert_called_once()

    def test_slow_capture_repeats_frames_instead_of_speeding_up_saved_video(self):
        def slow_read():
            self.clock.now += 0.22
            return True, self.frame
        self.capture.read.side_effect = slow_read
        with self.simulation():
            count = record_camera(0, self.target, 0.5, width=10)
        self.assertEqual(count, math.ceil(0.5 * RECORDING_FPS))
        self.read_output(self.target, count)
        self.assertLess(self.capture.read.call_count, count)
        self.capture.release.assert_called_once()

    def test_fractional_short_duration_saves_one_frame(self):
        with self.simulation():
            self.assertEqual(record_camera(0, self.target, 0.01, width=10), 1)
        self.read_output(self.target, 1)
        self.assertAlmostEqual(self.clock.now, 0.01)

    def test_invalid_durations_and_modes_fail_before_hardware_or_output_creation(self):
        cases = [["--camera", "--camera-duration=" + value, "--output", self.target] for value in ("0", "-1", "301", "nan", "inf", "-inf", "1e309", "abc")]
        cases += [["--camera", "--camera-duration", "1"], ["--camera-duration=1"],
                  ["--list-cameras", "--camera-duration=1", "--output", self.target],
                  ["-t", "hello", "--camera-duration=1", "--output", self.target],
                  ["examples/image1.png", "--camera-duration=1", "--output", self.target],
                  ["--camera", "--camera-duration=1", "--loop", "--output", self.target],
                  ["--camera-mirrored", "--camera-duration=1", "--loop-4", "--output", self.target]]
        cases += [["--camera", "--camera-duration=1", "--output", self.target.with_suffix(suffix)] for suffix in (".txt", ".png", ".html", ".gif", ".avi")]
        for args in cases:
            with self.subTest(args=args), patch("ascart.camera_art.cv2.VideoCapture") as hardware:
                code, output, errors = self.run_cli(*args)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            hardware.assert_not_called()
        self.assertFalse(self.target.parent.exists())
        for duration in (0, -1, 301, float("inf"), float("nan")):
            with self.assertRaises(ValueError), patch("ascart.camera_recording.camera_capture") as opened:
                record_camera(0, self.target, duration)
            opened.assert_not_called()

    def test_existing_destinations_and_links_are_preserved_before_camera_access(self):
        keep = self.root / "keep.mp4"
        keep.write_bytes(b"user video")
        symbolic = self.root / "symbolic.mp4"
        symbolic.symlink_to(keep)
        hard = self.root / "hard.mp4"
        hard.hardlink_to(keep)
        dangling = self.root / "dangling.mp4"
        dangling.symlink_to(self.root / "missing.mp4")
        for target in (keep, symbolic, hard, dangling, self.root):
            with patch("ascart.camera_art.cv2.VideoCapture") as hardware:
                code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", target)
            self.assertEqual(code, 2)
            hardware.assert_not_called()
        self.assertEqual(keep.read_bytes(), b"user video")
        self.assertTrue(dangling.is_symlink())

    def test_race_after_recording_preserves_competing_file(self):
        original_open = Path.open
        def competing_open(path, mode="r", *args, **kwargs):
            if path == self.target:
                self.capture.release.assert_called_once()
                self.assertEqual(mode, "xb")
                with original_open(path, "xb") as file:
                    file.write(b"other program")
            return original_open(path, mode, *args, **kwargs)
        with self.simulation(), patch("ascart.camera_recording.Path.open", new=competing_open):
            code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", self.target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("already exists", errors)
        self.assertEqual(self.target.read_bytes(), b"other program")
        self.assertFalse(list(self.target.parent.glob(".ascart-*")))

    def test_interrupt_discards_recording_and_restores_cursor(self):
        with self.simulation(), patch("ascart.camera_recording.time.sleep", side_effect=KeyboardInterrupt):
            code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--width=10", "--output", self.target, terminal=True)
        self.assertEqual(code, 0, errors)
        self.assertIn("recording cancelled", errors)
        self.assertIn("\033[?25h", output)
        self.assertNotIn("Saved ASCII", output)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.target.parent.glob(".ascart-*")))
        self.capture.release.assert_called_once()

    def test_camera_failures_release_handle_and_create_no_recording(self):
        for reads in ([(False, None)], [OSError("device failed")], [(True, self.frame), (False, None)]):
            self.capture.reset_mock()
            self.capture.read.side_effect = reads
            self.clock.now = 0
            with self.simulation():
                code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", self.target)
            self.assertEqual(code, 2)
            self.assertNotIn("Saved ASCII", output)
            self.assertFalse(self.target.exists())
            self.assertFalse(list(self.target.parent.glob(".ascart-*")))
            self.capture.release.assert_called_once()

    def test_dimension_change_stops_recording(self):
        self.capture.read.side_effect = [(True, self.frame), (True, np.zeros((40, 32, 3), dtype=np.uint8))]
        with self.simulation():
            code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", self.target)
        self.assertEqual(code, 2)
        self.assertIn("dimensions changed", errors)
        self.assertFalse(self.target.exists())

    def test_unavailable_encoder_is_closed_before_private_folder_cleanup(self):
        writer = Mock()
        writer.isOpened.return_value = False
        original_directory = tempfile.TemporaryDirectory
        @contextlib.contextmanager
        def checked_directory(*args, **kwargs):
            with original_directory(*args, **kwargs) as folder:
                try:
                    yield folder
                finally:
                    writer.release.assert_called_once()
                    self.capture.release.assert_called_once()
        with self.simulation(), patch("ascart.camera_recording.cv2.VideoWriter", return_value=writer), patch("ascart.camera_recording.tempfile.TemporaryDirectory", new=checked_directory):
            code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", self.target)
        self.assertEqual(code, 2)
        self.assertIn("MP4 encoding is unavailable", errors)
        self.assertFalse(self.target.exists())

    def test_readback_failure_does_not_publish_and_camera_is_closed_first(self):
        def fail_verify(*args):
            self.capture.release.assert_called_once()
            raise ValueError("Incomplete MP4 encoding")
        with self.simulation(), patch("ascart.camera_recording.verify_video", side_effect=fail_verify):
            code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", self.target)
        self.assertEqual(code, 2)
        self.assertIn("Incomplete MP4", errors)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.target.parent.glob(".ascart-*")))

    def test_encoder_write_error_closes_resources_and_restores_cursor(self):
        writer = Mock()
        writer.isOpened.return_value = True
        writer.write.side_effect = [None, OSError("encoder write failed")]
        with self.simulation(), patch("ascart.camera_recording.cv2.VideoWriter", return_value=writer):
            code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", self.target, terminal=True)
        self.assertEqual(code, 2)
        self.assertIn("encoder write failed", errors)
        self.assertIn("\033[?25h", output)
        self.assertNotIn("Saved ASCII", output)
        writer.release.assert_called_once()
        self.capture.release.assert_called_once()
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.target.parent.glob(".ascart-*")))

    def test_rendering_and_permission_failures_release_camera(self):
        for operation, failure in (("ascart.camera_recording.art_to_png", ValueError("picture too large")),
                                   ("ascart.camera_recording.Path.mkdir", PermissionError(errno.EACCES, "Permission denied"))):
            self.capture.reset_mock()
            with self.simulation(), patch(operation, side_effect=failure):
                code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", self.target)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.capture.release.assert_called_once()
            self.assertFalse(self.target.exists())

    def test_maximum_duration_is_accepted_without_a_real_recording(self):
        with patch("ascart.cli.record_camera", return_value=4500) as record:
            code, output, errors = self.run_cli("--camera-mirrored", "--camera-duration=300", "--output", self.target)
        self.assertEqual(code, 0, errors)
        self.assertEqual(record.call_args.args[2], 300)
        self.assertTrue(record.call_args.kwargs["mirrored"])

    def test_partial_copy_keeps_only_new_partial_file(self):
        def failing_copy(source, destination):
            destination.write(b"partial new video")
            raise OSError(errno.ENOSPC, "No space left on device")
        with self.simulation(), patch("ascart.camera_recording.shutil.copyfileobj", side_effect=failing_copy):
            code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", self.target)
        self.assertEqual(code, 2)
        self.assertNotIn("Saved ASCII", output)
        self.assertIn("No space left", errors)
        self.assertEqual(self.target.read_bytes(), b"partial new video")
        self.assertFalse(list(self.target.parent.glob(".ascart-*")))

    def test_bad_duration_option_can_still_be_literal_banner_text(self):
        code, output, errors = self.run_cli("--text=--camera-duration")
        self.assertEqual(code, 0, errors)
