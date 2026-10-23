# ascart

ascart is a Python command-line learning project that creates text banners and converts photos, GIFs, and videos into ASCII art. Characters such as `@`, `#`, and `.` represent image brightness, with optional colors taken from the original image or frame.

The main purpose is to understand Python, image processing, code organization, Git, and GitHub by building and explaining one feature at a time.

## Working features

- Standard, slanted, bold-looking, and named-font text banners, with width wrapping and text/PNG saving.
- Photo-to-ASCII conversion, with a default width of 60 characters.
- Custom output width or optional fitting to terminal width and height.
- Optional ASCII borders for photos, text banners, GIFs, and videos.
- Custom printable ASCII character palettes.
- RGB foreground color output with a denser default palette.
- Light/dark background mapping, with basic automatic selection and manual overrides.
- Saving photo conversions as plain text or PNG pictures, including optional colors and borders.
- GIF playback once, continuously, or for a specified number of playbacks.
- Saving GIF input as an animated ASCII GIF containing one complete animation, set to play once.
- Video playback once, continuously, or for a specified number of playbacks, converting one frame at a time with optional color and terminal fitting.
- Readable messages for common input, decoding, and file-saving errors.

## Setup

The project declares Python 3.10 or newer and these dependencies:

| Package | Purpose | Declared version |
| --- | --- | --- |
| Pillow | Read photos/GIFs, resize frames, get brightness and RGB colors, and save PNG/GIF artwork. | `>=13.0.0` |
| pyfiglet | Render text using character-based banner fonts. | `>=1.0.2,<2` |
| opencv-python-headless | Decode video frames through the `cv2` module, without desktop display windows. | `>=4.12,<5` |

OpenCV also installs NumPy, which represents frames as arrays of pixel values. Development has been checked with Python 3.14.8, Pillow 13.0.0, pyfiglet 1.0.4, OpenCV 4.14.0.94, and NumPy 2.5.4; other versions have not yet been verified.

From the project folder, on Linux/macOS with bash or zsh:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

`venv` creates an isolated environment for project packages. Pip installs the dependencies above and an editable copy of ascart, making the `ascart` command available in that environment. Source-code edits take effect without reinstalling; changes to dependencies or command definitions may require rerunning the installation command.

Create the environment once. In a new terminal, enter the project folder and activate it again:

```bash
source .venv/bin/activate
```

Use `deactivate` to leave the environment. The `.venv/` folder stays on your computer and is ignored by Git.

## Text banners

```bash
ascart --text "Hello"
ascart --text-slant "Hello"
ascart --text-bold "Hello"
ascart --text-font-small "Hello"
ascart --text "Hello world" --width 40
ascart --text "Hello" --output output/hello.txt
ascart --text-bold "Hello" --output output/bold.txt
ascart --text "Hello" --border
ascart --text-slant "Hello" --border --output output/hello.png
```

Choose exactly one text-input option or a photo/GIF/video path. Each text option takes its text directly; do not add `--text` again. Text mode accepts non-empty printable ASCII text. `--text` uses `standard`, `--text-slant` uses `slant`, and `--text-bold` uses the thicker character-based `banner3` font. `--text-font-FONTNAME` selects an installed pyfiglet font, such as `small`, `big`, or `standard`; unknown names are rejected. These designs, including bold-looking strokes, are made of ordinary characters and persist in saved text without terminal styling codes.

The default width is 60; `--width` sets the wrapping limit, not the size of individual letters. A width too small for a letter is rejected. Text-input options cannot be combined with each other.

`--text-slant` uses the original right-leaning font design. Separate direction options are not supported.

Text mode supports `--width`, `--output`, and `--border`. Photo/GIF/video options (`--fit`, `--color`, `--chars`, manual background selection, and looping) are rejected for banners. Saved files contain the same banner as terminal output, including the border when selected. Saving requires a new `.txt` or `.png` filename; existing files are never overwritten. Banner color is not implemented; banner PNGs use white characters on black.

## Photo conversion

Run these commands from the project folder using the included sample:

```bash
ascart examples/image1.png
ascart examples/image1.png --width 100
ascart examples/image1.png --fit
ascart examples/image1.png --color
ascart examples/image1.png --chars " .:*#@"
ascart examples/image1.png --background light
ascart examples/image1.png --output output/penguin.txt
ascart examples/image1.png --border
ascart examples/image1.png --color --border --output output/penguin.png
```

