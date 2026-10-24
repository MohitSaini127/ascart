"""Render a still image beside its ASCII artwork for PNG and offline HTML."""

import base64
from contextlib import closing
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from ascart.border import COLOR_CODE
from ascart.html_art import art_to_html
from ascart.png_art import art_to_png


GAP = 24
LABEL_HEIGHT = 32
MAX_COMPARISON_PIXELS = 20_000_000


def _layout(art):
    rows = COLOR_CODE.sub("", art).split("\n")
    artwork_size = (max(1, max(map(len, rows))) * 12 + 24, len(rows) * 22 + 24)
    panel_size = (max(96, artwork_size[0]), artwork_size[1])
    size = (panel_size[0] * 2 + GAP, panel_size[1] + LABEL_HEIGHT)
    if size[0] * size[1] > MAX_COMPARISON_PIXELS:
        raise ValueError("Comparison would exceed 20 million pixels; use a smaller --width")
    return artwork_size, panel_size, size


def _source_panel(image, size, background):
    """Fit without cropping, compositing transparent pixels on the canvas."""
    ratio = min((size[0] - 24) / image.width, (size[1] - 24) / image.height)
    fitted = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
    canvas = Image.new("RGB", size, "white" if background == "light" else "black")
    try:
        with closing(image.convert("RGBA")) as rgba:
            with closing(rgba.resize(fitted, Image.Resampling.LANCZOS)) as resized:
                position = ((size[0] - fitted[0]) // 2, (size[1] - fitted[1]) // 2)
                canvas.paste(resized, position, resized)
        return canvas
    except BaseException:
        canvas.close()
        raise


def comparison_to_png(image, art, background="dark"):
    """Return the labelled original-left / ASCII-right RGB comparison."""
    _, panel_size, size = _layout(art)
    canvas = Image.new("RGB", size, "white" if background == "light" else "black")
    try:
        with closing(_source_panel(image, panel_size, background)) as original:
            canvas.paste(original, (0, LABEL_HEIGHT))
        with closing(art_to_png(art, background)) as artwork:
            canvas.paste(artwork, (panel_size[0] + GAP + (panel_size[0] - artwork.width) // 2, LABEL_HEIGHT))
        try:
            font = ImageFont.load_default(size=16)
        except ImportError:
            font = ImageFont.load_default_imagefont()
        ink = "black" if background == "light" else "white"
        draw = ImageDraw.Draw(canvas)
        draw.text((12, 8), "Original", fill=ink, font=font)
        draw.text((panel_size[0] + GAP + 12, 8), "ASCII", fill=ink, font=font)
        return canvas
    except BaseException:
        canvas.close()
        raise


def comparison_to_html(image, art, background="dark"):
    """Embed a scaled source copy while keeping the ASCII panel selectable."""
    artwork_size, panel_size, _ = _layout(art)
    with closing(_source_panel(image, panel_size, background)) as original, BytesIO() as buffer:
        original.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    width, height = panel_size
    styles = f'''
.comparison {{ display: grid; grid-template-columns: repeat(2, {width}px); gap: {GAP}px; width: max-content; }}
figure {{ margin: 0; }}
figcaption {{ height: {LABEL_HEIGHT}px; padding-left: 12px; box-sizing: border-box; font: 16px sans-serif; }}
.panel {{ width: {width}px; height: {height}px; display: grid; place-items: center; }}
img {{ display: block; }}
pre {{ width: {artwork_size[0]}px; height: {artwork_size[1]}px; padding: 12px; box-sizing: border-box; line-height: 22px; }}
pre, code {{ font-size: 20px; }}
'''
    document = art_to_html(art, background).replace("</style>", styles + "</style>")
    opening = f'''<section class="comparison" aria-label="Original and ASCII comparison">
<figure><figcaption>Original</figcaption><img src="data:image/png;base64,{encoded}" width="{width}" height="{height}" alt="Original image, scaled to fit"></figure>
<figure><figcaption>ASCII</figcaption><div class="panel">'''
    document = document.replace('<pre aria-label="ASCII artwork">', opening + '<pre aria-label="ASCII artwork">', 1)
    return document.replace("</pre>", "</pre></div></figure></section>", 1)
