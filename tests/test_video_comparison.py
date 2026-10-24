import base64
import contextlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image

from ascart.cli import main
from ascart.video_comparison import video_comparison_frames, save_comparison_video
from ascart.gif_comparison import save_comparison_html
from ascart.html_art import art_to_markup


class VideoComparisonTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / "source.avi"
        writer = cv2.VideoWriter(str(self.source), cv2.VideoWriter_fourcc(*"MJPG"), 12.5, (32, 24))
        self.assertTrue(writer.isOpened())
        try:
            for color in ((0, 0, 255), (255, 0, 0), (0, 255, 0)):
                writer.write(np.full((24, 32, 3), color, dtype=np.uint8))
        finally:
            writer.release()
        self.original = self.source.read_bytes()

    def frames(self, **overrides):
        options = dict(width=8, palette=" .@", background="dark", max_height=None, color=True, border=False)
        options.update(overrides)
        return video_comparison_frames(self.source, **options)

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), \
             patch("sys.argv", ["ascart", str(self.source), "--compare", *map(str, args)]), \
             patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((16, 10))):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        self.assertEqual(self.source.read_bytes(), self.original)
        return code, output.getvalue(), errors.getvalue()

    def read_html(self, path):
        document = path.read_text()
        return json.loads(re.search(r'<script id="frames" type="application/json">(.*?)</script>', document, re.S)[1]), document

    def test_export_visual_options_colours_frame_count_and_fps(self):
        for index, (suffix, color, border, background, fit) in enumerate(itertools.product(
            ("mp4", "html"), (False, True), (False, True), ("dark", "light"), (False, True),
        )):
            with self.subTest(suffix=suffix, color=color, border=border, background=background, fit=fit):
                destination = self.root / f"comparison-{index}.{suffix.upper()}"
                args = ["--output", destination, "--chars", " .<&@", "--background", background]
                args += ["--fit"] if fit else ["--width", "8"]
                args += ["--color"] if color else []
                args += ["--border"] if border else []
                code, output, errors = self.run_cli(*args)
                self.assertEqual(code, 0, errors)
                self.assertIn("Saved ASCII video comparison", output)
                self.assertIn("preview is unavailable", errors)
                expected = self.frames(width=(13 if border else 15) if fit else 8,
                                       max_height=(6 if border else 8) if fit else None,
                                       palette=" .<&@", color=color, border=border, background=background)
                if suffix == "html":
                    frames, document = self.read_html(destination)
                    self.assertEqual(len(frames), 3)
                    self.assertNotIn('id="loop"', document)
                    self.assertNotIn(str(self.source), document)
                    with contextlib.closing(expected):
                        for saved, (original, art, duration) in zip(frames, expected):
                            self.assertEqual(saved[0], art_to_markup(art))
                            self.assertEqual(saved[1], duration)
                            with Image.open(io.BytesIO(base64.b64decode(saved[2].split(",", 1)[1]))) as picture:
                                self.assertEqual(picture.getpixel((picture.width // 2, picture.height // 2)), original.getpixel((16, 12)))
                else:
                    expected.close()
                    capture = cv2.VideoCapture(str(destination))
                    try:
                        self.assertTrue(capture.isOpened())
                        self.assertAlmostEqual(capture.get(cv2.CAP_PROP_FPS), 12.5, places=2)
                        for wanted in ((0, 0, 255), (255, 0, 0), (0, 255, 0)):
                            success, pixels = capture.read()
                            self.assertTrue(success)
                            height, width = pixels.shape[:2]
                            center = pixels[32 + (height - 32) // 2, (width - 24) // 4]
                            self.assertTrue(np.all(np.abs(center.astype(int) - wanted) < 15), center)
                        self.assertFalse(capture.read()[0])
                    finally:
                        capture.release()
        self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_output_and_loop_validation_preserves_existing_data(self):
        existing = self.root / "existing.mp4"
        existing.write_bytes(b"preserve")
        link = self.root / "link.html"
        link.symlink_to(existing)
        for args in ([], ["--output", existing], ["--output", link], ["--output", self.source],
                     ["--output", self.root / "new.gif"], ["--output", self.root / "new.png"],
                     ["--output", self.root / "new.mp4", "--loop-count", "0"]):
            with self.subTest(args=args), patch("ascart.cli.play_video") as play:
                code, output, errors = self.run_cli(*args)
                self.assertEqual(code, 2, errors)
                self.assertNotIn("Saved", output)
                play.assert_not_called()
        self.assertEqual(existing.read_bytes(), b"preserve")
        self.assertFalse((self.root / "new.mp4").exists())

    def test_encoder_or_verification_failure_does_not_publish_and_cleans_temporary_files(self):
        destination = self.root / "new" / "comparison.mp4"
        writer = Mock()
        writer.isOpened.return_value = False
        with patch("ascart.video_comparison.cv2.VideoWriter", return_value=writer):
            with self.assertRaisesRegex(ValueError, "encoding is unavailable"):
                save_comparison_video(self.frames(), destination)
        writer.release.assert_called_once()
        self.assertFalse(destination.exists())
        self.assertFalse(list(destination.parent.glob(".ascart-*")))
        with patch("ascart.video_comparison.verify_video", side_effect=ValueError("Incomplete MP4")):
            with self.assertRaisesRegex(ValueError, "Incomplete MP4"):
                save_comparison_video(self.frames(), destination)
        self.assertFalse(destination.exists())
        self.assertFalse(list(destination.parent.glob(".ascart-*")))

    def test_destination_race_is_protected(self):
        destination = self.root / "race.mp4"
        destination.write_bytes(b"another program")
        with self.assertRaises(FileExistsError):
            save_comparison_video(self.frames(), destination)
        self.assertEqual(destination.read_bytes(), b"another program")
        self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_capture_cleanup_for_missing_frames_failure_interrupt_and_fps_fallback(self):
        pixels = np.full((24, 32, 3), (0, 0, 255), dtype=np.uint8)
        for failure in (None, OSError("decode failed"), KeyboardInterrupt()):
            capture = Mock()
            capture.get.return_value = float("nan")
            capture.read.side_effect = [(True, pixels), (False, None) if failure is None else failure]
            with patch("ascart.video_comparison.open_video", return_value=capture), contextlib.redirect_stderr(io.StringIO()) as errors:
                with contextlib.closing(self.frames()) as frames:
                    first = next(frames)
                    self.assertAlmostEqual(first[2], 1000 / 30)
                    if failure is None:
                        self.assertIsNone(next(frames, None))
                    else:
                        with self.assertRaises(type(failure)):
                            next(frames)
            capture.release.assert_called_once()
            self.assertIn("using 30 FPS", errors.getvalue())
        capture = Mock()
        capture.get.return_value = 10
        capture.read.return_value = (False, None)
        with patch("ascart.video_comparison.open_video", return_value=capture):
            with self.assertRaisesRegex(ValueError, "no frame"):
                save_comparison_video(self.frames(), self.root / "empty.mp4")
        capture.release.assert_called_once()
        self.assertFalse((self.root / "empty.mp4").exists())

    def test_layout_and_html_limits_precede_destination_creation(self):
        for suffix in ("mp4", "html"):
            destination = self.root / "not-created" / ("comparison." + suffix)
            with patch("ascart.comparison.MAX_COMPARISON_PIXELS", 1), contextlib.closing(self.frames()) as frames:
                with self.assertRaisesRegex(ValueError, "20 million"):
                    if suffix == "mp4":
                        save_comparison_video(frames, destination)
                    else:
                        save_comparison_html(frames, destination, loop_control=False)
            self.assertFalse(destination.parent.exists())
        destination = self.root / "not-created" / "comparison.html"
        with patch("ascart.gif_comparison.MAX_ANIMATION_BYTES", 1):
            code, output, errors = self.run_cli("--output", destination)
        self.assertEqual(code, 2)
        self.assertIn("20 MiB", errors)
        self.assertNotIn("Saved", output)
        self.assertFalse(destination.parent.exists())

    def test_interruption_or_changed_layout_closes_frames_and_removes_private_output(self):
        for fail in (KeyboardInterrupt(), None):
            closed = []
            def frames():
                try:
                    with Image.new("RGB", (32, 24), "red") as source:
                        yield source, "@@", 80
                        if fail is not None:
                            raise fail
                        yield source, "@@\n@@", 80
                finally:
                    closed.append(True)
            destination = self.root / "interrupted.mp4"
            with self.assertRaises(KeyboardInterrupt if fail is not None else ValueError):
                save_comparison_video(frames(), destination)
            self.assertEqual(closed, [True])
            self.assertFalse(destination.exists())
            self.assertFalse(list(self.root.glob(".ascart-*")))

    def test_html_rejects_timing_beyond_browser_limit(self):
        capture = Mock()
        capture.get.return_value = 1e-9
        capture.read.return_value = (True, np.zeros((24, 32, 3), dtype=np.uint8))
        destination = self.root / "invalid-timing.html"
        with patch("ascart.video_comparison.open_video", return_value=capture), contextlib.closing(self.frames()) as frames:
            with self.assertRaisesRegex(ValueError, "browser timer limit"):
                save_comparison_html(frames, destination, loop_control=False)
        capture.release.assert_called_once()
        self.assertFalse(destination.exists())
