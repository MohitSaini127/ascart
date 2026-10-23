import contextlib
import errno
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ascart.cli import main
from ascart.gif_art import save_ascii_gif


class GifOutputTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "source.gif"
        frames = [Image.new("RGB", (16, 12), color) for color in ("red", "blue", "yellow")]
        try:
            frames[0].save(
                self.source, save_all=True, append_images=frames[1:],
                duration=[40, 90, 120], loop=0, disposal=2,
            )
        finally:
            for frame in frames:
                frame.close()

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

    def assert_animation(self, path, size=None):
        with Image.open(path) as gif:
            self.assertEqual(gif.format, "GIF")
            self.assertEqual(gif.n_frames, 3)
            self.assertNotIn("loop", gif.info)
            if size is not None:
                self.assertEqual(gif.size, size)
            durations = []
            for index in range(gif.n_frames):
                gif.seek(index)
                durations.append(gif.info["duration"])
                gif.load()
            self.assertEqual(durations, [40, 90, 120])

    def test_noninteractive_color_border_background_and_uppercase_extension(self):
        original = self.source.read_bytes()
        for background in ("dark", "light"):
            target = self.root / background / "my art.GIF"
            code, output, errors = self.run_cli(
                self.source, "--color", "--border", "--width", "10", "--chars", "@",
                "--background", background, "--output", target,
            )
            self.assertEqual(code, 0, errors)
            self.assertEqual(output, f"Saved ASCII GIF to {target}\n")
            self.assert_animation(target, (168, 134))
            with Image.open(target) as gif:
                for index, color in enumerate(((255, 0, 0), (0, 0, 255), (255, 255, 0))):
                    gif.seek(index)
                    with gif.convert("RGB") as picture:
                        self.assertIn(color, picture.get_flattened_data())
                        neutral = (255, 255, 255) if background == "dark" else (0, 0, 0)
                        self.assertIn(neutral, picture.crop((12, 12, 156, 34)).get_flattened_data())
                        self.assertEqual(picture.getpixel((0, 0)), (0, 0, 0) if background == "dark" else (255, 255, 255))
        self.assertEqual(self.source.read_bytes(), original)

    def test_terminal_loop_counts_do_not_repeat_saved_frames(self):
        for options, count in (((), 1), (("--loop-4",), 4)):
            target = self.root / f"play-{count}.gif"
            with patch("ascart.gif_art.time.sleep") as sleep:
                code, output, errors = self.run_cli(
                    self.source, "--width", "10", "--color", "--border",
                    *options, "--output", target, terminal=True,
                )
            self.assertEqual(code, 0, errors)
            self.assert_animation(target)
            self.assertEqual(output.count("\033[H\033[J"), 3 * count)
            self.assertEqual(sleep.call_count, 3 * count)
            self.assertTrue(output.endswith(f"Saved ASCII GIF to {target}\n"))

    def test_continuous_preview_interrupt_keeps_completed_file_and_restores_cursor(self):
        target = self.root / "continuous.gif"

        def interrupt_preview(delay):
            self.assert_animation(target)
            raise KeyboardInterrupt

        with patch("ascart.gif_art.time.sleep", side_effect=interrupt_preview):
            code, output, errors = self.run_cli(
                self.source, "--loop", "--output", target, terminal=True,
            )
        self.assertEqual(code, 0, errors)
        self.assertIn("\033[?25h", output)
        self.assertTrue(output.endswith(f"Saved ASCII GIF to {target}\n"))
        self.assert_animation(target)

    def test_no_terminal_export_ignores_preview_loops(self):
        target = self.root / "no-terminal.gif"
        with patch("ascart.cli.play_gif") as play:
            code, output, errors = self.run_cli(self.source, "--loop", "--output", target)
        self.assertEqual(code, 0, errors)
        play.assert_not_called()
        self.assert_animation(target)
        self.assertIn("Saved ASCII GIF", output)

    def test_missing_and_zero_timing_gets_playback_fallback(self):
        source = self.root / "untimed.gif"
        with Image.new("RGB", (16, 12), "white") as image:
            image.save(source)
        target = self.root / "timed.gif"
        code, _, errors = self.run_cli(source, "--output", target)
        self.assertEqual(code, 0, errors)
        with Image.open(target) as gif:
            self.assertEqual(gif.n_frames, 1)
            self.assertEqual(gif.info["duration"], 100)
            self.assertNotIn("loop", gif.info)

    def test_identical_ascii_frames_merge_without_losing_duration(self):
        target = self.root / "merged.gif"
        save_ascii_gif([("@", 40), ("@", 90)], target)
        with Image.open(target) as gif:
            self.assertEqual(gif.n_frames, 1)
            self.assertEqual(gif.info["duration"], 130)
            self.assertNotIn("loop", gif.info)

    def test_merged_frame_timing_overflow_is_readable_and_preserves_other_files(self):
        source = self.root / "long.gif"
        # Different source frames can become identical ASCII art. Each source
        # delay is valid, but their merged ASCII delay exceeds the GIF limit.
        first = Image.new("RGB", (16, 12), (0, 0, 0))
        second = Image.new("RGB", (16, 12), (1, 1, 1))
        try:
            first.save(source, save_all=True, append_images=[second], duration=[400000, 400000], optimize=False)
        finally:
            first.close()
            second.close()
        before = source.read_bytes()
        keep = self.root / "keep.gif"
        keep.write_bytes(b"user artwork")
        target = self.root / "new.gif"
        with patch("ascart.cli.play_gif") as play:
            code, output, errors = self.run_cli(source, "--border", "--output", target, terminal=True)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("GIF frame timing exceeds 655.35 seconds", errors)
        self.assertNotIn("Traceback", errors)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(keep.read_bytes(), b"user artwork")
        play.assert_not_called()

    def test_fit_is_respected_in_saved_frames(self):
        target = self.root / "fitted.gif"
        with patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((20, 10))):
            code, _, errors = self.run_cli(self.source, "--fit", "--border", "--output", target)
        self.assertEqual(code, 0, errors)
        with Image.open(target) as gif:
            self.assertLessEqual(gif.width, 19 * 12 + 24)
            self.assertLessEqual(gif.height, 8 * 22 + 24)

    def test_wrong_output_formats_and_static_inputs_rejected_without_directories(self):
        photo = self.root / "photo.png"
        with Image.new("RGB", (16, 12), "white") as image:
            image.save(photo)
        cases = (
            ((self.source,), ".txt"), ((self.source,), ".png"),
            ((self.source,), ".mp4"), ((photo,), ".gif"), (("--text", "Hi"), ".gif"),
        )
        for arguments, suffix in cases:
            with self.subTest(arguments=arguments, suffix=suffix):
                target = self.root / "not-created" / ("art" + suffix)
                code, output, errors = self.run_cli(*arguments, "--output", target)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("output", errors)
                self.assertFalse(target.parent.exists())

    def test_existing_destinations_input_and_links_preserved(self):
        original = self.source.read_bytes()
        keep = self.root / "keep.gif"
        keep.write_bytes(b"user data")
        symbolic = self.root / "symbolic.gif"
        symbolic.symlink_to(self.source)
        hard = self.root / "hard.gif"
        hard.hardlink_to(self.source)
        dangling = self.root / "dangling.gif"
        missing = self.root / "missing.gif"
        dangling.symlink_to(missing)
        for target in (keep, self.source, symbolic, hard, dangling, self.root):
            with self.subTest(target=target), patch("ascart.cli.play_gif") as play:
                code, output, errors = self.run_cli(self.source, "--output", target, terminal=True)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("Cannot save artwork", errors)
                play.assert_not_called()
        self.assertEqual(keep.read_bytes(), b"user data")
        self.assertEqual(self.source.read_bytes(), original)
        self.assertTrue(dangling.is_symlink())
        self.assertFalse(missing.exists())

    def test_file_appearing_during_save_preserved(self):
        target = self.root / "race.gif"
        original_open = Path.open

        def competing_create(path, mode="r", *args, **kwargs):
            self.assertEqual(path, target)
            self.assertEqual(mode, "xb")
            with original_open(path, "xb") as file:
                file.write(b"created by another program")
            return original_open(path, mode, *args, **kwargs)

        with patch("ascart.gif_art.Path.open", new=competing_create), patch("ascart.cli.play_gif") as play:
            code, output, errors = self.run_cli(self.source, "--output", target, terminal=True)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("already exists", errors)
        self.assertEqual(target.read_bytes(), b"created by another program")
        play.assert_not_called()

    def test_truncated_input_and_rendering_errors_leave_no_destination(self):
        broken = self.root / "broken.gif"
        broken.write_bytes(self.source.read_bytes()[:-6])
        target = self.root / "not-created" / "art.gif"
        code, output, errors = self.run_cli(broken, "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("Cannot decode GIF", errors)
        self.assertFalse(target.parent.exists())
        with patch("ascart.gif_art.art_to_png", side_effect=ValueError("Picture too large")):
            code, output, errors = self.run_cli(self.source, "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("Picture too large", errors)
        self.assertFalse(target.parent.exists())

    def test_permission_and_partial_write_errors_do_not_start_preview(self):
        target = self.root / "new.gif"
        for operation in ("ascart.gif_art.Path.mkdir", "ascart.gif_art.Path.open"):
            with patch(operation, side_effect=PermissionError(errno.EACCES, "Permission denied")), \
                 patch("ascart.cli.play_gif") as play:
                code, output, errors = self.run_cli(self.source, "--output", target, terminal=True)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("Permission denied", errors)
            self.assertFalse(target.exists())
            play.assert_not_called()

        def fail_save(image, file, **kwargs):
            file.write(b"partial new GIF")
            raise OSError(errno.ENOSPC, "No space left on device")

        with patch("PIL.Image.Image.save", new=fail_save), patch("ascart.cli.play_gif") as play:
            code, output, errors = self.run_cli(self.source, "--output", target, terminal=True)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("No space left", errors)
        self.assertEqual(target.read_bytes(), b"partial new GIF")
        play.assert_not_called()

    def test_empty_and_mismatched_frames_rejected_before_creation(self):
        target = self.root / "not-created" / "art.gif"
        for frames in ([], [("@", 40), ("@@", 40)]):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                save_ascii_gif(frames, target)
            self.assertFalse(target.parent.exists())

    def test_gif_dimension_limit_rejected_before_destination_creation(self):
        target = self.root / "not-created" / "wide.gif"
        with self.assertRaisesRegex(ValueError, "GIF dimensions must not exceed 65535"):
            save_ascii_gif([("@" * 5460, 100)], target)
        self.assertFalse(target.parent.exists())

    def test_unexpected_programming_errors_are_not_hidden(self):
        with patch("ascart.cli.save_ascii_gif", side_effect=TypeError("test bug")):
            with self.assertRaisesRegex(TypeError, "test bug"):
                self.run_cli(self.source, "--output", self.root / "art.gif")
