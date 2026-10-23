# Development log

This log explains how ascart is being built and what we learn along the way. It complements Git history by recording setup commands and the reasons behind our decisions.

The entries below reconstruct the steps completed before this log was written, using our discussion and the first commit. They are not separate commits. Future entries will be added as we work.

## 1. Project idea and structure

We chose to build a Python command-line tool for creating ASCII art from text, photos, GIFs, and videos. The main goal is to understand Python, image processing, Git, and GitHub through small, explained steps.

We created the basic structure:

- `README.md` for the project introduction, feature plan, and eventual setup instructions.
- `.gitignore` for files that should stay outside version control.
- `pyproject.toml` for future project metadata and dependency declarations.
- `docs/development-log.md` for this learning record.
- `examples/` for sample inputs.
- `src/ascart/` for the Python package, with empty modules for terminal commands and the different conversion types.
- `tests/test_converter.py` as a placeholder for future checks of the conversion logic.

We initially left the files empty, then wrote the README introduction and feature plan. No conversion code had been written at the time of the first commit.

## 2. Python environment and Pillow

The user checked the installed Python version:

```bash
python3 --version
```

Then created and activated a virtual environment from the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

We learned that `venv` creates the environment's files, including its activation script. Activation selects that environment for the current terminal. After opening a new terminal or restarting the computer, we activate the existing environment again rather than recreate it.

The user installed Pillow and confirmed that its image module could be imported:

```bash
python -m pip install Pillow
python -c "from PIL import Image; print('Pillow is ready')"
```

Pillow will open images, resize them, convert them to grayscale, and provide pixel data. Our own code will map brightness values to characters. The installed package is named Pillow, while its import name is `PIL`; `Image` is a module within that package.

We discussed uv as an alternative and chose pip for the initial learning steps. We also explained the `-m` flag, shell quoting, Python's case sensitivity, and the `with` statement for automatic resource cleanup.

Pillow was installed locally; its dependency declaration has not yet been added to `pyproject.toml`.

## 3. Feature plan and sample image

We agreed to keep basic usage simple while offering optional controls:

- Adjustable output width to control the number of characters and image detail.
- Automatic fitting to the terminal's width and height.
- Automatic brightness mapping for light or dark backgrounds where detection works, with a manual override and a fallback to be defined.
- Saving plain ASCII text without terminal color codes.
- Custom character palettes.
- Optional color output based on the source image.

These are planned features, not implemented behavior. We will start with a single photo, then reuse the image conversion logic for GIF and video frames. Text banners will use a separate approach.

We generated an unbranded blue mug image on a light background using the built-in image generator. It was initially saved as `examples/sample-mug.png`; the sample included in the first commit is `examples/image1.png`. Its clear silhouette and contrast will help test conversion, and its color will help test color output later.

## 4. Git setup and first commit — 22 October 2026

The user added these rules to `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
output/
```

These rules exclude the local environment, Python caches, and generated output. Ignore rules can be written before the matching files or folders exist.

The user initialized Git and inspected its state:

```bash
git init -b main
git status
```

Next, the user staged the project files:

```bash
git add .
git status
```

We learned that staging selects the changes for the next commit; it does not save a commit or upload files.

The first commit attempt stopped because Git did not have an author identity. We explained how to set a repository-local name and email using `git config user.name` and `git config user.email`. After the identity issue was resolved, the user retried:

```bash
git commit -m "Set up project structure and feature plan"
```

The commit succeeded:

- Commit ID: `6f8bd4b`.
- Message: `Set up project structure and feature plan`.
- Recorded time: 22 October 2026, 10:02:16 AM, India time (UTC+05:30).
- Included 14 files: the structure, README, ignore rules, and sample image. The development log and Python files were still empty in this snapshot.

The user ran `git status` and confirmed that the working tree was clean. We also explained `git log --oneline` for short commit IDs and messages, and `git log` for fuller details.

This commit is local. No GitHub remote setup or upload has been completed in our recorded steps.

## 5. Writing this log — 22 October 2026

With the user's permission, we filled this file with the completed steps above. This edit comes after commit `6f8bd4b` and is not part of that snapshot. No new commit was made while writing the log.

The next coding step is to open the sample photo with Pillow and inspect its size and color mode before implementing conversion.

## 6. Saving the initial development log

The user staged and committed the log:

```bash
git add docs/development-log.md
git commit -m "Document initial setup and learning progress"
```

The successful commit was `3dbd655`. We clarified that `git add` stages changes, while `git commit` saves the staged snapshot.

## 7. First Python function: inspect an image — 22 October 2026

With the user's approval, we added `inspect_image(path)` to `src/ascart/image_art.py`:

```python
from PIL import Image


def inspect_image(path):
    with Image.open(path) as image:
        print("Size:", image.size)
        print("Color mode:", image.mode)
```

We explained imports, function definitions, the `path` parameter, indentation, and the `with` block that closes the image file automatically. We also learned that `image.size` gives a width-and-height tuple and `image.mode` describes how colors are stored.

The function was run successfully on the sample. The user also ran this command from the project folder with the virtual environment activated:

```bash
PYTHONPATH=src python -c "from ascart.image_art import inspect_image; inspect_image('examples/image1.png')"
```

`PYTHONPATH=src` tells Python where to find our package for this command, since the project has not been installed yet. The import loads the function, and the function call runs it on the sample image.

The output was:

```text
Size: (1254, 1254)
Color mode: RGB
```

The user confirmed that it worked. This verifies image opening and inspection; ASCII conversion is not implemented yet. The next coding step is grayscale conversion to obtain pixel brightness values.

This log entry and the function are ready to stage and commit. No commit was made while writing this entry.

## 8. Saving image inspection

The user committed the image-inspection function and its learning notes in commit `d21ca92`, with the message `Add image inspection with Pillow`.

## 9. First photo-to-ASCII conversion — 22 October 2026

We added the following steps gradually, with the user's approval before each code change.

### Grayscale conversion

Inside the image-opening `with` block in `src/ascart/image_art.py`, we added:

```python
grayscale = image.convert("L")
print("Grayscale mode:", grayscale.mode)
print("First pixel brightness:", grayscale.getpixel((0, 0)))
```

`grayscale` is a variable holding a new image in Pillow's 8-bit grayscale mode, `L`. Each pixel has a brightness from 0 (black) to 255 (white). The original color image remains available for future color output; the source file is not overwritten.

The sample's top-left pixel, at coordinates `(0, 0)`, had brightness 245, which is close to white.

### Resizing

We added:

```python
width = 80
aspect_ratio = image.height / image.width
height = max(1, int(width * aspect_ratio * 0.5))
resized = grayscale.resize((width, height))

print("Resized size:", resized.size)
```

The width is temporarily fixed at 80 pixels, representing 80 character columns. The aspect ratio preserves the relationship between image height and width. The factor `0.5` approximately compensates for terminal characters being taller than they are wide. `int` produces a whole-number height, and `max(1, ...)` prevents a height of zero.

The square sample became an 80-by-40 grayscale image. Automatic terminal fitting and adjustable width are still planned.

### Brightness-to-character mapping

We added our first function to `src/ascart/converter.py`:

```python
def brightness_to_character(brightness):
    palette = " .:-=+*#%@"
    index = brightness * (len(palette) - 1) // 255
    character = palette[index]
    return character
```

The palette is ordered from least to most visually dense. The formula maps integer brightness values from 0–255 to palette positions from 0–9. Python indexes start at zero, and `//` performs whole-number division. `return` sends the selected character back to the caller.

We checked that 0 maps to a space, 128 maps to `=`, and 255 maps to `@`. An earlier approximate explanation suggested `+` for 128; the actual formula gives `=`.

This mapping currently suits a dark terminal background. Automatic inversion and custom palettes have not been implemented.

### Connecting the converter to the image

In `image_art.py`, we imported the function:

```python
from ascart.converter import brightness_to_character
```

After resizing, we added:

```python
for y in range(height):
    row = ""

    for x in range(width):
        brightness = resized.getpixel((x, y))
        row += brightness_to_character(brightness)

    print(row)
```

The outer loop visits each row. The inner loop visits each pixel across that row, reads its brightness, and appends the corresponding character to a string. The completed row is then printed.

### Verification and current limits

We ran the conversion, and the user independently ran the same function from the project folder with the virtual environment activated:

```bash
PYTHONPATH=src python -c "from ascart.image_art import inspect_image; inspect_image('examples/image1.png')"
```

The output showed:

```text
Size: (1254, 1254)
Color mode: RGB
Grayscale mode: L
First pixel brightness: 245
Resized size: (80, 40)
```

This was followed by 40 rows of 80 ASCII characters. The user confirmed the result and shared the output, with the mug's outline and handle visible. The bright background mostly became `%` because its brightness values fell below the final `@` threshold.

The working pipeline is now: open image, convert to grayscale, resize, map brightness to characters, and print rows. It still uses the learning function name `inspect_image` and prints diagnostic information. The command-line interface, dependency declaration, saving, color, custom palettes, background detection, GIFs, and videos remain unimplemented.

No commit was made while writing this entry. The two changed Python files and this log are ready to stage and commit as the first photo-to-ASCII milestone.

## 10. Saving the first ASCII conversion

The user committed the photo conversion and its learning notes in commit `7be9b94`, with the message `Convert sample photo to grayscale ASCII art`.

## 11. Command-line entry point — 22 October 2026

With the user's approval, we added code to two previously empty files:

- `src/ascart/cli.py` imports Python's built-in `argparse` module and defines `main()`. It creates an argument parser, requires an image `path`, reads the command-line arguments, and calls `inspect_image(args.path)`.
- `src/ascart/__main__.py` imports `main` and calls it under the `if __name__ == "__main__":` guard. Python uses this file as the package entry point when running `python -m ascart`.

We explained each line and left the existing conversion behavior unchanged. The user no longer needs to type Python import statements to start a conversion.

From the project folder, with the virtual environment activated, the new command is:

