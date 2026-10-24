# Development guide

## Setup

This setup is for working on the source code. For everyday use without manual environment activation, follow [Installation](../README.md#installation).

The project declares Python 3.10 or newer and these dependencies:

| Package | Purpose | Declared version |
| --- | --- | --- |
| Pillow | Read photos/GIFs, resize frames, get brightness and RGB colors, and draw saved ASCII frames. | `>=13.0.0` |
| pyfiglet | Render text using character-based banner fonts. | `>=1.0.2,<2` |
| opencv-python-headless | Decode video frames and encode silent MP4 output through `cv2`, without desktop display windows. | `>=4.12,<5` |

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
