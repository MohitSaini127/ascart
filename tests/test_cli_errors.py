import contextlib
import errno
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ascart.cli import main
from ascart.image_art import inspect_image
from ascart.text_art import text_to_ascii


class CliFileErrorTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.photo = self.root / "photo.png"
        Image.new("RGB", (20, 12), "blue").save(self.photo)
        self.gif = self.root / "animation.gif"
        Image.new("RGB", (20, 12), "red").save(self.gif)

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

    def assert_file_error(self, result, action, path):
        code, output, errors = result
        self.assertEqual(code, 2)
        self.assertIn(action, errors)
        self.assertIn(str(path), errors)
        self.assertNotIn("Traceback", errors)
        self.assertEqual(output, "")
        return errors

    def test_truncated_photo_preserves_existing_output(self):
        data = self.photo.read_bytes()
        truncated = data[:data.index(b"IDAT") + 6]
        self.photo.write_bytes(truncated)
        target = self.root / "keep.txt"
        target.write_text("previous artwork")
        errors = self.assert_file_error(
            self.run_cli(self.photo, "--output", target), "Cannot convert photo", self.photo
        )
        self.assertIn("truncated", errors)
        self.assertEqual(target.read_text(), "previous artwork")
        self.assertEqual(self.photo.read_bytes(), truncated)

    def test_truncated_gif_does_not_start_playback(self):
        self.gif.write_bytes(self.gif.read_bytes()[:-6])
        with patch("ascart.cli.play_gif") as play:
            errors = self.assert_file_error(
                self.run_cli(self.gif, terminal=True), "Cannot decode GIF", self.gif
            )
        self.assertIn("truncated", errors)
        play.assert_not_called()

    def test_unsupported_content_is_not_reported_as_video_option_error(self):
        source = self.root / "notes.txt"
        source.write_text("This is not an image or video.")
        target = self.root / "art.txt"
        with patch("ascart.cli.play_video") as play:
            errors = self.assert_file_error(
                self.run_cli(source, "--output", target), "Cannot decode input", source
            )
        self.assertIn("unsupported or damaged media", errors)
        self.assertNotIn("interactive terminal", errors)
        self.assertNotIn("Saving video", errors)
        self.assertFalse(target.exists())
        play.assert_not_called()

    def test_missing_file_and_directory_input(self):
        for source in (self.root / "missing.png", self.root):
            with self.subTest(source=source):
                self.assert_file_error(self.run_cli(source), "Cannot read input", source)

    def test_permission_denied_during_stat_or_open(self):
        for operation in ("ascart.cli.Path.stat", "ascart.cli.Image.open"):
            error = PermissionError(errno.EACCES, "Permission denied", str(self.photo))
            with self.subTest(operation=operation), patch(operation, side_effect=error):
                errors = self.assert_file_error(
                    self.run_cli(self.photo), "Cannot read input", self.photo
                )
            self.assertIn("Permission denied", errors)

    def test_file_disappearing_between_detection_and_conversion(self):
        error = FileNotFoundError(errno.ENOENT, "No such file or directory", str(self.photo))
        with patch("ascart.cli.inspect_image", side_effect=error):
            errors = self.assert_file_error(
                self.run_cli(self.photo), "Cannot convert photo", self.photo
            )
        self.assertIn("No such file", errors)

    def test_other_expected_decoder_errors(self):
        cases = (
            (self.photo, "ascart.cli.inspect_image", "Cannot convert photo"),
            (self.gif, "ascart.cli.gif_to_ascii", "Cannot decode GIF"),
        )
        for source, operation, action in cases:
            for error_type in (ValueError, EOFError, SyntaxError, Image.DecompressionBombError):
                with self.subTest(source=source, error=error_type.__name__), \
                     patch(operation, side_effect=error_type("invalid media data")):
                    self.assert_file_error(self.run_cli(source, terminal=True), action, source)

    def test_directory_as_output_for_photo_and_text(self):
        for inputs in ((self.photo,), ("--text", "Hi")):
            with self.subTest(inputs=inputs):
                errors = self.assert_file_error(
                    self.run_cli(*inputs, "--output", self.root), "Cannot save artwork to", self.root
                )
                self.assertIn("directory", errors.lower())

    def test_file_blocking_output_parent(self):
        blocker = self.root / "blocker"
        blocker.write_text("keep this file")
        target = blocker / "art.txt"
        self.assert_file_error(
            self.run_cli("--text", "Hi", "--output", target), "Cannot save artwork to", target
        )
        self.assertEqual(blocker.read_text(), "keep this file")

    def test_permission_and_disk_errors_during_saving(self):
        target = self.root / "keep.txt"
        target.write_text("previous artwork")
        cases = (
            ("ascart.cli.Path.mkdir", PermissionError(errno.EACCES, "Permission denied")),
            ("ascart.cli.Path.write_text", PermissionError(errno.EACCES, "Permission denied")),
            ("ascart.cli.Path.write_text", OSError(errno.ENOSPC, "No space left on device")),
        )
        for operation, error in cases:
            with self.subTest(operation=operation, error=error), patch(operation, side_effect=error):
                errors = self.assert_file_error(
                    self.run_cli("--text", "Hi", "--output", target), "Cannot save artwork to", target
                )
            self.assertIn(error.strerror, errors)
            self.assertEqual(target.read_text(), "previous artwork")

    def test_successful_photo_and_text_saving(self):
        cases = (
            ((self.photo, "--background", "dark", "--color"), inspect_image(self.photo, width=60)),
            (("--text-slant", "Hi"), text_to_ascii("Hi", font="slant")),
        )
        for index, (inputs, expected) in enumerate(cases):
            with self.subTest(inputs=inputs):
                target = self.root / f"nested-{index}" / "art.txt"
                for attempt in range(2):
                    code, output, errors = self.run_cli(*inputs, "--output", target)
                    self.assertEqual(code, 0, errors)
                    self.assertEqual(errors, "")
                    self.assertIn("Saved ASCII art to", output)
                    self.assertEqual(target.read_text(encoding="utf-8"), expected + "\n")
                    target.write_text("old artwork to replace")

    def test_successful_gif_playback_and_interrupt(self):
        with patch("ascart.gif_art.time.sleep"):
            code, output, errors = self.run_cli(self.gif, terminal=True)
        self.assertEqual(code, 0, errors)
        self.assertIn("\033[H\033[J", output)
        self.assertTrue(output.endswith("\033[0m\033[?25h\n"))
        with patch("ascart.cli.gif_to_ascii", side_effect=KeyboardInterrupt):
            self.assertEqual(self.run_cli(self.gif, terminal=True), (0, "", ""))

    def test_programming_errors_are_not_hidden(self):
        cases = (
            ((self.photo,), "ascart.cli.inspect_image"),
            ((self.gif,), "ascart.cli.gif_to_ascii"),
            (("--text", "Hi", "--output", self.root / "art.txt"), "ascart.cli.Path.write_text"),
        )
        for inputs, operation in cases:
            with self.subTest(operation=operation), patch(operation, side_effect=TypeError("test bug")):
                with self.assertRaisesRegex(TypeError, "test bug"):
                    self.run_cli(*inputs, terminal=True)


if __name__ == "__main__":
    unittest.main()
