import contextlib
import errno
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image

from ascart.border import add_border
from ascart.cli import main
from ascart.gif_art import gif_to_ascii
from ascart.html_art import art_to_markup, save_animated_html
from ascart.video_art import video_ascii_frames
from test_html_art import ArtworkParser


def read_frames(path):
    document = path.read_text(encoding="utf-8")
    data = re.search(r'<script id="frames" type="application/json">(.*?)</script>', document, re.S)[1]
    return json.loads(data), document


class AnimatedHtmlTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.target = self.root / "new folder" / "art.html"

    def test_escaping_colors_whitespace_timing_and_first_frame(self):
        art = '\n  </script><script>alert("x")</script>&\'\\\n\n'
        color = add_border("\033[38;2;12;34;56m<&>\033[0m")
        self.assertEqual(save_animated_html([(art, 50), (color, 0)], self.target, "light"), 2)
        frames, document = read_frames(self.target)
        self.assertEqual([delay for _, delay in frames], [50, 100])
        for markup, expected in zip((frame[0] for frame in frames), (art, "+---+\n|<&>|\n+---+")):
            self.assertEqual("".join(ArtworkParser(f"<code>{markup}</code>").text), expected)
        self.assertIn("color:rgb(12,34,56)", frames[1][0])
        self.assertEqual("".join(ArtworkParser(document).text), art)
        self.assertIn("background: #ffffff", document)
        self.assertEqual(document.count("</script>"), 2)
        self.assertNotIn("\033", document)
        self.assertNotIn("alert(\"x\")</script>", document)

    def test_frame_and_byte_limits_fail_before_creating_folders(self):
        for constant, limit, frames, message in (
            ("MAX_ANIMATION_FRAMES", 2, [("@", 10)] * 3, "3000 frames"),
            ("MAX_ANIMATION_BYTES", 32, [("@", 10)], "20 MiB"),
        ):
            with self.subTest(constant=constant), patch("ascart.html_art." + constant, limit):
                with self.assertRaisesRegex(ValueError, message):
                    save_animated_html(iter(frames), self.target)
                self.assertFalse(self.target.parent.exists())

    def test_empty_invalid_and_interrupted_inputs_create_no_destination(self):
        def interrupted():
            yield "@", 10
            raise KeyboardInterrupt
        for frames, error in (([], ValueError), ([("\033[31m@", 10)], ValueError),
                              ([("@", 2147483648)], ValueError), (interrupted(), KeyboardInterrupt)):
            with self.subTest(error=error), self.assertRaises(error):
                save_animated_html(frames, self.target)
            self.assertFalse(self.target.parent.exists())

    def test_exact_file_size_limit_and_invalid_timing_fallback(self):
        frames = [("<&>", delay) for delay in (-1, 0, float("nan"), float("inf"), 25.5)]
        save_animated_html(frames, self.target)
        expected = self.target.read_bytes()
        data, _ = read_frames(self.target)
        self.assertEqual([delay for _, delay in data], [100, 100, 100, 100, 25.5])
        with patch("ascart.html_art.MAX_ANIMATION_BYTES", len(expected)):
            save_animated_html(frames, self.root / "exact.html")
        with patch("ascart.html_art.MAX_ANIMATION_BYTES", len(expected) - 1):
            with self.assertRaisesRegex(ValueError, "20 MiB"):
                save_animated_html(frames, self.root / "too-big.html")
        self.assertFalse((self.root / "too-big.html").exists())

    def test_loop_checkbox_is_optional_unchecked_and_counted_in_size_limit(self):
        frames = [("@", 100)]
        save_animated_html(frames, self.target, loop_control=True)
        data, document = read_frames(self.target)
        self.assertIn('<input id="loop" type="checkbox">', document)
        self.assertNotIn('type="checkbox" checked', document)
        size = self.target.stat().st_size
        with patch("ascart.html_art.MAX_ANIMATION_BYTES", size):
            save_animated_html(frames, self.root / "exact.html", loop_control=True)
        with patch("ascart.html_art.MAX_ANIMATION_BYTES", size - 1):
            with self.assertRaisesRegex(ValueError, "20 MiB"):
                save_animated_html(frames, self.root / "too-big.html", loop_control=True)
        self.assertFalse((self.root / "too-big.html").exists())
        save_animated_html(frames, self.root / "video.html")
        self.assertNotIn('<input id="loop"', (self.root / "video.html").read_text())
        self.assertEqual(read_frames(self.root / "video.html")[0], data)

    def test_exclusive_creation_preserves_competing_file_and_symlink(self):
        self.target.parent.mkdir()
        self.target.write_text("user data")
        with self.assertRaises(FileExistsError):
            save_animated_html([("@", 10)], self.target)
        link = self.root / "link.html"
        link.symlink_to(self.target)
        with self.assertRaises(FileExistsError):
            save_animated_html([("@", 10)], link)
        self.assertEqual(self.target.read_text(), "user data")

    @unittest.skipUnless(shutil.which("node"), "Optional JavaScript test requires Node.js")
    def test_player_play_pause_resume_replay_and_end_with_fake_clock(self):
        # A minimal DOM and fake clock test the player without opening a browser.
        harness = r'''
const assert = require("node:assert/strict");
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
let now = 0, next = 1;
const timers = new Map();
const elements = {};
for (const id of ["play", "pause", "replay", "status", "artwork", "frames"]) {
    elements[id] = {disabled: id === "pause", innerHTML: "first", textContent: "",
        addEventListener(event, callback) {this[event] = callback;}};
}
elements.frames.textContent = JSON.stringify(input.frames);
if (input.loopControl) elements.loop = {checked: false};
const context = {document: {getElementById: id => elements[id], querySelector: () => elements.artwork},
    performance: {now: () => now},
    setTimeout: (fn, delay) => { const id = next++; timers.set(id, {fn, delay}); return id; },
    clearTimeout: id => timers.delete(id)};
vm.runInNewContext(input.script, context);
function tick() { const [id, task] = timers.entries().next().value;
    timers.delete(id); now += task.delay; task.fn(); }
assert.equal(timers.size, 0);
elements.play.click();
elements.play.click();
assert.equal(timers.size, 1);
assert.equal(elements.play.disabled, true);
now = 40;
elements.pause.click();
assert.equal(timers.size, 0);
assert.equal(elements.pause.disabled, true);
now = 1000;
elements.play.click();
assert.equal([...timers.values()][0].delay, 60);
tick();
assert.equal(elements.artwork.innerHTML, "last");
tick();
assert.equal(elements.status.textContent, "Finished");
assert.equal(timers.size, 0);
elements.play.click();
assert.equal(elements.artwork.innerHTML, "first");
tick();
elements.replay.click();
assert.equal(elements.artwork.innerHTML, "first");
assert.equal(timers.size, 1);
tick(); tick();
assert.equal(elements.status.textContent, "Finished");
if (input.loopControl) {
    assert.equal(elements.loop.checked, false);
    elements.loop.checked = true;
    // Enabling loop after completion waits for Play.
    assert.equal(timers.size, 0);
    elements.play.click();
    tick(); tick();
    assert.equal(elements.artwork.innerHTML, "first");
    assert.equal(timers.size, 1);
    tick(); tick();
    assert.equal(elements.artwork.innerHTML, "first");
    elements.pause.click();
    assert.equal(timers.size, 0);
    elements.play.click();
    tick();
    elements.loop.checked = false;
    assert.equal(elements.artwork.innerHTML, "last");
    assert.equal(timers.size, 1);
    tick();
    assert.equal(timers.size, 0);
    assert.equal(elements.status.textContent, "Finished");
    elements.loop.checked = true;
    elements.replay.click();
    assert.equal(elements.artwork.innerHTML, "first");
    assert.equal(timers.size, 1);
    elements.pause.click();
}
console.log("Player controls and one-pass timing passed");
'''
        for loop_control in (False, True):
            with self.subTest(loop_control=loop_control):
                target = self.root / f"player-{loop_control}.html"
                save_animated_html([("first", 100), ("last", 200)], target, loop_control=loop_control)
                frames, document = read_frames(target)
                script = re.search(r'<script>\n(.*?)</script>', document, re.S)[1]
                result = subprocess.run([shutil.which("node"), "-e", harness], input=json.dumps({"script": script, "frames": frames, "loopControl": loop_control}), text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("passed", result.stdout)


class AnimatedHtmlCliTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.gif = self.root / "source.gif"
        pictures = [Image.new("RGB", (32, 24), color) for color in ("red", "blue", "yellow")]
        try:
            pictures[0].save(self.gif, save_all=True, append_images=pictures[1:], duration=[50, 150, 250], loop=0)
        finally:
            for picture in pictures:
                picture.close()
        self.video = self.root / "source.mp4"
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 24))
        self.assertTrue(writer.isOpened())
        try:
            for color in ((0, 0, 255), (255, 0, 0), (0, 255, 255)):
                writer.write(np.full((24, 32, 3), color, dtype=np.uint8))
        finally:
            writer.release()
        self.originals = {source: source.read_bytes() for source in (self.gif, self.video)}

    def tearDown(self):
        for source, original in self.originals.items():
            self.assertEqual(source.read_bytes(), original)

    def run_cli(self, *args, terminal=False):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["ascart", *map(str, args)]), \
             patch.object(output, "isatty", return_value=terminal), \
             patch.dict(os.environ, {"COLORFGBG": "0;15"}), \
             patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((18, 10))), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_media_option_matrix_matches_shared_converters(self):
        cases = itertools.product((self.gif, self.video), (False, True), (False, True), ("dark", "light", "auto"), (False, True), (False, True))
        for index, (source, color, border, background, custom, fitted) in enumerate(cases):
            with self.subTest(case=index):
                target = self.root / "new folder" / f"art {index}.HTML"
                options = ["--background", background, "--loop-4"]
                options += ["--color"] if color else []
                options += ["--border"] if border else []
                options += ['--chars=<&>"\''] if custom else []
                options += ["--fit"] if fitted else ["--width=10"]
                code, output, errors = self.run_cli(source, *options, "--output", target)
                self.assertEqual(code, 0, errors)
                self.assertIn(str(target), output)
                self.assertNotIn("\033", output)
                frames, document = read_frames(target)
                self.assertEqual('<input id="loop" type="checkbox">' in document, source == self.gif)
                palette = '<&>"\'' if custom else ("#%@" if color else " .:-=+*#%@")
                settings = dict(width=(15 if border else 17) if fitted else 10,
                                max_height=(6 if border else 8) if fitted else None,
                                color=color, background="dark" if background == "dark" else "light", palette=palette)
                if source == self.gif:
                    expected = gif_to_ascii(source, **settings)
                    if border:
                        expected = [(add_border(art), delay) for art, delay in expected]
                else:
                    expected = list(video_ascii_frames(source, border=border, **settings))
                self.assertEqual(len(frames), 3)
                for (markup, delay), (art, expected_delay) in zip(frames, expected):
                    self.assertEqual(markup, art_to_markup(art))
                    self.assertEqual(delay, expected_delay)
                self.assertIn("background: #000000" if background == "dark" else "background: #ffffff", document)

    def test_terminal_loop_preview_and_interrupt_do_not_duplicate_export(self):
        for source in (self.gif, self.video):
            for loops in ((), ("--loop-4",), ("--loop",)):
                target = self.root / f"{source.suffix}-{loops}.html"
                name = "play_gif" if source == self.gif else "play_video"
                with patch("ascart.cli." + name, side_effect=KeyboardInterrupt) as play:
                    code, output, errors = self.run_cli(source, *loops, "--output", target, terminal=True)
                self.assertEqual(code, 0, errors)
                self.assertEqual(play.call_args.kwargs["loops"], 0 if loops == ("--loop",) else (4 if loops else 1))
                self.assertEqual(len(read_frames(target)[0]), 3)
                self.assertIn(str(target), output)

    def test_limits_stop_save_release_reader_and_skip_preview(self):
        for source in (self.gif, self.video):
            target = self.root / "not-created" / "art.html"
            with patch("ascart.html_art.MAX_ANIMATION_FRAMES", 1), \
                 patch("ascart.cli.play_gif") as gif_play, patch("ascart.cli.play_video") as video_play:
                code, output, errors = self.run_cli(source, "--output", target, terminal=True)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("3000 frames", errors)
            self.assertFalse(target.parent.exists())
            gif_play.assert_not_called()
            video_play.assert_not_called()

    def test_video_reader_cleanup_fps_fallback_and_empty_input(self):
        for fail in (None, OSError("read failed"), KeyboardInterrupt()):
            capture = Mock()
            capture.get.return_value = float("nan")
            capture.read.side_effect = [(True, np.zeros((24, 32, 3), dtype=np.uint8)), (False, None) if fail is None else fail]
            with patch("ascart.video_art.open_video", return_value=capture), contextlib.redirect_stderr(io.StringIO()) as warnings:
                if fail is None:
                    self.assertAlmostEqual(list(video_ascii_frames(self.video))[0][1], 1000 / 30)
                else:
                    with self.assertRaises(type(fail)):
                        list(video_ascii_frames(self.video))
            self.assertIn("30 FPS", warnings.getvalue())
            capture.release.assert_called_once()
        capture = Mock()
        capture.get.return_value = 10
        capture.read.return_value = (False, None)
        with patch("ascart.video_art.open_video", return_value=capture), self.assertRaisesRegex(ValueError, "no frame"):
            list(video_ascii_frames(self.video))
        capture.release.assert_called_once()

    def test_limit_and_interrupt_close_gif_and_video_generators(self):
        for source, name in ((self.gif, "gif_ascii_frames"), (self.video, "video_ascii_frames")):
            for interrupt in (False, True):
                closed = Mock()
                def frames(*args, **kwargs):
                    try:
                        yield "@", 10
                        if interrupt:
                            raise KeyboardInterrupt
                        yield "#", 10
                    finally:
                        closed()
                target = self.root / "not-created" / "art.html"
                with patch("ascart.cli." + name, new=frames), patch("ascart.html_art.MAX_ANIMATION_FRAMES", 1):
                    code, output, errors = self.run_cli(source, "--output", target)
                self.assertEqual(code, 0 if interrupt else 2)
                self.assertEqual(output, "")
                self.assertFalse(target.parent.exists())
                closed.assert_called_once()

    def test_partial_write_error_keeps_new_file_without_success_or_preview(self):
        original_open = Path.open
        for source in (self.gif, self.video):
            target = self.root / f"{source.suffix}-partial.html"
            @contextlib.contextmanager
            def failing_open(path, mode="r", *args, **kwargs):
                with original_open(path, mode, *args, **kwargs) as file:
                    class Writer:
                        def write(self, data):
                            file.write(data[:20])
                            raise OSError(errno.ENOSPC, "No space left on device")
                    yield Writer()
            with patch("ascart.html_art.Path.open", new=failing_open), patch("ascart.cli.play_gif") as gif_play, patch("ascart.cli.play_video") as video_play:
                code, output, errors = self.run_cli(source, "--output", target, terminal=True)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("No space left", errors)
            self.assertEqual(len(target.read_text()), 20)
            gif_play.assert_not_called()
            video_play.assert_not_called()

    def test_existing_destinations_races_and_permission_failures(self):
        for source in (self.gif, self.video):
            target = self.root / f"{source.suffix}.html"
            original_open = Path.open
            def compete(path, mode="r", *args, **kwargs):
                if path == target:
                    self.assertEqual(mode, "x")
                    with original_open(path, "x") as file:
                        file.write("other program")
                return original_open(path, mode, *args, **kwargs)
            with patch("ascart.html_art.Path.open", new=compete):
                code, output, errors = self.run_cli(source, "--output", target)
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("already exists", errors)
            self.assertEqual(target.read_text(), "other program")
            self.assertEqual(self.run_cli(source, "--output", target)[0], 2)
            with patch("ascart.html_art.Path.mkdir", side_effect=PermissionError(errno.EACCES, "Permission denied")):
                code, output, errors = self.run_cli(source, "--output", self.root / f"{source.suffix}-new.html")
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("Permission denied", errors)
