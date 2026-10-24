import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from ascart.cli import main
from ascart.gif_comparison import comparison_frames
from ascart.terminal_preview import NATIVE_BACKEND, preview_gif_comparison


class GifComparisonPreviewTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / "animation.gif"
        with Image.new("RGB", (16, 12), "red") as first, Image.new("RGB", (16, 12), "blue") as second:
            first.save(self.source, save_all=True, append_images=[second], duration=[40, 90], loop=0)
        self.original = self.source.read_bytes()

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), patch("sys.argv", ["ascart", str(self.source), "--compare", *map(str, args)]):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        self.assertEqual(self.source.read_bytes(), self.original)
        return code, output.getvalue(), errors.getvalue()

    def frames(self):
        return comparison_frames(self.source, width=8, palette=" .@", background="dark",
                                 max_height=None, color=True, border=False)

    def test_native_stream_reuses_area_releases_previous_images_and_times_frames(self):
        output = io.StringIO()
        passes = []
        def factory():
            passes.append(1)
            return self.frames()
        with contextlib.redirect_stdout(output), \
             patch("ascart.terminal_preview.shutil.get_terminal_size", return_value=os.terminal_size((80, 24))), \
             patch("ascart.terminal_preview.secrets.randbits", return_value=123), \
             patch("ascart.terminal_preview.time.monotonic", return_value=0), \
             patch("ascart.terminal_preview.time.sleep") as sleep:
            preview_gif_comparison(factory, loops=2)
        stream = output.getvalue()
        self.assertEqual(len(passes), 2)
        self.assertEqual(stream.count("a=T,f=100,I=123,c=79,C=1"), 2)
        self.assertEqual(stream.count("a=T,f=100,I=124,c=79,C=1"), 2)
        self.assertEqual(stream.count("a=d,d=N,I="), 3)
        self.assertNotIn("d=A", stream)
        self.assertNotIn("\033[2J", stream)
        self.assertEqual(stream.count("\n"), 22)
        self.assertTrue(stream.endswith("\033[?25h\033[21B\r\n"))
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [.04, .09, .04, .09])
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_interrupt_or_decode_error_restores_cursor_and_closes_reader(self):
        for failure in (KeyboardInterrupt(), OSError("decode failed")):
            closed = []
            def frames():
                try:
                    with Image.new("RGB", (16, 12), "red") as source:
                        yield source, "@@", 40
                        raise failure
                finally:
                    closed.append(True)
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch("ascart.terminal_preview.time.sleep"):
                with self.assertRaises(type(failure)):
                    preview_gif_comparison(frames)
            self.assertEqual(closed, [True])
            self.assertIn("\033[?25h", output.getvalue())

    def test_preview_only_default_counted_and_infinite_loops(self):
        for args, expected in (((), 1), (("--loop-4",), 4), (("--loop-count", "2"), 2), (("--loop",), 0)):
            with patch("ascart.cli.image_preview_backend", return_value=NATIVE_BACKEND), \
                 patch("ascart.cli.preview_gif_comparison") as preview:
                code, output, errors = self.run_cli(*args)
            self.assertEqual(code, 0, errors)
            self.assertEqual(preview.call_args.args[2], expected)
            self.assertNotIn("Saved", output)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_save_is_one_pass_and_survives_preview_failure_or_interrupt(self):
        for suffix in ("gif", "html"):
            for index, failure in enumerate((None, OSError("broken terminal"), KeyboardInterrupt())):
                destination = self.root / f"saved-{index}.{suffix}"
                def preview(factory, background, loops):
                    self.assertTrue(destination.exists())
                    self.assertEqual(loops, 4)
                    if failure is not None:
                        raise failure
                with patch("ascart.cli.image_preview_backend", return_value=NATIVE_BACKEND), \
                     patch("ascart.cli.preview_gif_comparison", side_effect=preview):
                    code, output, errors = self.run_cli("--output", destination, "--loop-4", "--width", "8")
                self.assertEqual(code, 0, errors)
                self.assertIn("Saved ASCII GIF comparison", output)
                if suffix == "gif":
                    with Image.open(destination) as saved:
                        self.assertEqual(saved.n_frames, 2)
                        self.assertNotIn("loop", saved.info)
                else:
                    self.assertEqual(destination.read_text().count('data:image/png;base64,'), 3)

    def test_unsupported_native_or_helper_only_preview_has_format_specific_hint(self):
        for backend in (None, ["kitten", "icat"]):
            with patch("ascart.cli.image_preview_backend", return_value=backend), \
                 patch("ascart.cli.preview_gif_comparison") as preview:
                code, output, errors = self.run_cli()
                self.assertEqual(code, 2)
                self.assertIn("--output comparison.gif", errors)
                self.assertNotIn("comparison.png", errors)
                destination = self.root / f"fallback-{bool(backend)}.gif"
                code, output, errors = self.run_cli("--output", destination, "--width", "8")
                self.assertEqual(code, 0, errors)
                self.assertTrue(destination.exists())
                preview.assert_not_called()

    def test_export_failure_prevents_preview_and_existing_file_is_preserved(self):
        destination = self.root / "existing.gif"
        destination.write_bytes(b"keep")
        with patch("ascart.cli.image_preview_backend") as backend:
            code, output, errors = self.run_cli("--output", destination)
        self.assertEqual(code, 2)
        self.assertEqual(destination.read_bytes(), b"keep")
        self.assertNotIn("Saved", output)
        backend.assert_not_called()

    def test_infinite_playback_stops_on_interrupt_without_buffering_passes(self):
        passes = []
        def factory():
            passes.append(1)
            if len(passes) == 3:
                raise KeyboardInterrupt
            return self.frames()
        with contextlib.redirect_stdout(io.StringIO()), patch("ascart.terminal_preview.time.sleep"):
            with self.assertRaises(KeyboardInterrupt):
                preview_gif_comparison(factory, loops=0)
        self.assertEqual(len(passes), 3)

    def test_interrupted_transfer_preserves_previous_complete_picture(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), \
             patch("ascart.terminal_preview.secrets.randbits", return_value=123), \
             patch("ascart.terminal_preview.time.sleep"), \
             patch("ascart.terminal_preview._write_png_chunks", side_effect=[None, KeyboardInterrupt()]):
            with self.assertRaises(KeyboardInterrupt):
                preview_gif_comparison(self.frames)
        self.assertIn("a=d,d=N,I=124,q=2", output.getvalue())
        self.assertNotIn("a=d,d=N,I=123,q=2", output.getvalue())
        self.assertIn("\033[?25h", output.getvalue())
