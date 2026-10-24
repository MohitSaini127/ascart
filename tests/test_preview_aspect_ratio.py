import contextlib
import io
import os
import unittest
from unittest.mock import patch

from PIL import Image

from ascart.comparison import comparison_to_png
from ascart.image_art import image_to_ascii
from ascart.terminal_preview import _native_placement, _terminal_cell_size


class PreviewAspectRatioTests(unittest.TestCase):
    def test_landscape_portrait_and_square_use_only_one_scaling_axis(self):
        for dimensions, viewport, cells, expected in (
            ((1920, 1080), (79, 21), (8, 16), "r=21,"),
            ((3840, 1080), (79, 21), (8, 16), "c=79,"),
            ((1080, 1920), (79, 21), (8, 16), "r=21,"),
            ((1000, 1000), (79, 21), (8, 16), "r=21,"),
            ((1920, 1080), (79, 21), (8, 24), "c=79,"),
            ((1920, 1080), (1, 1), (8, 16), "c=1,"),
        ):
            with self.subTest(dimensions=dimensions, viewport=viewport, cells=cells):
                placement = _native_placement(dimensions, *viewport, cells)
                self.assertEqual(placement, expected)
                self.assertEqual(placement.count("="), 1)
                key, value = placement.strip(",").split("=")
                # The terminal derives the other dimension from the PNG's ratio.
                scale = int(value) * cells[0 if key == "c" else 1] / dimensions[0 if key == "c" else 1]
                self.assertLessEqual(dimensions[0] * scale, viewport[0] * cells[0] + 1e-8)
                self.assertLessEqual(dimensions[1] * scale, viewport[1] * cells[1] + 1e-8)

    @unittest.skipUnless(os.name == "posix", "POSIX terminal pixel dimensions")
    def test_measures_cells_from_terminal_pixels(self):
        import struct
        with patch("ascart.terminal_preview.sys.stdout.fileno", return_value=5), \
             patch("fcntl.ioctl", return_value=struct.pack("HHHH", 40, 100, 1000, 800)):
            self.assertEqual(_terminal_cell_size(), (10, 20))

    def test_missing_terminal_pixel_dimensions_only_falls_back_for_fit_estimate(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(_terminal_cell_size(), (8, 16))
        placement = _native_placement((1920, 1080), 79, 21, (8, 16))
        self.assertEqual(placement.count("="), 1)

    def test_original_panel_preserves_video_ratios_before_terminal_scaling(self):
        for size in ((160, 90), (90, 160), (100, 100)):
            with self.subTest(size=size), Image.new("RGB", size, "red") as source:
                art = image_to_ascii(source, width=20, background="dark")
                with comparison_to_png(source, art, "dark") as picture:
                    panel_width = (picture.width - 24) // 2
                    with picture.crop((0, 32, panel_width, picture.height)) as panel:
                        left, top, right, bottom = panel.getbbox()
                        # Resizing rounds dimensions to a whole pixel.
                        self.assertLessEqual(abs((right - left) - (bottom - top) * size[0] / size[1]), 2)
