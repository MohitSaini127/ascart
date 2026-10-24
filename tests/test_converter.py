import re
import unittest
from collections import Counter

from PIL import Image

from ascart.converter import COLOR_PALETTE, DEFAULT_PALETTE, brightness_to_character
from ascart.image_art import image_to_ascii


class BrightnessMappingTests(unittest.TestCase):
    def test_black_and_white_select_palette_endpoints(self):
        for palette in (DEFAULT_PALETTE, COLOR_PALETTE, " .o@", "#"):
            with self.subTest(palette=palette):
                self.assertEqual(brightness_to_character(0, palette), palette[0])
                self.assertEqual(brightness_to_character(255, palette), palette[-1])

    def test_color_band_boundaries(self):
        for brightness, character in ((0, "#"), (85, "#"), (86, "%"), (170, "%"), (171, "@"), (255, "@")):
            with self.subTest(brightness=brightness):
                self.assertEqual(brightness_to_character(brightness, COLOR_PALETTE), character)

    def test_custom_four_character_palette_boundaries(self):
        for brightness, character in ((0, " "), (63, " "), (64, "."), (127, "."), (128, "o"), (191, "o"), (192, "@"), (255, "@")):
            with self.subTest(brightness=brightness):
                self.assertEqual(brightness_to_character(brightness, " .o@"), character)

    def test_all_brightness_values_have_balanced_bands(self):
        for palette in (DEFAULT_PALETTE, COLOR_PALETTE, " .o@", "abcdefg"):
            with self.subTest(palette=palette):
                counts = Counter(brightness_to_character(value, palette) for value in range(256))
                self.assertEqual(set(counts), set(palette))
                self.assertEqual(sum(counts.values()), 256)
                self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
                self.assertGreater(counts[palette[-1]], 1)

    def test_palette_positions_never_move_backwards(self):
        for palette in (DEFAULT_PALETTE, COLOR_PALETTE, " .o@"):
            with self.subTest(palette=palette):
                positions = [palette.index(brightness_to_character(value, palette)) for value in range(256)]
                self.assertEqual(positions, sorted(positions))

    def test_single_character_palette(self):
        self.assertTrue(all(brightness_to_character(value, "#") == "#" for value in range(256)))

    def test_image_mapping_background_and_color_preserve_pixels(self):
        with Image.new("L", (4, 1)) as image:
            image.putdata([0, 85, 170, 255])
            original = image.tobytes()
            for background, expected in (("dark", " .o@"), ("light", "@o. ")):
                for color in (False, True):
                    with self.subTest(background=background, color=color):
                        art = image_to_ascii(image, width=4, palette=" .o@", background=background, color=color)
                        plain = re.sub(r"\x1b\[[0-9;]*m", "", art)
                        self.assertEqual(plain, expected)
                        if color:
                            self.assertIn("\033[38;2;85;85;85m", art)
                        self.assertEqual(image.tobytes(), original)


class TransparentImageTests(unittest.TestCase):
    def test_hidden_pixels_match_canvas_and_do_not_modify_source(self):
        for mode, pixel in (("RGBA", (255, 0, 0, 0)), ("LA", (255, 0))):
            with Image.new(mode, (4, 2), pixel) as image:
                original = image.tobytes()
                for background, rgb in (("dark", "0;0;0"), ("light", "255;255;255")):
                    self.assertEqual(image_to_ascii(image, width=4, background=background), "    ")
                    art = image_to_ascii(image, width=4, background=background, color=True, palette="@")
                    self.assertEqual(art.count(f"\033[38;2;{rgb}m@"), 4)
                self.assertEqual(image.tobytes(), original)

    def test_partial_alpha_blends_with_selected_background(self):
        with Image.new("RGBA", (4, 2), (255, 0, 0, 128)) as image:
            for background, rgb in (("dark", "128;0;0"), ("light", "255;127;127")):
                art = image_to_ascii(image, width=4, palette="@", background=background, color=True)
                self.assertEqual(art.count(f"\033[38;2;{rgb}m@"), 4)

    def test_paletted_gif_transparency_is_preserved_until_conversion(self):
        import tempfile
        from pathlib import Path
        from ascart.gif_art import gif_to_ascii
        from ascart.gif_comparison import comparison_frames
        with tempfile.TemporaryDirectory() as folder, Image.new("P", (4, 2), 0) as image:
            image.putpalette([255, 0, 0] + [0, 0, 0] * 255)
            image.info["transparency"] = 0
            self.assertEqual(image_to_ascii(image, width=4), "    ")
            source = Path(folder) / "transparent.gif"
            image.save(source, transparency=0)
            original = source.read_bytes()
            for background in ("dark", "light"):
                self.assertEqual(gif_to_ascii(source, width=4, background=background)[0][0], "    ")
                frames = comparison_frames(source, width=4, palette=" .@", background=background,
                                           max_height=None, color=False, border=False)
                try:
                    self.assertEqual(next(frames)[1], "    ")
                finally:
                    frames.close()
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
