import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from stat import S_ISREG

import cv2
from PIL import Image, UnidentifiedImageError

from ascart import __version__
from ascart.border import add_border
from ascart.converter import COLOR_PALETTE, DEFAULT_PALETTE
from ascart.gif_art import gif_to_ascii, play_gif, save_ascii_gif
from ascart.image_art import inspect_image
from ascart.png_art import art_to_png
from ascart.text_art import text_to_ascii
from ascart.video_art import inspect_video, play_video, save_ascii_video


IMAGE_READ_ERRORS = (OSError, ValueError, EOFError, SyntaxError, Image.DecompressionBombError)


def report_file_error(parser, action, path, error):
    reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
    parser.error(f"{action} {str(path)!r}: {reason or 'invalid or incomplete file data'}")


def validate_output(output, input_path, parser):
    if output is None:
        return
    if not output.strip():
        parser.error("--output must not be empty or whitespace only")
    if "\0" in output:
        parser.error(f"Cannot validate output {output!r}: path must not contain a null character")
    output_path = Path(output)
    try:
        if input_path is not None:
            source = Path(input_path)
            if output_path.resolve() == source.resolve() or (
                output_path.exists() and source.exists() and output_path.samefile(source)
            ):
                parser.error(f"Cannot save artwork to {output!r}: output must not point to the input file")
        if output_path.is_dir():
            parser.error(f"Cannot save artwork to {output!r}: destination is a directory; choose a new filename with a supported extension")
        if output_path.exists() or output_path.is_symlink():
            parser.error(f"Cannot save artwork to {output!r}: destination already exists; choose a new filename")
    except (OSError, ValueError) as error:
        report_file_error(parser, "Cannot validate output", output, error)
    if output_path.suffix.lower() not in (".txt", ".png", ".gif", ".mp4"):
        parser.error("--output supports only .txt/.png for photos/banners, .gif for GIF input, or .mp4 for video input")


