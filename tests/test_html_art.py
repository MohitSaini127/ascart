import contextlib
import errno
import io
import itertools
import os
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from ascart.border import COLOR_CODE, add_border
from ascart.cli import main
from ascart.html_art import art_to_html


class ArtworkParser(HTMLParser):
    """Read the selectable artwork separately from document titles/styles."""
    def __init__(self, document):
        super().__init__(convert_charrefs=True)
        self.in_code = False
        self.foreground = None
        self.text = []
        self.segments = []
        self.tags = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "code":
            self.in_code = True
        elif tag == "span" and self.in_code:
            self.foreground = dict(attrs).get("style")

    def handle_endtag(self, tag):
        if tag == "code":
            self.in_code = False
        elif tag == "span":
            self.foreground = None

    def handle_data(self, data):
        if self.in_code:
            self.text.append(data)
            self.segments.append((data, self.foreground))


class HtmlRenderingTests(unittest.TestCase):
    def test_markup_characters_spaces_and_blank_rows_remain_literal(self):
        art = '\n  <script>alert("x")</script>&\'\\\n\n'
        document = art_to_html(art)
        parsed = ArtworkParser(document)
        self.assertEqual("".join(parsed.text), art)
        self.assertIn("&lt;script&gt;", document)
        self.assertNotIn("script", parsed.tags)
        self.assertNotIn("\033", document)
        self.assertTrue(document.startswith("<!doctype html>"))
        self.assertIn('charset="utf-8"', document)
        self.assertIn("white-space: pre", document)
        self.assertIn("monospace", document)
        self.assertFalse(set(parsed.tags) & {"script", "link", "iframe", "img"})

    def test_foreground_colors_reset_and_border_stays_neutral(self):
        art = add_border("\033[38;2;12;34;56m<&>\033[0m")
        for background in ("dark", "light"):
            with self.subTest(background=background):
                document = art_to_html(art, background)
                parsed = ArtworkParser(document)
                self.assertEqual("".join(parsed.text), COLOR_CODE.sub("", art))
                self.assertIn(("<&>", "color:rgb(12,34,56)"), parsed.segments)
                for text, color in parsed.segments:
                    if "|" in text or "+" in text or "-" in text:
                        self.assertIsNone(color)
                colors = "background: #ffffff; color: #000000" if background == "light" else "background: #000000; color: #ffffff"
                self.assertIn(colors, document)

    def test_black_and_white_rgb_are_preserved(self):
        parsed = ArtworkParser(art_to_html("\033[38;2;0;0;0m#\033[38;2;255;255;255m@\033[0m."))
        self.assertEqual(parsed.segments, [("#", "color:rgb(0,0,0)"), ("@", "color:rgb(255,255,255)"), (".", None)])

    def test_empty_art_and_trailing_spaces_are_preserved(self):
        for art in ("", "   ", "a  \n\n"):
            with self.subTest(art=art):
                self.assertEqual("".join(ArtworkParser(art_to_html(art)).text), art)

    def test_invalid_color_codes_are_rejected(self):
        for art in ("\033[31m@", "\033[38;2;999;0;0m@"):
            with self.subTest(art=art), self.assertRaises(ValueError):
                art_to_html(art)


class HtmlCliTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.photo = self.root / "photo.png"
        with Image.new("RGB", (20, 12), (12, 34, 56)) as image:
            image.save(self.photo)

    def run_cli(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, arguments)]), \
             patch.dict(os.environ, {"COLORFGBG": "0;15"}), \
             patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((18, 10))), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_photo_html_option_matrix(self):
        original = self.photo.read_bytes()
        for index, (color, border, background, custom, fitted) in enumerate(itertools.product((False, True), (False, True), ("dark", "light", "auto"), (False, True), (False, True))):
            with self.subTest(color=color, border=border, background=background, custom=custom, fitted=fitted):
                target = self.root / "new folder" / f"my art {index}.HTML"
                options = ["--background", background]
                options += ["--color"] if color else []
                options += ["--border"] if border else []
                options += ["--chars=<&>\"'"] if custom else []
                options += ["--fit"] if fitted else ["--width=10"]
                code, output, errors = self.run_cli(self.photo, *options, "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertEqual(errors, "")
                document = target.read_text(encoding="utf-8")
                parsed = ArtworkParser(document)
                preview = output.removesuffix(f"Saved ASCII art to {target}\n").removesuffix("\n")
                self.assertEqual("".join(parsed.text), COLOR_CODE.sub("", preview))
                self.assertEqual(self.run_cli(self.photo, *options), (0, preview + "\n", ""))
                self.assertEqual("color:rgb(12,34,56)" in document, color)
                canvas = "#000000" if background == "dark" else "#ffffff"
                self.assertIn(f"background: {canvas}", document)
                self.assertNotIn("\033", document)
                if border:
                    self.assertTrue("".join(parsed.text).startswith("+"))
                if fitted:
                    rows = "".join(parsed.text).split("\n")
                    self.assertLessEqual(len(rows), 8)
                    self.assertTrue(all(len(row) <= 17 for row in rows))
        self.assertEqual(self.photo.read_bytes(), original)

    def test_all_text_styles_shortcut_width_and_border_save_html(self):
        for index, (option, width, border) in enumerate(itertools.product(("--text", "-t", "--text-slant", "--text-bold", "--text-font-small"), (20, 60), (False, True))):
            with self.subTest(option=option, width=width, border=border):
                target = self.root / f"banner-{index}.html"
                options = [option, "Hi", "--width", width, *(["--border"] if border else [])]
                code, output, errors = self.run_cli(*options, "--output", target)
                self.assertEqual(code, 0, errors)
                preview = self.run_cli(*options)[1].removesuffix("\n")
                self.assertEqual(output, preview + f"\nSaved ASCII art to {target}\n")
                self.assertEqual("".join(ArtworkParser(target.read_text()).text), preview)

    def test_animation_html_saves_even_with_terminal_loop_options(self):
        gif = self.root / "source.gif"
        with Image.new("RGB", (20, 12), "red") as image:
            image.save(gif)
        video = self.root / "source.mp4"
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 24))
        self.assertTrue(writer.isOpened())
        try:
            writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
        finally:
            writer.release()
        for source, loop in itertools.product((gif, video), ((), ("--loop",), ("--loop-4",))):
            with self.subTest(source=source, loop=loop):
                target = self.root / "new folder" / f"{source.name}-{len(loop)}-{loop}.html"
                code, output, errors = self.run_cli(source, *loop, "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertIn("Saved ASCII", output)
                self.assertIn('id="frames"', target.read_text())

    def test_existing_files_input_links_and_directories_preserved(self):
        original = self.photo.read_bytes()
        keep = self.root / "keep.html"
        keep.write_text("user webpage")
        symbolic = self.root / "symbolic.html"
        symbolic.symlink_to(self.photo)
        hard = self.root / "hard.html"
        hard.hardlink_to(self.photo)
        dangling = self.root / "dangling.html"
        missing = self.root / "missing.html"
        dangling.symlink_to(missing)
        for target in (keep, self.photo, symbolic, hard, dangling, self.root):
            code, output, errors = self.run_cli(self.photo, "--output", target)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("Cannot save artwork", errors)
        self.assertEqual(keep.read_text(), "user webpage")
        self.assertEqual(self.photo.read_bytes(), original)
        self.assertTrue(dangling.is_symlink())
        self.assertFalse(missing.exists())

    def test_competing_creation_preserves_newly_appeared_file(self):
        target = self.root / "race.html"
        original_open = Path.open

        def competing_create(path, mode="r", *args, **kwargs):
            self.assertEqual(path, target)
            self.assertEqual(mode, "x")
            with original_open(path, "x", encoding="utf-8") as file:
                file.write("created by another program")
            return original_open(path, mode, *args, **kwargs)

        with patch("ascart.cli.Path.open", new=competing_create):
            code, output, errors = self.run_cli(self.photo, "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("already exists", errors)
        self.assertEqual(target.read_text(), "created by another program")

    def test_render_failure_creates_no_output_or_parent(self):
        target = self.root / "not-created" / "art.html"
        with patch("ascart.cli.art_to_html", side_effect=ValueError("invalid color code")):
            code, output, errors = self.run_cli(self.photo, "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("invalid color code", errors)
        self.assertFalse(target.parent.exists())

    def test_permission_and_partial_write_errors_are_reported(self):
        target = self.root / "new.html"
        for operation in ("ascart.cli.Path.mkdir", "ascart.cli.Path.open"):
            with patch(operation, side_effect=PermissionError(errno.EACCES, "Permission denied")):
                code, output, errors = self.run_cli(self.photo, "--output", target)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("Permission denied", errors)
            self.assertFalse(target.exists())
        original_open = Path.open

        @contextlib.contextmanager
        def failing_open(path, mode="r", *args, **kwargs):
            with original_open(path, mode, *args, **kwargs) as file:
                class Writer:
                    def write(self, data):
                        file.write(data[:20])
                        raise OSError(errno.ENOSPC, "No space left on device")
                yield Writer()

        with patch("ascart.cli.Path.open", new=failing_open):
            code, output, errors = self.run_cli(self.photo, "--output", target)
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("No space left", errors)
        self.assertEqual(target.read_text(), art_to_html("unused")[:20])

    def test_programming_errors_are_not_hidden(self):
        with patch("ascart.cli.art_to_html", side_effect=TypeError("test bug")):
            with self.assertRaisesRegex(TypeError, "test bug"):
                self.run_cli(self.photo, "--output", self.root / "new.html")
