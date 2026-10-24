"""Exercise complete CLI option combinations using temporary, real media."""

import contextlib
import hashlib
import io
import itertools
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from ascart.border import COLOR_CODE
from ascart.cli import detect_background, main


class FeatureCombinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        cls.root = Path(cls.folder.name)
        cls.photo = cls.root / "photo.png"
        pixels = np.zeros((24, 32, 3), dtype=np.uint8)
        pixels[:, :, 0] = np.arange(32, dtype=np.uint8) * 8
        pixels[:, :, 1] = np.arange(24, dtype=np.uint8)[:, None] * 10
        pixels[:, :, 2] = 140
        with Image.fromarray(pixels) as image:
            image.save(cls.photo)
        cls.gif = cls.root / "source.gif"
        frames = [Image.fromarray(np.roll(pixels, shift, axis=1)) for shift in (0, 8, 16)]
        try:
            frames[0].save(cls.gif, save_all=True, append_images=frames[1:], duration=[40, 70, 100], loop=0)
        finally:
            for frame in frames:
                frame.close()
        cls.video = cls.root / "source.mp4"
        writer = cv2.VideoWriter(str(cls.video), cv2.VideoWriter_fourcc(*"mp4v"), 20, (32, 24))
        if not writer.isOpened():
            writer.release()
            raise RuntimeError("Combination tests require working MP4 encoding")
        try:
            for shift in (0, 8):
                writer.write(np.roll(pixels, shift, axis=1))
        finally:
            writer.release()
        cls.originals = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (cls.photo, cls.gif, cls.video)}

    @classmethod
    def tearDownClass(cls):
        for path, original in cls.originals.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != original:
                raise AssertionError(f"Test changed source media: {path}")

    def run_cli(self, arguments, terminal=True, continuous=False):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, arguments)]), \
             patch.dict(os.environ, {"COLORFGBG": "0;15"}), \
             patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((22, 12))), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), \
             patch.object(output, "isatty", return_value=terminal), \
             patch("time.sleep", side_effect=KeyboardInterrupt if continuous else None):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def media_options(self, color, border, background, custom, sizing):
        options = ["--background", background]
        if color:
            options.append("--color")
        if border:
            options.append("--border")
        if custom:
            # Includes characters that can also be mistaken for CLI switches.
            options.append("--chars= .-+@")
        if sizing == "width":
            options.extend(("--width", "12"))
        elif sizing == "fit":
            options.append("--fit")
        return options

    def assert_grid(self, art, color, border, custom, sizing):
        self.assertEqual("\033[38;2;" in art, color)
        rows = COLOR_CODE.sub("", art).split("\n")
        self.assertTrue(rows)
        self.assertTrue(all(len(row) == len(rows[0]) for row in rows))
        if border:
            self.assertTrue(rows[0].startswith("+") and rows[0].endswith("+"))
            self.assertEqual(rows[0], rows[-1])
            self.assertTrue(all(row.startswith("|") and row.endswith("|") for row in rows[1:-1]))
            content = [row[1:-1] for row in rows[1:-1]]
        else:
            content = rows
        if custom:
            self.assertLessEqual(set("".join(content)), set(" .-+@"))
        if sizing == "fit":
            self.assertLessEqual(len(rows), 10)
            self.assertLessEqual(len(rows[0]), 21)
        else:
            self.assertEqual(len(rows[0]), (12 if sizing == "width" else 60) + (2 if border else 0))

    def test_photo_option_matrix(self):
        cases = itertools.product((False, True), (False, True), ("auto", "dark", "light"), (False, True), ("default", "width", "fit"), (None, ".txt", ".png"))
        count = 0
        for index, (color, border, background, custom, sizing, suffix) in enumerate(cases):
            with self.subTest(color=color, border=border, background=background, custom=custom, sizing=sizing, suffix=suffix):
                options = self.media_options(color, border, background, custom, sizing)
                target = self.root / f"photo-{index}{suffix}" if suffix else None
                args = [self.photo, *options, *(["--output", target] if target else [])]
                code, output, errors = self.run_cli(args)
                self.assertEqual(code, 0, errors)
                self.assertEqual(errors, "")
                art = output.removesuffix(f"Saved ASCII art to {target}\n").removesuffix("\n") if target else output.removesuffix("\n")
                self.assert_grid(art, color and suffix != ".txt", border, custom, sizing)
                if suffix == ".txt":
                    self.assertEqual(target.read_text(), art + "\n")
                    self.assertNotIn("\033", target.read_text())
                elif suffix == ".png":
                    rows = COLOR_CODE.sub("", art).split("\n")
                    with Image.open(target) as image:
                        self.assertEqual(image.format, "PNG")
                        self.assertEqual(image.size, (len(rows[0]) * 12 + 24, len(rows) * 22 + 24))
                        self.assertEqual(image.getpixel((0, 0)), (0, 0, 0) if background == "dark" else (255, 255, 255))
                        image.load()
                count += 1
        self.assertEqual(count, 216)

    def test_gif_option_matrix(self):
        cases = itertools.product((False, True), (False, True), ("auto", "dark", "light"), (False, True), ("default", "width", "fit"), ("once", "twice", "continuous"), (False, True), (False, True))
        count = 0
        for index, (color, border, background, custom, sizing, looping, saving, terminal) in enumerate(cases):
            with self.subTest(color=color, border=border, background=background, custom=custom, sizing=sizing, looping=looping, saving=saving, terminal=terminal):
                options = self.media_options(color, border, background, custom, sizing)
                if looping != "once":
                    options.append("--loop-2" if looping == "twice" else "--loop")
                target = self.root / f"animation-{index}.gif"
                code, output, errors = self.run_cli(
                    [self.gif, *options, *(["--output", target] if saving else [])],
                    terminal=terminal, continuous=looping == "continuous",
                )
                if not terminal and not saving:
                    self.assertEqual(code, 2)
                    self.assertIn("interactive terminal", errors)
                    self.assertEqual(output, "")
                else:
                    self.assertEqual(code, 0, errors)
                    self.assertEqual(errors, "")
                    if terminal:
                        expected = 1 if looping == "continuous" else (6 if looping == "twice" else 3)
                        self.assertEqual(output.count("\033[H\033[J"), expected)
                        self.assertIn("\033[?25h", output)
                        displayed = output.split("\033[H\033[J")[1].split("\033[0m\033[?25h")[0]
                        self.assert_grid(displayed, color, border, custom, sizing)
                    else:
                        self.assertNotIn("\033[", output)
                    if saving:
                        self.assertTrue(output.endswith(f"Saved ASCII GIF to {target}\n"))
                        with Image.open(target) as gif:
                            self.assertEqual(gif.n_frames, 3)
                            self.assertNotIn("loop", gif.info)
                            delays = []
                            for frame_index in range(gif.n_frames):
                                gif.seek(frame_index)
                                delays.append(gif.info["duration"])
                                gif.load()
                            self.assertEqual(delays, [40, 70, 100])
                    else:
                        self.assertFalse(target.exists())
                count += 1
        self.assertEqual(count, 864)

    def test_video_option_matrix(self):
        cases = itertools.product((False, True), (False, True), ("auto", "dark", "light"), (False, True), ("default", "width", "fit"), ("once", "twice", "continuous"))
        count = 0
        for color, border, background, custom, sizing, looping in cases:
            with self.subTest(color=color, border=border, background=background, custom=custom, sizing=sizing, looping=looping):
                options = self.media_options(color, border, background, custom, sizing)
                if looping != "once":
                    options.append("--loop-count=2" if looping == "twice" else "--loop")
                code, output, errors = self.run_cli([self.video, *options], continuous=looping == "continuous")
                self.assertEqual(code, 0, errors)
                self.assertEqual(errors, "")
                expected = 1 if looping == "continuous" else (4 if looping == "twice" else 2)
                self.assertEqual(output.count("\033[H\033[J"), expected)
                self.assertTrue(output.endswith("\033[0m\033[?25h\n"))
                displayed = output.split("\033[H\033[J")[1].split("\033[0m\033[?25h")[0]
                self.assert_grid(displayed, color, border, custom, sizing)
                count += 1
        self.assertEqual(count, 216)

    def test_text_option_matrix(self):
        cases = itertools.product(("--text", "--text-slant", "--text-bold", "--text-font-small"), (20, 60), (False, True), (None, ".txt", ".png"))
        count = 0
        for index, (font, width, border, suffix) in enumerate(cases):
            with self.subTest(font=font, width=width, border=border, suffix=suffix):
                target = self.root / f"banner-{index}{suffix}" if suffix else None
                args = [font, "Hi", "--width", width, *(["--border"] if border else []), *(["--output", target] if target else [])]
                code, output, errors = self.run_cli(args)
                self.assertEqual(code, 0, errors)
                self.assertEqual(errors, "")
                art = output.removesuffix(f"Saved ASCII art to {target}\n").removesuffix("\n") if target else output.removesuffix("\n")
                self.assertTrue(art.strip())
                self.assertNotIn("\033", art)
                if border:
                    self.assertEqual(art.split("\n")[0], art.split("\n")[-1])
                    self.assertTrue(art.startswith("+"))
                if suffix == ".txt":
                    self.assertEqual(target.read_text(), art + "\n")
                elif suffix == ".png":
                    with Image.open(target) as image:
                        self.assertEqual(image.format, "PNG")
                        image.load()
                count += 1
        self.assertEqual(count, 48)

    def test_invalid_combinations_leave_no_output(self):
        bad_options = (
            ("--width", "12", "--fit"), ("--loop", "--loop-2"),
            ("--loop-0",), ("--loop-count=-1",), ("--width=0",),
            ("--width=-1",), ("--width=word",), ("--background=purple",),
            ("--chars=",), ("--chars=é",), ("--chars=\t",),
        )
        for index, (source, options) in enumerate(itertools.product((self.photo, self.gif, self.video), bad_options)):
            with self.subTest(source=source, options=options):
                target = self.root / "rejected" / f"bad-{index}{'.gif' if source == self.gif else '.png'}"
                code, output, errors = self.run_cli([source, *options, "--border", "--output", target])
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("error:", errors)
                self.assertFalse(target.parent.exists())
        for options in (("--color",), ("--fit",), ("--background=light",), ("--chars=@",), ("--loop",), ("--loop-count=2",), ("--text-bold", "Hi")):
            with self.subTest(text_options=options):
                target = self.root / "rejected" / "banner.png"
                code, output, errors = self.run_cli(["--text", "Hi", *options, "--output", target])
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("error:", errors)
                self.assertFalse(target.parent.exists())

    def test_short_text_matches_long_form_with_width_borders_and_saving(self):
        for index, (width, border, suffix) in enumerate(itertools.product((20, 60), (False, True), (None, ".txt", ".png"))):
            with self.subTest(width=width, border=border, suffix=suffix):
                outputs = []
                saved = []
                for option, label in (("--text", "long"), ("-t", "short")):
                    target = self.root / f"alias-{label}-{index}{suffix}" if suffix else None
                    args = [option, "Hi", "--width", width, *(["--border"] if border else []), *(["--output", target] if target else [])]
                    code, output, errors = self.run_cli(args)
                    self.assertEqual(code, 0, errors)
                    self.assertEqual(errors, "")
                    outputs.append(output.removesuffix(f"Saved ASCII art to {target}\n") if target else output)
                    if target:
                        saved.append(target.read_bytes())
                self.assertEqual(outputs[0], outputs[1])
                if suffix:
                    self.assertEqual(saved[0], saved[1])

    def test_short_text_rejects_invalid_values_and_other_input_modes(self):
        for args in (
            ["-t"], ["-t", ""], ["-t", "   "], ["-t", "é"],
            ["-t", "Hi", self.photo], ["-t", "Hi", "--color"],
            ["-t", "Hi", "--fit"], ["-t", "Hi", "--loop"],
            ["-t", "Hi", "--text-slant", "Hi"],
            ["-t", "Hi", "--text-bold", "Hi"],
            ["-t", "Hi", "--text-font-small", "Hi"],
        ):
            with self.subTest(args=args):
                code, output, errors = self.run_cli(args)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("error:", errors)

    def test_short_text_help_and_option_like_literal_values(self):
        code, output, errors = self.run_cli(["--help"])
        self.assertEqual(code, 0, errors)
        self.assertRegex(output, r"(?m)^\s*-t(?: TEXT)?,\s*--text TEXT")
        for text in ("--loop-4", "--text-font-small"):
            short = self.run_cli([f"-t={text}", "--width=120"])
            long = self.run_cli([f"--text={text}", "--width=120"])
            self.assertEqual(short[0], 0, short[2])
            self.assertEqual(short, long)

    def test_option_like_text_values_remain_literal(self):
        for argument in ("--text=--loop-4", "--text-slant=--border", "--text-bold=--fit", "--text-font-small=--loop-4"):
            with self.subTest(argument=argument):
                code, output, errors = self.run_cli([argument, "--border", "--width=120"])
                self.assertEqual(code, 0, errors)
                self.assertNotIn("\033", output)
                self.assertTrue(output.startswith("+"))

    def test_malformed_python_api_paths_get_readable_errors(self):
        for args in (["bad\0.png"], ["--text", "Hi", "--output", "bad\0.png"]):
            with self.subTest(args=args):
                code, output, errors = self.run_cli(args)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("Cannot", errors)

    def test_background_hints_and_missing_hint(self):
        cases = (
            (None, "dark"), ("", "dark"), ("0;0", "dark"),
            ("15;0", "dark"), ("0;7", "light"), ("0;15", "light"),
            ("0; 15 ", "light"), ("unknown", "dark"),
            ("0;3", "dark"), ("31;15;0", "dark"),
        )
        for hint, expected in cases:
            with self.subTest(hint=hint), patch.dict(os.environ, {} if hint is None else {"COLORFGBG": hint}, clear=True):
                self.assertEqual(detect_background(), expected)

    def test_invalid_banner_values_and_missing_option_values(self):
        cases = [[], ["--text", ""], ["--text", "   "], ["--text", "Hi\nthere"], ["--text", "é"], ["--text-font-not_a_real_font", "Hi"]]
        cases.extend([[font, "Hi", "--width", "1"] for font in ("--text", "--text-slant", "--text-bold", "--text-font-small")])
        cases.extend([[self.photo, option] for option in ("--width", "--output", "--chars", "--background", "--loop-count")])
        for args in cases:
            with self.subTest(args=args):
                code, output, errors = self.run_cli(args)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("error:", errors)
