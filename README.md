# ascart

ascart is a Python command-line learning project that creates text banners and converts photos and GIF frames into ASCII art. Characters such as `@`, `#`, and `.` represent image brightness, with optional colors taken from the original image.

The main purpose is to understand Python, image processing, code organization, Git, and GitHub by building and explaining one feature at a time. Video conversion is a future goal.

## Working features

- Text banners using pyfiglet's standard font, with width wrapping and text-file saving.
- Photo-to-ASCII conversion, with a default width of 60 characters.
- Custom output width or optional fitting to terminal width and height.
- Custom printable ASCII character palettes.
- RGB foreground color output with a denser default palette.
- Light/dark background mapping, with basic automatic selection and manual overrides.
- Saving photo conversions as plain text.
- GIF playback once, continuously, or for a specified number of playbacks.

## Setup

The project declares Python 3.10 or newer, Pillow 13.0.0 or newer, and pyfiglet version 1.0.2 or newer below version 2. Development so far has been checked with Python 3.14.8, Pillow 13.0.0, and pyfiglet 1.0.4; other versions have not yet been verified.

From the project folder, on Linux/macOS with bash or zsh:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

`venv` creates an isolated environment for project packages. Pip installs Pillow, pyfiglet, and an editable copy of ascart, making the `ascart` command available in that environment. Source-code edits take effect without reinstalling; changes to dependencies or command definitions may require rerunning the installation command.

Create the environment once. In a new terminal, enter the project folder and activate it again:

```bash
source .venv/bin/activate
```

Use `deactivate` to leave the environment. The `.venv/` folder stays on your computer and is ignored by Git.

## Text banners

```bash
ascart --text "Hello"
ascart --text "Hello world" --width 40
ascart --text "Hello" --output output/hello.txt
```

Choose either `--text` or an image/GIF path, not both. Text mode accepts non-empty printable ASCII text and uses pyfiglet's `standard` font. The default width is 60; `--width` sets the wrapping limit, not the size of individual letters. A width too small for a letter is rejected.

Text mode supports `--width` and `--output`. Image/GIF options (`--fit`, `--color`, `--chars`, manual background selection, and looping) are rejected for banners. Saved files contain the same banner as terminal output, and existing files are replaced. No additional font selection or banner color option is implemented yet.

## Photo conversion

Run these commands from the project folder using the included sample:

```bash
ascart examples/image1.png
ascart examples/image1.png --width 100
ascart examples/image1.png --fit
ascart examples/image1.png --color
ascart examples/image1.png --chars " .:*#@"
ascart examples/image1.png --background light
ascart examples/image1.png --output output/mug.txt
```

| Option | Behavior |
| --- | --- |
| No sizing option | Use 60 character columns and calculate height from the image proportions. |
| `--width NUMBER` | Choose a positive width in character columns. |
| `--fit` | Fit both terminal dimensions, reserving one column and two rows. Cannot be combined with `--width`. |
| `--color` | Use RGB foreground colors. Requires a compatible terminal. |
| `--chars "CHARACTERS"` | Choose a non-empty palette of printable ASCII characters, ordered from least to most visually dense. Quote spaces. |
| `--background auto` | Default: use a limited terminal background hint, with a dark fallback. |
| `--background light` or `--background dark` | Manually choose brightness mapping. |
| `--output PATH` | Save photo artwork as UTF-8 plain text, creating parent folders as needed. Existing file contents are replaced. |

Monochrome uses the palette ` .:-=+*#%@`, including a leading space. Colored terminal output defaults to `#%@` so more character strokes show color. An explicit `--chars` overrides either default. With `--output`, color formatting is disabled and the monochrome default is used unless a custom palette is supplied. Generated files in `output/` are ignored by Git.

Automatic background selection reads the last field of the `COLORFGBG` environment variable. Conventional color indexes 7 and 15 select light mode; other, missing, or unsupported values fall back to dark. This does not measure the actual screen, and themes can redefine those colors. Use a manual override when needed. Light mode reverses the character palette; it does not invert the image's RGB colors.

## GIF playback

Supply your own GIF and replace `path/to/animation.gif` below with its location:

```bash
ascart path/to/animation.gif --fit
ascart path/to/animation.gif --fit --color
ascart path/to/animation.gif --fit --loop
ascart path/to/animation.gif --fit --loop-4
```

- Without a loop option, playback stops after one pass.
- `--loop` repeats continuously until Ctrl+C.
- `--loop-4` plays four times in total. Other positive counts work the same way; `--loop-count 4` is also supported.
- Continuous and counted loop options cannot be combined. Loop options are only supported for GIFs.

Playback requires an interactive terminal supporting ANSI screen and cursor controls. It clears the current screen, replaces each frame, and leaves the final frame visible. Ctrl+C stops playback and restores cursor visibility.

Frame durations come from the GIF in milliseconds. Missing or zero timing uses a 100 ms fallback. The program follows the command-line loop choice rather than the GIF's loop metadata. `--output` is not supported for GIFs yet.

## How conversion works

1. Pillow opens a photo or decodes a GIF frame.
2. A grayscale copy supplies pixel brightness values from 0 to 255.
3. The image is resized for the chosen character grid. A factor of 0.5 approximately compensates for terminal characters being taller than they are wide.
4. Each brightness value selects a character from the palette.
5. For color output, a resized RGB copy supplies each character's foreground color.
6. Rows are joined into text, then printed, saved, or displayed as animation frames.

Photos and GIFs share the same image conversion function.

## Current limitations and future work

- Video conversion is not implemented.
- GIF frames are converted into memory before playback, so large animations can consume substantial memory.
- Animation timing includes conversion-independent rendering overhead; playback does not compensate for that overhead.
- Terminal fitting reads dimensions once per command. Resize the terminal and rerun to recalculate. If size detection is unavailable, fitting uses an 80-column by 24-row fallback before margins.
- A fixed width can exceed a small terminal. Use `--fit` when needed.
- Color strength depends on the chosen characters, terminal background, and font. Spaces have no visible foreground strokes.
- Background detection is limited, and friendly handling of file errors is still future work.
- Current verification uses targeted development checks; a maintained automated test suite is still to be built.

## Development history

See the [development log](docs/development-log.md) for explanations, setup steps, checks, and commit milestones. Git history records the committed changes.

For all command-line options:

```bash
ascart --help
```
