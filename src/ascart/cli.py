import argparse
import os
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

from ascart.converter import COLOR_PALETTE, DEFAULT_PALETTE
from ascart.gif_art import gif_to_ascii, play_gif
from ascart.image_art import inspect_image
from ascart.text_art import text_to_ascii


def display_art(art, output):
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(art + "\n", encoding="utf-8")
        print("Saved ASCII art to", output_path)
    else:
        print(art)


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
    parser = argparse.ArgumentParser(description="Create text banners, convert photos, or play GIFs as ASCII art.")
    parser.add_argument("path", nargs="?", help="Path to the image or GIF file")
    text_inputs = parser.add_mutually_exclusive_group()
    text_inputs.add_argument("--text", type=lambda value: (value, "standard"), help="Standard text banner")
    text_inputs.add_argument("--text-slant", dest="text", type=lambda value: (value, "slant"), help="Slanted text banner")
    text_inputs.add_argument("--text-slant-left", dest="text", type=lambda value: (value, "ascart-left"), help="Left-leaning text banner")
    text_inputs.add_argument("--text-slant-right", dest="text", type=lambda value: (value, "slant"), help="Right-leaning text banner (same as --text-slant)")
    text_inputs.add_argument("--text-bold", dest="text", type=lambda value: (value, "banner3"), help="Thick text banner that also saves as plain text")
    parser.epilog = "Named font: --text-font-FONTNAME TEXT (for example, --text-font-small Hello)."
    sizing = parser.add_mutually_exclusive_group()
    sizing.add_argument(
        "--width", type=int, default=60, help="Output width in characters (default: 60)"
    )
    sizing.add_argument(
        "--fit", action="store_true", help="Fit output to the terminal width and height"
    )
    parser.add_argument("--output", help="Save ASCII art to a text file")
    looping = parser.add_mutually_exclusive_group()
    looping.add_argument("--loop", action="store_true", help="Repeat GIF playback until Ctrl+C")
    looping.add_argument(
        "--loop-count", type=int, help="Total GIF playbacks; --loop-4 is shorthand for --loop-count 4"
    )
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
    arguments = []
    registered_fonts = set()
    value_expected = False
    for position, argument in enumerate(sys.argv[1:]):
        if value_expected:
            arguments.append(argument)
            value_expected = False
            continue
        if argument == "--":
            arguments.extend(sys.argv[1:][position:])
            break
        font_option = argument.split("=", 1)[0]
        font_match = re.fullmatch(r"--text-font-([A-Za-z0-9_-]+)", font_option)
        if font_match and font_option not in registered_fonts:
            font_name = font_match.group(1)
            text_inputs.add_argument(
                font_option, dest="text",
                type=lambda value, font=font_name: (value, font),
                help=f"Text banner using the {font_name} font",
            )
            registered_fonts.add(font_option)
        match = re.fullmatch(r"--loop-(\d+)", argument)
        arguments.append("--loop-count=" + match.group(1) if match else argument)
        value_expected = argument in ("--text", "--text-slant", "--text-slant-left", "--text-slant-right", "--text-bold", "--chars", "--output", "--width", "--background", "--loop-count") or (font_match is not None and "=" not in argument)
    args = parser.parse_args(arguments)
    if (args.path is None) == (args.text is None):
        parser.error("Provide either an image/GIF path or --text, but not both")
    if args.text is not None:
        args.text, text_font = args.text
        if not args.text.strip():
            parser.error("--text must not be empty or whitespace only")
        if not args.text.isascii() or any(not char.isprintable() for char in args.text):
            parser.error("--text currently supports printable ASCII text only")
        if args.width <= 0:
            parser.error("--width must be greater than 0")
        if args.fit or args.color or args.chars is not None or args.background != "auto" or args.loop or args.loop_count is not None:
            parser.error("Text banners support --width and --output; image/GIF options do not apply")
        try:
            art = text_to_ascii(args.text, width=args.width, font=text_font)
        except ValueError as error:
            parser.error(str(error))
        display_art(art, args.output)
        return
    if args.loop_count is not None and args.loop_count <= 0:
        parser.error("Loop count must be greater than 0")
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
    with Image.open(args.path) as image:
        is_gif = image.format == "GIF"
    if is_gif:
        if args.output:
            parser.error("Saving GIF frames with --output is not supported yet")
        if not sys.stdout.isatty():
            parser.error("GIF playback requires an interactive terminal")
        try:
            frames = gif_to_ascii(
                args.path, width=width, palette=args.chars, background=background,
                max_height=max_height, color=color,
            )
            loops = 0 if args.loop else (args.loop_count or 1)
            play_gif(frames, loops=loops)
        except KeyboardInterrupt:
            pass
        return

    if args.loop or args.loop_count is not None:
        parser.error("Loop options are only supported for GIF files")
    art = inspect_image(
        args.path,
        width=width,
        palette=args.chars,
        background=background,
        max_height=max_height,
        color=color,
    )
    display_art(art, args.output)
