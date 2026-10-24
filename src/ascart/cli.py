import argparse
import math
import os
import re
import shutil
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from stat import S_ISREG

import cv2
from PIL import Image, UnidentifiedImageError

from ascart import __version__
from ascart.border import add_border
from ascart.camera_art import list_cameras, play_camera, snapshot_camera
from ascart.camera_recording import MAX_CAMERA_DURATION, RECORDING_FPS, record_camera
from ascart.comparison import comparison_to_html, comparison_to_png
from ascart.converter import COLOR_PALETTE, DEFAULT_PALETTE
from ascart.gif_comparison import comparison_frames, save_comparison_gif, save_comparison_html
from ascart.gif_art import gif_ascii_frames, gif_to_ascii, play_gif, save_ascii_gif
from ascart.html_art import MAX_ANIMATION_FRAMES, art_to_html, save_animated_html
from ascart.image_art import image_to_ascii, inspect_image
from ascart.png_art import art_to_png
from ascart.text_art import text_to_ascii
from ascart.terminal_preview import NATIVE_BACKEND, preview_gif_comparison, PREVIEW_UNAVAILABLE, image_preview_backend, preview_comparison
from ascart.video_art import inspect_video, play_video, save_ascii_video, video_ascii_frames


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
    if output_path.suffix.lower() not in (".txt", ".png", ".html", ".gif", ".mp4"):
        parser.error("--output supports .txt/.png/.html for photos/banners, .gif/.html for GIF input, or .mp4/.html for video input")


