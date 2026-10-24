"""Optional direct comparison preview through Kitty's image-display helper."""

from contextlib import closing, contextmanager
from io import BytesIO
import shutil
import subprocess
import sys

from ascart.comparison import comparison_to_png


PREVIEW_UNAVAILABLE = (
    "Direct image preview is unavailable in this terminal. "
    "Use --output comparison.png or --output comparison.html, then open the saved file."
)


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


def image_preview_backend():
    """Return a working icat command after a bounded capability check."""
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        return None
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


def preview_comparison(image, art, background, backend):
    """Send the composed PNG in memory; no user output file is created."""
    with closing(comparison_to_png(image, art, background)) as picture, BytesIO() as buffer:
        picture.save(buffer, format="PNG")
        sys.stdout.flush()
        with _preserve_terminal_state():
            subprocess.run(
                [*backend, "--stdin=yes", "--transfer-mode=stream", "--fit=both", "--align=left"],
                input=buffer.getvalue(), stdout=sys.stdout, stderr=subprocess.DEVNULL,
                timeout=10, check=True,
            )
