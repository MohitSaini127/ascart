import contextlib
import errno
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

from ascart.border import COLOR_CODE, add_border
from ascart.camera_art import snapshot_camera
from ascart.cli import main
from ascart.png_art import art_to_png
from ascart.video_art import video_frame_to_ascii
from test_camera_art import fake_capture
from test_html_art import ArtworkParser


class SnapshotCaptureTests(unittest.TestCase):
    def test_preview_freezes_final_frame_removes_timer_and_restores_cursor(self):
        now = [0.0]
        warmup = np.zeros((24, 32, 3), dtype=np.uint8)
        final = np.full((24, 32, 3), (10, 30, 200), dtype=np.uint8)
        capture = fake_capture([])
        capture.read.side_effect = lambda: (True, final if now[0] >= 3 else warmup)
        output, errors = io.StringIO(), io.StringIO()
        def sleep(delay):
            now[0] += delay
        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), \
             patch("ascart.camera_art.time.monotonic", side_effect=lambda: now[0]), \
             patch("ascart.camera_art.time.sleep", side_effect=sleep), \
             patch("ascart.camera_art.shutil.get_terminal_size", return_value=os.terminal_size((18, 10))), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            art = snapshot_camera(width=10, color=True, border=True, preview=True)
        expected = add_border(video_frame_to_ascii(cv2.flip(final, 1), width=10, color=True))
        self.assertEqual(art, expected)
        self.assertEqual(errors.getvalue(), "")
        for seconds in (3, 2, 1):
            self.assertIn(f"{seconds}s to snapshot", output.getvalue())
        screens = output.getvalue().split("\033[H\033[J")
        self.assertGreater(len(screens), 3)
        self.assertTrue(all(len(screen.split("\n")[-1]) <= 17 for screen in screens[1:-1]))
        self.assertEqual(screens[-1], expected + "\033[0m\033[?25h\n")
        capture.release.assert_called_once()

    def test_preview_failure_or_cancellation_restores_cursor_and_releases(self):
        frame = np.zeros((24, 32, 3), dtype=np.uint8)
        for failure in (OSError("device failed"), ValueError("conversion failed"), KeyboardInterrupt()):
            output = io.StringIO()
            capture = fake_capture([(True, frame), (True, frame)])
            with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), \
                 patch("ascart.camera_art.time.sleep"), \
                 patch("ascart.camera_art.camera_frame_to_ascii", side_effect=["@", failure]), \
                 contextlib.redirect_stdout(output):
                with self.assertRaises(type(failure)):
                    snapshot_camera(preview=True)
            self.assertIn("\033[?25h", output.getvalue())
            capture.release.assert_called_once()

    def test_countdown_discards_warmup_and_uses_frame_after_three_seconds(self):
        now = [0.0]
        warmup = np.zeros((24, 32, 3), dtype=np.uint8)
        final = np.full((24, 32, 3), (10, 30, 200), dtype=np.uint8)
        capture = fake_capture([])
        capture.read.side_effect = lambda: (True, final if now[0] >= 3 else warmup)
        errors = io.StringIO()

        def sleep(delay):
            now[0] += delay

        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), \
             patch("ascart.camera_art.time.monotonic", side_effect=lambda: now[0]), \
             patch("ascart.camera_art.time.sleep", side_effect=sleep), \
             contextlib.redirect_stderr(errors):
            art = snapshot_camera(width=10, color=True)
        self.assertEqual(art, video_frame_to_ascii(cv2.flip(final, 1), width=10, color=True))
        self.assertGreater(capture.read.call_count, 1)
        self.assertEqual(now[0], 3)
        self.assertEqual(errors.getvalue().splitlines(), [f"Snapshot in {i}... (Ctrl+C cancels)" for i in (3, 2, 1)])
        capture.release.assert_called_once()

    def test_countdown_read_and_conversion_failures_always_release_camera(self):
        frame = np.zeros((24, 32, 3), dtype=np.uint8)
        cases = (("read", OSError("device failed")), ("read", cv2.error("driver failed")),
                 ("read", KeyboardInterrupt()), ("sleep", KeyboardInterrupt()),
                 ("conversion", ValueError("conversion failed")))
        for operation, error in cases:
            with self.subTest(operation=operation, error=type(error).__name__):
                capture = fake_capture([])
                capture.read.side_effect = error if operation == "read" else None
                capture.read.return_value = (True, frame)
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch("ascart.camera_art.cv2.VideoCapture", return_value=capture))
                    stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                    if operation == "conversion":
                        stack.enter_context(patch("ascart.camera_art.SNAPSHOT_COUNTDOWN_SECONDS", 0))
                        stack.enter_context(patch("ascart.camera_art.video_frame_to_ascii", side_effect=error))
                    elif operation == "sleep":
                        stack.enter_context(patch("ascart.camera_art.time.sleep", side_effect=error))
                    with self.assertRaises(type(error)):
                        snapshot_camera()
                capture.release.assert_called_once()


class SnapshotCliTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.frame = np.zeros((24, 32, 3), dtype=np.uint8)
        self.frame[:, :12] = (10, 30, 200)
        self.frame[:, 12:] = (200, 80, 20)
        self.original = self.frame.copy()

    def run_cli(self, *args, terminal=False):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, args)]), \
             patch.object(output, "isatty", return_value=terminal), \
             patch("ascart.camera_art.SNAPSHOT_COUNTDOWN_SECONDS", 0), \
             patch.dict(os.environ, {"COLORFGBG": "0;15"}), \
             patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((18, 10))), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_interactive_snapshot_shows_and_saves_same_final_frame_for_all_formats(self):
        for suffix, mirrored in itertools.product(("txt", "png", "html"), (False, True)):
            target = self.root / f"preview-{mirrored}.{suffix}"
            capture = fake_capture([(True, self.frame)])
            option = "--camera-mirrored" if mirrored else "--camera"
            with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture):
                code, output, errors = self.run_cli(option, "--color", "--width=10", "--border", "--output", target, terminal=True)
            self.assertEqual(code, 0, errors)
            color = suffix != "txt"
            palette = "#%@" if color else " .:-=+*#%@"
            expected = add_border(video_frame_to_ascii(self.frame if mirrored else cv2.flip(self.frame, 1), 10, palette, "light", color=color))
            screens = output.split("\033[H\033[J")
            self.assertEqual(screens[-2], expected + "\033[0m\033[?25h\n")
            self.assertEqual(screens[-1], expected + f"\nSaved ASCII art to {target}\n")
            if suffix == "txt":
                self.assertEqual(target.read_text(), expected + "\n")
            elif suffix == "html":
                self.assertEqual("".join(ArtworkParser(target.read_text()).text), COLOR_CODE.sub("", expected))
            else:
                with Image.open(target) as saved, art_to_png(expected, "light") as picture:
                    np.testing.assert_array_equal(np.asarray(saved), np.asarray(picture))
            capture.release.assert_called_once()

    def test_save_failure_keeps_frozen_frame_without_success_message(self):
        target = self.root / "not-created" / "snapshot.png"
        capture = fake_capture([(True, self.frame)])
        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), patch("ascart.cli.art_to_png", side_effect=ValueError("render failed")):
            code, output, errors = self.run_cli("--camera", "--color", "--output", target, terminal=True)
        self.assertEqual(code, 2)
        self.assertIn("\033[?25h", output)
        self.assertNotIn("Saved ASCII", output)
        self.assertIn("render failed", errors)
        self.assertFalse(target.parent.exists())
        capture.release.assert_called_once()

    def test_snapshot_format_and_visual_option_matrix(self):
        cases = itertools.product((".txt", ".png", ".html"), (False, True), (False, True),
                                  ("dark", "light", "auto"), (False, True), (False, True), (False, True))
        for index, (suffix, color, border, background, custom, fitted, mirrored) in enumerate(cases):
            with self.subTest(case=index):
                target = self.root / "new folder" / f"my snapshot {index}{suffix.upper()}"
                capture = fake_capture([(True, self.frame)])
                options = ["--camera-mirrored" if mirrored else "--camera", "2", "--background", background]
                options += ["--color"] if color else []
                options += ["--border"] if border else []
                options += ['--chars= <&>@'] if custom else []
                options += ["--fit"] if fitted else ["--width=10"]
                with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture) as open_camera:
                    code, output, errors = self.run_cli(*options, "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertEqual(errors, "")
                open_camera.assert_called_once_with(2)
                capture.release.assert_called_once()
                actual_color = color and suffix != ".txt"
                palette = " <&>@" if custom else ("#%@" if actual_color else " .:-=+*#%@")
                actual_background = "dark" if background == "dark" else "light"
                width = (15 if border else 17) if fitted else 10
                height = (6 if border else 8) if fitted else None
                expected = video_frame_to_ascii(self.frame if mirrored else cv2.flip(self.frame, 1), width, palette, actual_background, height, actual_color)
                if border:
                    expected = add_border(expected)
                self.assertEqual(output, expected + f"\nSaved ASCII art to {target}\n")
                if suffix == ".txt":
                    self.assertEqual(target.read_text(), expected + "\n")
                    self.assertNotIn("\033", target.read_text())
                elif suffix == ".html":
                    self.assertEqual("".join(ArtworkParser(target.read_text()).text), COLOR_CODE.sub("", expected))
                else:
                    with Image.open(target) as saved, art_to_png(expected, actual_background) as picture:
                        np.testing.assert_array_equal(np.asarray(saved), np.asarray(picture))
        np.testing.assert_array_equal(self.frame, self.original)

    def test_camera_releases_before_destination_is_opened(self):
        capture = fake_capture([(True, self.frame)])
        target = self.root / "snapshot.txt"
        original_open = Path.open

        def checked_open(path, mode="r", *args, **kwargs):
            if path == target:
                capture.release.assert_called_once()
                self.assertEqual(mode, "x")
            return original_open(path, mode, *args, **kwargs)

        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), patch("ascart.cli.Path.open", new=checked_open):
            code, output, errors = self.run_cli("--camera", "--output", target)
        self.assertEqual(code, 0, errors)
        self.assertTrue(target.exists())

    def test_unsupported_formats_loops_listing_and_bad_paths_never_open_camera(self):
        target = self.root / "not-created" / "snapshot.mp4"
        cases = [["--camera", "--output", target.with_suffix(suffix)] for suffix in (".gif", ".mp4", ".svg", "")]
        cases += [["--list-cameras", "--output", target.with_suffix(".txt")],
                  ["--camera", "--loop", "--output", target.with_suffix(".txt")],
                  ["--camera-mirrored", "--loop-4", "--output", target.with_suffix(".html")],
                  ["--camera", "--output", ""], ["--camera", "--output", "   "],
                  ["--camera", "--output", "bad\0.txt"]]
        for args in cases:
            with self.subTest(args=args), patch("ascart.camera_art.cv2.VideoCapture") as open_camera:
                code, output, errors = self.run_cli(*args)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            open_camera.assert_not_called()
        self.assertFalse(target.parent.exists())

    def test_existing_files_directories_and_links_are_preserved_before_capture(self):
        keep = self.root / "keep.txt"
        keep.write_text("user content")
        symbolic = self.root / "symbolic.html"
        symbolic.symlink_to(keep)
        hard = self.root / "hard.txt"
        hard.hardlink_to(keep)
        dangling = self.root / "dangling.png"
        dangling.symlink_to(self.root / "missing.png")
        for target in (keep, symbolic, hard, dangling, self.root):
            with self.subTest(target=target), patch("ascart.camera_art.cv2.VideoCapture") as open_camera:
                code, output, errors = self.run_cli("--camera", "--output", target)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            open_camera.assert_not_called()
        self.assertEqual(keep.read_text(), "user content")
        self.assertTrue(dangling.is_symlink())
        self.assertFalse(dangling.exists())

    def test_competing_creation_after_capture_does_not_overwrite_file(self):
        capture = fake_capture([(True, self.frame)])
        target = self.root / "race.html"
        original_open = Path.open

        def competing_open(path, mode="r", *args, **kwargs):
            if path == target:
                capture.release.assert_called_once()
                with original_open(path, "x") as file:
                    file.write("created by another program")
            return original_open(path, mode, *args, **kwargs)

        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), patch("ascart.cli.Path.open", new=competing_open):
            code, output, errors = self.run_cli("--camera", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("already exists", errors)
        self.assertEqual(target.read_text(), "created by another program")

    def test_capture_failure_or_interrupt_creates_no_output(self):
        for failure in (OSError("device failed"), cv2.error("driver failed"), KeyboardInterrupt(), (False, None)):
            with self.subTest(failure=type(failure).__name__):
                capture = fake_capture([failure])
                target = self.root / "not-created" / "snapshot.png"
                with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture):
                    code, output, errors = self.run_cli("--camera", "--output", target)
                self.assertEqual(code, 0 if isinstance(failure, KeyboardInterrupt) else 2)
                self.assertEqual(output, "")
                self.assertFalse(target.parent.exists())
                capture.release.assert_called_once()
                if isinstance(failure, KeyboardInterrupt):
                    self.assertIn("snapshot cancelled", errors)

    def test_rendering_and_permission_errors_create_no_success_or_preview(self):
        target = self.root / "not-created" / "snapshot.png"
        operations = (("ascart.cli.art_to_png", ValueError("too large")),
                      ("ascart.cli.Path.mkdir", PermissionError(errno.EACCES, "Permission denied")))
        for operation, failure in operations:
            capture = fake_capture([(True, self.frame)])
            with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), patch(operation, side_effect=failure):
                code, output, errors = self.run_cli("--camera", "--output", target)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertFalse(target.parent.exists())
            capture.release.assert_called_once()

    def test_partial_new_file_on_disk_failure_preserves_other_files(self):
        target = self.root / "partial.txt"
        keep = self.root / "keep.txt"
        keep.write_text("user data")
        original_open = Path.open

        @contextlib.contextmanager
        def failing_open(path, mode="r", *args, **kwargs):
            with original_open(path, mode, *args, **kwargs) as file:
                class Writer:
                    def write(self, data):
                        file.write(data[:3])
                        raise OSError(errno.ENOSPC, "No space left on device")
                yield Writer()

        capture = fake_capture([(True, self.frame)])
        with patch("ascart.camera_art.cv2.VideoCapture", return_value=capture), patch("ascart.cli.Path.open", new=failing_open):
            code, output, errors = self.run_cli("--camera", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("No space left", errors)
        self.assertEqual(len(target.read_text()), 3)
        self.assertEqual(keep.read_text(), "user data")
        capture.release.assert_called_once()
