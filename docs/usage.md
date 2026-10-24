# Usage reference

Detailed behaviour, output limits, and troubleshooting. For installation and copyable commands, see the [README command guide](../README.md#command-guide).

## Text banners

Choose one input mode: text, a photo/GIF/video path, camera viewing, or camera listing. For a banner, choose exactly one text-input option. Each text option takes its text directly; do not add `--text` again. Text mode accepts non-empty printable ASCII text. `--text` uses `standard`, `--text-slant` uses `slant`, and `--text-bold` uses the thicker character-based `banner3` font. `--text-font-FONTNAME` selects an installed pyfiglet font, such as `small`, `big`, or `standard`; unknown names are rejected. These designs, including bold-looking strokes, are made of ordinary characters and persist in saved text without terminal styling codes.

`-t` is a short form of `--text`: `ascart -t "Hello"` produces the same standard banner. Both forms support width, borders, and TXT/PNG/HTML saving, for example `ascart -t "Hi" --border --output output/hi.png`. Use `--text-slant` or `--text-bold` directly for those styles; they are separate text-input choices.

The default width is 60; `--width` sets the wrapping limit, not the size of individual letters. A width too small for a letter is rejected. Text-input options cannot be combined with each other.

`--text-slant` uses the original right-leaning font design. Separate direction options are not supported.

Text mode supports `--width`, `--output`, and `--border`. Photo/GIF/video options (`--fit`, `--color`, `--chars`, manual background selection, and looping) are rejected for banners. Saved files contain the same banner as terminal output, including the border when selected. Saving requires a new `.txt`, `.png`, or `.html` filename; existing files are never overwritten. Banner color is not implemented; banner PNGs and HTML pages use white characters on black.

## Photo conversion

The [image command guide](../README.md#image-commands) uses the included sample. Replace its path to convert your own photo.

The included sample is Tux, the Linux penguin, downloaded from [garrett/Tux](https://github.com/garrett/Tux). Its embedded metadata and the [source README](https://github.com/garrett/Tux/blob/main/README.md) state [CC0](https://creativecommons.org/publicdomain/zero/1.0/). Original illustration by Larry Ewing using GIMP; redrawn in Inkscape by Garrett LeSage, with refinement and cleanup credited upstream to IFo Hancroft. Only this PNG is bundled; supply your own files for GIF and video playback.

| Option | Behavior |
| --- | --- |
| No sizing option | Use 60 character columns and calculate height from the image proportions. |
| `--width NUMBER` | Choose a positive width in character columns. |
| `--fit` | Fit both terminal dimensions, reserving one column and two rows. Cannot be combined with `--width`. |
| `--border` | Add a plain ASCII frame around the artwork. Off by default; also works for text banners and animation frames. |
| `--color` | Use RGB foreground colors in PNG pictures, HTML pages, or a compatible terminal. Saved `.txt` files stay plain. |
| `--chars "CHARACTERS"` | Choose a non-empty palette of printable ASCII characters, ordered from least to most visually dense. Quote spaces. |
| `--background auto` | Default: use a limited terminal background hint, with a dark fallback. |
| `--background light` or `--background dark` | Manually choose brightness mapping. |
| `--output PATH` | Show the artwork in the terminal and save it as UTF-8 plain text (`.txt`), a PNG picture (`.png`), or a webpage (`.html`), creating parent folders as needed. Existing destinations and input-file aliases are rejected. |

Monochrome uses the palette ` .:-=+*#%@`, including a leading space. Colored terminal, PNG, HTML, GIF, and MP4 output defaults to `#%@` so more character strokes show color. An explicit `--chars` overrides either default. With `.txt` output, color formatting is disabled and the monochrome default is used unless a custom palette is supplied. Generated files in `output/` are ignored by Git.

Brightness values from 0 through 255 are divided into near-equal bands across the palette. For the three-character color palette, `#` covers 0–85, `%` covers 86–170, and `@` covers 171–255 before any light-background reversal. Similar brightness values still produce repeated characters; adding more characters does not automatically improve clarity, and apparent character density depends on the terminal font.

Automatic background selection reads the last field of the `COLORFGBG` environment variable. Conventional color indexes 7 and 15 select light mode; other, missing, or unsupported values fall back to dark. This does not measure the actual screen, and themes can redefine those colors. Use a manual override when needed. Light mode reverses the character palette; it does not invert the image's RGB colors.

## Image comparison

**Experimental terminal preview:** direct side-by-side display is not supported in every terminal. PNG/HTML export remains available without terminal image support.

Use `--compare` to preview a still image beside its ASCII artwork. Add a new `.png` or `.html` output filename to save it too:

```bash
ascart photo.png --compare --color
ascart photo.png --compare --color --output output/comparison.png
ascart photo.png --compare --color --border --output output/comparison.html
```

The comparison labels the original on the left and ASCII artwork on the right. The original is scaled to fit its panel without cropping or changing its proportions; transparent pixels are composited on the chosen light/dark background. The ASCII side uses the existing converter and supports colour, custom palettes, width or fit, backgrounds, and borders. Borders apply to the ASCII side.

Direct terminal preview first tries the [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/) natively on POSIX systems such as Linux/macOS. This supports terminals such as Ghostty and Kitty without installing another terminal or helper. Input and output must be interactive and attached to the same terminal. A bounded query checks support, reads the protocol and device-attributes replies, and restores terminal settings afterward. Terminal names or environment variables are not treated as proof of support.

The native path sends the comparison PNG in base64 chunks of at most 4,096 bytes. The terminal fits it into a rectangle sized from its current columns and rows, preserving proportions. Space is reserved for the preview and the cursor is left below it. Replies are suppressed during image transfer so they do not become shell input. No user output file is created for preview-only commands. Native preview has been confirmed in one Ghostty setup; other terminal versions and configurations remain unverified. Automated checks use private pseudo-terminals.

If native probing is unavailable or fails, an installed [Kitty `icat` helper](https://sw.kovidgoyal.net/kitty/kittens/icat/) remains an optional fallback (`kitten icat` or legacy `kitty +kitten icat`). The preview displays the complete comparison as a PNG; its ASCII panel is an image, not selectable terminal text. Other graphics protocols, including SIXEL, are not implemented.

With `--compare` alone, unavailable or failed preview exits with a readable error asking for `--output comparison.png` or `--output comparison.html`. No comparison output file is created. With `--output`, the file is saved first; unsupported terminals, redirected output, helper failure, timeout, or cancelled preview leave that file intact. The CLI prints its saved location and an explanatory message if preview cannot be shown, without treating a successful export as a failure. It does not substitute a coloured-block approximation or launch another application.

`--width` and `--fit` size the ASCII artwork, not the combined comparison. The saved layout is wider because it includes both panels. PNG draws the ASCII characters; HTML keeps them selectable and embeds a scaled PNG copy of the source for offline viewing. HTML needs no JavaScript, does not reference the source path, and uses horizontal scrolling when the comparison is wider than the browser. Embedded images are re-encoded without the source metadata. Fonts may differ between PNG, HTML, and the terminal.

The combined layout is limited to 20 million pixels, checked before allocating comparison panels or creating the output directory. Use a smaller width if this limit is reached. Existing output files and source aliases are rejected; there is no overwrite or automatic numbering. As with ordinary exports, a write failure may leave a partial newly created file.

Still-image comparison rejects animated or multipage images other than GIFs, videos, text banners, camera inputs, and loop options. Still images export PNG/HTML only. Ordinary conversions without `--compare` keep their existing behaviour. No new Python dependencies are needed. The native preview does not require an external helper; the optional fallback helper is never required for export.

## GIF comparison

```bash
ascart animation.gif --compare --color
ascart animation.gif --compare --color --loop-4
ascart animation.gif --compare --color --output output/comparison.gif
ascart animation.gif --compare --color --border --output output/comparison.html
```

Each decoded frame appears as original-left / ASCII-right, with its source delay (missing/zero delay becomes 100 ms). Both panels use the same composited GIF frame, so they stay synchronized. Colour, palettes, backgrounds, borders, width, and fit work as for image comparisons. The original remains coloured; borders apply only to ASCII.

GIF saves one pass, without loop metadata, and streams pictures instead of collecting them in memory. Identical frames retain their separate delays. GIF supports at most 256 colours per frame, so shades can be approximated; some viewers may repeat the file anyway. The combined frame has the existing 20-million-pixel and GIF dimension limits. HTML embeds each scaled original alongside selectable ASCII, has Play/Pause/Replay and an optional Loop checkbox, and starts paused. It is limited to 3,000 frames and 20 MiB for the complete page.

**Experimental terminal preview:** `--compare` alone plays the comparison once in a terminal with native Kitty graphics support. `--loop`, `--loop-4`, and `--loop-count 4` repeat only terminal playback. Preview decodes one frame at a time and reopens the source for each pass. It reserves one display area, replaces only its own image, and restores the cursor below the final frame on completion or Ctrl+C. Frame rendering/transfer can make playback slower than the source; the display area is sized when playback starts, so resize the terminal before running the command. Both panels are pictures in the terminal, rather than selectable text.

Animated preview requires successful native detection with interactive input/output on the same terminal; the optional `icat` helper fallback is limited to still images. Compatibility remains experimental and needs a physical-terminal check. No output file is created for preview-only commands. Unsupported terminals get an error with GIF/HTML export commands.

With a new `.gif` or `.html` output filename, saving finishes before preview starts. A saved file contains one pass regardless of terminal loop flags. Unavailable/failed/cancelled preview leaves successful exports intact and reports how to view them. Unsupported or redirected terminals can export without playing. Existing files and links are protected. A write error or cancellation may leave a partial newly created GIF; HTML checks frame/size limits before creating the destination. No source media is modified or uploaded.

## Saving a PNG picture

The output filename chooses the format: `.txt` saves characters you can open in a text editor; `.png` saves a picture of those characters. After a successful save, ascart also displays the artwork in the terminal, followed by the saved-file location. PNG saving works for photos and all text-banner styles, without extra dependencies.

```bash
ascart examples/image1.png --output output/penguin-mono.png
ascart examples/image1.png --color --border --output output/penguin-color.png
ascart examples/image1.png --background light --output output/penguin-light.png
ascart --text-bold "Hi" --border --output output/hi.png
```

Pillow draws PNG characters with its built-in regular font and smooth edges at the final picture resolution. Every character occupies a fixed 12-by-22-pixel cell, with 12 pixels of outer padding on each side. Glyphs share a baseline and stay inside their cells, preserving spaces, rows, and borders; wide glyphs are fitted horizontally. This avoids the thick, blocky strokes of the previous enlarged bitmap rendering. Pillow builds without FreeType fall back to the original bitmap renderer. `--width` still chooses character columns; it does not set pixel width. PNG uses its own font rather than your terminal font, so an exact visual match is not guaranteed. Banner font options change the banner's character design, while this fixed font draws those characters into pixels.

Photo PNGs use black backgrounds with white characters in dark mode, or white backgrounds with black characters in light mode. Automatic background selection uses the existing terminal hint. Use `--background dark` or `--background light` for a predictable photo canvas. With `--color`, character strokes use the source RGB colours and the border stays neutral. Smooth edge pixels blend the stroke colour with the canvas background. PNGs are opaque RGB pictures. They contain the converted ASCII artwork, not a copy of the source photo.

PNG pictures larger than 20 million pixels are rejected before allocation; reduce `--width` or shorten the banner text. GIF input saves as `.gif` or animated `.html`, while video input saves as `.mp4` or animated `.html`. Individual animation-frame PNG export is not implemented; camera snapshots can save PNG.

## HTML export

Save photos, text banners, GIFs, and videos as standalone webpages using a new `.html` filename:

```bash
ascart examples/image1.png --color --border --output output/penguin.html
ascart examples/image1.png --background light --output output/penguin-light.html
ascart examples/image1.png --fit --chars " .:*#@" --output output/penguin-custom.html
ascart -t "Hello" --border --output output/hello.html
ascart --text-slant "Hello" --output output/slanted.html
ascart animation.gif --color --border --output output/animation.html
ascart video.mp4 --color --border --output output/video.html
```

Open the saved file in a web browser. Its ASCII characters stay selectable and copyable, with spaces, blank rows, and optional borders preserved. Photos support the existing width/fit, character palette, color, and background options. Banner styles and wrapping are preserved; banners keep their existing restrictions on media-only options and use white text on black.

HTML uses a fixed-width browser font rather than pixels, so its appearance can differ slightly from your terminal or PNG output. Source RGB foreground colors are converted to inline color styles, and color resets keep borders neutral. Dark photo mode uses white text on black; light mode uses black text on white. Automatic mode uses the same terminal hint as other photo output. Image colors themselves are not inverted.

Each file includes its own styles and needs no internet connection, external fonts, or additional Python packages. Photo/banner pages need no JavaScript; animated pages include a small JavaScript player. Characters such as `<`, `>`, quotes, and `&` are escaped so they display as artwork rather than HTML markup. The output contains the ASCII artwork, not the original photo or its source path.

After saving a photo or banner, the artwork is also printed in the terminal, followed by the output location. GIFs and videos get a terminal preview when an interactive terminal is available. Existing files and input aliases are rejected, including files appearing during saving. Parent folders are created as needed. `.HTML` also works; `.htm` is not currently supported. A write failure may leave a partial new file, as with other text exports.

### Animated HTML (GIF and video)

The page opens paused on its first frame. Click **Play** to play once, **Pause** to stop on the current frame, and **Play** again to resume. **Replay** starts over immediately. Playback ends on the last frame; Play after finishing starts a new pass. Characters remain selectable. With JavaScript disabled, the first frame is still visible.

GIF and camera-recording HTML pages also have a **Loop** checkbox, off by default. Check it and click Play to repeat until paused. Uncheck it during playback to finish the current pass and stop. Checking it while paused or finished does not start playback by itself. Looping reuses the saved frames; it never adds extra copies. Video HTML pages keep the Play, Pause, and Replay controls without this checkbox.

The file contains one complete sequence, regardless of `--loop`, `--loop-4`, or `--loop-count`. Those options control only the terminal preview, which starts after saving when a terminal is available. Without an interactive terminal, saving works and skips that preview. GIF delays are preserved (missing/zero delays use 100 ms). Video uses its reported FPS, or a warned 30 FPS fallback, and contains no audio. Variable-frame-rate timing is approximated; browser scheduling and background-tab throttling can slow playback.

Color, border, custom characters, width/fit, and background selection apply to every frame. HTML stores text and RGB styles rather than embedded GIF/MP4 pictures. All frames are bundled for offline playback, so exports are limited to **3,000 frames and 20 MiB per HTML file**. Either limit rejects the whole save before creating an output file or its folders; it never silently truncates the animation. Use a shorter source or smaller width if needed. At 30 FPS, 3,000 frames is about 100 seconds; the size limit may be reached sooner, especially with color. Conversion collects bounded frame markup in memory; large individual frames can still require substantial memory. No automatic frame dropping or time-limit option is added.

Artwork is escaped before display, and the embedded frame data is encoded to prevent characters such as `</script>` from becoming page instructions. The player uses no network resources and contains no source path or original media. OpenCV can report a damaged video tail as end-of-file, the same decoding limitation as MP4 export.

## Optional border

Add `--border` to a photo, text, GIF, or video command to frame the artwork with ordinary ASCII characters:

```text
+-----+
|ASCII|
|ART  |
+-----+
```

Rows of different lengths are padded to align the right edge. RGB color codes do not count toward the visible width, and color is reset before the right edge so the frame uses the normal terminal foreground. Photo and banner TXT/PNG/HTML output, animated HTML, and saved GIF/MP4 frames include the border.

`--width` describes the artwork inside the frame; a 60-column image becomes 62 columns wide with the border. Banner width still controls wrapping, and its frame surrounds the longest rendered row. The border adds two rows as well. For photos/GIFs/videos, `--fit --border` reserves those extra dimensions within the existing terminal margins. A terminal smaller than four columns by five rows is rejected in this mode. Text banners still do not support `--fit`.

For animation, the same frame decoration is applied on every playback pass. Sources with constant frame dimensions keep a consistent frame size. Without `--border`, output follows the existing rendering path.

## GIF playback and saving

Supply your own GIF and replace `animation.gif` in the [GIF command guide](../README.md#gif-commands) with its location.

- Without a loop option, playback stops after one pass.
- `--loop` repeats continuously until Ctrl+C.
- `--loop-4` plays four times in total. Other positive counts work the same way; `--loop-count 4` is also supported.
- Continuous and counted loop options cannot be combined. Loop options work with GIFs and videos.

Playback requires an interactive terminal supporting ANSI screen and cursor controls. It clears the current screen, replaces each frame, and leaves the final frame visible. Ctrl+C stops playback and restores cursor visibility. Saving with `--output` also works without an interactive terminal; it skips playback in that case.

Frame durations come from the GIF in milliseconds. Missing or zero timing uses a 100 ms fallback. Terminal playback follows the command-line loop choice rather than the GIF's loop metadata.

Use a new `.gif` output filename to save the complete converted animation. Existing files, input-file aliases, and symbolic links are rejected. Parent folders are created as needed. `.GIF` also works. GIF input also supports animated `.html` output; it does not save as `.txt` or `.png`; photo/banner input does not save as `.gif`.

The output stores one pass of the source frames with their timings. It omits GIF repeat metadata, requesting one playback even if the source repeats forever. `--loop`, `--loop-4`, and `--loop-count` control only the terminal preview; they never duplicate saved frames or change the saved GIF's repeat behavior. No saved-loop setting is offered yet. External viewers can override a GIF's playback behavior.

Saving finishes before terminal playback starts. The saved-file location is printed after playback finishes, including when Ctrl+C stops continuous playback. If saving fails, no terminal preview begins. Interrupting playback leaves the completed file intact. Without an interactive terminal, only the saved-file location is printed and loop options have no playback to repeat.

Saved GIF frames keep the existing enlarged bitmap font, with the same 12-by-22 character grid and padding as PNG output. PNG uses smoother regular glyphs; GIF rendering has not changed. Color, custom palettes, backgrounds, width, terminal fitting, and borders apply to the saved artwork. Each frame is converted to at most 256 colors because that is a GIF limit; this may approximate source RGB colors. Consecutive frames that become visually identical may be combined by Pillow, preserving their combined duration. The per-picture 20-million-pixel limit also applies to rendered GIF frames. ASCII and picture frames are held in memory during export, so use smaller widths for large animations. This is one complete-animation export, not an unlimited terminal recording.

The enlarged bitmap font and dense default color characters (`#%@`) can make saved artwork look thicker than terminal text. No additional bold styling is applied. Use a custom `--chars` palette if you prefer lighter characters.

GIF's per-frame timing field allows at most 655.35 seconds. If consecutive frames become identical ASCII art, Pillow can merge their delays and exceed this limit. Saving then reports a readable timing error; use a shorter animation. As with other write failures, a partial new output file may remain.

GIF also limits each picture dimension to 65,535 pixels. Oversized rendered frames are rejected before destination creation; reduce `--width` if this happens.

## Combining options

| Combination | Result |
| --- | --- |
| Photo: color + border + custom characters + width or fit + PNG or HTML output | Supported; the saved artwork and terminal preview use the selected options. |
| Photo: color + text-file output | Supported, but the saved text and preview are plain characters. |
| GIF: color + border + custom characters + width or fit + GIF or HTML output + terminal loop count | Supported; the file stores one animation, independently of terminal repeats. |
| Video: color + border + custom characters + width or fit + MP4 or HTML output + terminal loops | Supported; the saved video contains one pass without audio. |
| Text: banner style + width + border + TXT, PNG, or HTML output | Supported. |
| Width + fit, or continuous loop + counted loop | Rejected: choose one sizing method and one loop mode. |
| Text banners + color, fit, custom characters, manual background, or looping | Rejected: those options apply to media conversion. |

For palettes beginning with `-`, use the equals form, for example `--chars=-+@`, so the argument parser treats the palette as a value. Text starting with option-like words can also use equals, for example `--text=--loop-4` renders that literal text.

## Video playback and MP4 saving

Supply your own local video and replace the filenames in the [video command guide](../README.md#video-commands) with its location.

The CLI detects the media type; no extra video switch is required. The default width is 60, and the same width, fitting, color, palette, and background controls used for photos apply to videos. Decoding depends on the formats and codecs supported by the installed OpenCV package. A file extension alone does not guarantee support; MP4 and MJPG AVI decoding have been checked in development.

Video plays once by default, without audio. It uses the same loop options as GIFs:

- `--loop` repeats continuously until Ctrl+C.
- `--loop-4` plays four times in total; `--loop-count 4` means the same thing. Other positive counts are supported.
- Continuous and counted loop options cannot be combined. Zero and negative counts are rejected; use `--loop` for continuous playback.

Playback requires an interactive terminal supporting ANSI controls, clears the screen, replaces frames, and leaves the last frame visible. Ctrl+C stops playback, closes the video reader, and restores cursor visibility. With `--output`, saving also works without an interactive terminal and skips playback in that case.

OpenCV reads one frame at a time. Each frame is converted and displayed before reading the next, so ascart does not collect the whole video's converted frames in memory. It uses the video's reported FPS (frames per second) to calculate the time between frames, subtracting the time already spent reading, converting, and printing. Unknown FPS triggers a warning and a 30 FPS fallback.

For each repeat, the previous video reader is closed and a new one opens the file from the beginning. This keeps memory usage independent of the number of repetitions, though reopening can add a short pause between playbacks. If reopening fails or a pass has no decodable frames, playback stops with an error instead of retrying endlessly.

For inspection from Python, `ascart.video_art.inspect_video(path)` returns dimensions, reported FPS/frame count, and estimated duration. Unknown metadata is returned as `None`. Duration is estimated from frame count divided by FPS.

Use a new `.mp4` output filename to save one complete ASCII video without audio. `.MP4` also works. Any decodable video input, including supported AVI files, can produce MP4 output. Video input also supports animated `.html` output; it does not save as `.gif`, `.txt`, or `.png`; GIF input does not save as MP4.

Each decoded frame becomes ASCII text and then a picture using the existing enlarged bitmap font. MP4 keeps the same character grid, padding, backgrounds, and optional colours/borders as PNG saving; the smoother PNG font does not change MP4 rendering. OpenCV encodes those pictures with `mp4v` at the source's reported FPS. Missing or invalid FPS produces a warning and uses 30 FPS. The rendered pixel dimensions are even, as required by the encoder. Frames are processed one at a time, and every saved frame must have the same dimensions. Lossy video compression may slightly change character edges and RGB colors. MP4 viewers choose their own repeat behavior; the file contains no duplicated terminal playback passes.

The video is encoded once before the terminal preview starts. `--loop`, `--loop-4`, and `--loop-count` affect only that preview. Ctrl+C during preview leaves the completed MP4 intact. Without an interactive terminal, saving prints the saved-file location without playback. Interrupting encoding stops the save and cleans up its temporary files.

OpenCV writes into a private temporary folder beside the requested destination. After encoding closes, ascart decodes every generated frame to check the frame count and dimensions. Only then does it copy the video into a new file opened in exclusive creation mode. This protects existing files even if another program creates the destination during encoding. Temporary files are cleaned up after success, handled failure, or Ctrl+C; a hard process kill or shutdown can leave a temporary folder behind. `.ascart-*/` folders are ignored by Git to avoid accidentally committing such leftovers. Encoding and copying require enough free space for both the temporary video and the final copy. A failure during the final copy can leave a partial new destination, but never replaces an existing one.

MP4 encoding requires an available `mp4v` encoder in OpenCV; ascart reports an error if it cannot open one. Readback verification detects missing encoded frames, but cannot prove that a damaged source was decoded completely: OpenCV can report a failed read for both the end of a video and a damaged tail. Source video timestamps are approximated using one FPS, so variable-frame-rate timing is not preserved exactly. No extra dependencies or command-line recording limits were added.

## Live camera (experimental)

**Experimental feature:** basic live viewing has been checked on one local webcam. Automated tests use simulated cameras; broad hardware and operating-system compatibility has not been verified. Expect device-specific issues and report your operating system, camera model, command, and full error output when asking for help.

Run `ascart --camera` in an interactive terminal. Camera 0 is the default; choose another nonnegative ID with `ascart --camera 1`. Camera IDs can change after reconnecting devices. There is no extra window. Width (default 60), fit, colour, custom palettes, background mapping, and borders work like video playback. Choose either width or fit. Terminal fitting is calculated once at startup.

The default `--camera` view horizontally flips each incoming frame before ASCII conversion. Use `--camera-mirrored` instead to keep the camera-supplied orientation. Both commands accept an optional camera ID and the same visual options, for example `ascart --camera-mirrored 1 --color --width 120`. Choose one camera command; combining them is rejected. The camera/driver may already transform its frames, so these settings describe how ascart treats the supplied image rather than guaranteeing a physical orientation for every device. Photo, GIF, and video orientation is unchanged.

Lighting and camera placement strongly affect the visible detail and colours. Light the subject well and try `--width 120` for more detail if your terminal is wide enough. A dense palette such as `ascart --camera --color --width 120 --chars '@'` gives source colours more visible character strokes. You can also experiment with `--chars '@%&#$8BMWQ'`; single quotes keep `$` literal in the shell. These are optional palettes: the existing colour default remains `#%@`, and no automatic brightness or saturation enhancement is applied.

A camera opens only when you explicitly request camera viewing, a snapshot, timed recording, or camera listing. Ordinary text, photo, GIF, video, version, and help commands do not access cameras. OpenCV asks the operating system to open the local device; it reads one frame at a time, uses the existing video-to-ASCII conversion, and updates the terminal with up to 30 redraws per second. Processing or capture can make it slower. Live frames stay in memory. A snapshot is saved only when --output is supplied; no camera frames are uploaded. Recording requires an explicit duration and MP4/GIF/HTML output; unlimited recording is not supported. No new runtime dependency is needed.

`--list-cameras` briefly opens candidates and tries to read one frame, then releases them. On Linux it checks the IDs in `/dev/video*`; on other systems it probes IDs 0–9. It reports accessible capture IDs rather than a complete inventory or friendly hardware names. One physical webcam may expose multiple device IDs; some devices are metadata-only or cannot supply images. A failed probe may mean missing hardware, permission restrictions, an unsupported driver, or a camera used by another application. You can explicitly try an ID outside the non-Linux listing range. Listing also works without an interactive terminal. Devices are checked in sequence; driver opening/reading can be slow, and OpenCV provides no universal camera timeout for these operations.

Press Ctrl+C to stop. Cleanup releases the active camera, resets terminal colours, and restores cursor visibility after display begins. A missing first frame or a later disconnected camera produces a readable error. Native camera drivers can block while opening/reading, which can delay interruption; a forced kill or terminal failure cannot guarantee terminal cleanup. If access is blocked, check operating-system camera settings or close other camera applications. ascart does not change permissions or require sudo.

Camera mode supports one snapshot with `--output` or a timed MP4/GIF/HTML recording with `--camera-duration` plus `--output`, but rejects `--loop`, `--loop-4`, and `--loop-count`. Without output, a live stream already runs until stopped. It also rejects combining camera selection, listing, text input, or a media path. Invalid options and non-interactive playback are rejected before opening a device. Use visual options with --camera; listing rejects settings such as colour, borders, custom palettes, and fitting. HTML without duration remains a static snapshot; with duration it becomes an animation.

### Camera snapshots

Use a new `.txt`, `.png`, or `.html` output filename with either camera command. In an interactive terminal, it opens the selected camera and shows live ASCII with a **3 → 2 → 1** countdown beneath it. At the end it captures one final frame, freezes that frame on screen, closes the camera, then saves the same artwork and prints its location. The countdown disappears and the captured snapshot stays visible. The countdown begins after the camera opens; camera/driver delays can make the total command longer than three seconds. Frames continue to be read during the countdown so the final read supplies a recent picture and gives automatic exposure a chance to settle. Preview frames use the same orientation, size, colours, palette, and border as the snapshot. The countdown is not configurable yet. The status line is clipped to the terminal width to avoid wrapping when using --fit.

```bash
ascart --camera --color --width 120 --chars '@' --output output/camera.png
ascart --camera --border --output output/camera.txt
ascart --camera-mirrored 1 --color --output output/camera.html
```

Both orientations, width/fit, borders, custom palettes, and background options apply. TXT saves and previews stay plain even with --color; PNG/HTML save and preview colours. HTML contains a static, selectable frame, not an animation. Snapshots also work without an interactive terminal; they skip the animated preview and screen-control codes, print the countdown to standard error, and save/display only the final frame. Only unsaved live viewing requires an interactive terminal. The camera is released before rendering or writing the output file.

Existing files, directories, and links are rejected before the camera opens. The final save also uses exclusive creation, protecting a file created by another program during the countdown. Parent folders are created only after successful capture and rendering. Ctrl+C during the countdown closes the camera, reports cancellation, and creates no output. A capture or rendering failure also creates no output file. If saving or output rendering fails after an interactive capture, the frozen snapshot remains visible with the error; no success message is printed. A write failure can leave a partial new file, but never replaces existing data. For timed MP4/GIF/HTML instead of a snapshot, add --camera-duration as described below. Camera snapshots remain experimental and depend on local hardware/driver compatibility.

### Timed camera recording

Recording requires a camera input, a finite duration **greater than 0 and at most 300 seconds**, and a new `.mp4`, `.gif`, or `.html` output filename. Fractional seconds and uppercase extensions work. MP4/GIF require duration; HTML without duration saves a static snapshot. Duration with TXT/PNG, non-camera input, camera listing, or loop options is rejected before camera access. Snapshot commands without duration keep the three-second countdown.

```bash
ascart --camera --color --width 120 --chars '@' --camera-duration 10 --output output/camera.mp4
ascart --camera --color --width 60 --camera-duration 10 --output output/camera.gif
ascart --camera --color --width 60 --camera-duration 10 --output output/camera.html
ascart --camera-mirrored 1 --fit --border --camera-duration 5 --output output/camera-alt.mp4
```

Recording starts when the camera and first ASCII frame are ready (and the MP4 encoder is open, for MP4); it has no snapshot countdown. An interactive terminal shows the ASCII frames and time remaining, then leaves the last frame visible with the output location. Without an interactive terminal, it records without preview and prints progress to standard error and the saved location to standard output. Both orientations and existing visual settings apply. GIF and MP4 pictures use the smoother PNG font; HTML uses selectable browser text with its own fixed-width font. No format records audio; existing video-file conversion retains its previous bitmap font.

All camera recordings target **15 frames per second**. MP4 uses fixed 15 FPS, HTML uses approximately 66.67 ms per frame, and GIF alternates 60/70 ms delays to respect its 10 ms timing units without speeding up the whole animation. A monotonic clock controls the recording interval, separately from setup, verification, and copying. Slow capture or rendering repeats the latest available frame in missed output slots rather than making the saved video play faster. MP4 and camera GIF frames are streamed to disk; camera GIF encoding retains only the current frame's pictures and encoded data, instead of buffering the whole animation. HTML buffers escaped frame text, subject to the format limits below. Duration is rounded up to a whole frame (less than one extra 15-FPS frame), with GIF timing additionally rounded to 10 ms. Native camera/driver calls can block or overrun the deadline, so the requested duration is not a hard hardware timeout. Hardware compatibility and timing remain experimental.

Camera GIF encoding reuses the latest artwork's encoded bytes for repeated output slots, caching at most two delay variants instead of redrawing every repeat. This reduces work when the camera or renderer cannot keep up. `Encoding GIF` and `Checking GIF` frame counters, followed by a copying message, show progress on standard error. GIF checking decodes the completed animation once. Saving and checking may continue after the recording countdown reaches zero; larger widths still require more processing.

Press **Ctrl+C to cancel** during capture: the camera and any active encoder close, temporary output is cleaned up, and no completed recording is published. A disconnect, changed rendered dimensions, or encoder failure also aborts. Existing destinations and links are rejected before access. Saving uses a private `.ascart-*` directory beside the destination. MP4 is read back to verify frame count and dimensions; camera GIF is decoded to verify frame count, dimensions, and total timing. Camera GIF preserves each frame, including repeated pictures. HTML uses the existing escaped, bounded page writer. After capture closes and saving succeeds, the result is copied to an exclusively created destination. A competing file is preserved. Temporary output is cleaned up on handled failures, but empty parent directories may remain; a hard kill can leave a private folder behind. A final-copy failure or interruption may leave a partial new destination, without replacing existing files. Sufficient space for the temporary output and final copy is needed.

Format limits:

- **GIF:** camera recordings no longer have the old 64-million-pixel aggregate limit. Widths such as `--width 140` can be used without collecting every picture in memory. The existing **20-million-pixel limit per rendered picture**, GIF's 65,535-pixel limit per side, and 300-second recording limit still apply. Larger widths require more processing and disk space; MP4 generally produces smaller recordings. Each frame supports at most 256 colours, so RGB shades may be approximated. The file contains one pass and omits loop metadata; an external viewer may choose to repeat it.
- **HTML:** at most **3,000 frames and 20 MiB**, including the player. At 15 FPS, a duration above **200 seconds** is rejected before camera access. The byte limit may be reached much sooner with large coloured frames; reduce width or duration. Play, Pause, Replay, and an unchecked-by-default Loop checkbox control browser playback independently of capture duration.
- A limit error aborts the export, releases the camera, and preserves the requested destination. It never silently truncates the recording.

Automated camera tests use simulated devices and never access real cameras. Check actual compatibility, colours, responsiveness, and camera release on your own hardware before relying on this feature.

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
| Output supports .txt/.png/.html for photos/banners, .gif/.html for GIF input, or .mp4/.html for video input | Match the output format to the input. |
| GIF output supports only .gif and .html files | Use a new `.gif` or `.html` filename for GIF input. |
| Video output supports only .mp4 and .html files | Use a new `.mp4` or `.html` filename for video input. |
| MP4 encoding is unavailable | The OpenCV installation needs an available `mp4v` encoder. |
| Incomplete MP4 encoding | The temporary encoding failed verification; the final destination was not created. |
| HTML animation exceeds 3000 frames / 20 MiB | Use a shorter source or smaller width. No output is created. |
| PNG would exceed 20 million pixels | Reduce `--width` or shorten the banner text. |
| No space left on device | Free storage space or choose another output location. |

If Pillow cannot identify a photo/GIF, ascart checks whether OpenCV can decode a video frame before treating the input as a video. This avoids reporting video-only option errors for an unrelated or unreadable media file. This check does not verify every frame in a video.

Photo and text saving share the same rules. Without `--output`, artwork is displayed in the terminal. With `--output`, artwork is saved and then displayed in the terminal, followed by the saved-file location. A non-empty path ending in `.txt`, `.png`, or `.html` is required (uppercase extensions also work). The terminal preview uses the same artwork: `.txt` saves and previews remain plain, while colored PNG/HTML saves also show colored characters in the terminal. If saving fails, ascart reports the error without printing a preview or success message. Quote paths containing spaces. Empty or whitespace-only arguments and unsupported extensions are rejected before conversion or folder creation. Repeating a save command with the same destination produces an error; choose a new filename.

Input/output aliases, existing files, directories, and existing symbolic links are rejected as destinations. Parent folders are created when possible. Files are opened in exclusive creation mode, which also refuses replacement if a destination appears after validation. Input media is opened for reading. A failure during writing or closing can leave a partial new file, but no success message is printed and existing files are not overwritten. These protections also apply to GIF and MP4 saving. Automatic numbering and overwriting are not implemented.

## How conversion works

1. Pillow opens a photo or decodes a GIF frame. For video, OpenCV decodes a frame, its BGR color order is changed to RGB, and Pillow receives the resulting image.
2. A grayscale copy supplies pixel brightness values from 0 to 255.
3. The image is resized for the chosen character grid. A factor of 0.5 approximately compensates for terminal characters being taller than they are wide.
4. Each brightness value selects a character using `brightness * len(palette) // 256`. Integer division gives the palette position, allocating near-equal brightness bands. Brightness must be an integer in the range 0–255, as supplied by Pillow's grayscale pixels.
5. For color output, a resized RGB copy supplies each character's foreground color.
6. Rows are joined into text, then printed, saved, or displayed as animation frames.

Photos, GIFs, videos, and camera frames share the same image conversion function.

## Current limitations and future work

- Camera mode supports live viewing, one-frame TXT/PNG/HTML snapshots, and bounded GIF/HTML/silent MP4 recording with format limits. Camera access depends on the operating system, permissions, drivers, and hardware.

- Video playback and saved MP4s have no audio. Codec availability depends on the OpenCV installation; export currently uses `mp4v` only.
- Video timing uses a single reported FPS; variable-frame-rate timing is approximate. Slow processing or terminal output slows playback because frames are not skipped, and small scheduling delays can accumulate.
- GIF-file playback converts frames into memory, and GIF-file export also holds rendered picture frames in memory. Large input animations can consume substantial memory. Camera GIF recording writes frames incrementally instead.
- GIF playback does not compensate for terminal rendering overhead.
- Terminal fitting reads dimensions once per command. Resize the terminal and rerun to recalculate. If size detection is unavailable, fitting uses an 80-column by 24-row fallback before margins.
- A fixed width can exceed a small terminal. Use `--fit` when needed.
- Color strength depends on the chosen characters, terminal background, and font. Spaces have no visible foreground strokes.
- Automatic background detection still relies on a limited terminal hint.
