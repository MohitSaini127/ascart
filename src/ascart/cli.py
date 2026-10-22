import argparse
import os
from pathlib import Path

from ascart.converter import DEFAULT_PALETTE
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
    parser.add_argument(
        "--width", type=int, default=80, help="Output width in characters (default: 80)"
    )
    parser.add_argument("--output", help="Save ASCII art to a text file")
    parser.add_argument(
        "--chars",
        default=DEFAULT_PALETTE,
        help="Character palette, ordered from least to most visually dense",
    )
    parser.add_argument(
        "--background",
        choices=["auto", "dark", "light"],
        default="auto",
        help="Background: auto uses COLORFGBG when available, otherwise dark (default: auto)",
    )
    args = parser.parse_args()
    if args.width <= 0:
        parser.error("--width must be greater than 0")
    if not args.chars:
        parser.error("--chars must contain at least one character")
    if any(not character.isascii() or not character.isprintable() for character in args.chars):
        parser.error("--chars must contain only printable ASCII characters")
    background = args.background
    if background == "auto":
        background = detect_background()
    art = inspect_image(
        args.path, width=args.width, palette=args.chars, background=background
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(art + "\n", encoding="utf-8")
        print("Saved ASCII art to", output_path)
    else:
        print(art)
