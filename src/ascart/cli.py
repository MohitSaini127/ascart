import argparse
import os
import shutil
from pathlib import Path

from ascart.converter import COLOR_PALETTE, DEFAULT_PALETTE
from ascart.image_art import inspect_image


def detect_background():
    """Use a conventional COLORFGBG hint, falling back to a dark background."""
    color_hint = os.environ.get("COLORFGBG", "")
    background_color = color_hint.split(";")[-1].strip()
    # These indexes conventionally represent light gray and white.
    # Terminal themes can redefine them, so this is only a hint.
    if background_color in ("7", "15"):
        return "light"
    return "dark"


def main():
    parser = argparse.ArgumentParser(description="Convert a photo to ASCII art.")
    parser.add_argument("path", help="Path to the image file")
    sizing = parser.add_mutually_exclusive_group()
    sizing.add_argument(
        "--width", type=int, default=60, help="Output width in characters (default: 60)"
    )
    sizing.add_argument(
        "--fit", action="store_true", help="Fit output to the terminal width and height"
    )
    parser.add_argument("--output", help="Save ASCII art to a text file")
    parser.add_argument(
        "--color", action="store_true", help="Use RGB terminal colors (saved text stays plain)"
    )
    parser.add_argument(
        "--chars",
        help="Character palette, least to most dense (default: #%%@ for color, grayscale palette otherwise)",
    )
    parser.add_argument(
        "--background",
        choices=["auto", "dark", "light"],
        default="auto",
        help="Background: auto uses COLORFGBG when available, otherwise dark (default: auto)",
    )
    args = parser.parse_args()
    color = args.color and not args.output
    if args.chars is None:
        args.chars = COLOR_PALETTE if color else DEFAULT_PALETTE
    if args.width is not None and args.width <= 0:
        parser.error("--width must be greater than 0")
    if not args.chars:
        parser.error("--chars must contain at least one character")
    if any(not character.isascii() or not character.isprintable() for character in args.chars):
        parser.error("--chars must contain only printable ASCII characters")
    background = args.background
    if background == "auto":
        background = detect_background()
    width = args.width
    max_height = None
    if args.fit:
        terminal_size = shutil.get_terminal_size(fallback=(80, 24))
        width = max(1, terminal_size.columns - 1)
        max_height = max(1, terminal_size.lines - 2)
    art = inspect_image(
        args.path,
        width=width,
        palette=args.chars,
        background=background,
        max_height=max_height,
        color=color,
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(art + "\n", encoding="utf-8")
        print("Saved ASCII art to", output_path)
    else:
        print(art)
