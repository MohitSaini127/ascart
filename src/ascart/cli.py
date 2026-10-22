import argparse
from pathlib import Path

from ascart.image_art import inspect_image


def main():
    parser = argparse.ArgumentParser(description="Convert a photo to ASCII art.")
    parser.add_argument("path", help="Path to the image file")
    parser.add_argument(
        "--width", type=int, default=80, help="Output width in characters (default: 80)"
    )
    parser.add_argument("--output", help="Save ASCII art to a text file")
    args = parser.parse_args()
    if args.width <= 0:
        parser.error("--width must be greater than 0")
    art = inspect_image(args.path, width=args.width)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(art + "\n", encoding="utf-8")
        print("Saved ASCII art to", output_path)
    else:
        print(art)
