import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from ascart.cli import main
from ascart.image_art import inspect_image
from ascart.text_art import text_to_ascii


class MediaCliTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.video = self.root / "clip.mp4"
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 24))
        self.assertTrue(writer.isOpened(), "Test machine needs MP4 encoding")
        try:
            writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
        finally:
            writer.release()
        self.photo = self.root / "photo.png"
        Image.new("RGB", (32, 24), "blue").save(self.photo)
        self.gif = self.root / "sample.gif"
        Image.new("RGB", (32, 24), "red").save(self.gif)

    def run_cli(self, *arguments, terminal=True):
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

    def test_video_options_and_interrupt(self):
        with patch("ascart.cli.play_video") as play:
            self.assertEqual(self.run_cli(self.video, "--width", "20", "--color")[0], 0)
            self.assertEqual(play.call_args.kwargs["width"], 20)
            self.assertTrue(play.call_args.kwargs["color"])
            self.assertEqual(play.call_args.kwargs["palette"], "#%@")
        with patch("ascart.cli.play_video", side_effect=KeyboardInterrupt):
            self.assertEqual(self.run_cli(self.video)[0], 0)
        with patch("ascart.cli.Image.open") as image_open, patch("ascart.cli.play_video") as play:
            image_open.return_value.__enter__.return_value.format = "MPEG"
            self.assertEqual(self.run_cli(self.video)[0], 0)
            play.assert_called_once()

    def test_actual_video_playback(self):
        with patch("ascart.video_art.time.sleep"):
            code, output, errors = self.run_cli(self.video, "--width", "20")
        self.assertEqual(code, 0, errors)
        self.assertIn("\033[H\033[J", output)
        self.assertTrue(output.endswith("\033[0m\033[?25h\n"))

    def test_rejected_video_options(self):
        for options in (("--output", str(self.root / "art.txt")), ("--loop",), ("--loop-4",)):
            with patch("ascart.cli.play_video") as play:
                self.assertEqual(self.run_cli(self.video, *options)[0], 2)
                play.assert_not_called()
        self.assertEqual(self.run_cli(self.video, terminal=False)[0], 2)
        self.assertFalse((self.root / "art.txt").exists())

    def test_missing_and_unsupported_files(self):
        self.assertEqual(self.run_cli(self.root / "missing.mp4")[0], 2)
        self.assertEqual(self.run_cli(self.root)[0], 2)
        self.assertEqual(self.run_cli(self.photo, "--text", "Hi")[0], 2)
        with patch("ascart.cli.play_video", side_effect=ValueError("unsupported codec")):
            code, _, errors = self.run_cli(self.video)
        self.assertEqual(code, 2)
        self.assertIn("unsupported codec", errors)
        self.assertNotIn("Traceback", errors)

    def test_photo_text_and_gif_regressions(self):
        code, art, _ = self.run_cli(self.photo, "--background", "dark", terminal=False)
        self.assertEqual(code, 0)
        self.assertEqual(art, inspect_image(self.photo, width=60) + "\n")
        target = self.root / "nested" / "banner.txt"
        self.assertEqual(self.run_cli("--text-slant", "Hi", "--output", target)[0], 0)
        self.assertEqual(target.read_text(), text_to_ascii("Hi", font="slant") + "\n")
        with patch("ascart.cli.play_gif") as play:
            self.assertEqual(self.run_cli(self.gif, "--loop-4")[0], 0)
            self.assertEqual(play.call_args.kwargs["loops"], 4)


if __name__ == "__main__":
    unittest.main()