```bash
PYTHONPATH=src python -m ascart examples/image1.png
```

`PYTHONPATH=src` makes our source package discoverable for this command because the project has not been installed yet. `-m ascart` runs the package's entry point, and the remaining argument supplies the image path.

We tested this command successfully. The user also ran it and confirmed that ASCII art was generated.

We checked the automatically generated help:

```bash
PYTHONPATH=src python -m ascart --help
```

It shows the required `path` argument, the program description, and the built-in help option. No additional dependency was needed because `argparse` is included with Python.

We also explained how to check environment activation using the usual `(.venv)` prompt marker and `which python`. For this environment, the Python path should point to the project's `.venv/bin/python`.

The program still prints diagnostic image information and uses a fixed width of 80. The next planned feature is a `--width` option for controlling the output's character columns and detail.

No commit was made while writing this entry. The command-line files and this log are ready to stage and commit together.

## 12. Saving the command-line entry point

The user committed the entry point and its learning notes in commit `4312b81`, with the message `Add command-line entry point for image conversion`.

## 13. Adjustable output width — 22 October 2026

With the user's approval, we added an optional `--width` argument in `src/ascart/cli.py`:

```python
parser.add_argument(
    "--width", type=int, default=80, help="Output width in characters (default: 80)"
)
```

`type=int` converts the argument to an integer and rejects non-integer input. `default=80` keeps the existing width when the option is omitted. The help text explains the option in `--help`.

After parsing, we reject zero and negative widths and pass the chosen width to the image function:

```python
if args.width <= 0:
    parser.error("--width must be greater than 0")
inspect_image(args.path, width=args.width)
```

In `src/ascart/image_art.py`, we changed the function definition to `inspect_image(path, width=80)` and removed the internal `width = 80` assignment. The existing height calculation and resizing now use the supplied width. We explained default parameters and passing a value using the keyword argument `width=`.

We verified that `--width 100` produces 50 rows of 100 characters for the square sample. We also checked that `--width 0` exits with an argument error rather than attempting conversion.

The user tried the larger output and found it too big. After discussing smaller widths, the user reported that 60 looked good. The sample command is:

```bash
PYTHONPATH=src python -m ascart examples/image1.png --width 60
```

For this square image, the calculated dimensions are 60 columns by 30 rows. A larger width gives more character columns and detail; a smaller width produces a smaller image. The default remains 80, and automatic terminal fitting is still planned.

No commit was made while writing this entry. The width changes and this log are ready to stage and commit together.

## 14. Saving adjustable width

The user committed the width feature and its notes in commit `f29057b`, with the message `Add adjustable ASCII output width`.

## 15. Saving ASCII art to a text file — 22 October 2026

With the user's approval, we added optional text-file output. An earlier proposed command failed with "unrecognized arguments" because `--output` had not yet been implemented; we clarified this before making the changes.

In `src/ascart/image_art.py`, the conversion function now collects completed rows in a list instead of printing each row:

```python
rows = []
# After building each row:
rows.append(row)
# After building all rows:
return "\n".join(rows)
```

`append` adds a row to the list. `join` combines the rows into one string separated by newline characters, and `return` sends that string back to the caller. We removed the diagnostic size, mode, and pixel prints so output contains only artwork. The function is still named `inspect_image`, although it now returns converted art.

In `src/ascart/cli.py`, we imported `Path` from Python's built-in `pathlib` module and added:

```python
parser.add_argument("--output", help="Save ASCII art to a text file")
```

After conversion, the command-line function chooses whether to save or print:

```python
art = inspect_image(args.path, width=args.width)
if args.output:
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(art + "\n", encoding="utf-8")
    print("Saved ASCII art to", output_path)
else:
    print(art)
```

We explained that `Path` represents a filesystem path, `.parent` refers to its containing folder, and `mkdir` creates missing folders. `parents=True` allows creating intermediate folders, while `exist_ok=True` accepts folders that already exist. `write_text` saves UTF-8 text with a final newline. If the target file already exists, its contents are replaced. Without `--output`, the artwork is printed in the terminal.

We checked that terminal output and saved text match exactly for the sample at width 60: 30 rows of 60 characters, with no diagnostic messages. We also verified automatic creation of a missing output folder using a temporary test location.

The user successfully ran:

```bash
PYTHONPATH=src python -m ascart examples/image1.png --width 60 --output output/mug.txt
cat output/mug.txt
```

The user confirmed that the saved artwork was visible. The generated `output/` folder is excluded by our existing `.gitignore` rule. No new dependency was needed.

No commit was made while writing this entry. The two changed Python files and this log are ready to stage and commit together.

## 16. Saving plain text output

The user committed text-file output and its notes in commit `bfb191e`, with the message `Add plain text output for ASCII art`.

## 17. Custom character palettes — 22 October 2026

With the user's approval, we added the optional `--chars` argument. The original palette remains the default when this option is omitted.

In `src/ascart/converter.py`, we introduced a shared value:

```python
DEFAULT_PALETTE = " .:-=+*#%@"
```

Uppercase names conventionally identify constants: values intended to stay unchanged. Python does not enforce that convention. `brightness_to_character` now accepts `palette=DEFAULT_PALETTE` as a parameter instead of assigning a fixed palette inside the function. Its existing brightness formula works with different palette lengths.

In `src/ascart/image_art.py`, we imported the default palette, added the same optional parameter to `inspect_image`, and passed it to `brightness_to_character` for each pixel.

In `src/ascart/cli.py`, we added `--chars` with the shared default. The parser rejects empty palettes and characters that are non-ASCII or non-printable, including newlines and tabs. We pass the accepted value using:

```python
art = inspect_image(args.path, width=args.width, palette=args.chars)
```

We explained how the palette travels from the command-line argument to the image function and then to the pixel converter. Users should order characters from least to most visually dense; that order is supplied by the user rather than automatically measured. Quoting the palette preserves spaces as part of the argument.

The example command was:

```bash
PYTHONPATH=src python -m ascart examples/image1.png --width 60 --chars " .:*#@"
```

We checked that the default endpoints still map 0 to a space and 255 to `@`. With the custom palette `01`, we verified the endpoint mapping and confirmed that the sample output contained only those two characters in 30 rows of 60 columns. We also verified rejection of empty, newline, and non-ASCII palettes.

The user ran the feature and reported completion. No new dependency was needed. No commit was made while writing this entry; the three changed Python files and this log are ready to stage and commit together.

## 18. Saving custom character palettes

The user committed the custom palette feature and its notes in commit `fd08cb3`, with the message `Add custom ASCII character palettes`.

## 19. Manual background selection — 22 October 2026

With the user's approval, we implemented manual light/dark background selection as the first step toward automatic brightness mapping. Automatic detection remains planned; this change does not detect the terminal background.

In `src/ascart/cli.py`, we added:

```python
parser.add_argument(
    "--background",
    choices=["dark", "light"],
    default="dark",
    help="Terminal background (default: dark; automatic detection not yet available)",
)
```

`choices` restricts the option to the two supported values. The default remains `dark` to preserve existing output. The parsed value is passed to `inspect_image` using `background=args.background`.

In `src/ascart/image_art.py`, we added a `background="dark"` parameter and reversed the palette for a light background:

```python
if background == "light":
    palette = palette[::-1]
```

We explained that the slice `[::-1]` reverses a sequence. Dark-background mode uses dense characters for bright pixels; light-background mode uses dense characters for dark pixels. This changes character selection, not the source image or its colors. Custom palettes are reversed in the same way.

The user compared the modes using:

```bash
PYTHONPATH=src python -m ascart examples/image1.png --width 60 --background light
PYTHONPATH=src python -m ascart examples/image1.png --width 60 --background dark
```

We verified that light mode matches conversion with a reversed palette, the default matches explicit dark mode, and custom palettes work with reversal. We checked that output remains 60 columns by 30 rows and invalid background choices are rejected. The user confirmed that the feature worked.

No new dependency was needed. No commit was made while writing this entry. The two changed Python files and this log are ready to stage and commit together before implementing automatic detection.

## 20. Saving manual background selection

The user committed the manual background modes and their notes in commit `2db4e66`, with the message `Add light and dark background modes`.

## 21. Basic automatic background selection — 22 October 2026

With the user's approval, we added `detect_background()` to `src/ascart/cli.py`, using Python's built-in `os` module:

```python
def detect_background():
    color_hint = os.environ.get("COLORFGBG", "")
    background_color = color_hint.split(";")[-1].strip()
    if background_color in ("7", "15"):
        return "light"
    return "dark"
```

Some terminals provide `COLORFGBG` as an environment variable describing color indexes. `os.environ.get` reads it, using an empty string when absent. `split(";")[-1]` selects its last field as the background hint, and `strip()` removes surrounding whitespace.

