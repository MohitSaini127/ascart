import contextlib
import errno
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ascart.border import add_border
from ascart.cli import main
from ascart.png_art import art_to_png


class PngRenderingTests(unittest.TestCase):
    def test_regular_font_has_smooth_edges_and_less_ink_than_enlarged_bitmap(self):
        with art_to_png("@%#") as smooth, art_to_png("@%#", smooth=False) as bitmap:
            self.assertEqual(smooth.size, bitmap.size)
            smooth_ink = list(smooth.convert("L").get_flattened_data())
            bitmap_ink = list(bitmap.convert("L").get_flattened_data())
            self.assertTrue(any(0 < value < 255 for value in smooth_ink))
            self.assertLess(sum(smooth_ink), sum(bitmap_ink))
            self.assertEqual(set(bitmap_ink), {0, 255})

    def test_printable_glyphs_stay_in_their_cells_and_leave_spaces_empty(self):
        characters = "".join(chr(value) for value in range(33, 127))
        with art_to_png(" ".join(characters)) as image:
            for index, character in enumerate(characters):
                with self.subTest(character=character):
                    cell = image.crop((12 + index * 24, 12, 24 + index * 24, 34))
                    self.assertIsNotNone(cell.getbbox())
                    if index + 1 < len(characters):
                        self.assertIsNone(image.crop((24 + index * 24, 12, 36 + index * 24, 34)).getbbox())

    def test_bitmap_fallback_works_when_freetype_is_unavailable(self):
        with art_to_png("@ i", smooth=False) as expected:
            with patch("ascart.png_art.ImageFont.load_default", side_effect=ImportError("FreeType unavailable")):
                with art_to_png("@ i") as actual:
                    self.assertEqual(actual.size, expected.size)
                    self.assertEqual(actual.tobytes(), expected.tobytes())
    def test_fixed_grid_preserves_spaces_and_blank_rows(self):
        image = art_to_png("W i\n\n#")
        self.assertEqual(image.size, (60, 90))
        self.assertEqual(set(image.crop((24, 12, 36, 34)).get_flattened_data()), {(0, 0, 0)})
        self.assertIn((255, 255, 255), image.crop((36, 12, 48, 34)).get_flattened_data())
        self.assertEqual(set(image.crop((12, 34, 48, 56)).get_flattened_data()), {(0, 0, 0)})

    def test_rgb_strokes_and_neutral_border(self):
        image = art_to_png(add_border("\033[38;2;12;34;56m@\033[0m"))
        self.assertEqual(image.size, (60, 90))
        self.assertIn((12, 34, 56), image.crop((24, 34, 36, 56)).get_flattened_data())
        border_pixels = image.crop((36, 34, 48, 56)).get_flattened_data()
        self.assertTrue(any(red > 0 for red, _, _ in border_pixels))
        self.assertTrue(all(red == green == blue for red, green, blue in border_pixels))
        self.assertNotIn((12, 34, 56), image.crop((36, 34, 48, 56)).get_flattened_data())

    def test_light_background_and_color_reset(self):
        image = art_to_png("\033[38;2;255;0;0m@\033[0m@", "light")
        self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
        self.assertIn((255, 0, 0), image.crop((12, 12, 24, 34)).get_flattened_data())
        self.assertIn((0, 0, 0), image.crop((24, 12, 36, 34)).get_flattened_data())

    def test_large_picture_rejected_before_allocation(self):
        with patch("ascart.png_art.Image.new") as new_image:
            with self.assertRaisesRegex(ValueError, "20 million pixels"):
                art_to_png("@" * 100_000)
        new_image.assert_not_called()


class PngCliTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.photo = self.root / "source.png"
        Image.new("RGB", (20, 12), (12, 34, 56)).save(self.photo)

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

    def test_photo_colors_border_backgrounds_and_custom_palette(self):
        original = self.photo.read_bytes()
        for background in ("dark", "light"):
            target = self.root / f"{background}.png"
            code, output, errors = self.run_cli(
                self.photo, "--width", "10", "--color", "--chars", "@",
                "--border", "--background", background, "--output", target,
            )
            self.assertEqual(code, 0, errors)
            self.assertIn("Saved ASCII art", output)
            code, preview, errors = self.run_cli(
                self.photo, "--width", "10", "--color", "--chars", "@",
                "--border", "--background", background,
            )
            self.assertEqual(code, 0, errors)
            self.assertIn("\033[38;2;12;34;56m", preview)
            self.assertEqual(output, preview + f"Saved ASCII art to {target}\n")
            with Image.open(target) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.size, (168, 134))
                self.assertIn((12, 34, 56), image.get_flattened_data())
                self.assertEqual(image.getpixel((0, 0)), (0, 0, 0) if background == "dark" else (255, 255, 255))
        self.assertEqual(self.photo.read_bytes(), original)

    def test_all_banner_styles_save_png_with_border(self):
        for index, option in enumerate(("--text", "--text-slant", "--text-bold", "--text-font-small")):
            target = self.root / "new folder" / f"banner {index}.PNG"
            code, output, errors = self.run_cli(option, "Hi", "--border", "--output", target)
            self.assertEqual(code, 0, errors)
            self.assertIn("Saved ASCII art", output)
            code, preview, errors = self.run_cli(option, "Hi", "--border")
            self.assertEqual(code, 0, errors)
            self.assertEqual(output, preview + f"Saved ASCII art to {target}\n")
            with Image.open(target) as image:
                self.assertEqual(image.format, "PNG")
                pixels = set(image.get_flattened_data())
                self.assertIn((0, 0, 0), pixels)
                self.assertTrue(any(0 < red < 255 for red, _, _ in pixels))
                self.assertTrue(all(red == green == blue for red, green, blue in pixels))

    def test_existing_png_and_links_preserved(self):
        target = self.root / "keep.png"
        target.write_bytes(b"existing user data")
        link = self.root / "link.png"
        link.symlink_to(target)
        dangling = self.root / "dangling.png"
        dangling.symlink_to(self.root / "missing.png")
        hardlink = self.root / "hard.png"
        hardlink.hardlink_to(self.photo)
        original = self.photo.read_bytes()
        for destination in (target, link, dangling, hardlink, self.photo):
            code, output, errors = self.run_cli(self.photo, "--output", destination)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("Cannot save artwork", errors)
        self.assertEqual(target.read_bytes(), b"existing user data")
        self.assertTrue(dangling.is_symlink())
        self.assertFalse(dangling.exists())
        self.assertEqual(self.photo.read_bytes(), original)

    def test_file_appearing_during_save_preserved(self):
        target = self.root / "race.png"
        original_open = Path.open

        def competing_create(path, mode="r", *args, **kwargs):
            self.assertEqual(path, target)
            self.assertEqual(mode, "xb")
            with original_open(path, "xb") as file:
                file.write(b"created by another program")
            return original_open(path, mode, *args, **kwargs)

        with patch("ascart.cli.Path.open", new=competing_create), \
             patch("ascart.cli.text_to_ascii", return_value="Hi"):
            code, output, errors = self.run_cli("--text", "Hi", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("already exists", errors)
        self.assertEqual(target.read_bytes(), b"created by another program")

    def test_rendering_failure_leaves_no_output_or_parent(self):
        target = self.root / "not-created" / "art.png"
        with patch("ascart.cli.art_to_png", side_effect=ValueError("PNG would exceed 20 million pixels")):
            code, output, errors = self.run_cli("--text", "Hi", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("20 million pixels", errors)
        self.assertFalse(target.parent.exists())

    def test_permission_and_partial_write_failures(self):
        target = self.root / "denied.png"
        with patch("ascart.cli.Path.open", side_effect=PermissionError(errno.EACCES, "Permission denied")), \
             patch("ascart.cli.text_to_ascii", return_value="Hi"):
            code, output, errors = self.run_cli("--text", "Hi", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("Permission denied", errors)
        self.assertFalse(target.exists())

        def fail_save(image, file, **kwargs):
            file.write(b"partial new PNG")
            raise OSError(errno.ENOSPC, "No space left on device")

        with patch("PIL.Image.Image.save", new=fail_save):
            code, output, errors = self.run_cli("--text", "Hi", "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("No space left", errors)
        self.assertEqual(target.read_bytes(), b"partial new PNG")
