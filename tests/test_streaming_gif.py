import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import GifImagePlugin, Image

from ascart.gif_art import save_streaming_ascii_gif


class StreamingGifTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.target = Path(folder.name) / "stream.gif"

    def test_palettes_repeated_frames_and_delays_survive_readback(self):
        colors = ("red", "blue", "blue", "green")
        durations = (60, 70, 70, 60)
        with patch("ascart.gif_art.art_to_png", side_effect=lambda color, *args, **kwargs: Image.new("RGB", (20, 20), color)):
            save_streaming_ascii_gif(zip(colors, durations), self.target)
        with Image.open(self.target) as saved:
            self.assertEqual(saved.n_frames, 4)
            self.assertEqual(saved.info["version"], b"GIF89a")
            self.assertNotIn("loop", saved.info)
            for index, (color, delay) in enumerate(zip(colors, durations)):
                saved.seek(index)
                with saved.convert("RGB") as picture, Image.new("RGB", (1, 1), color) as expected:
                    self.assertEqual(picture.getpixel((10, 10)), expected.getpixel((0, 0)))
                self.assertEqual(saved.info["duration"], delay)
        self.assertTrue(self.target.read_bytes().endswith(b";"))

    def test_closes_each_picture_before_requesting_another_frame(self):
        pictures = []

        def render(*args, **kwargs):
            picture = Image.new("RGB", (20, 20), "red")
            pictures.append(picture)
            return picture

        def frames():
            for index in range(5):
                if index:
                    with self.assertRaises(ValueError):
                        pictures[-1].getpixel((0, 0))
                    self.assertTrue(self.target.exists())
                    self.assertEqual(encode.call_count, index)
                yield str(index), 60

        with patch("ascart.gif_art.art_to_png", side_effect=render), \
             patch("ascart.gif_art.GifImagePlugin.getdata", wraps=GifImagePlugin.getdata) as encode:
            save_streaming_ascii_gif(frames(), self.target)
        with self.assertRaises(ValueError):
            pictures[-1].getpixel((0, 0))

    def test_repeated_frames_reuse_two_delay_variants_and_report_every_slot(self):
        frames = [("@", 60), ("@", 70)] * 20
        progress = []
        with patch("ascart.gif_art.art_to_png", side_effect=lambda *args, **kwargs: Image.new("RGB", (20, 20), "red")) as render, \
             patch("ascart.gif_art.GifImagePlugin.getdata", wraps=GifImagePlugin.getdata) as encode:
            save_streaming_ascii_gif(frames, self.target, progress=progress.append)
        self.assertEqual(render.call_count, 2)
        self.assertEqual(encode.call_count, 2)
        self.assertEqual(progress, list(range(1, 41)))
        with Image.open(self.target) as saved:
            self.assertEqual(saved.n_frames, 40)
            for index, (_, delay) in enumerate(frames):
                saved.seek(index)
                self.assertEqual(saved.info["duration"], delay)

    def test_cache_is_discarded_when_artwork_changes(self):
        colors = ["red", "blue", "red"]
        with patch("ascart.gif_art.art_to_png", side_effect=lambda color, *args, **kwargs: Image.new("RGB", (20, 20), color)) as render:
            save_streaming_ascii_gif([(color, 60) for color in colors], self.target)
        self.assertEqual(render.call_count, 3)
        with Image.open(self.target) as saved:
            for index, expected in enumerate(((255, 0, 0), (0, 0, 255), (255, 0, 0))):
                saved.seek(index)
                with saved.convert("RGB") as picture:
                    self.assertEqual(picture.getpixel((0, 0)), expected)

    def test_empty_stream_and_invalid_delays_do_not_create_destination(self):
        with self.assertRaisesRegex(ValueError, "No frames"):
            save_streaming_ascii_gif(iter(()), self.target)
        for duration in (0, -1, 9, 655360, float("inf"), float("nan")):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, "duration"):
                save_streaming_ascii_gif(iter([("@", duration)]), self.target)
            self.assertFalse(self.target.exists())

    def test_existing_file_is_preserved(self):
        self.target.write_bytes(b"user content")
        with self.assertRaises(FileExistsError):
            save_streaming_ascii_gif(iter([("@", 60)]), self.target)
        self.assertEqual(self.target.read_bytes(), b"user content")

    def test_frame_dimensions_must_match(self):
        with self.assertRaisesRegex(ValueError, "matching dimensions"):
            save_streaming_ascii_gif(iter([("@", 60), ("@@", 70)]), self.target)

    def test_individual_picture_limit_still_applies(self):
        with self.assertRaisesRegex(ValueError, "20 million pixels"):
            save_streaming_ascii_gif(iter([("@" * 40000, 60)]), self.target)
        self.assertFalse(self.target.exists())
