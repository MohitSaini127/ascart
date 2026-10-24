import base64
import contextlib
import io
import os
import re
import select
import threading
import unittest
from unittest.mock import patch

from PIL import Image

from ascart.terminal_preview import NATIVE_BACKEND, _native_graphics_supported, image_preview_backend, preview_comparison


class NativePreviewEncodingTests(unittest.TestCase):
    def test_native_support_does_not_require_external_helper(self):
        with patch("ascart.terminal_preview.sys.stdin.isatty", return_value=True), \
             patch("ascart.terminal_preview.sys.stdout.isatty", return_value=True), \
             patch("ascart.terminal_preview._native_graphics_supported", return_value=True), \
             patch("ascart.terminal_preview.shutil.which") as lookup, \
             patch("ascart.terminal_preview.subprocess.run") as run:
            self.assertEqual(image_preview_backend(), NATIVE_BACKEND)
            lookup.assert_not_called()
            run.assert_not_called()

    def test_native_transfer_encodes_real_png_in_bounded_chunks(self):
        output = io.StringIO()
        with Image.new("RGB", (32, 24), "red") as source, \
             contextlib.redirect_stdout(output), \
             patch("ascart.terminal_preview.shutil.get_terminal_size", return_value=os.terminal_size((80, 24))), \
             patch("ascart.terminal_preview.subprocess.run") as run:
            # Changing rows make the data larger than a single packet.
            art = "\n".join("@%#WMQ8 " * 8 for _ in range(30))
            preview_comparison(source, art, "dark", NATIVE_BACKEND)
            run.assert_not_called()
        packets = re.findall(r"\x1b_G([^;]*);([^\x1b]*)\x1b\\", output.getvalue())
        self.assertGreater(len(packets), 1)
        first = dict(part.split("=", 1) for part in packets[0][0].split(","))
        self.assertEqual(first["a"], "T")
        self.assertEqual(first["f"], "100")
        self.assertEqual(first["c"], "79")
        self.assertNotIn("r", first)
        self.assertEqual(first["C"], "1")
        for index, (control, payload) in enumerate(packets):
            fields = dict(part.split("=", 1) for part in control.split(","))
            self.assertEqual(fields["q"], "2")
            self.assertEqual(fields["m"], "0" if index == len(packets) - 1 else "1")
            self.assertLessEqual(len(payload), 4096)
            self.assertEqual(len(payload) % 4, 0)
        encoded = "".join(payload for _, payload in packets)
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as saved:
            saved.load()
            self.assertEqual(saved.format, "PNG")
            self.assertEqual(saved.mode, "RGB")
        self.assertTrue(output.getvalue().endswith("\033[21B\r\n"))

    def test_non_tty_probe_is_unavailable(self):
        with patch("ascart.terminal_preview.sys.stdin", io.StringIO()), \
             patch("ascart.terminal_preview.sys.stdout", io.StringIO()):
            self.assertFalse(_native_graphics_supported())


@unittest.skipUnless(os.name == "posix", "native POSIX terminal probing")
class NativePreviewProbeTests(unittest.TestCase):
    def probe(self, response):
        import pty
        import termios

        master, slave = pty.openpty()
        failures = []
        seen = []

        def terminal():
            try:
                query = b""
                while b"\x1b[c" not in query:
                    if not select.select([master], [], [], 1)[0]:
                        raise AssertionError("No complete capability query arrived")
                    query += os.read(master, 512)
                seen.append(query)
                match = re.search(rb"i=(\d+)", query)
                self.assertIsNotNone(match)
                for piece in response(match.group(1)):
                    os.write(master, piece)
            except BaseException as error:
                failures.append(error)

        worker = threading.Thread(target=terminal, daemon=True)
        try:
            original = termios.tcgetattr(slave)
            with os.fdopen(os.dup(slave), "r") as stdin, os.fdopen(os.dup(slave), "w", buffering=1) as stdout, \
                 patch("ascart.terminal_preview.sys.stdin", stdin), \
                 patch("ascart.terminal_preview.sys.stdout", stdout), \
                 patch("ascart.terminal_preview.PROBE_TIMEOUT", 0.1):
                worker.start()
                supported = _native_graphics_supported()
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertFalse(failures, failures)
            self.assertEqual(termios.tcgetattr(slave), original)
            self.assertEqual(len(seen), 1)
            self.assertIn(b"a=q,t=d,f=24;AAAA", seen[0])
            return supported
        finally:
            os.close(master)
            os.close(slave)

    def test_matching_positive_reply_and_device_attributes(self):
        self.assertTrue(self.probe(lambda identifier: [b"\x1b_Gi=" + identifier + b";OK\x1b\\\x1b[?62;4c"]))

    def test_fragmented_reply_with_additional_control_fields(self):
        self.assertTrue(self.probe(lambda identifier: [b"\x1b_", b"Gi=" + identifier + b",p=0;", b"OK\x1b", b"\\\x1b[?62;4c"]))

    def test_unsupported_terminal_device_attributes_only(self):
        self.assertFalse(self.probe(lambda identifier: [b"\x1b[?62;4c"]))

    def test_wrong_id_and_negative_response_do_not_claim_support(self):
        for response in (lambda identifier: [b"\x1b_Gi=0;OK\x1b\\\x1b[?62;4c"],
                         lambda identifier: [b"\x1b_Gi=" + identifier + b";ENOTSUP\x1b\\\x1b[?62;4c"]):
            self.assertFalse(self.probe(response))

    def test_no_reply_times_out_and_restores_terminal_state(self):
        self.assertFalse(self.probe(lambda identifier: []))
