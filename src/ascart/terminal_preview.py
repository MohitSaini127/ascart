"""Direct Kitty-graphics comparison preview, with an optional helper fallback."""

import base64
from contextlib import closing, contextmanager
from io import BytesIO
import os
import re
import secrets
import select
import shutil
import subprocess
import sys
import time

from ascart.comparison import comparison_to_png


PREVIEW_UNAVAILABLE = (
    "Direct image preview is unavailable in this terminal. "
    "Use --output comparison.png or --output comparison.html, then open the saved file."
)
NATIVE_BACKEND = "kitty-graphics"
PROBE_TIMEOUT = 1.0


@contextmanager
def _preserve_terminal_state():
    """Restore POSIX terminal settings even if the helper times out."""
    try:
        import termios
    except ImportError:
        yield
        return
    try:
        descriptor = sys.stdin.fileno()
        settings = termios.tcgetattr(descriptor)
    except (AttributeError, OSError, ValueError, termios.error):
        yield
        return
    try:
        yield
    finally:
        try:
            termios.tcsetattr(descriptor, termios.TCSANOW, settings)
        except (OSError, ValueError, termios.error):
            pass


def _native_graphics_supported():
    """Query the real POSIX terminal; never infer support from its name."""
    try:
        import termios
        import tty
    except ImportError:
        return False
    try:
        descriptor = sys.stdin.fileno()
        if os.ttyname(descriptor) != os.ttyname(sys.stdout.fileno()):
            return False
        query_id = secrets.randbits(32) or 1
        query = f"\033_Gi={query_id},s=1,v=1,a=q,t=d,f=24;AAAA\033\\\033[c"
        with _preserve_terminal_state():
            tty.setraw(descriptor, termios.TCSANOW)
            sys.stdout.write(query)
            sys.stdout.flush()
            deadline = time.monotonic() + PROBE_TIMEOUT
            received = b""
            supported = False
            while len(received) < 8192:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([descriptor], [], [], remaining)[0]:
                    break
                chunk = os.read(descriptor, 512)
                if not chunk:
                    break
                received += chunk
                for control, message in re.findall(rb"\x1b_G([^;]*);([^\x1b]*)\x1b\\", received):
                    fields = dict(part.split(b"=", 1) for part in control.split(b",") if b"=" in part)
                    if fields.get(b"i") == str(query_id).encode("ascii"):
                        supported = message == b"OK"
                # Consume the following device-attributes reply as well, so
                # it cannot appear as stray input at the shell prompt.
                if re.search(rb"\x1b\[[?>]?[0-9;]*c", received):
                    break
            return supported
    except (AttributeError, OSError, ValueError, termios.error):
        return False


def image_preview_backend():
    """Prefer native graphics; otherwise try an available icat helper."""
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        return None
    if _native_graphics_supported():
        return NATIVE_BACKEND
    kitten = shutil.which("kitten")
    if kitten:
        command = [kitten, "icat"]
    else:
        kitty = shutil.which("kitty")
        if not kitty:
            return None
        command = [kitty, "+kitten", "icat"]
    try:
        with _preserve_terminal_state():
            result = subprocess.run(
                [*command, "--detect-support", "--detection-timeout=1", "--stdin=no"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=3, check=False,
            )
    except (OSError, subprocess.SubprocessError):
        return None
    return command if result.returncode == 0 else None


def _send_native_png(buffer):
    """Send bounded base64 chunks and leave the prompt below the image."""
    size = shutil.get_terminal_size(fallback=(80, 24))
    columns, rows = max(1, size.columns - 1), max(1, size.lines - 3)
    # Reserve space without clearing existing terminal history. C=1 keeps
    # image placement from moving the cursor; we move below it explicitly.
    sys.stdout.write("\r" + "\n" * rows + f"\033[{rows}A\r")
    buffer.seek(0)
    first = True
    try:
        chunk = buffer.read(3072)
        while chunk:
            following = buffer.read(3072)
            metadata = f"a=T,f=100,c={columns},r={rows},C=1," if first else ""
            payload = base64.b64encode(chunk).decode("ascii")
            sys.stdout.write(f"\033_G{metadata}q=2,m={1 if following else 0};{payload}\033\\")
            first = False
            chunk = following
    finally:
        sys.stdout.write(f"\033[{rows}B\r\n")
        sys.stdout.flush()


def preview_comparison(image, art, background, backend):
    """Send the composed PNG in memory; no user output file is created."""
    with closing(comparison_to_png(image, art, background)) as picture, BytesIO() as buffer:
        picture.save(buffer, format="PNG")
        sys.stdout.flush()
        if backend == NATIVE_BACKEND:
            _send_native_png(buffer)
            return
        with _preserve_terminal_state():
            subprocess.run(
                [*backend, "--stdin=yes", "--transfer-mode=stream", "--fit=both", "--align=left"],
                input=buffer.getvalue(), stdout=sys.stdout, stderr=subprocess.DEVNULL,
                timeout=10, check=True,
            )
