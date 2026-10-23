"""Draw generated ASCII artwork on a fixed character grid using Pillow."""

import re

from PIL import Image, ImageDraw, ImageFont

from ascart.border import COLOR_CODE


def art_to_png(art, background="dark"):
    """Return an RGB picture, including the converter's foreground colors."""
    rows = art.split("\n")
    columns = max(len(COLOR_CODE.sub("", row)) for row in rows)
    # Pillow's built-in bitmap font has fixed 6-by-11 cells. Unlike a system
    # font, it is available wherever this project's Pillow dependency runs.
    cell_width, cell_height, padding, scale = 6, 11, 6, 2
    size = (max(1, columns) * cell_width + padding * 2,
            len(rows) * cell_height + padding * 2)
    if size[0] * size[1] * scale ** 2 > 20_000_000:
        raise ValueError("PNG would exceed 20 million pixels; use a smaller --width or shorter text")
    canvas_color = (255, 255, 255) if background == "light" else (0, 0, 0)
    default_color = (0, 0, 0) if background == "light" else (255, 255, 255)
    image = Image.new("RGB", size, canvas_color)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default_imagefont()
    for row_number, row in enumerate(rows):
        x = padding
        y = padding + row_number * cell_height
        foreground = default_color
        for part in re.split(r"(\x1b\[[0-9;]*m)", row):
            if COLOR_CODE.fullmatch(part):
                values = part[2:-1].split(";")
                if values == ["0"]:
                    foreground = default_color
                elif len(values) == 5 and values[:2] == ["38", "2"]:
                    foreground = tuple(int(value) for value in values[2:])
                else:
                    raise ValueError("Unsupported color code in PNG artwork")
            else:
                draw.text((x, y), part, font=font, fill=foreground)
                x += len(part) * cell_width
    # Enlarge without blurring the character strokes.
    return image.resize((size[0] * scale, size[1] * scale), Image.Resampling.NEAREST)