def display_art(art, output, parser, background="dark", refresh_terminal=False, comparison=None, show_art=True):
    if output is not None:
        output_path = Path(output)
        picture = None
        try:
            # Render before creating a destination, so rendering errors leave
            # no empty output file behind.
            if comparison is not None:
                picture = comparison_to_png(comparison, art, background) if output_path.suffix.lower() == ".png" else None
                document = comparison_to_html(comparison, art, background) if output_path.suffix.lower() == ".html" else None
            else:
                picture = art_to_png(art, background) if output_path.suffix.lower() == ".png" else None
                document = art_to_html(art, background) if output_path.suffix.lower() == ".html" else None
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as error:
            if picture is not None:
                picture.close()
            report_file_error(parser, "Cannot save artwork to", output_path, error)
        try:
            if picture is not None:
                with output_path.open("xb") as file:
                    picture.save(file, format="PNG")
            else:
                with output_path.open("x", encoding="utf-8") as file:
                    file.write(document if document is not None else art + "\n")
        except FileExistsError:
            parser.error(f"Cannot save artwork to {output!r}: destination already exists; choose a new filename")
        except OSError as error:
            report_file_error(parser, "Cannot save artwork to", output_path, error)
        finally:
            if picture is not None:
                picture.close()
        if refresh_terminal:
            print("\033[H\033[J", end="")
        if show_art:
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
    parser = argparse.ArgumentParser(description="Create text banners or convert photos, GIFs, videos, and a live camera to ASCII art.")
    parser.add_argument("-V", "--version", action="version", version=f"ascart {__version__}", help="Show the installed version and exit")
    parser.add_argument("path", nargs="?", help="Path to a local image, GIF, or video file")
    camera_inputs = parser.add_mutually_exclusive_group()
    camera_inputs.add_argument("--camera", nargs="?", const=0, type=int, metavar="ID", help="Live camera with the default horizontally flipped view; default ID 0; Ctrl+C stops")
    camera_inputs.add_argument("--camera-mirrored", nargs="?", const=0, type=int, metavar="ID", help="Live camera using the previous, source orientation; default ID 0; use instead of --camera")
    parser.add_argument("--list-cameras", action="store_true", help="Test local camera access (may briefly activate cameras); Linux video devices, otherwise IDs 0-9")
    parser.add_argument("--camera-duration", type=float, metavar="SECONDS", help="Record camera ASCII for 0 < SECONDS <= 300; requires a camera and new .mp4/.gif/.html output; 15 FPS, format limits apply")
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
    parser.add_argument("--output", help="Save and display artwork: .txt/.png/.html for photos, banners, or a camera snapshot; .mp4/.gif/.html with --camera-duration for camera recording; .gif/.html for GIF input, .mp4/.html for videos; existing files are never overwritten")
    parser.add_argument("--border", action="store_true", help="Frame the artwork with an ASCII border (off by default)")
    parser.add_argument("--compare", action="store_true", help="Experimental terminal preview of a still image beside ASCII art; optionally save PNG or HTML with --output (export needs no terminal image support); GIF comparison plays in native graphics terminals and optionally exports GIF or HTML")
    looping = parser.add_mutually_exclusive_group()
    looping.add_argument("--loop", action="store_true", help="Repeat GIF or video playback until Ctrl+C")
    looping.add_argument(
        "--loop-count", type=int, help="Total terminal GIF or video playbacks; --loop-4 means --loop-count 4; saved animations contain one pass"
    )
    parser.add_argument(
        "--color", action="store_true", help="Use source colors in terminal, PNG, HTML, GIF, or MP4 output (saved text stays plain)"
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
        value_expected = argument in ("-t", "--text", "--text-slant", "--text-bold", "--chars", "--output", "--width", "--background", "--loop-count", "--camera-duration") or (font_match is not None and "=" not in argument)
    args = parser.parse_args(arguments)
    if args.camera_mirrored is not None:
        args.camera = args.camera_mirrored
    if args.camera_duration is not None:
        if args.camera is None:
            parser.error("--camera-duration requires --camera or --camera-mirrored")
        if not math.isfinite(args.camera_duration) or not 0 < args.camera_duration <= MAX_CAMERA_DURATION:
            parser.error("Camera duration must be greater than 0 and at most 300 seconds")
        if args.output is None:
            parser.error("--camera-duration requires --output with a new .mp4, .gif, or .html filename")
    if sum((args.path is not None, args.text is not None, args.camera is not None, args.list_cameras)) != 1:
        parser.error("Choose one input: a media path, --text, --camera [ID], --camera-mirrored [ID], or --list-cameras")
    if args.compare:
        if args.path is None:
            parser.error("--compare supports still images or GIF files; not text, camera, or video input")
        if args.output is not None and Path(args.output).suffix.lower() not in (".png", ".gif", ".html"):
            parser.error("--compare output requires a new .png, .gif, or .html filename")
    if args.camera is not None or args.list_cameras:
        if args.list_cameras and args.output is not None:
            parser.error("--list-cameras checks devices only; --output does not apply")
        if args.loop or args.loop_count is not None:
            parser.error("Camera viewing, snapshots, and recording do not accept loop options")
        if args.camera is not None and args.camera < 0:
            parser.error("Camera ID must be 0 or greater")
        if args.camera is not None and args.camera > 2147483647:
            parser.error("Camera ID is too large; maximum is 2147483647")
    if args.list_cameras:
        if args.color or args.border or args.fit or args.chars is not None or args.background != "auto" or args.width != 60:
            parser.error("--list-cameras checks devices only; visual options apply to --camera")
        print("Checking local camera access; cameras may briefly activate.", flush=True)
        try:
            cameras = list_cameras()
        except KeyboardInterrupt:
            print("Camera check stopped.")
            return
        except (OSError, ValueError, cv2.error) as error:
            parser.error(f"Cannot list cameras: {error}")
        if cameras:
            for index in cameras:
                print(f"Camera {index}: readable (use ascart --camera {index})")
        else:
            print("No readable cameras found in the checked devices; cameras may be unavailable, busy, or blocked by permissions.")
        return
    validate_output(args.output, args.path, parser)
    output_suffix = Path(args.output).suffix.lower() if args.output is not None else None
    if args.camera_duration is not None and output_suffix not in (".mp4", ".gif", ".html"):
        parser.error("Camera recording supports only .mp4, .gif, and .html output; omit --camera-duration for a TXT/PNG snapshot")
    if args.camera_duration is not None and output_suffix == ".html" and math.ceil(args.camera_duration * RECORDING_FPS) > MAX_ANIMATION_FRAMES:
        parser.error("HTML animation exceeds 3000 frames; use a duration of at most 200 seconds")
    if args.camera is not None and args.camera_duration is None and output_suffix in (".gif", ".mp4"):
        parser.error("Camera snapshots support only .txt, .png, and .html files; use --camera-duration SECONDS with .mp4 or .gif for recording")
    if args.text is not None:
        if output_suffix in (".gif", ".mp4"):
            parser.error("Photo and text output supports only .txt, .png, and .html files")
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
    if args.camera is not None:
        if not sys.stdout.isatty() and args.output is None:
            parser.error("Camera playback requires an interactive terminal")
        try:
            settings = dict(width=width, palette=args.chars, background=background,
                            max_height=max_height, color=color, border=args.border,
                            mirrored=args.camera_mirrored is not None)
            if args.camera_duration is not None:
                print(f"Recording camera {args.camera} for {args.camera_duration:g} seconds; Ctrl+C cancels.", file=sys.stderr, flush=True)
                record_camera(args.camera, args.output, args.camera_duration, preview=sys.stdout.isatty(), **settings)
            elif args.output is not None:
                art = snapshot_camera(args.camera, preview=sys.stdout.isatty(), **settings)
            else:
                print(f"Starting camera {args.camera}; press Ctrl+C to stop.", flush=True)
                play_camera(args.camera, **settings)
        except KeyboardInterrupt:
            if args.camera_duration is not None:
                print("Camera recording cancelled.", file=sys.stderr)
            elif args.output is not None:
                print("Camera snapshot cancelled.", file=sys.stderr)
            else:
                print("Camera stopped.")
            return
        except FileExistsError:
            parser.error(f"Cannot save artwork to {args.output!r}: destination already exists; choose a new filename")
        except (OSError, ValueError, cv2.error) as error:
            parser.error(f"Cannot use camera {args.camera}: {error}")
        if args.camera_duration is not None:
            print("Saved ASCII camera recording to", args.output)
        elif args.output is not None:
            display_art(art, args.output, parser, background, refresh_terminal=sys.stdout.isatty())
        return
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
            if args.compare and not is_gif and getattr(image, "n_frames", 1) != 1:
                parser.error("--compare supports still images only; animated images are not supported yet")
    except UnidentifiedImageError:
        is_video = True
        is_gif = False
    except IMAGE_READ_ERRORS as error:
        report_file_error(parser, "Cannot read input", args.path, error)
    if args.compare and is_video:
        parser.error("--compare supports still images and GIF files; video comparison is not supported yet")
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
        if args.output and output_suffix not in (".mp4", ".html"):
            parser.error("Video output supports only .mp4 and .html files; other video output formats are not supported yet")
        interactive = sys.stdout.isatty()
        if not interactive and not args.output:
            parser.error("Video playback requires an interactive terminal")
        if args.output:
            try:
                if output_suffix == ".html":
                    with closing(video_ascii_frames(
                        args.path, width=width, palette=args.chars, background=background,
                        max_height=max_height, color=color, border=args.border,
                    )) as frames:
                        save_animated_html(frames, args.output, background)
                else:
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
    if is_gif and args.compare:
        if args.output and output_suffix not in (".gif", ".html"):
            parser.error("GIF --compare output requires a new .gif or .html filename")

        def frame_factory():
            return comparison_frames(
                args.path, width=width, palette=args.chars, background=background,
                max_height=max_height, color=color, border=args.border,
            )

        if args.output:
            try:
                with closing(frame_factory()) as frames:
                    saver = save_comparison_gif if output_suffix == ".gif" else save_comparison_html
                    saver(frames, args.output, background)
            except FileExistsError:
                parser.error(f"Cannot save artwork to {args.output!r}: destination already exists; choose a new filename")
            except IMAGE_READ_ERRORS as error:
                report_file_error(parser, "Cannot save artwork to", args.output, error)
            except KeyboardInterrupt:
                print("Comparison export cancelled.", file=sys.stderr)
                return
            print("Saved ASCII GIF comparison to", args.output)
        unavailable = "Animated comparison preview is unavailable in this terminal. Use --output comparison.gif or --output comparison.html, then open the saved file."
        try:
            if image_preview_backend() != NATIVE_BACKEND:
                if not args.output:
                    parser.error(unavailable)
                print(unavailable, file=sys.stderr)
                return
            preview_gif_comparison(frame_factory, background, loops)
        except (OSError, ValueError, subprocess.SubprocessError, EOFError, SyntaxError, Image.DecompressionBombError) as error:
            if not args.output:
                parser.error(f"Cannot preview GIF comparison: {error}. {unavailable}")
            print("Animated comparison preview failed; the saved comparison is intact. Open it to view it.", file=sys.stderr)
        except KeyboardInterrupt:
            message = "Preview cancelled; the comparison is already saved." if args.output else "Comparison preview cancelled."
            print(message, file=sys.stderr)
        return
    if is_gif:
        if args.output and output_suffix not in (".gif", ".html"):
            parser.error("GIF output supports only .gif and .html files; other GIF output formats are not supported yet")
        interactive = sys.stdout.isatty()
        if not interactive and not args.output:
            parser.error("GIF playback requires an interactive terminal")
        if output_suffix == ".html":
            try:
                with closing(gif_ascii_frames(
                    args.path, width=width, palette=args.chars, background=background,
                    max_height=max_height, color=color,
                )) as source_frames:
                    frames = ((add_border(art) if args.border else art, duration)
                              for art, duration in source_frames)
                    save_animated_html(frames, args.output, background, loop_control=True)
            except FileExistsError:
                parser.error(f"Cannot save artwork to {args.output!r}: destination already exists; choose a new filename")
            except IMAGE_READ_ERRORS as error:
                report_file_error(parser, "Cannot save artwork to", args.output, error)
            except KeyboardInterrupt:
                return
            # Decode a fresh pass only when a terminal preview is needed.
            if not interactive:
                print("Saved ASCII GIF to", args.output)
                return
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
        if args.output and output_suffix != ".html":
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
        parser.error("Photo and text output supports only .txt, .png, and .html files")
    if args.loop or args.loop_count is not None:
        parser.error("--compare loop options require a GIF input" if args.compare else "Loop options are only supported for GIF and video files")
    if args.compare:
        try:
            with Image.open(args.path) as image:
                art = image_to_ascii(image, width, args.chars, background, max_height, color)
                if args.border:
                    art = add_border(art)
                if args.output is not None:
                    display_art(art, args.output, parser, background, comparison=image, show_art=False)
                try:
                    backend = image_preview_backend()
                    if backend is None:
                        if args.output is None:
                            parser.error(PREVIEW_UNAVAILABLE)
                        print("Direct image preview is unavailable in this terminal; open the saved comparison to view it.", file=sys.stderr)
                    else:
                        preview_comparison(image, art, background, backend)
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    if args.output is None:
                        parser.error(str(error) if isinstance(error, ValueError) else PREVIEW_UNAVAILABLE)
                    print("Direct image preview failed; the saved comparison is intact. Open it to view it.", file=sys.stderr)
                except KeyboardInterrupt:
                    message = "Preview cancelled; the comparison is already saved." if args.output else "Comparison preview cancelled."
                    print(message, file=sys.stderr)
        except IMAGE_READ_ERRORS as error:
            report_file_error(parser, "Cannot convert photo", args.path, error)
        return
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
