import contextlib
import errno
import hashlib
import io
import itertools
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image

from ascart.cli import main
from ascart.video_art import save_ascii_video, verify_video


class VideoOutputTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "source.mp4"
        writer = cv2.VideoWriter(str(self.source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 24))
        self.assertTrue(writer.isOpened(), "Tests require MP4 encoding")
        try:
            for color in ((0, 0, 255), (255, 0, 0), (0, 255, 255)):
                writer.write(np.full((24, 32, 3), color, dtype=np.uint8))
        finally:
            writer.release()
        self.original = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.original)

    def run_cli(self, *arguments, terminal=False):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, arguments)]), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), \
             patch.object(output, "isatty", return_value=terminal):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def read_output(self, path):
        capture = cv2.VideoCapture(str(path))
        self.assertTrue(capture.isOpened())
        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            frames = []
            while True:
                success, frame = capture.read()
                if not success:
                    break
                frames.append(frame)
            return fps, frames
        finally:
            capture.release()

    def assert_output(self, path, expected_size=None, expected_fps=10):
        fps, frames = self.read_output(path)
        self.assertAlmostEqual(fps, expected_fps, places=2)
        self.assertEqual(len(frames), 3)
        if expected_size:
            self.assertTrue(all((frame.shape[1], frame.shape[0]) == expected_size for frame in frames))
        self.assertFalse(list(path.parent.glob(".ascart-*")))
        return frames

    def test_real_color_output_has_correct_dimensions_fps_and_color_order(self):
        target = self.root / "new folder" / "my art.MP4"
        code, output, errors = self.run_cli(
            self.source, "--width", "10", "--color", "--chars=@", "--border",
            "--background", "dark", "--output", target,
        )
        self.assertEqual(code, 0, errors)
        self.assertEqual(output, f"Saved ASCII video to {target}\n")
        frames = self.assert_output(target, (168, 134))
        # Compression changes exact RGB values. Check that red strokes remain
        # red in the first frame and blue strokes remain blue in the second.
        first = frames[0][34:100, 24:144].astype(np.int16)
        second = frames[1][34:100, 24:144].astype(np.int16)
        self.assertGreater(int((first[:, :, 2] - first[:, :, 0]).max()), 100)
        self.assertGreater(int((second[:, :, 0] - second[:, :, 2]).max()), 100)

    def test_save_option_matrix(self):
        cases = itertools.product((False, True), (False, True), ("dark", "light"), (False, True), (False, True))
        for index, (color, border, background, custom, fitted) in enumerate(cases):
            with self.subTest(color=color, border=border, background=background, custom=custom, fitted=fitted):
                target = self.root / f"combination-{index}.mp4"
                options = ["--background", background]
                options += ["--color"] if color else []
                options += ["--border"] if border else []
                options += ["--chars= .-+@"] if custom else []
                options += ["--fit"] if fitted else ["--width=10"]
                with patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((22, 12))):
                    code, output, errors = self.run_cli(self.source, *options, "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertEqual(output, f"Saved ASCII video to {target}\n")
                frames = self.assert_output(target)
                if fitted:
                    self.assertLessEqual(frames[0].shape[1], 21 * 12 + 24)
                    self.assertLessEqual(frames[0].shape[0], 10 * 22 + 24)
                expected_canvas = 0 if background == "dark" else 255
                self.assertLess(abs(float(frames[0][:8, :8].mean()) - expected_canvas), 15)

    def test_terminal_loops_do_not_duplicate_saved_video(self):
        for options, expected in (((), 3), (("--loop-4",), 12)):
            target = self.root / f"preview-{expected}.mp4"
            with patch("ascart.video_art.time.sleep"):
                code, output, errors = self.run_cli(self.source, "--width=10", "--color", "--border", *options, "--output", target, terminal=True)
            self.assertEqual(code, 0, errors)
            self.assertEqual(output.count("\033[H\033[J"), expected)
            self.assertIn("\033[?25h", output)
            self.assertTrue(output.endswith(f"Saved ASCII video to {target}\n"))
            self.assert_output(target)

    def test_continuous_preview_interrupt_preserves_finished_output(self):
        target = self.root / "continuous.mp4"

        def interrupt_preview(delay):
            self.assert_output(target)
            raise KeyboardInterrupt

        with patch("ascart.video_art.time.sleep", side_effect=interrupt_preview):
            code, output, errors = self.run_cli(self.source, "--width=10", "--loop", "--output", target, terminal=True)
        self.assertEqual(code, 0, errors)
        self.assertIn("\033[?25h", output)
        self.assertTrue(output.endswith(f"Saved ASCII video to {target}\n"))
        self.assert_output(target)

    def test_noninteractive_loop_does_not_start_playback(self):
        target = self.root / "no-preview.mp4"
        with patch("ascart.cli.play_video") as play:
            code, output, errors = self.run_cli(self.source, "--width=10", "--loop", "--output", target)
        self.assertEqual(code, 0, errors)
        play.assert_not_called()
        self.assert_output(target)

    def test_avi_input_can_save_mp4(self):
        source = self.root / "source.avi"
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
        self.assertTrue(writer.isOpened())
        try:
            for value in (40, 100, 200):
                writer.write(np.full((24, 32, 3), value, dtype=np.uint8))
        finally:
            writer.release()
        target = self.root / "from-avi.mp4"
        code, _, errors = self.run_cli(source, "--width=10", "--output", target)
        self.assertEqual(code, 0, errors)
        self.assert_output(target)

    def test_wrong_input_output_combinations_create_no_folders(self):
        photo = self.root / "photo.png"
        gif = self.root / "image.gif"
        with Image.new("RGB", (16, 12), "red") as image:
            image.save(photo)
            image.save(gif)
        cases = [((self.source,), suffix) for suffix in (".txt", ".png", ".gif", ".avi")]
        cases += [((photo,), ".mp4"), ((gif,), ".mp4"), (("--text", "Hi"), ".mp4")]
        for inputs, suffix in cases:
            with self.subTest(inputs=inputs, suffix=suffix):
                target = self.root / "not-created" / ("art" + suffix)
                code, output, errors = self.run_cli(*inputs, "--output", target)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("output", errors)
                self.assertFalse(target.parent.exists())

    def test_existing_files_input_aliases_and_links_preserved(self):
        keep = self.root / "keep.mp4"
        keep.write_bytes(b"user data")
        symbolic = self.root / "symbolic.mp4"
        symbolic.symlink_to(self.source)
        hard = self.root / "hard.mp4"
        hard.hardlink_to(self.source)
        dangling = self.root / "dangling.mp4"
        dangling.symlink_to(self.root / "missing.mp4")
        for target in (keep, self.source, symbolic, hard, dangling, self.root):
            code, output, errors = self.run_cli(self.source, "--output", target)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("Cannot save artwork", errors)
        self.assertEqual(keep.read_bytes(), b"user data")
        self.assertTrue(dangling.is_symlink())
        self.assertFalse(dangling.exists())

    def test_competing_creation_after_encoding_does_not_replace_file(self):
        target = self.root / "race.mp4"
        original_open = Path.open

        def competing_open(path, mode="r", *args, **kwargs):
            if path == target:
                self.assertEqual(mode, "xb")
                with original_open(path, "xb") as file:
                    file.write(b"created by another program")
            return original_open(path, mode, *args, **kwargs)

        with patch("ascart.video_art.Path.open", new=competing_open):
            code, output, errors = self.run_cli(self.source, "--width=10", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("already exists", errors)
        self.assertEqual(target.read_bytes(), b"created by another program")
        self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_unavailable_encoder_reports_error_and_removes_temporary_files(self):
        target = self.root / "new.mp4"
        writer = Mock()
        writer.isOpened.return_value = False
        with patch("ascart.video_art.cv2.VideoWriter", return_value=writer), patch("ascart.cli.play_video") as play:
            code, output, errors = self.run_cli(self.source, "--width=10", "--output", target, terminal=True)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("MP4 encoding is unavailable", errors)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".ascart-*")))
        writer.release.assert_called_once()
        play.assert_not_called()

    def test_incomplete_encoding_does_not_create_destination(self):
        target = self.root / "new.mp4"
        with patch("ascart.video_art.verify_video", side_effect=ValueError("Incomplete MP4 encoding")):
            code, output, errors = self.run_cli(self.source, "--width=10", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("Incomplete MP4 encoding", errors)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_encoder_silently_dropping_frames_is_detected(self):
        target = self.root / "new.mp4"
        original_writer = cv2.VideoWriter

        def dropping_writer(*args):
            writer = original_writer(*args)
            return Mock(isOpened=writer.isOpened, release=writer.release, write=Mock())

        with patch("ascart.video_art.cv2.VideoWriter", side_effect=dropping_writer):
            code, output, errors = self.run_cli(self.source, "--width=10", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("Cannot save artwork", errors)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_missing_fps_uses_30_fps(self):
        target = self.root / "fallback.mp4"
        with patch("ascart.video_art.positive_property", return_value=None):
            code, output, errors = self.run_cli(self.source, "--width=10", "--output", target)
        self.assertEqual(code, 0, errors)
        self.assertIn("30 FPS for saving", errors)
        self.assert_output(target, expected_fps=30)

    def test_source_failure_or_interrupt_releases_encoder_and_cleans_temporary_files(self):
        for error in (OSError("read failed"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                capture = Mock()
                capture.get.return_value = 10
                capture.read.side_effect = [(True, np.zeros((24, 32, 3), dtype=np.uint8)), error]
                writer = Mock()
                writer.isOpened.return_value = True
                target = self.root / "new.mp4"
                with patch("ascart.video_art.open_video", return_value=capture), patch("ascart.video_art.cv2.VideoWriter", return_value=writer):
                    with self.assertRaises(type(error)):
                        save_ascii_video(self.source, target, width=10)
                capture.release.assert_called_once()
                writer.release.assert_called_once()
                self.assertFalse(target.exists())
                self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_empty_input_does_not_create_output_folder(self):
        capture = Mock()
        capture.get.return_value = 10
        capture.read.return_value = (False, None)
        target = self.root / "not-created" / "new.mp4"
        with patch("ascart.video_art.open_video", return_value=capture):
            with self.assertRaisesRegex(ValueError, "no frame"):
                save_ascii_video(self.source, target)
        self.assertFalse(target.parent.exists())
        capture.release.assert_called_once()

    def test_encoder_closes_before_temporary_folder_cleanup_on_error(self):
        target = self.root / "new.mp4"
        writer = Mock()
        writer.isOpened.return_value = True
        writer.write.side_effect = OSError("encoder write failed")
        original_directory = tempfile.TemporaryDirectory

        @contextlib.contextmanager
        def checked_directory(*args, **kwargs):
            with original_directory(*args, **kwargs) as folder:
                try:
                    yield folder
                finally:
                    writer.release.assert_called_once()

        with patch("ascart.video_art.tempfile.TemporaryDirectory", new=checked_directory), \
             patch("ascart.video_art.cv2.VideoWriter", return_value=writer):
            code, output, errors = self.run_cli(self.source, "--width=10", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("encoder write failed", errors)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_permission_and_partial_copy_failures(self):
        target = self.root / "new.mp4"
        with patch("ascart.video_art.Path.mkdir", side_effect=PermissionError(errno.EACCES, "Permission denied")):
            code, output, errors = self.run_cli(self.source, "--width=10", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("Permission denied", errors)
        self.assertFalse(target.exists())

        def failing_copy(source, destination):
            destination.write(b"new partial video")
            raise OSError(errno.ENOSPC, "No space left on device")

        with patch("ascart.video_art.shutil.copyfileobj", side_effect=failing_copy):
            code, output, errors = self.run_cli(self.source, "--width=10", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("No space left", errors)
        self.assertEqual(target.read_bytes(), b"new partial video")
        self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_readback_detects_missing_frames_and_wrong_dimensions(self):
        for count, size, message in ((4, (32, 24), "Incomplete"), (3, (16, 12), "dimensions")):
            with self.subTest(count=count, size=size), self.assertRaisesRegex(ValueError, message):
                verify_video(self.source, count, size)
