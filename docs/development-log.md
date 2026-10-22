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
