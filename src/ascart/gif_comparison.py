"""Export synchronized original/ASCII GIF comparisons without buffering pictures."""

import json
import re
from contextlib import ExitStack, closing
from pathlib import Path

from PIL import GifImagePlugin, Image

from ascart.border import add_border
from ascart.comparison import comparison_to_html, comparison_to_png
from ascart.html_art import (
    ANIMATION_PLAYER, MAX_ANIMATION_BYTES, MAX_ANIMATION_FRAMES, art_to_markup,
)
from ascart.image_art import image_to_ascii


def comparison_frames(path, *, width, palette, background, max_height, color, border):
    """Decode each composited source frame and convert that very same picture."""
    with Image.open(path) as source:
        for index in range(source.n_frames):
            source.seek(index)
            duration = source.info.get("duration", 0) or 100
            with closing(source.convert("RGBA")) as frame:
                art = image_to_ascii(frame, width, palette, background, max_height, color)
                yield frame, add_border(art) if border else art, duration


def save_comparison_gif(frames, output, background="dark"):
    """Stream complete GIF frames, retaining identical frames and their delays."""
    count = 0
    size = None
    with ExitStack() as resources:
        file = None
        for source, art, duration in frames:
            with closing(comparison_to_png(source, art, background)) as picture:
                if max(picture.size) > 65535:
                    raise ValueError("GIF dimensions exceed 65,535 pixels; use a smaller --width")
                if size is not None and picture.size != size:
                    raise ValueError("GIF comparison frames must have the same dimensions")
                with closing(picture.convert("P", palette=Image.Palette.ADAPTIVE,
                                             colors=256, dither=Image.Dither.NONE)) as indexed:
                    if file is None:
                        size = picture.size
                        destination = Path(output)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        file = resources.enter_context(destination.open("xb"))
                        header, _ = GifImagePlugin.getheader(indexed, info={"optimize": False})
                        file.writelines(header)
                    file.writelines(GifImagePlugin.getdata(
                        indexed, duration=duration, disposal=2, include_color_table=True,
                    ))
            count += 1
        if file is None:
            raise ValueError("No frames to save")
        file.write(b";")
    return count


def save_comparison_html(frames, output, background="dark"):
    """Keep selectable artwork and embedded originals on the same player clock."""
    player = ANIMATION_PLAYER.replace(
        "<!-- LOOP_CONTROL -->",
        '<label><input id="loop" type="checkbox"> Loop</label>',
    ).replace(
        "artwork.innerHTML = frames[index][0];",
        'artwork.innerHTML = frames[index][0];\n'
        '    document.querySelector(".comparison img").src = frames[index][2];',
    )
    entries = []
    first = None
    size = 0
    for source, art, duration in frames:
        if len(entries) >= MAX_ANIMATION_FRAMES:
            raise ValueError("HTML animation exceeds 3000 frames; use a shorter source")
        # The still comparison renderer supplies the layout, strips metadata,
        # and composites transparency before encoding the embedded PNG.
        page = comparison_to_html(source, art, background)
        image = re.search(r'<img src="([^"]+)"', page).group(1)
        entry = json.dumps([art_to_markup(art), duration, image], separators=(",", ":"))
        entry = entry.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        if first is None:
            first = page
            size = len((page + player + '<script id="frames" type="application/json">[]</script>\n').encode("utf-8"))
        size += len(entry.encode("utf-8")) + bool(entries)
        if size > MAX_ANIMATION_BYTES:
            raise ValueError("HTML animation exceeds 20 MiB; use a smaller --width or shorter source")
        entries.append(entry)
    if first is None:
        raise ValueError("No frames to save")
    data = '<script id="frames" type="application/json">[' + ",".join(entries) + ']</script>\n'
    document = first.replace("</body>", data + player + "</body>")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as file:
        file.write(document)
    return len(entries)
