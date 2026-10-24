"""Draw generated ASCII artwork on a fixed character grid using Pillow."""

import re

from PIL import Image, ImageDraw, ImageFont

from ascart.border import COLOR_CODE


def art_to_png(art, background="dark", *, smooth=True):
    """Return an RGB picture, including the converter's foreground colors."""
    rows = art.split("\n")
    columns = max(len(COLOR_CODE.sub("", row)) for row in rows)
    # Keep the output grid stable while drawing PNG glyphs at their final
    # resolution. The regular font is embedded in Pillow; no system font is used.
    scale = 1
    if smooth:
        try:
            font = ImageFont.load_default(size=18)
        except ImportError:
            # Pillow builds without FreeType can still use the bitmap renderer.
            smooth = False
    if not smooth:
        font = ImageFont.load_default_imagefont()
        scale = 2
    cell_width, cell_height, padding = 12 // scale, 22 // scale, 12 // scale
    size = (max(1, columns) * cell_width + padding * 2,
            len(rows) * cell_height + padding * 2)
    if size[0] * size[1] * scale ** 2 > 20_000_000:
        raise ValueError("PNG would exceed 20 million pixels; use a smaller --width or shorter text")
    canvas_color = (255, 255, 255) if background == "light" else (0, 0, 0)
    default_color = (0, 0, 0) if background == "light" else (255, 255, 255)
    image = Image.new("RGB", size, canvas_color)
    draw = ImageDraw.Draw(image)
    glyphs = {}
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
                if smooth:
                    # Keep glyphs on one baseline and contain them within
                    # fixed cells, including wide letters such as W and @.
                    for character in part:
                        if character not in glyphs:
                            left, _, right, _ = font.getbbox(character, anchor="ls")
                            glyph_width = max(cell_width, right - left)
                            mask = Image.new("L", (glyph_width, cell_height))
                            offset = (glyph_width - (right - left)) // 2 - left
                            ImageDraw.Draw(mask).text((offset, 17), character,
                                                      font=font, fill=255, anchor="ls")
                            if glyph_width != cell_width:
                                mask = mask.resize((cell_width, cell_height), Image.Resampling.LANCZOS)
                            glyphs[character] = mask
                        image.paste(foreground, (x, y, x + cell_width, y + cell_height), glyphs[character])
                        x += cell_width
                else:
                    draw.text((x, y), part, font=font, fill=foreground)
                    x += len(part) * cell_width
    if scale == 1:
        return image
    return image.resize((size[0] * scale, size[1] * scale), Image.Resampling.NEAREST)
