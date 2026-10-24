import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

from ascart.cli import main
from ascart.text_art import text_to_ascii


class CliVersionTests(unittest.TestCase):
    def run_cli(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, arguments)]), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_version_matches_installed_package_and_needs_no_input(self):
        for option in ("--version", "-V"):
            with self.subTest(option=option):
                self.assertEqual(self.run_cli(option), (0, f"ascart {version('ascart')}\n", ""))

    def test_version_does_not_open_media_or_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            keep = root / "keep.txt"
            keep.write_text("user artwork")
            for option in ("--version", "-V"):
                for target in (keep, root / "not-created" / "art.png"):
                    with self.subTest(option=option, target=target), patch("ascart.cli.Image.open") as image_open:
                        result = self.run_cli("missing.png", "--output", target, option)
                        self.assertEqual(result, (0, f"ascart {version('ascart')}\n", ""))
                        image_open.assert_not_called()
            self.assertEqual(keep.read_text(), "user artwork")
            self.assertFalse((root / "not-created").exists())

    def test_help_lists_version_and_literal_text_still_renders(self):
        code, output, errors = self.run_cli("--help")
        self.assertEqual(code, 0, errors)
        self.assertRegex(output, r"-V,\s*--version")
        for option in ("--text", "-t"):
            for text in ("--version", "-V"):
                self.assertEqual(self.run_cli(f"{option}={text}", "--width=120"), (0, text_to_ascii(text, width=120) + "\n", ""))
        code, output, errors = self.run_cli("-v")
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("unrecognized arguments: -v", errors)

    def test_module_entry_point_reports_version(self):
        for option in ("--version", "-V"):
            with self.subTest(option=option):
                result = subprocess.run([sys.executable, "-B", "-m", "ascart", option], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f"ascart {version('ascart')}\n")
                self.assertEqual(result.stderr, "")
