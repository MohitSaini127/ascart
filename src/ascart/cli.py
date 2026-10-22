import argparse

from ascart.image_art import inspect_image


def main():
    parser = argparse.ArgumentParser(description="Convert a photo to ASCII art.")
    parser.add_argument("path", help="Path to the image file")
    args = parser.parse_args()
    inspect_image(args.path)
