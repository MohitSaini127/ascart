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
        previous = self.root / "keep.txt"
        previous.write_text("previous artwork")
        target = self.root / "new.txt"
        errors = self.assert_file_error(
            self.run_cli(self.photo, "--output", target), "Cannot convert photo", self.photo
        )
        self.assertIn("truncated", errors)
        self.assertEqual(previous.read_text(), "previous artwork")
        self.assertFalse(target.exists())
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
        previous = self.root / "keep.txt"
        previous.write_text("previous artwork")
        target = self.root / "new.txt"
        cases = (
            ("ascart.cli.Path.mkdir", PermissionError(errno.EACCES, "Permission denied")),
            ("ascart.cli.Path.open", PermissionError(errno.EACCES, "Permission denied")),
            ("ascart.cli.Path.open", OSError(errno.ENOSPC, "No space left on device")),
        )
        for operation, error in cases:
            with self.subTest(operation=operation, error=error), patch(operation, side_effect=error), \
                 patch("ascart.cli.text_to_ascii", return_value="art"):
                errors = self.assert_file_error(
                    self.run_cli("--text", "Hi", "--output", target), "Cannot save artwork to", target
                )
            self.assertIn(error.strerror, errors)
            self.assertEqual(previous.read_text(), "previous artwork")
            self.assertFalse(target.exists())

    def test_successful_photo_and_text_saving(self):
        cases = (
            ((self.photo, "--background", "dark", "--color"), inspect_image(self.photo, width=60)),
            (("--text-slant", "Hi"), text_to_ascii("Hi", font="slant")),
        )
        for index, (inputs, expected) in enumerate(cases):
            with self.subTest(inputs=inputs):
                target = self.root / f"nested-{index}" / "art.txt"
                code, output, errors = self.run_cli(*inputs, "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertEqual(errors, "")
                self.assertIn("Saved ASCII art to", output)
                self.assertEqual(output, expected + "\n" + f"Saved ASCII art to {target}\n")
                self.assertEqual(target.read_text(encoding="utf-8"), expected + "\n")
                before = target.read_bytes()
                errors = self.assert_file_error(
                    self.run_cli(*inputs, "--output", target), "Cannot save artwork to", target
                )
                self.assertIn("already exists", errors)
                self.assertEqual(target.read_bytes(), before)

    def test_empty_output_and_unsupported_extensions(self):
        for inputs in ((self.photo,), ("--text", "Hi")):
            for value in ("", "   ", "\t"):
                with self.subTest(inputs=inputs, value=value):
                    code, output, errors = self.run_cli(*inputs, "--output", value)
                    self.assertEqual(code, 2)
                    self.assertEqual(output, "")
                    self.assertIn("--output must not be empty", errors)
            for suffix in ("gif", "mp4", "jpg", "html", ""):
                target = self.root / "not-created" / (f"art.{suffix}" if suffix else "art")
                with self.subTest(inputs=inputs, suffix=suffix):
                    code, output, errors = self.run_cli(*inputs, "--output", target)
                    self.assertEqual(code, 2)
                    self.assertEqual(output, "")
                    self.assertIn("only .txt", errors)
                    self.assertFalse(target.parent.exists())

    def test_missing_output_value_and_terminal_default(self):
        for inputs in ((self.photo,), ("--text", "Hi")):
            with self.subTest(inputs=inputs):
                code, output, errors = self.run_cli(*inputs, "--output")
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("expected one argument", errors)
                code, output, errors = self.run_cli(*inputs)
                self.assertEqual(code, 0, errors)
                self.assertTrue(output.strip())
                self.assertNotIn("Saved ASCII art", output)

    def test_output_cannot_be_input_or_its_alias(self):
        before = self.photo.read_bytes()
        symlink = self.root / "symbolic.txt"
        symlink.symlink_to(self.photo)
        hardlink = self.root / "hard.txt"
        hardlink.hardlink_to(self.photo)
        targets = (self.photo, self.root / ".." / self.root.name / "photo.png", symlink, hardlink)
        for target in targets:
            with self.subTest(target=target):
                errors = self.assert_file_error(
                    self.run_cli(self.photo, "--output", target), "Cannot save artwork to", target
                )
                self.assertIn("input file", errors)
                self.assertEqual(self.photo.read_bytes(), before)
                self.assertEqual(target.read_bytes(), before)

    def test_existing_destination_links_are_preserved(self):
        other = self.root / "other.txt"
        other.write_text("keep other data")
        link = self.root / "link.txt"
        link.symlink_to(other)
        dangling = self.root / "dangling.txt"
        missing = self.root / "missing.txt"
        dangling.symlink_to(missing)
        for target in (link, dangling):
            with self.subTest(target=target):
                errors = self.assert_file_error(
                    self.run_cli("--text", "Hi", "--output", target), "Cannot save artwork to", target
                )
                self.assertIn("already exists", errors)
                self.assertTrue(target.is_symlink())
        self.assertEqual(other.read_text(), "keep other data")
        self.assertFalse(missing.exists())

    def test_file_created_after_validation_is_preserved(self):
        target = self.root / "race.txt"
        original_open = Path.open

        def competing_create(path, mode="r", *args, **kwargs):
            self.assertEqual(path, target)
            self.assertEqual(mode, "x")
            with original_open(path, "x", encoding="utf-8") as file:
                file.write("created by another process")
            return original_open(path, mode, *args, **kwargs)

        with patch("ascart.cli.Path.open", new=competing_create), \
             patch("ascart.cli.text_to_ascii", return_value="art"):
            errors = self.assert_file_error(
                self.run_cli("--text", "Hi", "--output", target), "Cannot save artwork to", target
            )
        self.assertIn("already exists", errors)
        self.assertEqual(target.read_text(), "created by another process")

    def test_spaces_and_uppercase_txt_extension(self):
        target = self.root / "new folder" / "my art.TXT"
        code, output, errors = self.run_cli("--text", "Hi", "--output", target)
        self.assertEqual(code, 0, errors)
        self.assertIn("Saved ASCII art", output)
        self.assertEqual(target.read_text(), text_to_ascii("Hi") + "\n")

    def test_failure_during_write_only_leaves_new_partial_file(self):
        target = self.root / "partial.txt"
        previous = self.root / "keep.txt"
        previous.write_text("previous artwork")
        original_open = Path.open
        art = text_to_ascii("Hi")

        @contextlib.contextmanager
        def failing_open(path, mode="r", *args, **kwargs):
            with original_open(path, mode, *args, **kwargs) as file:
                class Writer:
                    def write(self, content):
                        file.write(content[:3])
                        raise OSError(errno.ENOSPC, "No space left on device")
                yield Writer()

        with patch("ascart.cli.Path.open", new=failing_open), \
             patch("ascart.cli.text_to_ascii", return_value=art):
            errors = self.assert_file_error(
                self.run_cli("--text", "Hi", "--output", target), "Cannot save artwork to", target
            )
        self.assertIn("No space left", errors)
        self.assertEqual(target.read_text(), art[:3])
        self.assertEqual(previous.read_text(), "previous artwork")

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
            (("--text", "Hi", "--output", self.root / "art.txt"), "ascart.cli.Path.open"),
        )
        for inputs, operation in cases:
            with self.subTest(operation=operation), patch(operation, side_effect=TypeError("test bug")), \
                 patch("ascart.cli.text_to_ascii", return_value="art"):
                with self.assertRaisesRegex(TypeError, "test bug"):
                    self.run_cli(*inputs, terminal=True)


if __name__ == "__main__":
    unittest.main()
