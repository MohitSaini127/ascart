"""Create a standalone webpage containing selectable ASCII artwork."""

import re
from html import escape

from ascart.border import COLOR_CODE


def art_to_html(art, background="dark"):
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
    canvas = "#ffffff" if background == "light" else "#000000"
    ink = "#000000" if background == "light" else "#ffffff"
    scheme = "light" if background == "light" else "dark"
    # The code element preserves an initial blank row that HTML would strip
    # if a newline appeared immediately after the opening pre tag.
    content = "".join(pieces)
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
