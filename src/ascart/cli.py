import argparse

from ascart.image_art import inspect_image


def main():
    parser = argparse.ArgumentParser(description="Convert a photo to ASCII art.")
    parser.add_argument("path", help="Path to the image file")
    parser.add_argument(
        "--width", type=int, default=80, help="Output width in characters (default: 80)"
    )
    args = parser.parse_args()
    if args.width <= 0:
        parser.error("--width must be greater than 0")
    inspect_image(args.path, width=args.width)
