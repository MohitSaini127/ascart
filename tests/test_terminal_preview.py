import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from ascart.cli import main
from ascart.terminal_preview import image_preview_backend, preview_comparison


class TerminalPreviewTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.photo = self.root / "source.png"
        with Image.new("RGB", (24, 16), "red") as image:
            image.save(self.photo)
        self.original = self.photo.read_bytes()

    def run_cli(self, *args, interactive=False):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, args)]), \
             patch.object(output, "isatty", return_value=interactive), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_redirected_input_or_output_never_probes_terminal(self):
        for stdin_tty, stdout_tty in ((False, False), (True, False), (False, True)):
            with self.subTest(stdin=stdin_tty, stdout=stdout_tty), \
                 patch("ascart.terminal_preview.sys.stdin.isatty", return_value=stdin_tty), \
                 patch("ascart.terminal_preview.sys.stdout.isatty", return_value=stdout_tty), \
                 patch("ascart.terminal_preview.shutil.which") as lookup, \
                 patch("ascart.terminal_preview.subprocess.run") as run:
                self.assertIsNone(image_preview_backend())
                lookup.assert_not_called()
                run.assert_not_called()

    def test_detects_modern_and_legacy_helpers_with_bounded_check(self):
        for helper, expected in (("kitten", ["/usr/bin/kitten", "icat"]), ("kitty", ["/usr/bin/kitty", "+kitten", "icat"])):
            with self.subTest(helper=helper), \
                 patch("ascart.terminal_preview.sys.stdin.isatty", return_value=True), \
                 patch("ascart.terminal_preview.sys.stdout.isatty", return_value=True), \
                 patch("ascart.terminal_preview.shutil.which", side_effect=lambda name: "/usr/bin/" + name if name == helper else None), \
                 patch("ascart.terminal_preview.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(image_preview_backend(), expected)
                args, kwargs = run.call_args
                self.assertEqual(args[0][:len(expected)], expected)
                self.assertIn("--detect-support", args[0])
                self.assertIn("--detection-timeout=1", args[0])
                self.assertEqual(kwargs["timeout"], 3)

    def test_missing_helper_is_unavailable(self):
        with patch("ascart.terminal_preview.sys.stdin.isatty", return_value=True), \
             patch("ascart.terminal_preview.sys.stdout.isatty", return_value=True), \
             patch("ascart.terminal_preview.shutil.which", return_value=None), \
             patch("ascart.terminal_preview.subprocess.run") as run:
            self.assertIsNone(image_preview_backend())
            run.assert_not_called()

    def test_probe_failure_or_timeout_is_unavailable(self):
        outcomes = [subprocess.CompletedProcess([], 1), FileNotFoundError("gone"), subprocess.TimeoutExpired("icat", 3)]
        for outcome in outcomes:
            with self.subTest(outcome=outcome), \
                 patch("ascart.terminal_preview.sys.stdin.isatty", return_value=True), \
                 patch("ascart.terminal_preview.sys.stdout.isatty", return_value=True), \
                 patch("ascart.terminal_preview.shutil.which", return_value="/usr/bin/kitten"), \
                 patch("ascart.terminal_preview.subprocess.run") as run:
                if isinstance(outcome, Exception):
                    run.side_effect = outcome
                else:
                    run.return_value = outcome
                self.assertIsNone(image_preview_backend())

    def test_preview_sends_real_comparison_png_without_creating_files(self):
        backend = ["/usr/bin/kitten", "icat"]
        with Image.open(self.photo) as image, patch("ascart.terminal_preview.subprocess.run") as run:
            preview_comparison(image, "@@\n@@", "dark", backend)
        args, kwargs = run.call_args
        self.assertEqual(args[0][:2], backend)
        self.assertIn("--stdin=yes", args[0])
        self.assertIn("--transfer-mode=stream", args[0])
        self.assertIn("--fit=both", args[0])
        self.assertEqual(kwargs["timeout"], 10)
        self.assertTrue(kwargs["check"])
        with Image.open(io.BytesIO(kwargs["input"])) as saved:
            self.assertEqual(saved.format, "PNG")
            self.assertEqual(saved.mode, "RGB")
            self.assertEqual(saved.size, (216, 100))
        self.assertEqual(list(self.root.iterdir()), [self.photo])
        self.assertEqual(self.photo.read_bytes(), self.original)

    def test_unsupported_preview_only_reports_export_hint_and_creates_nothing(self):
        with patch("ascart.cli.image_preview_backend", return_value=None), \
             patch("ascart.cli.preview_comparison") as preview:
            code, output, errors = self.run_cli(self.photo, "--compare")
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("Direct image preview is unavailable", errors)
        self.assertIn("--output comparison.png", errors)
        self.assertIn("--output comparison.html", errors)
        self.assertEqual(list(self.root.iterdir()), [self.photo])
        preview.assert_not_called()

    def test_supported_preview_only_calls_renderer_with_same_converted_art(self):
        code, art, errors = self.run_cli(self.photo, "--color", "--width=10", "--border")
        self.assertEqual(code, 0, errors)
        with patch("ascart.cli.image_preview_backend", return_value=["kitten", "icat"]), \
             patch("ascart.cli.preview_comparison") as preview:
            code, output, errors = self.run_cli(self.photo, "--compare", "--color", "--width=10", "--border")
        self.assertEqual(code, 0, errors)
        self.assertEqual(output, "")
        self.assertEqual(preview.call_args.args[1], art.removesuffix("\n"))
        self.assertEqual(list(self.root.iterdir()), [self.photo])

    def test_exports_are_complete_before_probe_and_preview(self):
        for suffix in ("png", "html"):
            target = self.root / ("saved." + suffix)

            def detect():
                self.assertTrue(target.is_file())
                if suffix == "png":
                    with Image.open(target) as image:
                        image.load()
                else:
                    self.assertIn("data:image/png;base64,", target.read_text())
                return ["kitten", "icat"]

            with patch("ascart.cli.image_preview_backend", side_effect=detect), \
                 patch("ascart.cli.preview_comparison") as preview:
                code, output, errors = self.run_cli(self.photo, "--compare", "--output", target)
            self.assertEqual(code, 0, errors)
            self.assertEqual(output, f"Saved ASCII art to {target}\n")
            preview.assert_called_once()

    def test_failed_unavailable_or_cancelled_preview_does_not_lose_export(self):
        failures = [None, OSError("display failed"), subprocess.TimeoutExpired("icat", 10),
                    subprocess.CalledProcessError(1, "icat"), KeyboardInterrupt()]
        for suffix in ("png", "html"):
            for index, failure in enumerate(failures):
                target = self.root / f"preserved-{index}.{suffix}"
                with self.subTest(suffix=suffix, failure=failure), \
                     patch("ascart.cli.image_preview_backend", return_value=None if failure is None else ["kitten", "icat"]), \
                     patch("ascart.cli.preview_comparison", side_effect=failure):
                    code, output, errors = self.run_cli(self.photo, "--compare", "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertIn("Saved ASCII art to", output)
                self.assertTrue(target.is_file())
                self.assertTrue(errors)
                if suffix == "png":
                    with Image.open(target) as image:
                        image.load()
                else:
                    self.assertIn("<figcaption>ASCII</figcaption>", target.read_text())
        self.assertEqual(self.photo.read_bytes(), self.original)

    def test_preview_only_failure_is_readable_and_cancellation_is_handled(self):
        for failure in (OSError("display failed"), subprocess.TimeoutExpired("icat", 10),
                        ValueError("Comparison would exceed 20 million pixels"), KeyboardInterrupt()):
            with self.subTest(failure=failure), \
                 patch("ascart.cli.image_preview_backend", return_value=["kitten", "icat"]), \
                 patch("ascart.cli.preview_comparison", side_effect=failure):
                code, output, errors = self.run_cli(self.photo, "--compare")
            self.assertEqual(code, 0 if isinstance(failure, KeyboardInterrupt) else 2)
            expected = ("cancelled" if isinstance(failure, KeyboardInterrupt) else
                        "20 million pixels" if isinstance(failure, ValueError) else "--output comparison.png")
            self.assertIn(expected, errors)
        self.assertEqual(list(self.root.iterdir()), [self.photo])

    def test_saving_failure_never_attempts_preview(self):
        target = self.root / "exists.png"
        target.write_bytes(b"user data")
        with patch("ascart.cli.image_preview_backend") as detect, patch("ascart.cli.preview_comparison") as preview:
            code, output, errors = self.run_cli(self.photo, "--compare", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(target.read_bytes(), b"user data")
        detect.assert_not_called()
        preview.assert_not_called()

    def test_unrelated_commands_do_not_probe_terminal(self):
        for args in (["--help"], ["--version"], ["-t", "Hi"], [self.photo]):
            with self.subTest(args=args), patch("ascart.cli.image_preview_backend") as detect:
                code, output, errors = self.run_cli(*args)
                self.assertEqual(code, 0, errors)
                detect.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "POSIX terminal-state protection")
    def test_terminal_settings_restore_after_probe_timeout(self):
        import pty
        import termios
        import tty

        master, slave = pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            fake_input = Mock()
            fake_input.isatty.return_value = True
            fake_input.fileno.return_value = slave

            def timeout(*args, **kwargs):
                tty.setraw(slave)
                raise subprocess.TimeoutExpired("icat", 3)

            with patch("ascart.terminal_preview.sys.stdin", fake_input), \
                 patch("ascart.terminal_preview.sys.stdout.isatty", return_value=True), \
                 patch("ascart.terminal_preview.shutil.which", return_value="/usr/bin/kitten"), \
                 patch("ascart.terminal_preview.subprocess.run", side_effect=timeout):
                self.assertIsNone(image_preview_backend())
            self.assertEqual(termios.tcgetattr(slave), original)
        finally:
            os.close(master)
            os.close(slave)
