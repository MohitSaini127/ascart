import base64
import contextlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from ascart.cli import main
from ascart.gif_comparison import comparison_frames, save_comparison_gif, save_comparison_html


class GifComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source.gif"
        with Image.new("RGB", (16, 12), "red") as red, Image.new("RGB", (16, 12), "blue") as blue:
            red.save(self.source, save_all=True, append_images=[blue], duration=[40, 90], loop=0)
        self.original = self.source.read_bytes()

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), patch("sys.argv", ["ascart", *map(str, args)]):
            try:
                main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def frames(self):
        return comparison_frames(self.source, width=12, palette=" .@", background="dark",
                                 max_height=None, color=True, border=False)

    def test_exports_visual_option_combinations_and_preserves_timing(self):
        for suffix, color, border, background, fit in itertools.product(
            ("gif", "html"), (False, True), (False, True), ("dark", "light"), (False, True),
        ):
            with self.subTest(suffix=suffix, color=color, border=border, background=background, fit=fit):
                destination = self.root / (f"{suffix}-{color}-{border}-{background}-{fit}." + suffix)
                args = [self.source, "--compare", "--output", destination, "--width", "12",
                        "--chars", " .<&@", "--background", background]
                if color:
                    args.append("--color")
                if border:
                    args.append("--border")
                if fit:
                    args.remove("--width")
                    args.remove("12")
                    args.append("--fit")
                with patch("ascart.cli.shutil.get_terminal_size", return_value=os.terminal_size((24, 12))):
                    code, output, errors = self.run_cli(*args)
                self.assertEqual(code, 0, errors)
                self.assertIn("Saved ASCII GIF comparison", output)
                if suffix == "gif":
                    with Image.open(destination) as result:
                        self.assertEqual(result.n_frames, 2)
                        self.assertNotIn("loop", result.info)
                        durations = []
                        for index, expected in enumerate(((255, 0, 0), (0, 0, 255))):
                            result.seek(index)
                            durations.append(result.info["duration"])
                            rgb = result.convert("RGB")
                            self.assertEqual(rgb.getpixel((result.width // 4, 32 + (result.height - 32) // 2)), expected)
                            rgb.close()
                        self.assertEqual(durations, [40, 90])
                else:
                    document = destination.read_text()
                    frames = json.loads(re.search(r'<script id="frames" type="application/json">(.*?)</script>', document, re.S).group(1))
                    self.assertEqual([frame[1] for frame in frames], [40, 90])
                    self.assertIn('document.querySelector(".comparison img").src = frames[index][2]', document)
                    self.assertIn('id="loop"', document)
                    for frame, expected in zip(frames, ((255, 0, 0), (0, 0, 255))):
                        with Image.open(io.BytesIO(base64.b64decode(frame[2].split(",", 1)[1]))) as picture:
                            self.assertEqual(picture.getpixel((picture.width // 2, picture.height // 2)), expected)
                        self.assertNotIn("\x1b", frame[0])
                    self.assertNotIn(str(self.source), document)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_unsupported_options_and_existing_destinations(self):
        existing = self.root / "existing.gif"
        existing.write_bytes(b"preserve")
        link = self.root / "link.html"
        link.symlink_to(existing)
        cases = [[], ["--output", self.root / "new.png"],
                 ["--output", existing], ["--output", link], ["--output", self.source],
                 ["--output", self.root / "new.gif", "--loop-count", "0"]]
        for args in cases:
            with self.subTest(args=args):
                code, output, errors = self.run_cli(self.source, "--compare", *args)
                self.assertEqual(code, 2, errors)
                self.assertNotIn("Saved ASCII", output)
        self.assertEqual(existing.read_bytes(), b"preserve")
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertFalse((self.root / "new.gif").exists())

    def test_identical_frames_are_not_merged(self):
        destination = self.root / "repeated.gif"
        with Image.new("RGB", (16, 12), "red") as source:
            save_comparison_gif(((source, "@@", 40) for _ in range(3)), destination)
        self.assertEqual(destination.read_bytes()[:6], b"GIF89a")
        with Image.open(destination) as result:
            self.assertEqual(result.n_frames, 3)
            for index in range(3):
                result.seek(index)
                self.assertEqual(result.info["duration"], 40)

    def test_html_size_and_frame_limits_precede_destination_creation(self):
        for constant, value, expected in (("MAX_ANIMATION_BYTES", 1, "20 MiB"),
                                          ("MAX_ANIMATION_FRAMES", 1, "3000 frames")):
            destination = self.root / constant / "result.html"
            with patch("ascart.gif_comparison." + constant, value), contextlib.closing(self.frames()) as frames:
                with self.assertRaisesRegex(ValueError, expected):
                    save_comparison_html(frames, destination)
            self.assertFalse(destination.parent.exists())

    def test_exclusive_save_handles_racing_file(self):
        for saver, suffix in ((save_comparison_gif, "gif"), (save_comparison_html, "html")):
            destination = self.root / ("race." + suffix)
            destination.write_bytes(b"winner")
            with contextlib.closing(self.frames()) as frames:
                with self.assertRaises(FileExistsError):
                    saver(frames, destination)
            self.assertEqual(destination.read_bytes(), b"winner")

    def test_missing_delay_falls_back_to_100ms(self):
        with Image.new("RGB", (16, 12), "red") as image:
            image.save(self.source)
        with contextlib.closing(self.frames()) as frames:
            self.assertEqual(next(frames)[2], 100)

    def test_html_escapes_artwork_and_enforces_layout_limit(self):
        destination = self.root / "escaped.html"
        with Image.new("RGB", (16, 12), "red") as source:
            save_comparison_html([(source, '</script><script>alert("x")</script>&', 40)], destination)
        document = destination.read_text()
        self.assertEqual(document.count("</script>"), 2)
        self.assertIn("&lt;/script&gt;", document)
        for saver, suffix in ((save_comparison_gif, "gif"), (save_comparison_html, "html")):
            destination = self.root / "too-large" / ("result." + suffix)
            with patch("ascart.comparison.MAX_COMPARISON_PIXELS", 1), contextlib.closing(self.frames()) as frames:
                with self.assertRaisesRegex(ValueError, "20 million"):
                    saver(frames, destination)
            self.assertFalse(destination.parent.exists())

    @unittest.skipUnless(shutil.which("node"), "Optional player test requires Node.js")
    def test_html_player_advances_both_panels_and_loops_together(self):
        destination = self.root / "player.html"
        with contextlib.closing(self.frames()) as frames:
            save_comparison_html(frames, destination)
        document = destination.read_text()
        frames = json.loads(re.search(r'<script id="frames" type="application/json">(.*?)</script>', document, re.S)[1])
        script = re.search(r'<script>\n(.*?)</script>', document, re.S)[1]
        harness = r'''
const assert = require("node:assert/strict"), vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const elements = {}, original = {}; let task = null;
for (const id of ["play", "pause", "replay", "status", "frames", "artwork", "loop"])
    elements[id] = {checked: false, addEventListener(event, fn) {this[event] = fn;}};
elements.frames.textContent = JSON.stringify(input.frames);
elements.artwork.innerHTML = input.frames[0][0];
original.src = input.frames[0][2];
vm.runInNewContext(input.script, {
    document: {getElementById: id => elements[id],
        querySelector: selector => selector === "pre code" ? elements.artwork : original},
    performance: {now: () => 0}, setTimeout: fn => {task = fn; return 1;},
    clearTimeout: () => {task = null;}
});
function check(index) {
    assert.equal(elements.artwork.innerHTML, input.frames[index][0]);
    assert.equal(original.src, input.frames[index][2]);
}
function tick() {const next = task; task = null; next();}
check(0); assert.equal(task, null);
elements.play.click(); tick(); check(1); tick();
assert.equal(task, null); assert.equal(elements.status.textContent, "Finished");
elements.loop.checked = true; elements.replay.click(); check(0);
tick(); check(1); tick(); check(0);
elements.pause.click(); assert.equal(task, null);
elements.play.click(); tick(); check(1);
'''
        result = subprocess.run([shutil.which("node"), "-e", harness],
                                input=json.dumps({"frames": frames, "script": script}),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