def display_art(art, output, parser, background="dark"):
    if output is not None:
        output_path = Path(output)
        try:
            # Render before creating a destination, so rendering errors leave
            # no empty output file behind.
            picture = art_to_png(art, background) if output_path.suffix.lower() == ".png" else None
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as error:
            report_file_error(parser, "Cannot save artwork to", output_path, error)
        try:
            if picture is not None:
                with output_path.open("xb") as file:
                    picture.save(file, format="PNG")
            else:
                with output_path.open("x", encoding="utf-8") as file:
                    file.write(art + "\n")
        except FileExistsError:
            parser.error(f"Cannot save artwork to {output!r}: destination already exists; choose a new filename")
        except OSError as error:
            report_file_error(parser, "Cannot save artwork to", output_path, error)
        print(art)
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
    parser = argparse.ArgumentParser(description="Create text banners, convert photos, or play GIFs and videos as ASCII art.")
    parser.add_argument("-V", "--version", action="version", version=f"ascart {__version__}", help="Show the installed version and exit")
    parser.add_argument("path", nargs="?", help="Path to a local image, GIF, or video file")
    text_inputs = parser.add_mutually_exclusive_group()
    text_inputs.add_argument("-t", "--text", type=lambda value: (value, "standard"), help="Standard text banner")
    text_inputs.add_argument("--text-slant", dest="text", type=lambda value: (value, "slant"), help="Slanted text banner")
    text_inputs.add_argument("--text-bold", dest="text", type=lambda value: (value, "banner3"), help="Thick text banner that also saves as plain text")
    parser.epilog = "Named font: --text-font-FONTNAME TEXT (for example, --text-font-small Hello)."
    sizing = parser.add_mutually_exclusive_group()
    sizing.add_argument(
        "--width", type=int, default=60, help="Output width in characters (default: 60)"
    )
    sizing.add_argument(
        "--fit", action="store_true", help="Fit output to the terminal width and height"
    )
    parser.add_argument("--output", help="Save and display artwork: .txt/.png for photos or banners, .gif for GIF input, .mp4 for videos; existing files are never overwritten")
    parser.add_argument("--border", action="store_true", help="Frame the artwork with an ASCII border (off by default)")
    looping = parser.add_mutually_exclusive_group()
    looping.add_argument("--loop", action="store_true", help="Repeat GIF or video playback until Ctrl+C")
    looping.add_argument(
        "--loop-count", type=int, help="Total terminal GIF or video playbacks; --loop-4 means --loop-count 4; saved animations contain one pass"
    )
    parser.add_argument(
        "--color", action="store_true", help="Use source colors in the terminal, PNG, GIF, or MP4 output (saved text stays plain)"
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
        value_expected = argument in ("-t", "--text", "--text-slant", "--text-bold", "--chars", "--output", "--width", "--background", "--loop-count") or (font_match is not None and "=" not in argument)
    args = parser.parse_args(arguments)
    if (args.path is None) == (args.text is None):
        parser.error("Provide either a media path or --text, but not both")
    validate_output(args.output, args.path, parser)
    output_suffix = Path(args.output).suffix.lower() if args.output is not None else None
    if args.text is not None:
        if output_suffix in (".gif", ".mp4"):
            parser.error("Photo and text output supports only .txt and .png files")
        args.text, text_font = args.text
        if not args.text.strip():
            parser.error("--text must not be empty or whitespace only")
        if not args.text.isascii() or any(not char.isprintable() for char in args.text):
            parser.error("--text currently supports printable ASCII text only")
        if args.width <= 0:
            parser.error("--width must be greater than 0")
        if args.fit or args.color or args.chars is not None or args.background != "auto" or args.loop or args.loop_count is not None:
            parser.error("Text banners support --width, --output, and --border; photo/GIF/video options do not apply")
        try:
            art = text_to_ascii(args.text, width=args.width, font=text_font)
        except ValueError as error:
            parser.error(str(error))
        if args.border:
            art = add_border(art)
        display_art(art, args.output, parser)
        return
    if args.loop_count is not None and args.loop_count <= 0:
        parser.error("Loop count must be greater than 0")
    loops = 0 if args.loop else (args.loop_count or 1)
    color = args.color and output_suffix != ".txt"
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
        if args.border:
            if width < 3 or max_height < 3:
                parser.error("Terminal is too small for --fit --border; need at least 4 columns and 5 rows")
            width -= 2
            max_height -= 2
    try:
        mode = Path(args.path).stat().st_mode
    except (OSError, ValueError) as error:
        report_file_error(parser, "Cannot read input", args.path, error)
    if not S_ISREG(mode):
        parser.error(f"Cannot read input {args.path!r}: expected a regular file")
    is_video = False
    try:
        with Image.open(args.path) as image:
            is_gif = image.format == "GIF"
            # Pillow recognizes MPEG headers but cannot decode their video frames.
            is_video = image.format == "MPEG"
    except UnidentifiedImageError:
        is_video = True
        is_gif = False
    except IMAGE_READ_ERRORS as error:
        report_file_error(parser, "Cannot read input", args.path, error)
    if is_video:
        # Confirm that unrecognized image content really contains a video frame.
        try:
            inspect_video(args.path)
        except OSError as error:
            report_file_error(parser, "Cannot read input", args.path, error)
        except (ValueError, cv2.error):
            parser.error(f"Cannot decode input {args.path!r}: unsupported or damaged media")
        except KeyboardInterrupt:
            return
        if args.output and output_suffix != ".mp4":
            parser.error("Video output supports only .mp4 files; other video output formats are not supported yet")
        interactive = sys.stdout.isatty()
        if not interactive and not args.output:
            parser.error("Video playback requires an interactive terminal")
        if args.output:
            try:
                save_ascii_video(
                    args.path, args.output, width=width, palette=args.chars, background=background,
                    max_height=max_height, color=color, border=args.border,
                )
            except FileExistsError:
                parser.error(f"Cannot save artwork to {args.output!r}: destination already exists; choose a new filename")
            except (OSError, ValueError, cv2.error) as error:
                report_file_error(parser, "Cannot save artwork to", args.output, error)
            except KeyboardInterrupt:
                return
        try:
            if interactive:
                play_video(
                    args.path, width=width, palette=args.chars, background=background,
                    max_height=max_height, color=color, loops=loops, border=args.border,
                )
        except KeyboardInterrupt:
            pass
        except (ValueError, OSError, cv2.error) as error:
            report_file_error(parser, "Cannot play video", args.path, error)
        if args.output:
            print("Saved ASCII video to", args.output)
        return
    if is_gif:
        if args.output and output_suffix != ".gif":
            parser.error("GIF output supports only .gif files; other GIF output formats are not supported yet")
        interactive = sys.stdout.isatty()
        if not interactive and not args.output:
            parser.error("GIF playback requires an interactive terminal")
        try:
            frames = gif_to_ascii(
                args.path, width=width, palette=args.chars, background=background,
                max_height=max_height, color=color,
            )
            if args.border:
                frames = [(add_border(art), duration) for art, duration in frames]
        except IMAGE_READ_ERRORS as error:
            report_file_error(parser, "Cannot decode GIF", args.path, error)
        except KeyboardInterrupt:
            return
        if args.output:
            try:
                save_ascii_gif(frames, args.output, background)
            except FileExistsError:
                parser.error(f"Cannot save artwork to {args.output!r}: destination already exists; choose a new filename")
            except (OSError, ValueError) as error:
                report_file_error(parser, "Cannot save artwork to", args.output, error)
            except KeyboardInterrupt:
                return
        try:
            if interactive:
                play_gif(frames, loops=loops)
        except KeyboardInterrupt:
            pass
        if args.output:
            print("Saved ASCII GIF to", args.output)
        return

    if output_suffix in (".gif", ".mp4"):
        parser.error("Photo and text output supports only .txt and .png files")
    if args.loop or args.loop_count is not None:
        parser.error("Loop options are only supported for GIF and video files")
    try:
        art = inspect_image(
            args.path,
            width=width,
            palette=args.chars,
            background=background,
            max_height=max_height,
            color=color,
        )
    except IMAGE_READ_ERRORS as error:
        report_file_error(parser, "Cannot convert photo", args.path, error)
    if args.border:
        art = add_border(art)
    display_art(art, args.output, parser, background)