The included sample is Tux, the Linux penguin, downloaded from [garrett/Tux](https://github.com/garrett/Tux). Its embedded metadata and the [source README](https://github.com/garrett/Tux/blob/main/README.md) state [CC0](https://creativecommons.org/publicdomain/zero/1.0/). Original illustration by Larry Ewing using GIMP; redrawn in Inkscape by Garrett LeSage, with refinement and cleanup credited upstream to IFo Hancroft. Only this PNG is bundled; supply your own files for GIF and video playback.

| Option | Behavior |
| --- | --- |
| No sizing option | Use 60 character columns and calculate height from the image proportions. |
| `--width NUMBER` | Choose a positive width in character columns. |
| `--fit` | Fit both terminal dimensions, reserving one column and two rows. Cannot be combined with `--width`. |
| `--border` | Add a plain ASCII frame around the artwork. Off by default; also works for text banners and animation frames. |
| `--color` | Use RGB foreground colors in PNG pictures or a compatible terminal. Saved `.txt` files stay plain. |
| `--chars "CHARACTERS"` | Choose a non-empty palette of printable ASCII characters, ordered from least to most visually dense. Quote spaces. |
| `--background auto` | Default: use a limited terminal background hint, with a dark fallback. |
| `--background light` or `--background dark` | Manually choose brightness mapping. |
| `--output PATH` | Show the artwork in the terminal and save it as UTF-8 plain text (`.txt`) or a PNG picture (`.png`), creating parent folders as needed. Existing destinations and input-file aliases are rejected. |

Monochrome uses the palette ` .:-=+*#%@`, including a leading space. Colored terminal, PNG, and GIF output defaults to `#%@` so more character strokes show color. An explicit `--chars` overrides either default. With `.txt` output, color formatting is disabled and the monochrome default is used unless a custom palette is supplied. Generated files in `output/` are ignored by Git.

Brightness values from 0 through 255 are divided into near-equal bands across the palette. For the three-character color palette, `#` covers 0–85, `%` covers 86–170, and `@` covers 171–255 before any light-background reversal. Similar brightness values still produce repeated characters; adding more characters does not automatically improve clarity, and apparent character density depends on the terminal font.

Automatic background selection reads the last field of the `COLORFGBG` environment variable. Conventional color indexes 7 and 15 select light mode; other, missing, or unsupported values fall back to dark. This does not measure the actual screen, and themes can redefine those colors. Use a manual override when needed. Light mode reverses the character palette; it does not invert the image's RGB colors.

## Saving a PNG picture

The output filename chooses the format: `.txt` saves characters you can open in a text editor; `.png` saves a picture of those characters. After a successful save, ascart also displays the artwork in the terminal, followed by the saved-file location. PNG saving works for photos and all text-banner styles, without extra dependencies.

```bash
ascart examples/image1.png --output output/penguin-mono.png
ascart examples/image1.png --color --border --output output/penguin-color.png
ascart examples/image1.png --background light --output output/penguin-light.png
ascart --text-bold "Hi" --border --output output/hi.png
```

Pillow draws the characters in its built-in fixed-width bitmap font, preserving spaces, rows, and borders. Every character occupies a 12-by-22-pixel cell after enlargement, with 12 pixels of outer padding on each side. `--width` still chooses character columns; it does not set pixel width. The font is fixed and can look different from your terminal font. Banner font options change the banner's character design, while this fixed font draws those characters into pixels.

Photo PNGs use black backgrounds with white characters in dark mode, or white backgrounds with black characters in light mode. Automatic background selection uses the existing terminal hint. Use `--background dark` or `--background light` for a predictable photo canvas. With `--color`, the character strokes retain the source RGB colors and the border stays neutral. PNGs are opaque RGB pictures. They contain the converted ASCII artwork, not a copy of the source photo.

PNG pictures larger than 20 million pixels are rejected before allocation; reduce `--width` or shorten the banner text. GIF input saves only as `.gif`, not `.png` or `.txt`. Video saving, including MP4 export, is not implemented.

## Optional border

Add `--border` to a photo, text, GIF, or video command to frame the artwork with ordinary ASCII characters:

```text
+-----+
|ASCII|
|ART  |
+-----+
```

Rows of different lengths are padded to align the right edge. RGB color codes do not count toward the visible width, and color is reset before the right edge so the frame uses the normal terminal foreground. Photo and banner `.txt`/`.png` output and saved GIF frames include the border. Video saving remains unsupported.

`--width` describes the artwork inside the frame; a 60-column image becomes 62 columns wide with the border. Banner width still controls wrapping, and its frame surrounds the longest rendered row. The border adds two rows as well. For photos/GIFs/videos, `--fit --border` reserves those extra dimensions within the existing terminal margins. A terminal smaller than four columns by five rows is rejected in this mode. Text banners still do not support `--fit`.

For animation, the same frame decoration is applied on every playback pass. Sources with constant frame dimensions keep a consistent frame size. Without `--border`, output follows the existing rendering path.

## GIF playback and saving

Supply your own GIF and replace `path/to/animation.gif` with its location:

```bash
ascart path/to/animation.gif --fit
ascart path/to/animation.gif --fit --color
ascart path/to/animation.gif --fit --loop
ascart path/to/animation.gif --fit --loop-4
ascart path/to/animation.gif --fit --border --color
ascart path/to/animation.gif --color --border --output output/ascii.gif
ascart path/to/animation.gif --loop-4 --output output/ascii-four-preview.gif
```

- Without a loop option, playback stops after one pass.
- `--loop` repeats continuously until Ctrl+C.
- `--loop-4` plays four times in total. Other positive counts work the same way; `--loop-count 4` is also supported.
- Continuous and counted loop options cannot be combined. Loop options work with GIFs and videos.

Playback requires an interactive terminal supporting ANSI screen and cursor controls. It clears the current screen, replaces each frame, and leaves the final frame visible. Ctrl+C stops playback and restores cursor visibility. Saving with `--output` also works without an interactive terminal; it skips playback in that case.

Frame durations come from the GIF in milliseconds. Missing or zero timing uses a 100 ms fallback. Terminal playback follows the command-line loop choice rather than the GIF's loop metadata.

Use a new `.gif` output filename to save the complete converted animation. Existing files, input-file aliases, and symbolic links are rejected. Parent folders are created as needed. `.GIF` also works. GIF input does not currently save as `.txt` or `.png`; photo/banner input does not save as `.gif`.

The output stores one pass of the source frames with their timings. It omits GIF repeat metadata, requesting one playback even if the source repeats forever. `--loop`, `--loop-4`, and `--loop-count` control only the terminal preview; they never duplicate saved frames or change the saved GIF's repeat behavior. No saved-loop setting is offered yet. External viewers can override a GIF's playback behavior.

Saving finishes before terminal playback starts. The saved-file location is printed after playback finishes, including when Ctrl+C stops continuous playback. If saving fails, no terminal preview begins. Interrupting playback leaves the completed file intact. Without an interactive terminal, only the saved-file location is printed and loop options have no playback to repeat.

Saved frames use the same fixed-width font and padding as PNG output. Color, custom palettes, backgrounds, width, terminal fitting, and borders apply to the saved artwork. Each frame is converted to at most 256 colors because that is a GIF limit; this may approximate source RGB colors. Consecutive frames that become visually identical may be combined by Pillow, preserving their combined duration. The per-picture 20-million-pixel limit also applies to rendered GIF frames. ASCII and picture frames are held in memory during export, so use smaller widths for large animations. This is one complete-animation export, not an unlimited terminal recording.

The enlarged bitmap font and dense default color characters (`#%@`) can make saved artwork look thicker than terminal text. No additional bold styling is applied. Use a custom `--chars` palette if you prefer lighter characters.

GIF's per-frame timing field allows at most 655.35 seconds. If consecutive frames become identical ASCII art, Pillow can merge their delays and exceed this limit. Saving then reports a readable timing error; use a shorter animation. As with other write failures, a partial new output file may remain.

GIF also limits each picture dimension to 65,535 pixels. Oversized rendered frames are rejected before destination creation; reduce `--width` if this happens.

## Combining options

| Combination | Result |
| --- | --- |
| Photo: color + border + custom characters + width or fit + PNG output | Supported; the saved picture and terminal preview use the selected artwork. |
| Photo: color + text-file output | Supported, but the saved text and preview are plain characters. |
| GIF: color + border + custom characters + width or fit + GIF output + terminal loop count | Supported; the file stores one animation, independently of terminal repeats. |
| Video: color + border + custom characters + width or fit + terminal loops | Supported for terminal playback; video saving is not implemented. |
| Text: banner style + width + border + TXT or PNG output | Supported. |
| Width + fit, or continuous loop + counted loop | Rejected: choose one sizing method and one loop mode. |
| Text banners + color, fit, custom characters, manual background, or looping | Rejected: those options apply to media conversion. |

For palettes beginning with `-`, use the equals form, for example `--chars=-+@`, so the argument parser treats the palette as a value. Text starting with option-like words can also use equals, for example `--text=--loop-4` renders that literal text.

## Video playback

Supply your own local video and replace `path/to/video.mp4` with its location:

```bash
ascart path/to/video.mp4
ascart path/to/video.mp4 --width 60
ascart path/to/video.mp4 --fit --color
ascart path/to/video.mp4 --fit --chars " .:*#@" --background dark
ascart path/to/video.mp4 --color --loop
ascart path/to/video.mp4 --color --loop-4
ascart path/to/video.mp4 --fit --border --color
```

The CLI detects the media type; no extra video switch is required. The default width is 60, and the same width, fitting, color, palette, and background controls used for photos apply to videos. Decoding depends on the formats and codecs supported by the installed OpenCV package. A file extension alone does not guarantee support; MP4 and MJPG AVI decoding have been checked in development.

Video plays once by default, without audio. It uses the same loop options as GIFs:

- `--loop` repeats continuously until Ctrl+C.
- `--loop-4` plays four times in total; `--loop-count 4` means the same thing. Other positive counts are supported.
- Continuous and counted loop options cannot be combined. Zero and negative counts are rejected; use `--loop` for continuous playback.

Playback requires an interactive terminal supporting ANSI controls, clears the screen, replaces frames, and leaves the last frame visible. Ctrl+C stops playback, closes the video reader, and restores cursor visibility. Video `--output` is not supported yet.

OpenCV reads one frame at a time. Each frame is converted and displayed before reading the next, so ascart does not collect the whole video's converted frames in memory. It uses the video's reported FPS (frames per second) to calculate the time between frames, subtracting the time already spent reading, converting, and printing. Unknown FPS triggers a warning and a 30 FPS fallback.

For each repeat, the previous video reader is closed and a new one opens the file from the beginning. This keeps memory usage independent of the number of repetitions, though reopening can add a short pause between playbacks. If reopening fails or a pass has no decodable frames, playback stops with an error instead of retrying endlessly.

For inspection from Python, `ascart.video_art.inspect_video(path)` returns dimensions, reported FPS/frame count, and estimated duration. Unknown metadata is returned as `None`. Duration is estimated from frame count divided by FPS.

## File errors

Common file and decoding failures produce a message containing the operation, file path, and reason. For example:

```text
ascart: error: Cannot convert photo 'broken.png': image file is truncated
ascart: error: Cannot save artwork to 'readonly.txt': Permission denied
```

The CLI prints usage and the error to standard error, then exits with status 2. It does not print a Python traceback for these handled failures or a success message when saving fails. Successful commands exit with status 0. Exact operating-system and decoder wording can vary.

| Message | What to do |
| --- | --- |
| No such file or directory | Check the input path and your current folder. |
| Permission denied | Choose an input you can read or an output location you can write to. |
| Expected a regular file / Is a directory | Provide a file path, including a filename for output. |
| Image file is truncated | Use a complete, undamaged copy of the source. |
| Unsupported or damaged media | Check the file and whether its format/codec is supported. |
| File exists while creating an output folder | Check whether a normal file is blocking one of the parent folders. |
| Destination already exists | Choose a new output filename; ascart does not overwrite or automatically number files. |
| Output must not point to the input file | Use a different destination, not the source or a link to it. |
| Output currently supports only .txt and .png for photos/banners, or .gif for GIF input | Match the output format to the input; MP4 export is not implemented. |
| GIF output supports only .gif files | Use a new `.gif` filename for GIF input. |
| PNG would exceed 20 million pixels | Reduce `--width` or shorten the banner text. |
| No space left on device | Free storage space or choose another output location. |

If Pillow cannot identify a photo/GIF, ascart checks whether OpenCV can decode a video frame before treating the input as a video. This avoids reporting video-only option errors for an unrelated or unreadable media file. This check does not verify every frame in a video.

Photo and text saving share the same rules. Without `--output`, artwork is displayed in the terminal. With `--output`, artwork is saved and then displayed in the terminal, followed by the saved-file location. A non-empty path ending in `.txt` or `.png` is required (uppercase extensions also work). The terminal preview uses the same artwork: `.txt` saves and previews remain plain, while colored PNG saves also show colored characters in the terminal. If saving fails, ascart reports the error without printing a preview or success message. Quote paths containing spaces. Empty or whitespace-only arguments and unsupported extensions are rejected before conversion or folder creation. Repeating a save command with the same destination produces an error; choose a new filename.

Input/output aliases, existing files, directories, and existing symbolic links are rejected as destinations. Parent folders are created when possible. Files are opened in exclusive creation mode, which also refuses replacement if a destination appears after validation. Input media is opened for reading. A failure during writing or closing can leave a partial new file, but no success message is printed and existing files are not overwritten. These protections also apply to GIF saving. Automatic numbering, overwriting, and video export are not implemented.

## How conversion works

1. Pillow opens a photo or decodes a GIF frame. For video, OpenCV decodes a frame, its BGR color order is changed to RGB, and Pillow receives the resulting image.
2. A grayscale copy supplies pixel brightness values from 0 to 255.
3. The image is resized for the chosen character grid. A factor of 0.5 approximately compensates for terminal characters being taller than they are wide.
4. Each brightness value selects a character using `brightness * len(palette) // 256`. Integer division gives the palette position, allocating near-equal brightness bands. Brightness must be an integer in the range 0–255, as supplied by Pillow's grayscale pixels.
5. For color output, a resized RGB copy supplies each character's foreground color.
6. Rows are joined into text, then printed, saved, or displayed as animation frames.

Photos, GIFs, and videos share the same image conversion function.

## Current limitations and future work

- Video playback has no audio or export yet. Codec availability depends on the OpenCV installation.
- Video timing uses a single reported FPS; variable-frame-rate timing is approximate. Slow processing or terminal output slows playback because frames are not skipped, and small scheduling delays can accumulate.
- GIF frames are converted into memory before playback, and GIF export also holds rendered picture frames in memory. Large animations can consume substantial memory.
- GIF playback does not compensate for terminal rendering overhead.
- Terminal fitting reads dimensions once per command. Resize the terminal and rerun to recalculate. If size detection is unavailable, fitting uses an 80-column by 24-row fallback before margins.
- A fixed width can exceed a small terminal. Use `--fit` when needed.
- Color strength depends on the chosen characters, terminal background, and font. Spaces have no visible foreground strokes.
- Automatic background detection still relies on a limited terminal hint.

## Running tests

With the virtual environment active:

```bash
python -B -m unittest discover -s tests -v
python -m pip check
```

The suite checks video inspection, MP4/AVI decoding, color conversion, timing, counted and continuous playback, cleanup after interruption or failed restarts, rejected options, and selected photo/GIF/text regressions. It creates temporary media that is deleted afterward. The real decoding tests require working MP4 and MJPG encoders in OpenCV. Automated checks do not replace viewing the artwork in your own terminal.

Converter tests cover palette endpoints and boundaries, balanced band sizes, monotonic brightness mapping, custom and single-character palettes, and color/light-background behavior on a controlled grayscale image.

Border tests cover visible widths with ANSI colors, row padding, saved text, terminal margins, tiny-terminal errors, counted animation playback, and interruption cleanup.

PNG tests check fixed character cells, blank rows/spaces, RGB strokes, light/dark canvases, neutral borders, all banner styles, uppercase extensions, the size limit, no-overwrite protection including links and competing creation, and readable save failures. GIF/video PNG export is rejected before creating output folders, including with loop options.

GIF export tests read back actual saved animations to check frame timing, source-loop removal, colors, borders, fitting, missing-timing fallback, merged identical frames, and independence from terminal loop counts. They also cover saving without an interactive terminal, completed-file preservation on playback interruption, wrong input/output combinations, existing-file/link protection, competing creation, truncated input, rendering failures, permission errors, and partial writes. Fixtures and outputs stay in temporary directories.

The combination suite exercises 1,344 option combinations: 216 photo cases, 864 GIF cases (including expected non-interactive playback rejections), 216 real MP4 playback cases, and 48 text-banner cases. It crosses colors, borders, automatic/manual backgrounds, default/custom palettes, default/explicit/fitted sizing, supported save formats, terminal availability, and loop modes where applicable. It checks displayed grids and reopens saved files to verify dimensions, timing, and one-pass GIF metadata. Additional cases check invalid combinations, option-like text, background hints, and malformed paths. Source-media SHA-256 hashes must remain unchanged. This covers the listed scenarios; it is not a guarantee for every possible file or codec.

File-error tests use real truncated PNG/GIF data and invalid save paths, plus simulated permission and disk-space failures. They verify successful saving, rejection of existing destinations and source aliases, exclusive creation when another file appears during saving, and partial-new-file behavior. They also ensure unexpected programming errors are not hidden by a catch-all exception handler. Test media and outputs are created in temporary directories.

## Development history

See the [development log](docs/development-log.md) for explanations, setup steps, checks, and commit milestones. Git history records the committed changes.

For all command-line options:

```bash
ascart --help
```
