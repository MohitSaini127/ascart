import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from ascart.cli import main
from ascart.video_comparison import video_comparison_frames
from ascart.terminal_preview import NATIVE_BACKEND, preview_animation_comparison


class VideoComparisonPreviewTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / "source.avi"
        writer = cv2.VideoWriter(str(self.source), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
        self.assertTrue(writer.isOpened())
        try:
            for color in ((0, 0, 255), (255, 0, 0)):
                writer.write(np.full((24, 32, 3), color, dtype=np.uint8))
        finally:
            writer.release()
        self.original = self.source.read_bytes()

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), \
             patch("sys.argv", ["ascart", str(self.source), "--compare", "--width", "8", *map(str, args)]):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        self.assertEqual(self.source.read_bytes(), self.original)
        return code, output.getvalue(), errors.getvalue()

    def test_preview_only_default_counted_and_continuous_options(self):
        for args, expected in (((), 1), (("--loop-4",), 4), (("--loop-count", "2"), 2), (("--loop",), 0)):
            with patch("ascart.cli.image_preview_backend", return_value=NATIVE_BACKEND), \
                 patch("ascart.cli.preview_animation_comparison") as preview:
                code, output, errors = self.run_cli(*args, "--color", "--border")
                self.assertEqual(code, 0, errors)
                factory, background, loops = preview.call_args.args
                self.assertEqual(loops, expected)
                with contextlib.closing(factory()) as frames:
                    source, art, duration = next(frames)
                    self.assertEqual(source.size, (32, 24))
                    self.assertIn("\033[38;2;", art)
                    self.assertIn("+", art)
                    self.assertEqual(duration, 100)
                self.assertNotIn("Saved", output)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_real_video_decodes_fresh_passes_and_streams_correct_panels(self):
        passes, colours = [], []
        def factory():
            passes.append(1)
            return video_comparison_frames(self.source, width=8, palette=" .@", background="dark",
                                           max_height=None, color=True, border=False)
        def transfer(buffer, metadata):
            buffer.seek(0)
            with Image.open(buffer) as image:
                colours.append(image.getpixel(((image.width - 24) // 4, 32 + (image.height - 32) // 2)))
            self.assertIn("a=T,f=100", metadata)
        with contextlib.redirect_stdout(io.StringIO()), \
             patch("ascart.terminal_preview._write_png_chunks", side_effect=transfer), \
             patch("ascart.terminal_preview.time.monotonic", return_value=0), \
             patch("ascart.terminal_preview.time.sleep") as sleep:
            preview_animation_comparison(factory, loops=2)
        self.assertEqual(len(passes), 2)
        self.assertEqual(len(colours), 4)
        for got, expected in zip(colours, ((255, 0, 0), (0, 0, 255)) * 2):
            self.assertTrue(all(abs(a - b) < 5 for a, b in zip(got, expected)), got)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [.1] * 4)

    def test_unavailable_or_helper_only_terminal_gives_mp4_hint_and_preserves_export(self):
        for index, backend in enumerate((None, ["kitten", "icat"])):
            with patch("ascart.cli.image_preview_backend", return_value=backend), \
                 patch("ascart.cli.preview_animation_comparison") as preview:
                code, output, errors = self.run_cli()
                self.assertEqual(code, 2)
                self.assertIn("--output comparison.mp4", errors)
                self.assertNotIn("comparison.gif", errors)
                destination = self.root / f"fallback-{index}.mp4"
                code, output, errors = self.run_cli("--output", destination, "--loop-4")
                self.assertEqual(code, 0, errors)
                self.assertTrue(destination.exists())
                self.assertIn("Saved ASCII video comparison", output)
                preview.assert_not_called()

    def test_save_precedes_preview_and_failure_or_cancellation_keeps_one_pass(self):
        for suffix in ("mp4", "html"):
            for index, failure in enumerate((None, OSError("terminal failed"), cv2.error("decoder failed"), KeyboardInterrupt())):
                destination = self.root / f"saved-{index}.{suffix}"
                def preview(factory, background, loops):
                    self.assertTrue(destination.exists())
                    self.assertEqual(loops, 4)
                    if failure is not None:
                        raise failure
                with patch("ascart.cli.image_preview_backend", return_value=NATIVE_BACKEND), \
                     patch("ascart.cli.preview_animation_comparison", side_effect=preview):
                    code, output, errors = self.run_cli("--output", destination, "--loop-4")
                self.assertEqual(code, 0, errors)
                self.assertIn("Saved ASCII video comparison", output)
                if suffix == "mp4":
                    capture = cv2.VideoCapture(str(destination))
                    try:
                        self.assertEqual(capture.get(cv2.CAP_PROP_FRAME_COUNT), 2)
                    finally:
                        capture.release()
                else:
                    self.assertEqual(destination.read_text().count("data:image/png;base64,"), 3)

    def test_preview_only_failure_and_interrupt_have_clear_outcomes(self):
        for failure, expected in ((ValueError("frame invalid"), 2), (cv2.error("decoder failed"), 2), (KeyboardInterrupt(), 0)):
            with patch("ascart.cli.image_preview_backend", return_value=NATIVE_BACKEND), \
                 patch("ascart.cli.preview_animation_comparison", side_effect=failure):
                code, output, errors = self.run_cli()
            self.assertEqual(code, expected)
            self.assertIn("comparison", errors.lower())
            self.assertNotIn("Saved", output)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_export_failure_skips_probe_and_preview_and_preserves_existing_file(self):
        destination = self.root / "existing.mp4"
        destination.write_bytes(b"keep")
        with patch("ascart.cli.image_preview_backend") as backend, patch("ascart.cli.preview_animation_comparison") as preview:
            code, output, errors = self.run_cli("--output", destination)
        self.assertEqual(code, 2)
        self.assertEqual(destination.read_bytes(), b"keep")
        backend.assert_not_called()
        preview.assert_not_called()
        self.assertNotIn("Saved", output)

    def test_fps_fallback_warning_precedes_preview_and_is_not_repeated_in_display_area(self):
        def preview(factory, background, loops):
            for _ in range(2):
                with contextlib.closing(factory()) as frames:
                    self.assertAlmostEqual(next(frames)[2], 1000 / 30)
        with patch("ascart.cli.inspect_video", return_value={"fps": None}), \
             patch("ascart.video_comparison.positive_property", return_value=None), \
             patch("ascart.cli.image_preview_backend", return_value=NATIVE_BACKEND), \
             patch("ascart.cli.preview_animation_comparison", side_effect=preview):
            code, output, errors = self.run_cli("--loop-count", "2")
        self.assertEqual(code, 0, errors)
        self.assertEqual(errors.count("using 30 FPS"), 1)
        self.assertNotIn("FPS", output)
