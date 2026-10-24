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

## Running tests

With the virtual environment active:

```bash
python -B -m unittest discover -s tests -v
python -m pip check
```

The suite checks video inspection, MP4/AVI decoding, color conversion, timing, counted and continuous playback, cleanup after interruption or failed restarts, rejected options, and selected photo/GIF/text regressions. It creates temporary media that is deleted afterward. The real decoding tests require working MP4 and MJPG encoders in OpenCV. Automated checks do not replace viewing the artwork in your own terminal.

Converter tests cover palette endpoints and boundaries, balanced band sizes, monotonic brightness mapping, custom and single-character palettes, and color/light-background behavior on a controlled grayscale image.

Border tests cover visible widths with ANSI colors, row padding, saved text, terminal margins, tiny-terminal errors, counted animation playback, and interruption cleanup.

PNG tests check smooth regular strokes with less ink than the previous bitmap sample, printable-character cell containment, bitmap fallback without FreeType, fixed character cells, blank rows/spaces, RGB strokes, light/dark canvases, neutral borders, all banner styles, uppercase extensions, the size limit, no-overwrite protection including links and competing creation, and readable save failures. GIF/video PNG export is rejected before creating output folders, including with loop options.

GIF export tests read back actual saved animations to check frame timing, source-loop removal, colors, borders, fitting, missing-timing fallback, merged identical frames, and independence from terminal loop counts. They also cover saving without an interactive terminal, completed-file preservation on playback interruption, wrong input/output combinations, existing-file/link protection, competing creation, truncated input, rendering failures, permission errors, and partial writes. Fixtures and outputs stay in temporary directories.

Camera GIF tests additionally cover streaming frame encoding and image cleanup, per-frame palettes, repeated-frame timing, and a width-140 recording exceeding the former 64-million-pixel aggregate budget. These checks use simulated cameras and reopen real GIF output.

The combination suite exercises 1,344 option combinations: 216 photo cases, 864 GIF cases (including expected non-interactive playback rejections), 216 real MP4 playback cases, and 48 text-banner cases. It crosses colors, borders, automatic/manual backgrounds, default/custom palettes, default/explicit/fitted sizing, supported save formats, terminal availability, and loop modes where applicable. It checks displayed grids and reopens saved files to verify dimensions, timing, and one-pass GIF metadata. Additional cases check invalid combinations, option-like text, background hints, and malformed paths. Source-media SHA-256 hashes must remain unchanged. This covers the listed scenarios; it is not a guarantee for every possible file or codec.

Short-text alias tests compare `-t` with `--text` across widths, borders, and terminal/TXT/PNG output, including identical saved contents. They also check help text, literal option-like text, invalid values, and incompatible input modes.

HTML tests parse exported pages to check selectable characters, escaping, whitespace/blank rows, colors and resets, neutral borders, and standalone markup. They include 48 photo-option combinations and 20 banner combinations, including -t, width, fitting, borders, backgrounds, and custom palettes with HTML-special characters. Other checks cover animated exports with terminal loop options, uppercase extensions, existing destinations/links, competing creation, rendering failures, permissions, partial writes, and unchanged source media.

MP4 export tests add 32 saved-video rendering combinations, reopen real encoded MP4s, and check dimensions, frame count, FPS, color order, source preservation, and temporary-file cleanup. They cover AVI input, terminal-loop independence, interrupted playback, non-interactive saving, unsupported format combinations, existing files and links, competing destination creation, unavailable/failing encoders, incomplete encoding, missing FPS, permission failures, source interruption, and partial-copy errors.

File-error tests use real truncated PNG/GIF data and invalid save paths, plus simulated permission and disk-space failures. They verify successful saving, rejection of existing destinations and source aliases, exclusive creation when another file appears during saving, and partial-new-file behavior. They also ensure unexpected programming errors are not hidden by a catch-all exception handler. Test media and outputs are created in temporary directories.

Animated HTML tests add 96 GIF/video option combinations, check exact converted frames and timings, escaping, initial-frame fallback, size/frame limits, exclusive creation, reader cleanup, FPS fallback, and independent terminal loops. An optional Node.js test runs the actual player code with a simulated clock and document to verify Play/Pause/resume/Replay and stopping after one pass; Node.js is not a runtime dependency. Browser appearance is checked manually.

Camera tests use mock capture handles and controlled image arrays, covering 96 rendering combinations across both camera orientations, default/explicit camera IDs, listing discovery, inaccessible/empty devices, read/conversion failures, disconnects, Ctrl+C, redraw pacing, cursor restoration, and handle release. An asymmetric colour-frame test checks that the default flips left/right before conversion while the mirrored option preserves source pixels, without modifying the source array. Invalid modes/output/loops, non-interactive playback, and malformed IDs must fail before camera access or file creation. Existing command checks verify that help, version, text, and photo commands do not open cameras. Real webcam compatibility remains a manual check.

Snapshot tests add 288 format/visual combinations and a simulated countdown clock. Interactive checks verify live countdown frames, clipped status text, cursor restoration, final-frame freezing, matching saved/visible artwork for all formats and orientations, and readable save failures. They check fresh post-countdown frames, both orientations, plain TXT, exact PNG pixels, selectable HTML, camera release before writing, non-interactive saving, invalid formats/options, existing files and links, competing creation, cancellation, capture/render errors, permissions, and partial-write safety. No automated test accesses physical cameras.

Camera-recording tests use a simulated clock/camera with real MP4 encoding and readback. They cover 96 visual combinations, both orientations, reported FPS/dimensions/frame count, fractional durations, slow capture, repeated-frame timing, non-interactive saving, limits and invalid modes, existing files/links, competing creation, cancellation, decoder/encoder cleanup, changed dimensions, verification failure, permission/render errors, and partial copying. They do not establish physical-webcam timing or hardware compatibility.

Camera GIF/HTML tests add 192 visual-option combinations, format timing/readback, orientation/colour checks, selectable escaped frames and player controls, slow-capture timing, limits and early HTML-duration rejection, cancellation, camera cleanup, dimension changes, GIF timing verification, existing files/links, competing creation, permission errors, and partial-copy safety. Simulated cameras are used throughout.
