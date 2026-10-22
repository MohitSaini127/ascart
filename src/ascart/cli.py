import argparse
from pathlib import Path

from ascart.converter import DEFAULT_PALETTE
from ascart.image_art import inspect_image


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
    args = parser.parse_args()
    if args.width <= 0:
        parser.error("--width must be greater than 0")
    if not args.chars:
        parser.error("--chars must contain at least one character")
    if any(not character.isascii() or not character.isprintable() for character in args.chars):
        parser.error("--chars must contain only printable ASCII characters")
    art = inspect_image(args.path, width=args.width, palette=args.chars)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(art + "\n", encoding="utf-8")
        print("Saved ASCII art to", output_path)
    else:
        print(art)
