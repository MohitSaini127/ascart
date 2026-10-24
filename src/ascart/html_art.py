"""Create a standalone webpage containing selectable ASCII artwork."""

import json
import math
import re
from pathlib import Path
from html import escape

from ascart.border import COLOR_CODE


def art_to_markup(art):
    """Escape artwork and translate ascart's foreground colors into spans."""
    pieces = []
    foreground = None
    for part in re.split(r"(\x1b\[[0-9;]*m)", art):
        if COLOR_CODE.fullmatch(part):
            values = part[2:-1].split(";")
            if values == ["0"]:
                foreground = None
            elif len(values) == 5 and values[:2] == ["38", "2"]:
                foreground = tuple(int(value) for value in values[2:])
                if any(value > 255 for value in foreground):
                    raise ValueError("HTML foreground colors must be between 0 and 255")
            else:
                raise ValueError("Unsupported color code in HTML artwork")
        elif part:
            text = escape(part)
            if foreground is not None:
                red, green, blue = foreground
                text = f'<span style="color:rgb({red},{green},{blue})">{text}</span>'
            pieces.append(text)
    return "".join(pieces)


def art_to_html(art, background="dark"):
    """Create a standalone page with selectable, escaped artwork."""
    canvas = "#ffffff" if background == "light" else "#000000"
    ink = "#000000" if background == "light" else "#ffffff"
    scheme = "light" if background == "light" else "dark"
    # The code element preserves an initial blank row that HTML would strip
    # if a newline appeared immediately after the opening pre tag.
    content = art_to_markup(art)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ascart ASCII art</title>
<style>
:root {{ color-scheme: {scheme}; }}
body {{ margin: 0; padding: 24px; background: {canvas}; color: {ink}; }}
pre {{ margin: 0; white-space: pre; line-height: 1.2; }}
pre, code {{ font-family: "Courier New", Courier, monospace; font-size: 14px; font-variant-ligatures: none; }}
</style>
</head>
<body>
<pre aria-label="ASCII artwork"><code>{content}</code></pre>
</body>
</html>
'''


MAX_ANIMATION_FRAMES = 3000
MAX_ANIMATION_BYTES = 20 * 1024 * 1024

# Only generated, escaped artwork is assigned to innerHTML. Frame data is
# separately JSON-encoded and cannot close its containing script element.
ANIMATION_PLAYER = '''
<p>
<button id="play" type="button">Play</button>
<button id="pause" type="button" disabled>Pause</button>
<button id="replay" type="button">Replay</button>
<!-- LOOP_CONTROL -->
<span id="status" role="status">Ready</span>
</p>
<noscript>Enable JavaScript to play the animation. The first frame remains visible.</noscript>
<script>
"use strict";
const frames = JSON.parse(document.getElementById("frames").textContent);
const artwork = document.querySelector("pre code");
const play = document.getElementById("play");
const pause = document.getElementById("pause");
const replay = document.getElementById("replay");
const loop = document.getElementById("loop");
const status = document.getElementById("status");
let index = 0, timer = null, deadline = 0, remaining = frames[0][1], ended = false;
function show() {
    artwork.innerHTML = frames[index][0];
    status.textContent = `Frame ${index + 1} of ${frames.length}`;
}
function stop() {
    if (timer !== null) {
        remaining = Math.max(0, deadline - performance.now());
        clearTimeout(timer);
        timer = null;
    }
    play.disabled = false;
    pause.disabled = true;
}
function schedule() {
    deadline = performance.now() + remaining;
    timer = setTimeout(() => {
        timer = null;
        if (index + 1 === frames.length) {
            if (loop && loop.checked) {
                index = 0;
            } else {
                ended = true;
                stop();
                status.textContent = "Finished";
                return;
            }
        } else {
            index += 1;
        }
        remaining = frames[index][1];
        show();
        schedule();
    }, remaining);
}
function start() {
    if (timer !== null) return;
    if (ended) {
        index = 0;
        remaining = frames[0][1];
        ended = false;
    }
    show();
    play.disabled = true;
    pause.disabled = false;
    schedule();
}
play.addEventListener("click", start);
pause.addEventListener("click", stop);
replay.addEventListener("click", () => {
    stop();
    ended = true;
    start();
});
</script>
'''


def save_animated_html(frames, output, background="dark", loop_control=False):
    """Consume one pass of (art, milliseconds) into a bounded, offline player."""
    entries = []
    first = None
    control = '<label><input id="loop" type="checkbox"> Loop</label>' if loop_control else ""
    player = ANIMATION_PLAYER.replace("<!-- LOOP_CONTROL -->", control)
    # Count the entire document, including both copies of the initial frame.
    size = len(art_to_html("", background).encode("utf-8"))
    size += len(player.encode("utf-8")) + len('<script id="frames" type="application/json">[]</script>\n')
    for art, duration in frames:
        if len(entries) >= MAX_ANIMATION_FRAMES:
            raise ValueError("HTML animation exceeds 3000 frames; use a shorter source")
        if not math.isfinite(duration) or duration <= 0:
            duration = 100
        if duration > 2147483647:
            raise ValueError("HTML frame duration exceeds the browser timer limit")
        markup = art_to_markup(art)
        entry = json.dumps([markup, duration], ensure_ascii=True, separators=(",", ":"))
        entry = entry.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        size += len(entry.encode("utf-8")) + (1 if entries else 0)
        if first is None:
            first = art
            size += len(markup.encode("utf-8"))
        if size > MAX_ANIMATION_BYTES:
            raise ValueError("HTML animation exceeds 20 MiB; use a smaller --width or shorter source")
        entries.append(entry)
    if first is None:
        raise ValueError("No frames to save")
    data = '<script id="frames" type="application/json">[' + ",".join(entries) + ']</script>\n'
    document = art_to_html(first, background).replace("</body>", data + player + "</body>")
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as file:
        file.write(document)
    return len(entries)
