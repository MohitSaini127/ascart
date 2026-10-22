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
