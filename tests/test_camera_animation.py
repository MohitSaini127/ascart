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

import numpy as np
from PIL import Image

from ascart.cli import main
from ascart.camera_recording import RECORDING_FPS, record_camera
from ascart.html_art import art_to_markup
from ascart.png_art import art_to_png
from ascart.video_art import video_frame_to_ascii
from test_animated_html import read_frames
from test_camera_recording import Clock


class CameraAnimationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.frame = np.zeros((24, 32, 3), dtype=np.uint8)
        self.frame[:, :16] = (0, 0, 255)
        self.frame[:, 16:] = (255, 0, 0)
        self.original = self.frame.copy()
        self.capture = Mock()
        self.capture.read.return_value = (True, self.frame)
        self.clock = Clock()

    @contextlib.contextmanager
    def fake_camera(self, index):
        try:
            yield self.capture
        finally:
            self.capture.release()

    @contextlib.contextmanager
    def simulation(self):
        with patch("ascart.camera_recording.camera_capture", side_effect=self.fake_camera) as opened, \
             patch("ascart.camera_recording.time.monotonic", side_effect=self.clock.monotonic), \
             patch("ascart.camera_recording.time.sleep", side_effect=self.clock.sleep):
            yield opened

    def run_cli(self, *args, terminal=False):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, args)]), patch.object(output, "isatty", return_value=terminal), \
             patch.dict(os.environ, {"COLORFGBG": "0;15"}), \
             patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((18, 10))), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def gif_data(self, target):
        delays = []
        with Image.open(target) as saved:
            self.assertEqual(saved.format, "GIF")
            self.assertNotIn("loop", saved.info)
            size = saved.size
            first = np.asarray(saved.convert("RGB"))
            for index in range(saved.n_frames):
                saved.seek(index)
                saved.load()
                self.assertEqual(saved.size, size)
                delays.append(saved.info.get("duration", 0))
        return size, first, sum(delays)

    def test_visual_option_matrix_for_both_formats(self):
        cases = itertools.product(("gif", "html"), (False, True), (False, True), ("dark", "light", "auto"), (False, True), (False, True), (False, True))
        for index, (suffix, color, border, background, custom, fitted, mirrored) in enumerate(cases):
            with self.subTest(case=index):
                self.clock.now = 0
                self.capture.reset_mock()
                target = self.root / "new folder" / f"art {index}.{suffix.upper()}"
                options = ["--camera-mirrored" if mirrored else "--camera", "2", "--camera-duration=.2", "--background", background]
                options += ["--color"] if color else []
                options += ["--border"] if border else []
                options += ['--chars= <&>@'] if custom else []
                options += ["--fit"] if fitted else ["--width=10"]
                with self.simulation() as opened:
                    code, output, errors = self.run_cli(*options, "--output", target)
                self.assertEqual(code, 0, errors)
                opened.assert_called_once_with(2)
                self.capture.release.assert_called_once()
                self.assertEqual(output, f"Saved ASCII camera recording to {target}\n")
                self.assertFalse(list(target.parent.glob(".ascart-*")))
                if suffix == "html":
                    frames, document = read_frames(target)
                    self.assertEqual(len(frames), 3)
                    self.assertAlmostEqual(sum(delay for _, delay in frames), 200)
                    self.assertIn('<input id="loop" type="checkbox">', document)
                    self.assertIn('id="play"', document)
                    self.assertNotIn("\033", document)
                else:
                    size, first, duration = self.gif_data(target)
                    self.assertEqual(duration, 200)
                    canvas = 0 if background == "dark" else 255
                    self.assertEqual(tuple(first[0, 0]), (canvas,) * 3)
                    if fitted:
                        self.assertLessEqual(size[0], 17 * 12 + 24)
                        self.assertLessEqual(size[1], 8 * 22 + 24)
        np.testing.assert_array_equal(self.frame, self.original)

    def test_gif_preserves_orientation_and_smooth_coloured_strokes(self):
        for mirrored in (False, True):
            self.clock.now = 0
            self.capture.reset_mock()
            target = self.root / f"orientation-{mirrored}.gif"
            with self.simulation():
                code, output, errors = self.run_cli("--camera-mirrored" if mirrored else "--camera", "--camera-duration=.2", "--width=10", "--chars=@", "--color", "--border", "--background=dark", "--output", target, terminal=True)
            self.assertEqual(code, 0, errors)
            self.assertIn("\033[?25h", output)
            size, first, duration = self.gif_data(target)
            self.assertEqual(size, (168, 134))
            left = first[34:100, 24:72].astype(np.int16)
            difference = float((left[:, :, 0] - left[:, :, 2]).mean())
            self.assertGreater(difference if mirrored else -difference, 10)

    def test_html_uses_exact_escaped_ascii_from_shared_converter(self):
        target = self.root / "camera.html"
        with self.simulation():
            code, output, errors = self.run_cli("--camera-mirrored", "--camera-duration=.2", "--width=10", '--chars=<&>"\'', "--color", "--background=dark", "--output", target)
        self.assertEqual(code, 0, errors)
        expected = video_frame_to_ascii(self.frame, width=10, palette='<&>"\'', color=True)
        frames, document = read_frames(target)
        self.assertTrue(all(markup == art_to_markup(expected) for markup, _ in frames))
        self.assertEqual(document.count("</script>"), 2)

    def test_slow_capture_preserves_total_duration_for_both_formats(self):
        for suffix in ("gif", "html"):
            self.clock.now = 0
            self.capture.reset_mock()
            def slow_read():
                self.clock.now += .22
                return True, self.frame
            self.capture.read.side_effect = slow_read
            target = self.root / ("slow." + suffix)
            with self.simulation():
                count = record_camera(0, target, .5, width=10)
            self.assertEqual(count, math.ceil(.5 * RECORDING_FPS))
            if suffix == "gif":
                self.assertEqual(self.gif_data(target)[2], 530)
            else:
                frames, _ = read_frames(target)
                self.assertEqual(len(frames), 8)
                self.assertAlmostEqual(sum(delay for _, delay in frames), 8 * 1000 / RECORDING_FPS)
            self.assertLess(self.capture.read.call_count, count)
            self.capture.release.assert_called_once()

    def test_html_frame_limit_rejected_before_device_access(self):
        target = self.root / "not-created" / "too-long.html"
        with patch("ascart.camera_recording.camera_capture") as opened:
            code, output, errors = self.run_cli("--camera", "--camera-duration=201", "--output", target)
            self.assertEqual(code, 2)
            self.assertIn("3000 frames", errors)
            self.assertEqual(output, "")
            with self.assertRaisesRegex(ValueError, "3000 frames"):
                record_camera(0, target, 201)
            opened.assert_not_called()
        self.assertFalse(target.parent.exists())

    def test_format_memory_limits_abort_and_release_without_publishing(self):
        for suffix, constant in (("gif", "ascart.camera_recording.CAMERA_GIF_PIXEL_LIMIT"), ("html", "ascart.html_art.MAX_ANIMATION_BYTES")):
            target = self.root / ("limited." + suffix)
            self.capture.reset_mock()
            self.clock.now = 0
            with self.simulation(), patch(constant, 1):
                code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", target, terminal=True)
            self.assertEqual(code, 2)
            self.assertIn("\033[?25h", output)
            self.assertNotIn("Saved ASCII", output)
            self.capture.release.assert_called_once()
            self.assertFalse(target.exists())
            self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_cancellation_cleans_up_and_restores_cursor_for_both_formats(self):
        for suffix in ("gif", "html"):
            self.capture.reset_mock()
            self.clock.now = 0
            target = self.root / ("cancelled." + suffix)
            with self.simulation(), patch("ascart.camera_recording.time.sleep", side_effect=KeyboardInterrupt):
                code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", target, terminal=True)
            self.assertEqual(code, 0, errors)
            self.assertIn("recording cancelled", errors)
            self.assertIn("\033[?25h", output)
            self.assertFalse(target.exists())
            self.capture.release.assert_called_once()
            self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_recording_failures_do_not_publish(self):
        for suffix, failure in itertools.product(("gif", "html"), (OSError("device failed"), (False, None))):
            self.capture.reset_mock()
            self.clock.now = 0
            self.capture.read.side_effect = [(True, self.frame), failure]
            target = self.root / ("failed." + suffix)
            with self.simulation():
                code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", target)
            self.assertEqual(code, 2)
            self.assertFalse(target.exists())
            self.capture.release.assert_called_once()
            self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_existing_destinations_links_and_competing_creation_are_preserved(self):
        for suffix in ("gif", "html"):
            self.clock.now = 0
            self.capture.reset_mock()
            keep = self.root / ("keep." + suffix)
            keep.write_bytes(b"user file")
            symbolic = self.root / ("symbolic." + suffix)
            symbolic.symlink_to(keep)
            hard = self.root / ("hard." + suffix)
            hard.hardlink_to(keep)
            dangling = self.root / ("dangling." + suffix)
            dangling.symlink_to(self.root / ("missing." + suffix))
            for target in (keep, symbolic, hard, dangling):
                with patch("ascart.camera_recording.camera_capture") as opened:
                    code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", target)
                self.assertEqual(code, 2)
                opened.assert_not_called()
            self.assertEqual(keep.read_bytes(), b"user file")
            target = self.root / ("race." + suffix)
            original_open = Path.open
            def competing_open(path, mode="r", *args, **kwargs):
                if path == target:
                    self.capture.release.assert_called_once()
                    with original_open(path, "xb") as file:
                        file.write(b"other program")
                return original_open(path, mode, *args, **kwargs)
            with self.simulation(), patch("ascart.camera_recording.Path.open", new=competing_open):
                code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", target)
            self.assertEqual(code, 2)
            self.assertIn("already exists", errors)
            self.assertEqual(target.read_bytes(), b"other program")
            self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_gif_timing_failure_and_changed_dimensions_do_not_publish(self):
        target = self.root / "changed.html"
        self.capture.read.side_effect = [(True, self.frame), (True, np.zeros((40, 32, 3), dtype=np.uint8))]
        with self.simulation():
            code, output, errors = self.run_cli("--camera", "--camera-duration=1", "--output", target)
        self.assertEqual(code, 2)
        self.assertIn("dimensions changed", errors)
        self.assertFalse(target.exists())
        self.capture.reset_mock()
        self.capture.read.side_effect = None
        self.clock.now = 0
        target = self.root / "bad-timing.gif"
        def wrong_timing(entries, path, *args, **kwargs):
            frames = list(entries)
            self.capture.release.assert_called_once()
            with art_to_png(frames[0][0]) as picture:
                picture.save(path, format="GIF", duration=10)
        with self.simulation(), patch("ascart.camera_recording.save_ascii_gif", side_effect=wrong_timing):
            code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", target)
        self.assertEqual(code, 2)
        self.assertIn("timing does not match", errors)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_permission_and_partial_copy_failures_preserve_user_files(self):
        keep = self.root / "keep.txt"
        keep.write_text("user data")
        for suffix in ("gif", "html"):
            target = self.root / ("partial." + suffix)
            self.capture.reset_mock()
            self.clock.now = 0
            with self.simulation(), patch("ascart.camera_recording.Path.mkdir", side_effect=PermissionError(errno.EACCES, "Permission denied")):
                code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", target)
            self.assertEqual(code, 2)
            self.assertIn("Permission denied", errors)
            self.assertFalse(target.exists())
            self.capture.release.assert_called_once()
            self.capture.reset_mock()
            self.clock.now = 0
            def failed_copy(source, destination):
                self.capture.release.assert_called_once()
                destination.write(b"partial new animation")
                raise OSError(errno.ENOSPC, "No space left on device")
            with self.simulation(), patch("ascart.camera_recording.shutil.copyfileobj", side_effect=failed_copy):
                code, output, errors = self.run_cli("--camera", "--camera-duration=.2", "--output", target)
            self.assertEqual(code, 2)
            self.assertNotIn("Saved ASCII", output)
            self.assertIn("No space left", errors)
            self.assertEqual(target.read_bytes(), b"partial new animation")
            self.assertEqual(keep.read_text(), "user data")
            self.assertFalse(list(self.root.glob(".ascart-*")))
