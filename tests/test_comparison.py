import base64
import contextlib
import errno
import io
import itertools
import os
from pathlib import Path
import tempfile
import unittest
from html.parser import HTMLParser
from unittest.mock import patch

from PIL import Image, PngImagePlugin

from ascart.border import COLOR_CODE
from ascart.cli import main
from ascart.comparison import comparison_to_html, comparison_to_png
from ascart.png_art import art_to_png
from test_html_art import ArtworkParser


class ImagesParser(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.images = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs))


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / 'source <&".png'
        with Image.new("RGB", (32, 24), "red") as image:
            image.paste("blue", (16, 0, 32, 24))
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("private-note", "source-private-metadata")
            image.save(self.source, pnginfo=metadata)
        self.original_bytes = self.source.read_bytes()

    def run_cli(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, arguments)]), \
             patch.dict(os.environ, {"COLORFGBG": "0;15"}), \
             patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((22, 12))), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_visual_options_match_existing_artwork_for_png_and_html(self):
        cases = itertools.product(("png", "html"), (False, True), (False, True),
                                  ("dark", "light", "auto"), (False, True), (False, True))
        for index, (suffix, color, border, background, custom, fit) in enumerate(cases):
            with self.subTest(case=index):
                target = self.root / "new folder" / f"comparison {index}.{suffix.upper()}"
                settings = ["--background", background]
                settings += ["--color"] if color else []
                settings += ["--border"] if border else []
                settings += ['--chars= <&>@'] if custom else []
                settings += ["--fit"] if fit else ["--width=10"]
                code, plain, errors = self.run_cli(self.source, *settings)
                self.assertEqual(code, 0, errors)
                code, compared, errors = self.run_cli(self.source, *settings, "--compare", "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertEqual(compared, f"Saved ASCII art to {target}\n")
                self.assertIn("open the saved comparison", errors)
                art = plain.removesuffix("\n")
                resolved = "dark" if background == "dark" else "light"
                if suffix == "png":
                    with Image.open(target) as saved, contextlib.closing(art_to_png(art, resolved)) as expected:
                        panel_width = max(96, expected.width)
                        self.assertEqual(saved.size, (panel_width * 2 + 24, expected.height + 32))
                        self.assertEqual(saved.mode, "RGB")
                        x = panel_width + 24 + (panel_width - expected.width) // 2
                        with saved.crop((x, 32, x + expected.width, 32 + expected.height)) as right:
                            self.assertEqual(right.tobytes(), expected.tobytes())
                        self.assertEqual(saved.getpixel((panel_width // 4, 32 + expected.height // 2)), (255, 0, 0))
                        self.assertEqual(saved.getpixel((panel_width * 3 // 4, 32 + expected.height // 2)), (0, 0, 255))
                else:
                    document = target.read_text()
                    parsed = ArtworkParser(document)
                    self.assertEqual("".join(parsed.text), COLOR_CODE.sub("", art))
                    self.assertNotIn("script", parsed.tags)
                    self.assertIn("<figcaption>Original</figcaption>", document)
                    self.assertIn("<figcaption>ASCII</figcaption>", document)
                    self.assertNotIn(str(self.source), document)
                    self.assertNotIn("source-private-metadata", document)
                    images = ImagesParser(document).images
                    self.assertEqual(len(images), 1)
                    self.assertTrue(images[0]["src"].startswith("data:image/png;base64,"))
                    with Image.open(io.BytesIO(base64.b64decode(images[0]["src"].split(",", 1)[1]))) as source:
                        self.assertEqual(source.mode, "RGB")
                        self.assertFalse(source.info)
                        self.assertEqual(source.getpixel((source.width // 4, source.height // 2)), (255, 0, 0))
                self.assertEqual(self.source.read_bytes(), self.original_bytes)

    def test_preserves_aspect_ratio_and_transparency_on_both_backgrounds(self):
        with Image.new("RGBA", (20, 10), (255, 0, 0, 0)) as image:
            image.paste((255, 0, 0, 255), (0, 0, 10, 10))
            original_pixels = image.tobytes()
            for background, canvas in (("dark", (0, 0, 0)), ("light", (255, 255, 255))):
                with self.subTest(background=background), contextlib.closing(comparison_to_png(image, "@" * 10 + "\n" + "@" * 10, background)) as saved:
                    # Panel is 144x68: the 20x10 source fits at 88x44,
                    # centred at x=28, y=12 below the label strip.
                    self.assertEqual(saved.getpixel((28, 32 + 34)), (255, 0, 0))
                    self.assertEqual(saved.getpixel((115, 32 + 34)), canvas)
                    self.assertEqual(saved.getpixel((27, 32 + 34)), canvas)
                    self.assertEqual(saved.getpixel((40, 32 + 11)), canvas)
            self.assertEqual(image.tobytes(), original_pixels)

    def test_html_escapes_art_and_preserves_blank_rows(self):
        art = '\n<&>"\'\n\n'
        with Image.open(self.source) as image:
            document = comparison_to_html(image, art)
        self.assertEqual("".join(ArtworkParser(document).text), art)
        self.assertIn("&lt;&amp;&gt;", document)
        self.assertNotIn("<script", document)

    def test_combined_limit_precedes_picture_allocation_for_both_formats(self):
        # Each panel alone is under 20 MP; the full comparison is over it.
        art = ("@" * 1000 + "\n") * 40
        with Image.open(self.source) as image:
            for renderer in (comparison_to_png, comparison_to_html):
                with self.subTest(renderer=renderer), patch("ascart.comparison.Image.new") as allocate:
                    with self.assertRaisesRegex(ValueError, "Comparison would exceed 20 million pixels"):
                        renderer(image, art)
                    allocate.assert_not_called()

    def test_requires_still_image_mode_and_png_or_html_output(self):
        cases = [
            [self.source, "--output", self.root / "new" / "bad.txt"],
            [self.source, "--output", self.root / "new" / "bad.gif"],
            [self.source, "--output", self.root / "new" / "bad.mp4"],
            ["-t", "Hi", "--output", self.root / "new" / "text.png"],
            ["--camera", "--output", self.root / "new" / "camera.png"],
            ["--list-cameras"],
            [self.source, "--loop", "--output", self.root / "new" / "loop.png"],
        ]
        for args in cases:
            with self.subTest(args=args), patch("cv2.VideoCapture") as camera:
                code, output, errors = self.run_cli(*args, "--compare")
                self.assertEqual(code, 2)
                self.assertIn("--compare", errors)
                self.assertNotIn("Saved ASCII", output)
                camera.assert_not_called()
        self.assertFalse((self.root / "new").exists())

    def test_animated_images_gifs_and_video_are_rejected_without_output(self):
        with Image.new("RGB", (16, 12), "red") as first, Image.new("RGB", (16, 12), "blue") as second:
            for suffix in ("png", "webp"):
                source = self.root / ("animated." + suffix)
                first.save(source, save_all=True, append_images=[second], duration=60)
                code, output, errors = self.run_cli(source, "--compare", "--output", self.root / "new" / "bad.html")
                self.assertEqual(code, 2, (suffix, errors))
                self.assertIn("still images only", errors)
        gif = self.root / "still.gif"
        with Image.new("RGB", (16, 12), "red") as image:
            image.save(gif)
        for source in (gif, self.root / "video.mp4"):
            if source.suffix == ".mp4":
                source.write_bytes(b"not an image")
            with patch("ascart.cli.inspect_video") as decode:
                code, output, errors = self.run_cli(source, "--compare", "--output", self.root / "new" / "bad.png")
                self.assertEqual(code, 2)
                self.assertIn("--compare", errors)
                decode.assert_not_called()
        self.assertFalse((self.root / "new").exists())

    def test_existing_files_links_and_source_aliases_are_preserved(self):
        existing = self.root / "existing.png"
        existing.write_bytes(b"keep me")
        link = self.root / "link.png"
        link.symlink_to(existing)
        dangling = self.root / "dangling.png"
        dangling.symlink_to(self.root / "missing")
        hard = self.root / "hard.png"
        hard.hardlink_to(self.source)
        for target in (existing, link, dangling, hard, self.source):
            with self.subTest(target=target):
                code, output, errors = self.run_cli(self.source, "--compare", "--output", target)
                self.assertEqual(code, 2)
                self.assertNotIn("Saved ASCII", output)
        self.assertEqual(existing.read_bytes(), b"keep me")
        self.assertTrue(dangling.is_symlink())
        self.assertEqual(self.source.read_bytes(), self.original_bytes)

    def test_competing_destination_is_not_overwritten(self):
        for suffix in ("png", "html"):
            target = self.root / ("racing." + suffix)
            original_open = Path.open

            def race(path, mode="r", *args, **kwargs):
                if path == target and "x" in mode:
                    with original_open(path, "wb") as file:
                        file.write(b"another user")
                return original_open(path, mode, *args, **kwargs)

            with patch("pathlib.Path.open", new=race):
                code, output, errors = self.run_cli(self.source, "--compare", "--output", target)
            self.assertEqual(code, 2)
            self.assertIn("already exists", errors)
            self.assertEqual(target.read_bytes(), b"another user")

    def test_rendering_failure_does_not_create_output_folders(self):
        for suffix, renderer in (("png", "comparison_to_png"), ("html", "comparison_to_html")):
            with patch("ascart.cli." + renderer, side_effect=ValueError("Cannot render comparison")):
                code, output, errors = self.run_cli(self.source, "--compare", "--output", self.root / "new" / ("error." + suffix))
            self.assertEqual(code, 2)
            self.assertIn("Cannot render comparison", errors)
            self.assertNotIn("Saved ASCII", output)
        self.assertFalse((self.root / "new").exists())

    def test_write_errors_are_readable_and_report_no_success(self):
        for suffix in ("png", "html"):
            target = self.root / ("write-error." + suffix)
            original_open = Path.open

            def fail(path, mode="r", *args, **kwargs):
                if path == target and "x" in mode:
                    raise PermissionError(errno.EACCES, "Permission denied")
                return original_open(path, mode, *args, **kwargs)

            with patch("pathlib.Path.open", new=fail):
                code, output, errors = self.run_cli(self.source, "--compare", "--output", target)
            self.assertEqual(code, 2)
            self.assertIn("Permission denied", errors)
            self.assertNotIn("Saved ASCII", output)
            self.assertFalse(target.exists())

    def test_help_documents_comparison(self):
        code, output, errors = self.run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("--compare", output)
        self.assertIn("optionally save PNG or HTML", " ".join(output.split()))