Indexes 7 and 15 conventionally represent light gray and white, so we choose light mode for those values. Other values, including missing, malformed, and unsupported hints, fall back to dark. This is a limited heuristic, not a direct measurement of the terminal background: not all terminals provide the variable, and themes can redefine palette colors. Our research reference was the [ncurses FAQ](https://invisible-island.net/ncurses/ncurses.faq.html), which discusses `COLORFGBG` and its limitations.

We added `auto` to the `--background` choices and made it the default. After argument parsing, the CLI resolves `auto` through `detect_background()` and passes the resulting `light` or `dark` value to the existing conversion function. Explicit manual choices skip detection.

The default command is now:

```bash
PYTHONPATH=src python -m ascart examples/image1.png --width 60
```

Users can explicitly request `--background auto`, or override the result with `--background light` or `--background dark`. No terminal configuration was modified.

We tested conventional light/dark hints, missing and unsupported values, and a three-field hint. We also verified through command-line runs that automatic mode selects the corresponding manual output and that manual overrides work independently of the hint. The user ran the feature and confirmed that it worked; this confirmation alone does not establish whether their terminal supplied a hint or used the fallback.

No new dependency was needed. No commit was made while writing this entry. The CLI change and this log are ready to stage and commit together.

## 22. Saving automatic background selection

The user committed automatic background selection and its notes in commit `d4853f6`, with the message `Add automatic background selection with dark fallback`.

## 23. Terminal fitting and a 60-column default — 22 October 2026

With the user's approval, we added terminal fitting in `src/ascart/cli.py` and `src/ascart/image_art.py`.

The CLI uses Python's built-in `shutil` module to read terminal dimensions:

```python
terminal_size = shutil.get_terminal_size(fallback=(80, 24))
width = max(1, terminal_size.columns - 1)
max_height = max(1, terminal_size.lines - 2)
```

The fallback is 80 columns by 24 rows when terminal dimensions are unavailable. We reserve one column to reduce line wrapping and two rows for prompts. `max(1, ...)` keeps each available dimension positive, even in a tiny terminal.

The image function now accepts `max_height=None`. After calculating height using the existing character-proportion correction, it limits an oversized result and recalculates width:

```python
if max_height is not None and height > max_height:
    height = max_height
    width = max(1, min(width, int(height / (aspect_ratio * 0.5))))
```

This keeps output within both available dimensions while approximately preserving proportions, subject to rounding to whole character cells. It does not stretch an image to fill both dimensions. Terminal size is read when the command runs; resizing the terminal afterward does not update existing output.

We initially made fitting the default and kept explicit `--width` as an override. We tested square, tall, and wide images against simulated terminal sizes, including tiny terminals, and checked that explicit width bypassed the height limit. The user confirmed that fitting worked, then requested a smaller default rather than filling the available terminal space.

With approval, we changed the final interface to:

- No sizing option: use 60 character columns.
- `--width NUMBER`: use the requested positive width.
- `--fit`: calculate width and height from the terminal.

In the CLI, `parser.add_mutually_exclusive_group()` groups `--width` and `--fit`, so supplying both produces an argument error. The width argument uses `default=60`. The fit argument uses `action="store_true"`, making `args.fit` true only when that flag is supplied. Terminal sizing now runs only when `args.fit` is true.

The commands are:

```bash
PYTHONPATH=src python -m ascart examples/image1.png
PYTHONPATH=src python -m ascart examples/image1.png --fit
PYTHONPATH=src python -m ascart examples/image1.png --width 100
```

For our square sample, the default produces 60 columns by 30 rows. These sizing choices also apply when saving with `--output`.

We verified the final behavior: default 60-by-30 output, explicit width 100 producing 100-by-50 output, fitting within a simulated 40-column by 12-row terminal (producing 20-by-10 artwork), and rejection of combined `--fit` and `--width`. The user welcomed the changed default.

No new dependency was needed. No commit was made while writing this entry. The two changed Python files and this log are ready to stage and commit together. Color output is the next planned feature.

## 24. Saving terminal fitting and default sizing

The user committed terminal fitting and the 60-column default in commit `3bdbfce`, with the message `Add optional terminal fitting with default width of 60`.

## 25. Color output and a denser color palette — 22 October 2026

With the user's approval, we added `--color` in `src/ascart/cli.py` using `action="store_true"`. The flag enables RGB foreground colors for terminal output. When `--output` is supplied, color formatting is disabled so saved text remains plain.

In `src/ascart/image_art.py`, the conversion function now accepts `color=False`. When enabled, it creates an RGB copy resized to the same dimensions as the grayscale image:

```python
resized_color = image.convert("RGB").resize((width, height))
```

Brightness still chooses each ASCII character. The corresponding RGB pixel supplies its foreground color:

```python
red, green, blue = resized_color.getpixel((x, y))
row += f"\033[38;2;{red};{green};{blue}m{character}"
```

We explained unpacking the three channel values, f-strings, and terminal escape sequences. The sequence sets the character's RGB foreground color; it does not color the whole character cell. At the end of each colored row, `\033[0m` resets formatting to prevent color from carrying into later terminal text. Display requires a terminal that supports RGB foreground colors.

We checked a known red pixel's color sequence, row resets, and command-line color output. With the same palette, removing formatting codes reproduced the monochrome artwork in both background modes. We also verified that `--color` combined with `--output` saved plain text.

The user initially saw only faint color. We explained that thin character strokes and spaces leave much of the terminal background visible, and suggested:

```bash
PYTHONPATH=src python -m ascart examples/image1.png --color --chars "#%@"
```

The user preferred the stronger color coverage. With approval, we added `COLOR_PALETTE = "#%@"` in `src/ascart/converter.py` and changed CLI palette selection:

- Colored terminal output defaults to `#%@`.
- Monochrome output and saved text keep the original default palette.
- An explicit `--chars` always takes priority.

The CLI leaves an omitted `--chars` as `None`, then selects the appropriate default after determining whether color output is enabled. Empty explicit palettes are still rejected. We escaped the percent sign as `%%` in argparse's help string, which displays as a single `%`, after a check caught its special formatting meaning there.

The shorter command now provides the user's preferred color result:

```bash
PYTHONPATH=src python -m ascart examples/image1.png --color
```

We verified that this matches explicit `--chars "#%@"`, that monochrome output is unchanged, and that custom palettes override either default. We checked help output and saved-file palette selection as well. The user confirmed that the final result looked good.

No new dependency was needed. No commit was made while writing this entry. The CLI, image conversion, palette constants, and this log are ready to stage and commit together.

## 26. Saving color output

The user committed color output and its notes in commit `90402c9`, with the message `Add RGB color output with a dense default palette`.

## 27. Installing ascart in editable mode — 22 October 2026

With approval, we filled the previously empty `pyproject.toml`:

- `[build-system]` selects `setuptools>=68` and its `setuptools.build_meta` backend to prepare the project for installation.
- `[project]` declares the name `ascart`, version `0.1.0`, description, README, Python requirement `>=3.10`, and dependency `Pillow>=13.0.0`.
- `[project.scripts]` maps the command `ascart` to `ascart.cli:main`.
- `[tool.setuptools.packages.find]` tells setuptools to find packages in `src`.

We checked the local environment before choosing these settings: Python was 3.14.8 and Pillow was 13.0.0. The Python requirement is a declared minimum, not a claim that all supported versions have been tested. We verified that the TOML configuration parsed correctly.

We clarified that a Python virtual environment is not a virtual machine: it uses the existing operating system and keeps project packages separate. The user used the existing `.venv` and ran:

```bash
source .venv/bin/activate
python -m pip install -e .
ascart examples/image1.png --color
```

The dot selects the current project folder. `-e` requests an editable installation, allowing source-code edits to take effect without reinstalling. Changes to dependencies or command definitions can still require reinstalling. Pip installs the declared dependencies and uses setuptools to generate installation metadata and the command entry point. The user confirmed that the installed command worked; `PYTHONPATH=src` is no longer needed while this environment is active.

The installation generated `src/ascart.egg-info/`. We explained that setuptools creates this metadata, including information about the project, dependencies, and entry points. With approval, we inspected Git status and added `*.egg-info/` to `.gitignore`. This pattern excludes generated packaging metadata, which installation can recreate; it does not delete the folder.

No additional installation, staging, or commit was performed while updating this log and the ignore rule. The configuration, ignore rule, and log are ready to stage and commit together.

## 28. Saving editable installation

The project configuration, packaging ignore rule, and learning notes were committed as `ae681e9`, with the message `Configure editable installation and ascart command`. At the user's request, the assistant ran staging, commit, and status commands and explained their output. Git metadata writes required sandbox escalation; the retry succeeded and status was clean.

## 29. Inspecting GIF frames — 22 October 2026

The user authorized adding code, maintaining this log, testing, and staging/committing meaningful milestones. We added `inspect_gif(path)` to `src/ascart/gif_art.py` as the first GIF step, before animation conversion or playback.

```python
from PIL import Image


def inspect_gif(path):
    with Image.open(path) as gif:
        if gif.format != "GIF":
            raise ValueError("Expected a GIF file")

        print("Frame count:", gif.n_frames)

        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            duration = gif.info.get("duration", 0)
            print(f"Frame {frame_index + 1}: {duration} ms")
```

Pillow opens the image and identifies its format. The function rejects non-GIF images, prints the number of frames, then visits each frame with `seek`. Frame indexes start at zero, while printed frame numbers start at one. Pillow's frame duration metadata is in milliseconds. `get("duration", 0)` reports zero if timing is absent; it is not a playback timing policy. Actual GIF playback and CLI integration have not been implemented.

We ran an inline Python check using `.venv/bin/python -B` and the editable installation. The check generated a temporary two-frame GIF with known durations, captured the function's output, and asserted that it matched the expected count and timing. It also checked a single-frame GIF without duration metadata and rejection of our PNG sample. Temporary test images were removed automatically, and no example GIF was added to the repository.

The command output was:

```text
Frame count: 2
Frame 1: 100 ms
Frame 2: 200 ms
Checks passed: frame count, per-frame timing, missing timing, and non-GIF rejection.
```

No new dependency was needed. This inspection function and log form a small tested milestone to commit with the message `Add GIF frame and timing inspection`. The resulting commit ID can be read from Git history; it is not embedded here to avoid changing the log after the commit.

## 30. Shared conversion and ASCII GIF frames — 22 October 2026

With approval, we extracted `image_to_ascii(image, ...)` in `image_art.py`. It accepts an already-open Pillow image and performs the existing grayscale, sizing, palette, and optional RGB conversion. `inspect_image(path, ...)` still opens and closes a photo, then delegates to this shared function. Existing CLI behavior remains unchanged.

We added `gif_to_ascii(path, ...)` in `gif_art.py`. It checks the GIF format, seeks through frames, reads each duration in milliseconds (zero when absent), converts the current frame to RGB, and calls the shared converter. It appends `(art, duration)` tuples to a list and returns the list after closing the file. Pillow handles GIF frame decoding/compositing during seeking. This first implementation holds all converted frames in memory; streaming can be considered for larger animations. No playback timing policy, playback, or CLI GIF dispatch has been added yet.

We tested with temporary images using `.venv/bin/python -B` and an inline script. We compared the refactored photo converter against its version from `git show HEAD:src/ascart/image_art.py` for plain, colored, and fitted custom-palette output. All outputs matched. A temporary black/white two-frame GIF produced distinct ASCII frames with durations 100 and 200 ms. We also checked color sequences, equality with shared per-frame conversion, missing timing, and rejection of PNG input. Test files were automatically removed.

Output:

```text
Photo regression checks passed: plain, color, and fitted custom palette output unchanged.
Frame 1: 100 ms
0000
0000
Frame 2: 200 ms
1111
1111
GIF checks passed: distinct frames, timing, color, shared conversion, missing timing, and format validation.
```

No new dependencies were added. The milestone is prepared for a commit named `Convert GIF frames using shared ASCII image logic`. Its ID is available in Git history. The next step is animation playback and connecting GIF handling to the CLI.

## 31. GIF terminal playback — 22 October 2026

With approval, we added `play_gif(frames)` to `gif_art.py` and connected GIF handling to the CLI. Playback clears the terminal screen, homes the cursor, and hides it. For each `(art, duration)` tuple, it returns to the top and clears the old frame before printing the next one with `flush=True`. `time.sleep` takes seconds, so positive millisecond durations are divided by 1000. Missing or zero durations use a 0.1-second fallback. The animation plays once, regardless of GIF loop metadata.

A `try/finally` block resets formatting and shows the cursor even if playback is interrupted. The CLI catches `KeyboardInterrupt` around GIF conversion and playback to stop without a traceback. This implementation uses ANSI terminal sequences and assumes the chosen artwork size fits the terminal; `--fit` is recommended for playback. Frames are still prepared in memory before playback, and conversion/rendering overhead is not compensated in timing.

The CLI opens the input briefly to inspect its actual format, dispatching GIF files to `gif_to_ascii` and `play_gif`. Other images keep the existing photo workflow. GIFs with `--output` are rejected with a parser error until a frame-saving format is defined. GIF playback also rejects non-interactive stdout so redirection does not receive terminal control codes. Help text now mentions photos and GIFs.

We ran an inline verification script with `.venv/bin/python -B`. Mocked waits checked exact requested delays without real-time sleeping; captured output checked frame replacement and cleanup, including simulated Ctrl+C. A temporary two-frame GIF tested CLI dispatch. We checked GIF save rejection, non-interactive rejection, and unchanged photo dimensions. This was a simulated playback test, not visual verification in the user's terminal. No sample GIF was added.

Output:

```text
Playback checks passed: frame replacement, millisecond delays, 100 ms fallback, and cursor cleanup after Ctrl+C.
CLI checks passed: GIF dispatch, GIF save rejection, non-interactive rejection, and unchanged photo dimensions.
```

For a user-provided GIF, the command is `ascart path/to/animation.gif --fit`, optionally with `--color`. Playback clears the current screen and leaves the last frame visible after completion. Ctrl+C stops it early.

No new dependency was needed. This log and the CLI/playback changes are prepared for the commit `Add one-pass ASCII GIF playback in the terminal`. Its ID is available in Git history.

## 32. Optional GIF looping — 22 October 2026

The user visually tested GIF playback and confirmed it worked. They requested one playback by default, `--loop` for continuous playback, and `--loop-4` for four total playbacks.

We added mutually exclusive `--loop` and `--loop-count` arguments to the CLI. Before parsing, a regular-expression match translates the shorthand `--loop-N` into `--loop-count=N`; a `--` separator ends option translation. Counts must be positive. Explicit loop options are rejected for photos. The player receives 1 by default, 0 as the internal continuous-loop marker, or the requested count. GIF metadata does not override these choices.

`play_gif(frames, loops=1)` now tracks completed passes with a while loop. It repeats while `loops == 0` or fewer than the requested passes have completed. An empty frame list returns immediately to avoid an infinite empty loop. Existing timing, frame replacement, and cleanup behavior remain in place. Four means four total playbacks, not four additional repetitions.

Tests used mocked waits and a temporary GIF. Output:

```text
Playback checks passed: once by default, four total passes, continuous repetition, and Ctrl+C cleanup.
CLI checks passed: --loop, --loop-4, positive counts, conflicting-option rejection, and photo-loop rejection.
```

Example commands (replace the path with a real GIF):

```bash
ascart examples/animation.gif --fit
ascart examples/animation.gif --fit --loop
ascart examples/animation.gif --fit --loop-4
```

The alternative `--loop-count 4` is also supported. Continuous playback ends with Ctrl+C. No new dependency was added. This milestone is prepared for the commit `Add continuous and counted GIF looping`.

## 33. Documenting the working photo and GIF features — 22 October 2026

The user requested updating both documentation files, staging them, and committing. We rewrote the README to describe implemented behavior rather than label the working features as future plans.

The README now covers virtual environment setup, editable installation, the 60-column default, explicit sizing, optional terminal fitting, color and custom palettes, background selection and fallback, and plain-text photo saving. It documents GIF playback once, continuously with `--loop`, or a total count with `--loop-4` / `--loop-count 4`, plus Ctrl+C cleanup and the interactive-terminal requirement.

We added the shared conversion workflow and practical limitations: text banners and video remain future work, GIF saving is unsupported, frames are stored in memory, timing does not compensate for rendering overhead, terminal size is read once, and background hints can be absent or inaccurate. The setup version claims distinguish declared requirements from the versions actually checked during development.

We ran `.venv/bin/ascart --help` and an inline verification script through `.venv/bin/python -B`. The script executed the documented photo options, saved artwork to a temporary directory, and checked help output. It did not reinstall the project or run another live animation. Output:

```text
README command checks passed: default photo, width, fit, color, custom palette, light background, text saving, and help.
GIF options match the tested implementation; no additional live playback was run for this documentation update.
```

Only README.md and this development log are included in this documentation milestone. The user's untracked `examples/scuba.gif` is left outside the commit. Earlier looping changes are in commit `4741a85`. The documentation commit is named `Document setup and working photo and GIF features`; its ID is available in Git history.

## 34. Optional clarity enhancement experiment — 22 October 2026

The user clarified that their desired density control means visual clarity at the same output size. We distinguished character-grid width from contrast, edge definition, and palette shading. With approval, we added an optional `--enhance` flag; normal conversion remains unchanged.

The CLI passes `enhance` through photo and GIF functions to the shared image converter. After grayscale resizing, enhancement applies Pillow's `ImageEnhance.Contrast(...).enhance(1.2)` and `ImageFilter.UnsharpMask(radius=1, percent=80, threshold=3)`. These adjust brightness separation and edge definition on an in-memory grayscale copy. Original RGB values remain the source of foreground colors. No new dependency was needed.

We ran an inline verification script using `.venv/bin/python -B`. It compared normal output with the previous committed converter, checked source-file hashes and original pixel bytes, dimensions, enhanced color character mapping, GIF timing, and CLI text saving. Output:

```text
Checks passed: original file and pixels unchanged; normal output matches previous version.
Checks passed: enhanced output stays 60 x 30; color, GIF timing, and text saving work.
Comparison: 961 of 1800 character cells changed. Visual improvement still needs your judgment.
```

A changed output is not proof of better clarity. The user should compare `ascart examples/image1.png --width 60` with the same command plus `--enhance`. Enhancement can increase noise or clip tones on some images. It remains opt-in, and these experimental changes have not yet been staged or committed, pending the user's visual assessment. The existing committed converter remains available in Git.

## 35. Removing the enhancement experiment — 22 October 2026

The user saw a small difference on the photo but reported no noticeable difference on the GIF. They requested removal of enhancement. We removed the CLI flag, enhancement parameters, and contrast/sharpening processing. The experiment was never committed, so no Git history was rewritten. Its learning record remains above.

We verified that `cli.py`, `image_art.py`, and `gif_art.py` match their previously committed versions byte for byte, that normal photo output is still 60 columns by 30 rows, and that help no longer advertises `--enhance`.

Verification output:

```text
Verified: all three Python files match the committed version; photo output is 60 x 30; --enhance is removed.
```

Only this learning log remains changed by the experiment and its removal. No staging or commit was performed during removal. The original sample files were not modified.

## 36. Text-to-ASCII banners — 22 October 2026

The user approved implementing, explaining, testing, documenting, staging, and committing text banners. We added pyfiglet as a declared dependency (`>=1.0.2,<2`) and refreshed the editable installation with `.venv/bin/python -m pip install -e .`. The initial sandboxed installation failed because package-server DNS access was blocked; an escalated retry succeeded. Final installation output was `Successfully installed ascart-0.1.0 pyfiglet-1.0.4`.

`text_art.py` now imports `figlet_format` and `CharNotPrinted`. `text_to_ascii(text, width=60)` renders the standard font and removes trailing newline characters so the shared output routine adds exactly one final newline. A too-narrow font rendering error is converted into a readable ValueError; the CLI displays it as an argument error.

The CLI makes the positional image path optional using `nargs="?"` and adds `--text`. It requires exactly one input type. Text must be non-empty printable ASCII. Banners support positive `--width` and `--output`; image/GIF-specific switches are rejected in this initial implementation. Width controls wrapping rather than resizing font glyphs. The text branch runs before opening image files and returns when finished.

We extracted existing print/save behavior into `display_art(art, output)` so photos and text share directory creation, UTF-8 saving, overwrite behavior, and terminal printing. Loop shorthand preprocessing now preserves values following named options rather than interpreting a text or palette value as a loop switch.

Tests ran using an inline script through `.venv/bin/python -B`. We checked banner rendering, wrapping, exact saved-text equality, no-input and conflicting-input errors, empty/non-ASCII input, unsupported text options, and narrow widths. Photo output and counted GIF dispatch were also checked. Output:

```text
Checks passed: banner rendering, width wrapping, text saving, invalid inputs, and narrow-width errors.
Regression checks passed: photo output and counted GIF dispatch; --text values stay intact during loop shorthand parsing.
```

We ran `.venv/bin/ascart --text Hello` and saw a large ASCII Hello banner. A narrow-width check initially exposed pyfiglet's CharNotPrinted exception, which we handled before completing verification. The README now documents setup, text usage, limits, and the implemented feature status. The user's untracked `examples/scuba.gif` remains excluded.

The milestone is prepared for the commit `Add text banners with pyfiglet and plain text saving`; its ID is recorded in Git history. No GitHub upload is part of this step.

## 37. Persistent text styles and named fonts — 22 October 2026

The user approved implementation, explanations, documentation, testing, staging, and committing. They requested each text style to accept its own text directly, without repeating `--text`, and required bold's appearance to survive plain-text saving.

We added mutually exclusive text input options: `--text` uses `standard`, `--text-slant` uses `slant`, and `--text-bold` uses the thick-stroke `banner3` font. `--text-font-FONTNAME` selects an installed pyfiglet font. These are character-based designs, not terminal bold or italic escape sequences, so saved text preserves the appearance.

The CLI uses each option's `type` callable to return a `(text, font)` tuple in the shared `text` destination. Small lambda functions perform that pairing. Named font switches are recognized with a regular expression and registered before parsing, with a set preventing duplicate registration. The lambda's default `font` parameter captures each registered font name. Existing option-value preservation prevents rewriting text values as loop shorthand. After parsing, tuple unpacking separates the text and selected font before calling the renderer.

`text_to_ascii` now accepts `font="standard"`, checks the font against `FigletFont.getFonts()`, and passes it to `figlet_format`. Unknown fonts and too-narrow widths receive readable errors. Existing ASCII validation, width wrapping, and shared saving remain in place. No new dependency or installation was needed.

We ran inline checks with `.venv/bin/python -B`, including all four input forms, equals syntax, exact saved-text equality with terminal characters, conflicts, unknown fonts, narrow widths, value handling, and photo regression. Output:

```text
Checks passed: standard, slant, bold, and named fonts; saved files exactly match terminal characters.
Checks passed: conflicting inputs, unknown fonts, narrow widths, option values, and photo regression.
```

We also ran direct slant/bold demonstrations, selecting `banner3` after comparing its visibly thicker strokes with the simpler `banner` design. The README now explains the final syntax and persistent character-based styling.

We reviewed `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `output/`, and `*.egg-info/` already cover current generated files. No new rules were required. Source code, configuration, and documentation are intentionally tracked. The user's `examples/scuba.gif` remains untracked and outside this milestone.

This milestone is prepared for the commit `Add persistent text styles and named banner fonts`. Its ID is available in Git history.

## 38. Optional text slant directions — 22 October 2026

The user approved adding explicit left/right directions while preserving the existing `--text-slant` default. We added mutually exclusive `--text-slant-left` and `--text-slant-right` text inputs. Right is an alias for the existing pyfiglet `slant` font. Inspection of installed font names and sample renderings did not reveal a matching left font, so left uses a row-shift approximation of the standard font instead. Letters are not mirrored or reversed.

`left_slanted_text` determines the standard font's row count from a single-character rendering. It reserves padding within the requested width, renders using the remaining width, then offsets successive rows by one extra space every two rows. Modulo resets offsets for each wrapped block. The font strokes themselves remain unchanged; left and right are different designs, not a matched pair. Too-small widths are rejected. Saved output retains the spaces that form the lean.

We tested default/right equality, unchanged left character order, line width bounds including wrapping, saved-text equality, narrow widths, conflicting direction options, and photo conversion. Output:

```text
Checks passed: default/right equality, left row shifts without reversed letters, width limits, saved-text equality, conflicts, and photo conversion.
```

We also ran `.venv/bin/ascart --text-slant-left Hi` to inspect the rendered text. The README describes both direction options and the left approximation. Existing output size defaults were not changed. No dependencies or ignore rules needed changes. The user's sample GIF remains untracked. This milestone is prepared for the commit `Add optional left and right text slant directions`.

## 39. Removing separate slant directions — 22 October 2026

The user visually tested the left-slant approximation and found it distorted. The earlier automated checks verified row ordering and width constraints, but did not establish visual quality. The user requested removing both explicit direction options because the original `--text-slant` already provides the desired slanted design.

We removed `--text-slant-left`, `--text-slant-right`, and the row-shifting helper, retaining the original `--text-slant` font. We updated the README to describe only supported options. The prior experiment remains in this historical log and in commit `08174d2`; no Git history was rewritten.

We ran an inline check using `.venv/bin/python -B` to verify standard, slant, bold, and named-font output; equality of saved and printed slanted text; and rejection of removed options. Output:

```text
Checks passed: remaining text styles, slant text saving, and rejection of removed direction options.
```

No dependencies, sample files, or ignore rules changed. The correction is prepared for the commit `Remove separate text slant direction options`.

## 40. Video inspection and OpenCV setup — 22 October 2026

The user authorized implementing the video plan without repeated permission requests, explaining edits, maintaining documentation, and committing meaningful stages. We added `opencv-python-headless>=4.12,<5` to pyproject.toml. This package supplies video decoding through `cv2` without desktop window tools and installs NumPy for frame arrays. Official references: https://docs.opencv.org/doc/doxygen/html/db/dd1/tutorial_py_pip_install.html and https://opencv.org/reading-and-writing-videos-using-opencv/.

The first `.venv/bin/python -m pip install --retries 0 -e .` attempt hit sandbox DNS restrictions in the build dependency subprocess. An escalated `.venv/bin/python -m pip install -e .` succeeded with: `Successfully installed ascart-0.1.0 numpy-2.5.4 opencv-python-headless-4.14.0.94`.

We filled video_art.py with helpers to open local regular files, sanitize positive metadata properties, and inspect the first decoded frame. Dimensions come from actual frame pixels; FPS and frame count are reported metadata. Estimated duration is count/FPS only when both are known. Missing metadata is None. Capture resources close in a finally block, including on decoding errors.

We added tests/test_video_art.py using standard-library unittest. Tests generate a temporary three-frame, 32x24 MJPG AVI at 10 FPS and verify metadata, invalid metadata, missing files, and release on failed decoding. `.venv/bin/python -B -m unittest discover -s tests -v` reported `Ran 4 tests in 0.138s` and `OK`. No video input was added to Git; temporary files clean themselves up. README documents the inspection function and test command. The first milestone is `Add OpenCV video inspection and metadata tests`.

## 41. Streaming ASCII video playback — 22 October 2026

The inspection and dependency milestone above was committed as `a4881c0` (`Add OpenCV video inspection and metadata tests`). We continued with terminal video playback under the user's authorization to implement, explain edits, maintain documentation, stage, and commit without repeated confirmation.

### Files changed and the reasoning

In `src/ascart/video_art.py`, we added `video_frame_to_ascii` and `play_video`. OpenCV supplies frames as NumPy arrays with channels ordered blue, green, red (BGR). `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` changes that order to the red, green, blue expected by Pillow; skipping this would swap red and blue. `Image.fromarray(rgb)` makes a Pillow image, and a `with` block closes that temporary image after the existing `image_to_ascii` function finishes. Reusing that converter gives videos the existing width, fitting, palette, background, and color behavior.

The playback loop works as follows:

1. `open_video(path)` obtains the video reader. `screen_started = False` tracks whether terminal cleanup is needed, and `displayed = 0` counts completed frame displays.
2. `positive_property(..., cv2.CAP_PROP_FPS)` reads the reported frame rate. Missing or invalid FPS uses 30 FPS and prints a warning. `frame_interval = 1 / fps` gives seconds per frame: 10 FPS means 0.1 seconds.
3. `time.monotonic()` records a timer value that is suitable for measuring elapsed time. `capture.read()` returns a success flag and the next frame. Failure before any frame produces a readable error; after displayed frames, it ends playback. OpenCV's false return does not reliably distinguish end-of-file from all decoding failures.
4. `video_frame_to_ascii(...)` converts that frame. The program retains the current frame's data instead of building a list of converted frames for the whole video.
5. On the first frame, ANSI control sequences clear the screen and hide the cursor. Each display moves to the top, clears the previous frame, and prints the new artwork. `flush=True` sends the output immediately rather than waiting in Python's output buffer.
6. The elapsed reading, conversion, and printing time is subtracted from `frame_interval`. `time.sleep(delay)` waits only when time remains. At 10 FPS, if processing takes 0.04 seconds, the wait is 0.06 seconds. If processing takes longer than a frame interval, there is no extra wait; this version does not skip frames to catch up.
7. The `finally` block releases the reader and, if screen output started, resets terminal styling and shows the cursor. This also runs when Ctrl+C interrupts playback or an exception occurs. The function returns the number of displayed frames on normal completion.

In `src/ascart/cli.py`, we added video dispatch and updated help text. The CLI first checks that the path is a regular local file, then lets Pillow identify photos/GIFs. Unrecognized image content is offered to OpenCV as a potential video. Pillow also recognizes MPEG headers without decoding their frames, so that format is explicitly routed to OpenCV. No `--video` switch is needed. The CLI forwards existing conversion options and catches Ctrl+C and expected decoding errors. Video output requires an interactive terminal. Video `--output`, `--loop`, and counted loops are rejected with explanations; GIF loop behavior remains available.

In `tests/test_video_art.py`, we extended inspection tests with BGR/RGB color verification, frame timing, missing-FPS fallback, cleanup on interruption/errors, and real AVI playback. We corrected import placement so imports precede the test classes and the direct test entry point. In the new `tests/test_cli_media.py`, we added real MP4 playback, option dispatch and rejection, MPEG routing, readable errors, and selected photo/GIF/text regression checks. Controlled clocks and fake readers test timing and failure cases without relying on a real-time delay.

`README.md` now describes video as implemented, lists dependencies and their roles, gives video commands, explains streaming and timing, and documents tests and practical limits. Video plays once without audio. Export and video looping remain future work. Timing uses one reported FPS, so variable-frame-rate sources are approximate; slow conversion/output can slow playback. Format support depends on available codecs.

### Commands and observed results

We ran:

```bash
.venv/bin/python -B -m unittest discover -s tests -v
```

After the final source changes, output included:

```text
Ran 14 tests in 0.437s

OK
```

`-B` prevents writing Python bytecode cache files. `-m unittest` runs Python's built-in test tool; `discover -s tests` finds tests in the tests folder, and `-v` lists individual results.

We also ran:

```bash
.venv/bin/python -m pip check
```

The result was `No broken requirements found.` Pip also warned that its normal cache directory was not writable in the sandbox, so it disabled caching for that command. The dependency check itself succeeded.

An inline Python command created `output/video-demo.mp4` for a local demonstration: a moving colored circle and two rectangles. This is a generated test clip, not a downloaded video. The command refuses to overwrite an existing file. Inspection output:

```text
Created: output/video-demo.mp4
{'width': 160, 'height': 96, 'fps': 12.0, 'frame_count': 36, 'duration_seconds': 3.0}
```

A second inline Python check launched the actual installed CLI in a pseudo-terminal, which supplies the interactive terminal interface required for playback. It captured screen-control output rather than assessing visual appearance. The full run used `.venv/bin/ascart output/video-demo.mp4 --width 20 --color`. The interruption run used `.venv/bin/ascart output/video-demo.mp4 --fit` and sent the interrupt signal after a frame appeared. Results:

```text
Terminal playback: 36 color frames; exit 0; cursor restored; 3.57s including startup.
Ctrl+C terminal check: exit 0; cursor restored; no traceback.
```

To view the demo with the environment active, run `ascart output/video-demo.mp4 --fit --color`. The file exists only in this development folder; it is not included in the repository. `.gitignore` already excludes `output/`, `.venv/`, bytecode, and package metadata, so no new ignore rule is necessary. The user's untracked `examples/scuba.gif` is left unchanged and outside this commit.

This playback milestone is prepared for the commit `Add streaming ASCII video playback with frame timing`. Only the two source files, two test files, README, and this log belong in that commit. Git history supplies its final ID.

Final review: `git diff --check` produced no output, indicating no whitespace errors. `.venv/bin/ascart --help` listed video support and retained GIF-only loop descriptions. `git check-ignore output/video-demo.mp4 .venv/bin/python src/ascart.egg-info/PKG-INFO` printed all three paths, confirming those generated files are ignored.

Git commands for this milestone:

```bash
git add src/ascart/cli.py src/ascart/video_art.py tests/test_video_art.py tests/test_cli_media.py README.md docs/development-log.md
git commit -m "Add streaming ASCII video playback with frame timing"
```

`git add` stages the selected file contents; `git commit` records that staged snapshot. The generated video and the user's untracked GIF are not included.

## 42. Continuous and counted video looping — 22 October 2026

The user confirmed the video demo worked. The previous streaming playback milestone was committed as `e0a3159` (`Add streaming ASCII video playback with frame timing`). They then approved adding video looping with the existing GIF syntax: once by default, `--loop` continuously, and `--loop-4` for four total playbacks.

### Implementation and learning notes

In `src/ascart/video_art.py`, `play_video` now accepts `loops=1`. The default argument preserves one playback when no count is supplied. Inside Python, `0` is the marker for continuous playback, matching the GIF player. The function rejects negative counts before opening a reader. Command-line counted options still require a positive integer: `--loop-0` is invalid; `--loop` selects the internal zero marker.

The main additions work as follows:

- `completed = 0` starts a counter for finished playbacks.
- `while loops == 0 or completed < loops:` is the new outer loop. Python continues if either condition is true: continuous mode is selected, or fewer than the requested number of playbacks have finished. For `loops=4`, the starting counter values are 0, 1, 2, and 3; after the fourth pass, `completed` becomes 4 and the condition becomes false.
- `capture = open_video(path)` opens a fresh reader for each pass, starting from the beginning. No list of the video's frames is retained between passes.
- `frames_in_pass = 0` resets the current pass's frame counter. The inner `while True` still reads, converts, displays, and times individual frames. If a new pass cannot decode even its first frame, it raises an error. Using a per-pass counter instead of the lifetime display count prevents endless retries of an empty restart.
- `displayed += 1` counts every displayed frame across all repetitions, while `frames_in_pass += 1` counts only the current pass. The function still returns the total displayed count on normal completion.
- An inner `finally` calls `capture.release()` at the end of each pass, including on failure or interruption. `completed += 1` then records a successfully finished pass. This happens before the next reader opens.
- The outer `finally` restores terminal styling and cursor visibility when playback ends. It also runs if reopening the file fails or is interrupted. The cursor is hidden once at the beginning and shown once at the end, rather than toggling between repetitions.
- Unknown FPS still uses the 30 FPS fallback. For a file with unknown FPS, the warning is printed on the first pass so continuous playback does not repeatedly print it.

In `src/ascart/cli.py`, we moved the existing `loops = 0 if args.loop else (args.loop_count or 1)` calculation into the shared media path, after validating counts. This expression selects zero for `--loop`, the requested positive count otherwise, or one if no loop option was supplied. Both players now receive the same value. We removed the video-specific loop rejection and updated help text and the photo-loop error message. The existing shorthand parser already translates `--loop-4` into `--loop-count=4`; no new shorthand parser or dependency was needed. Photos and text banners still reject loop options.

In `tests/test_video_art.py`, we added checks for exact repetition counts, releasing a reader before opening the next, continuous playback interrupted during a later pass, failed or interrupted reopening, empty later passes, and negative direct counts. The real three-frame AVI check now also verifies that four passes return 12 displayed frames. The missing-FPS test checks that repeated playback prints only one warning.

In `tests/test_cli_media.py`, we added loop-option dispatch checks, four passes through an actual one-frame MP4, positive-count validation, conflicting-option rejection, and continuous-playback interruption. We extended GIF checks for default, continuous, and counted dispatch, and confirmed that photos/text still reject loops. `README.md` now documents the shared options and the possible short pause from reopening between video passes. Audio and video export remain unimplemented.

### Commands and observed results

We ran:

```bash
.venv/bin/python -B -m unittest discover -s tests -v
```

Output included:

```text
Ran 20 tests in 0.512s

OK
```

As before, `-B` prevents writing bytecode caches, `-m unittest` runs Python's test tool, and `discover -s tests -v` discovers the test files and lists their results. The tests use temporary generated media and controlled clocks/readers for failure cases.

We also used an inline Python script to run these actual commands in a pseudo-terminal:

```bash
.venv/bin/ascart output/video-demo.mp4 --width 20 --color --loop-4
.venv/bin/ascart output/video-demo.mp4 --width 20 --color --loop
```

The script counted frame-display sequences. For continuous playback, it sent the Ctrl+C interrupt signal after the first frame of the second pass. Output:

```text
--loop-4: 144 frames = 36 x 4; exit 0; cursor restored; 12.31s including startup.
--loop: restarted into second pass; interrupted after 37 frames; exit 0; cursor restored; no traceback.
```

These checks verify actual command execution, counts, color output, and terminal cleanup. They do not assess visual smoothness in the user's terminal. The existing demo was read without modification. `.gitignore` already covers generated output, environments, bytecode, and package metadata. No new ignore rule or dependency installation was necessary, and `examples/scuba.gif` remains untracked and outside the commit.

Final review: `git diff --check` produced no output, indicating no whitespace errors. `.venv/bin/ascart --help` described loops as applying to both GIFs and videos. `git check-ignore output/video-demo.mp4 .venv/bin/python src/ascart.egg-info/PKG-INFO` printed all three paths, confirming they remain ignored.

Git commands for this milestone:

```bash
git add src/ascart/video_art.py src/ascart/cli.py tests/test_video_art.py tests/test_cli_media.py README.md docs/development-log.md
git commit -m "Add continuous and counted ASCII video looping"
```

`git add` selects these six files for the staged snapshot; `git commit` records that snapshot. The final commit ID is available through `git log --oneline`.

## 43. Readable input, decoding, and saving errors — 22 October 2026

The previous video-looping milestone was committed as `801ff9f` (`Add continuous and counted ASCII video looping`), including its code, tests, README, and log updates. The user approved the next step: handling common file errors with clear messages, explaining the edits, testing them, updating documentation, and committing.

### Investigation and code changes

We inspected the CLI and the installed Pillow source to identify errors that can occur while opening and decoding images. A small in-memory experiment created PNG/GIF data and removed bytes. Both headers were still recognized by Pillow, but converting their pixels raised `OSError`: `image file is truncated` for PNG and `image file is truncated (24 bytes not processed)` for GIF. This showed why checking only `Image.open` was insufficient: decoding can fail later.

All application-code edits for this milestone are in `src/ascart/cli.py`:

1. `IMAGE_READ_ERRORS` is a tuple naming the expected file/decoder exception classes: `OSError`, `ValueError`, `EOFError`, `SyntaxError`, and Pillow's `Image.DecompressionBombError`. `PermissionError`, `FileNotFoundError`, and `UnidentifiedImageError` are covered through their relationship to `OSError`. These handlers surround image opening or conversion rather than the entire program. Unexpected exceptions such as `TypeError` still propagate so programming bugs remain visible.
2. `report_file_error(parser, action, path, error)` centralizes the message format. `isinstance(error, OSError)` checks the exception's type. When available, `error.strerror` supplies the operating system's reason without repeating the error number and path; otherwise, `str(error)` uses the exception's description. The f-string includes the action, path, and reason. `!r` shows the path as a quoted representation, which also makes embedded whitespace clearer. An empty reason receives the fallback `invalid or incomplete file data`.
3. `parser.error(...)` prints usage and the error to standard error, then raises `SystemExit` with status 2. It does not return normally, so processing stops at that point. This preserves the CLI's existing error-exit convention.
4. `display_art` now also receives `parser`. A `try` block surrounds parent-folder creation and UTF-8 writing. `except OSError as error` means that, if a filesystem operation fails, Python stores the exception in the local variable `error` and runs the handler. The helper reports `Cannot save artwork to 'path': reason`. The success message is printed only after writing finishes. Both text and photo call sites pass the parser, so they share this behavior.
5. Input validation now uses `Path.stat().st_mode` and `S_ISREG`. `stat` obtains filesystem information and can report access or missing-file failures; `S_ISREG` checks whether the entry is a regular file. Directories and other non-regular input paths are rejected before decoding. This preserves the actual failure reason instead of treating every failed check as a missing file.
6. We handle expected Pillow errors both during initial identification and later photo/GIF conversion. `UnidentifiedImageError` is handled before the broader image-error tuple so ordinary video files can still reach the video decoder. Existing `with` blocks in the converters continue closing input resources when decoding raises an exception.
7. Before treating unrecognized image content (or Pillow-recognized MPEG content) as video, the CLI calls the existing `inspect_video` function to check that a frame can be decoded. If neither decoder recognizes usable media, the message is `Cannot decode input 'path': unsupported or damaged media`. This avoids telling someone with an unrelated file that video playback requires a terminal or cannot use `--output`. The check decodes only the first frame and closes its reader; playback opens its own reader afterward. It adds an initial open/decode step, not a full-video scan. Ctrl+C during this check returns cleanly.
8. GIF decoding and playback now have separate `try` blocks. A decoding failure is reported before the screen is cleared. Ctrl+C during either phase still stops the command. Expected video-playback errors now also include the input path through the shared reporting helper.

We did not add a new dependency or change the image-conversion algorithm. Saving still creates parent folders and replaces existing text files. It is a direct write, not an atomic save: an error after writing begins can leave partial output. Tests that inject a write error before bytes are written do not establish preservation during every possible write failure. The README records this limitation.

### Tests and observed results

We added `tests/test_cli_errors.py`. It creates temporary PNG/GIF fixtures and checks real truncated media, unsupported content, missing files, directory inputs, directory output paths, and a normal file blocking an output folder. It simulates denied access, a file disappearing between identification and conversion, decoder failures, and disk-space errors. Tests check the status code, operation/path in the message, absence of a traceback, and absence of false success output. A photo conversion failure is checked before any existing output is overwritten. Successful photo/text saving, overwriting, GIF playback, and unexpected programming errors are also covered.

We ran:

```bash
.venv/bin/python -B -m unittest discover -s tests -v
```

Output included:

```text
Ran 33 tests in 1.280s

OK
```

This includes all previous video timing, looping, color, and cleanup tests. `-B` prevents writing bytecode caches; `-m unittest discover -s tests -v` runs Python's test discovery in the tests folder and prints each result.

An inline Python script then launched the installed command in a temporary working folder, using generated files only. It created real read/write permission failures by changing permissions on temporary files and restored those permissions afterward. It also checked missing, truncated, unsupported, and directory-path cases. The actual commands and final error lines were:

```text
$ ascart missing.png
ascart: error: Cannot read input 'missing.png': No such file or directory
Exit code: 2
$ ascart broken.png
ascart: error: Cannot convert photo 'broken.png': image file is truncated
Exit code: 2
$ ascart notes.txt
ascart: error: Cannot decode input 'notes.txt': unsupported or damaged media
Exit code: 2
$ ascart --text Hi --output folder
ascart: error: Cannot save artwork to 'folder': Is a directory
Exit code: 2
$ ascart locked.png
ascart: error: Cannot read input 'locked.png': Permission denied
Exit code: 2
$ ascart --text Hi --output readonly.txt
ascart: error: Cannot save artwork to 'readonly.txt': Permission denied
Exit code: 2
```

The CLI also printed its usage before each error; the script displayed only the final error line and exit status above. All six commands produced empty standard output and no Python traceback. The temporary folder and fixtures were removed automatically. No sample media or existing user output was modified.

`README.md` now documents the error behavior, exit status, troubleshooting examples, first-frame video identification check, direct-write limitation, and expanded test coverage. `.gitignore` already covers generated output, environments, bytecode, and package metadata; temporary test fixtures do not need a new rule. The user's `examples/scuba.gif` remains untracked and outside this milestone.

Git commands for this milestone:

```bash
git add src/ascart/cli.py tests/test_cli_errors.py README.md docs/development-log.md
git commit -m "Handle common media and output file errors clearly"
```

Staging selects these four files; committing records that snapshot. The final commit ID is available in Git history.

## 44. Newly generated meme-style PNG, GIF, and video samples — 23 October 2026

The user had replaced the original sample with a downloaded cat meme whose source and license could not be identified. We checked that replacement: PNG, 480x520, RGBA, 207,438 bytes, no author/license metadata. Monochrome and color conversion worked, but this did not establish redistribution rights. That cat replacement was never committed. The user then requested newly created meme-style samples in image, GIF, and video formats.

We used the built-in image generation tool through the imagegen skill to create a new teal robot, an oversized orange coffee mug, and three red cartoon bugs, captioned `ONE QUICK FIX / THREE NEW BUGS`. A second generation call used only that generated image as reference and produced a 2-by-2 pose sheet: holding the mug, raising it, blinking/drinking, and looking surprised. No downloaded meme or third-party picture was supplied as a generation reference. Both generated source images were RGB, 1254x1254. This records provenance rather than guaranteeing exclusivity, public-domain status, or legal clearance. Full prompts are recorded in examples/README.md.

Before replacing examples/image1.png, we copied the user's local cat image to the ignored `output/sample-sources/previous-image1.png`. We also preserved generated originals as `output/sample-sources/robot-original.png` and `robot-poses.png`. The original tool outputs remain in Codex's generated-images folder. The preservation command refuses to overwrite an existing backup. These local source/backup files are excluded from Git; examples/scuba.gif remains untracked.

### Build script and sample files

We added tools/build_sample_media.py, a separate asset-building utility using existing Pillow, OpenCV, and NumPy packages. No application conversion code or dependencies changed. It accepts the standalone image, the four-pose sheet, and an optional output directory. It writes image1.png, robot.gif, and robot.mp4. The script does not call an image service.

The main operations are:

1. `Image.open` reads the generated standalone image in a `with` block. RGB conversion and a 640x640 resize prepare a smaller PNG. The original input path must differ from the output path.
2. The sheet must be square with an even edge length. `cell = sheet.width // 2` gives each cell's width and height. Nested row/column loops form crop coordinates for the four cells in reading order.
3. Each extracted pose is resized to 384x384 using LANCZOS resampling. This is packaging of generated animation poses, not a modification of the project's converter.
4. GIF frames are quantized to 128 colors. `save_all=True` and `append_images` encode all four poses. `duration=400` assigns 400 ms to each, giving 1.6 seconds per sequence. `loop=0` stores continuous-loop metadata in the GIF; ascart still follows its own command-line loop selection and defaults to one pass. `disposal=2` clears the preceding frame before the next display.
5. OpenCV writes MPEG-4 Part 2 video inside an MP4 container, using `mp4v`, 384x384 pixels, and 10 FPS. RGB arrays are reordered to BGR for OpenCV. Four copies of each pose hold it for 0.4 seconds. Five repeats of four poses, with four video frames per pose, give 80 frames and 8 seconds. The reader is not involved in generation; the video writer closes in a `finally` block. The clip has no audio.
6. The PNG is saved with optimization enabled. The tool prints the resulting paths and byte counts. It overwrites the named final samples, and `--output-dir` can select a separate destination.

Initial full-resolution packaging was larger than needed. We reduced the still to 640 pixels and animated frames to 384 pixels to keep the final files small. The final build command was:

```bash
.venv/bin/python -B tools/build_sample_media.py output/sample-sources/robot-original.png output/sample-sources/robot-poses.png
```

Output:

```text
Created examples/image1.png: 435,580 bytes
Created examples/robot.gif: 388,415 bytes
Created examples/robot.mp4: 884,433 bytes
```

Together these final assets occupy 1,708,428 bytes, about 1.63 MiB. The source sheet and full-size original are not required to run ascart with the included final samples. They are needed only to rerun the optional build utility; they remain local rather than being bundled with a clone. Equivalent inputs can be generated with the documented prompts, though image generation is nondeterministic.

### Checks and documentation

An inline verification command using `.venv/bin/python -B` checked monochrome and color conversion at width 60 for the still and all four GIF poses. The still produced 30 rows. It verified that all GIF poses produce distinct artwork, that their durations are 400 ms, and that the MP4 reports 384x384, 10 FPS, 80 frames, and an estimated duration of 8 seconds. It read the entire video to confirm that all 80 frames decode. Output:

```text
PNG and GIF: monochrome/color conversion passed; GIF has 4 distinct poses, 400 ms each.
MP4: {'width': 384, 'height': 384, 'fps': 10.0, 'frame_count': 80, 'duration_seconds': 8.0} ; all 80 frames decoded.
Total sample size: 1708428 bytes
```

We visually inspected the generated artwork and the extracted blinking/drinking GIF pose. A second inline script launched the installed CLI in a pseudo-terminal with these commands and counted frame-display sequences:

```bash
.venv/bin/ascart examples/robot.gif --width 40 --color
.venv/bin/ascart examples/robot.mp4 --width 40 --color
```

Results:

```text
robot.gif: 4 ASCII frames; color output; normal exit; cursor restored.
robot.mp4: 80 ASCII frames; color output; normal exit; cursor restored.
```

These terminal checks establish decoding, command execution, display counts, color output, and cleanup. Visual readability of captions in ASCII depends on output width and terminal font. The four-pose animation holds each pose rather than interpolating motion.

README.md now uses the included GIF and MP4 in runnable example commands, describes the new still, links to examples/README.md, and saves the photo example to output/robot.txt. examples/README.md records sizes, timing, provenance, exact generation prompts, commands, and optional rebuilding. The source/backup files are already covered by the output/ ignore rule. No new ignore pattern is needed.

Git commands for this milestone:

```bash
git add README.md docs/development-log.md examples/image1.png examples/README.md examples/robot.gif examples/robot.mp4 tools/build_sample_media.py
git commit -m "Add generated robot meme samples for images GIFs and videos"
```

Only these seven files belong to this milestone. The local cat backup, full-size generation sources, and the user's scuba.gif are not part of the commit. The final commit ID is available in Git history. Publishing this new local commit to GitHub is a separate push.

The sample milestone was committed as `1591d2a`. The staged whitespace check reported an extra blank line at the end of examples/README.md; the commit had already been recorded before that result was addressed. We removed that blank line and recorded this note in a small follow-up documentation commit rather than rewriting the sample commit. No media bytes changed during this cleanup.

## 45. Keeping only one simple sample image — 23 October 2026

The user requested simplifying the project by keeping examples/image1.png and removing the additional sample-media machinery. We kept the generated 640x640 PNG unchanged and verified its SHA-256 hash before and after cleanup. Its file size remains 435,580 bytes. examples/ now contains only image1.png.

We removed examples/robot.gif, examples/robot.mp4, examples/README.md, and tools/build_sample_media.py, then removed the empty tools directory. The user's untracked examples/scuba.gif was moved to output/local-media/scuba.gif so it remains available locally under the existing ignored output/ directory. The move refused to overwrite an existing destination. Existing full-size generation sources and the earlier cat-image backup remain in the ignored output/sample-sources directory.

README.md now describes the single AI-generated PNG and uses path/to/animation.gif and path/to/video.mp4 as placeholders for users' own files. The separate sample-generation notes and their link were removed. GIF/video conversion and looping features remain implemented. Historical development-log entries remain as records of the earlier work.

Verification commands and results:

```bash
.venv/bin/python -B -m unittest discover -s tests -v
```

```text
Ran 33 tests in 2.465s

OK
```

An inline image-conversion check through .venv/bin/python -B verified the retained PNG at width 60 in both monochrome and color, with 30 output rows. Output:

```text
Remaining sample converts successfully in monochrome and color at width 60.
Files in examples: image1.png
```

No dependencies or ignore rules needed changes. This is a normal cleanup commit; earlier media remains in Git history. No history rewrite or GitHub push is part of this step.

Git commands for this milestone:

```bash
git add README.md docs/development-log.md examples/README.md examples/robot.gif examples/robot.mp4 tools/build_sample_media.py
git commit -m "Simplify examples to a single sample image"
```

git add stages the documentation changes and the four tracked deletions. The retained PNG is unchanged, so it needs no new staging. Git history records the final commit ID.

## 46. Creator-sourced Tux sample and manual Git workflow — 23 October 2026

The user downloaded a replacement PNG from the creator-hosted garrett/Tux repository and placed it at examples/image1.png. They also instructed the assistant to stop staging or committing changes and instead provide commands for them to run. This instruction applies from this milestone onward; no staging, commit, or push was performed during this check.

The new file is a valid RGBA PNG, 933x1139 pixels, 211,886 bytes (about 207 KiB). Its embedded metadata names Garrett LeSage, identifies the title as Tux and source as https://github.com/garrett/Tux, and states `CC0 Public Domain Dedication http://creativecommons.org/publicdomain/zero/1.0/`. We visually inspected the image, ran Pillow's verify immediately after opening, and tested the existing converter in both monochrome and color at width 60; each produced 36 rows.

We checked https://github.com/garrett/Tux/blob/main/README.md. It states CC0 and credits the original illustration to Larry Ewing using GIMP, the redraw to Garrett LeSage using Inkscape, and refinement/cleanup to IFo Hancroft. README.md now records those credits and links to the source and license. The example save path is output/penguin.txt. No separate licensing-notes file or new sample media was added.

An earlier, uncommitted replacement from Pixabay had also converted successfully (1605x1920 RGBA, 322,180 bytes), but was recognized as a Tux variant. The assistant corrected its earlier blanket CC0 reassurance: an upload date and a platform license statement do not by themselves establish all underlying derivative rights. That intermediate PNG was not committed. The user chose the creator-hosted version instead, whose own metadata and repository README provide a clearer source/license record. This records the source's stated license rather than asserting independent legal clearance for every possible use.

The first diagnostic check on that intermediate PNG called verify after reading pixels, producing `RuntimeError: verify must be called directly after open`. This was a verification-script ordering error, not an invalid image; reopening and verifying immediately passed. The check on the final creator-sourced PNG used the correct order.

We also ran the installed CLI through an inline verification script using .venv/bin/python -B. It invoked `.venv/bin/ascart examples/image1.png --width 60 --output` with a temporary destination, checked successful exit, checked 36 lines of 60 characters, and compared the source SHA-256 before and after. Output:

```text
Installed CLI: saved 60 x 36 plain-text artwork successfully.
Source PNG unchanged; temporary output removed.
```

Only the sample PNG and two documentation files changed; no converter code or dependencies changed. The earlier local commits remain in history. The following commands are for the user to run, not commands executed by the assistant:

```bash
git add examples/image1.png README.md docs/development-log.md
git diff --staged --stat
git commit -m "Replace sample image with credited Tux artwork"
git status
```

The commit ID should be recorded after the user performs the commit. No GitHub upload is included in this step.

## 47. Saving only to new text files — 23 October 2026

The user committed the preceding sample replacement as `cfadd24` (`Replace sample image with credited Tux artwork`). They then approved implementing and testing safe text-file saving without disrupting their media or existing output. Their instruction remains that the assistant must not stage, commit, or push; commands are provided for the user instead.

Before testing, an inline .venv/bin/python -B command recorded SHA-256 hashes for examples/image1.png and all existing files under output/ (8 files total). Tests use only generated fixtures and temporary directories. The final preservation check compared hashes and the file list to ensure those existing image/output files were neither changed, added to, nor removed.

### Implementation

In src/ascart/cli.py, we added `validate_output(output, input_path, parser)` and call it after selecting exactly one input, before either the text or media branch performs conversion:

- `output is None` means the option was omitted, so terminal display remains the default. Otherwise, `output.strip()` must be non-empty. The original path is kept intact rather than stripping spaces from valid filenames.
- `Path.resolve()` compares normalized paths and follows symbolic links. If both files exist, `samefile()` also compares their filesystem identity, catching hard links to the source. Matching the input produces an error before any write, even if its extension is not .txt.
- A directory is rejected with a specific message. Existing destinations and symbolic links (including dangling links) are rejected rather than replaced. Expected filesystem validation failures use the shared error-reporting helper.
- The suffix must be .txt, case-insensitively. Unsupported extensions and filenames with no extension are rejected before conversion or parent-folder creation. PNG, GIF, and MP4 export remain unimplemented.

In the shared `display_art` function, the existing UTF-8 overwriting write was replaced with:

```python
with output_path.open("x", encoding="utf-8") as file:
    file.write(art + "\n")
```

`x` means exclusive creation: create a new file or raise FileExistsError if the destination already exists. This enforces the no-overwrite rule even when another process creates the file between validation and opening. The with block closes the stream. Expected write or close errors are caught, and the success message appears only after the with block finishes successfully. Parent-folder creation has its own error handler so failures there keep their filesystem explanation. A file-created-during-saving error gets the clear existing-destination message.

There is no overwriting option or automatic filename numbering. A failed write can leave a partial newly created file. The application does not delete that file or any existing user file. Preventing replacement of existing data is the implemented guarantee; all-or-nothing creation of a complete new output is a separate future feature. No character palettes or image-conversion algorithms changed.

### Tests and results

We updated tests/test_cli_errors.py to replace the previous successful-overwrite expectation with rejection and byte-for-byte preservation. New cases cover blank output, unsupported/missing extensions, omitted and missing-value output options, existing destinations, source paths and aliases, hard links, symbolic links, dangling links, spaces, uppercase .TXT, a competing file creation, and a simulated disk error partway through writing a new file.

The initial run exposed test mocks that intercepted pyfiglet's own font reads because Path.open is shared across modules. We isolated the saving-failure tests by supplying already-rendered banner text, allowing those mocks to exercise only the intended output failure. Successful rendering/saving tests still use the real banner renderer. The race test creates another file just before exclusive opening, then checks that its bytes survive. The partial-write test uses a real temporary destination, writes only three characters, raises a simulated disk-space error, and verifies that a neighboring existing file is intact.

Command:

```bash
.venv/bin/python -B -m unittest discover -s tests -v
```

Final output:

```text
Ran 40 tests in 0.461s

OK
```

An additional inline script launched the actual installed CLI using generated PNG input and a destination in a temporary folder. It verified successful saving in a new parent folder, rejection of a repeated destination, rejection of using the input as output, blank output rejection, and unsupported-extension rejection. Success exited with status 0; errors exited with status 2 without tracebacks or false success output. Key messages:

```text
New .txt output: exit 0; saved successfully in new parent folder.
destination already exists; choose a new filename
output must not point to the input file
--output must not be empty or whitespace only
--output currently supports only .txt files; PNG, GIF, and MP4 export is not implemented
Temporary source and pre-existing output preserved byte for byte.
```

The preservation check on the user's actual files reported:

```text
Preservation check passed: all 8 existing image/output files unchanged; no files added or removed there.
```

README.md now documents new-file-only saving, .txt validation, input-alias protection, repeated-command behavior, and the partial-new-file limitation. Help text now says that saving requires a new .txt file. No dependencies or ignore rules changed. Historical log entries describing earlier overwrite behavior remain as history.

Commands for the user to review, stage, and commit this milestone (not executed by the assistant):

```bash
git diff --check
git add src/ascart/cli.py tests/test_cli_errors.py README.md docs/development-log.md
git diff --staged --stat
git commit -m "Prevent overwriting existing files when saving ASCII art"
git status
```
