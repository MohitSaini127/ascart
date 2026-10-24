from contextlib import ExitStack

from PIL import Image

from ascart.converter import DEFAULT_PALETTE, brightness_to_character


def inspect_image(
    path, width=80, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False
):
    with Image.open(path) as image:
        return image_to_ascii(image, width, palette, background, max_height, color)


def image_to_ascii(
    image, width=80, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False
):
    if background == "light":
        palette = palette[::-1]

    with ExitStack() as resources:
        # Hidden RGB values under transparent pixels are not visible artwork.
        # Composite before resizing so alpha edges blend against the selected canvas.
        source = image
        if image.has_transparency_data:
            rgba = resources.enter_context(image.convert("RGBA"))
            source = resources.enter_context(Image.new("RGB", image.size, "white" if background == "light" else "black"))
            source.paste(rgba, (0, 0), rgba)

        grayscale = resources.enter_context(source.convert("L"))

        aspect_ratio = image.height / image.width
        height = max(1, int(width * aspect_ratio * 0.5))
        if max_height is not None and height > max_height:
            height = max_height
            width = max(1, min(width, int(height / (aspect_ratio * 0.5))))
        resized = resources.enter_context(grayscale.resize((width, height)))
        if color:
            rgb = resources.enter_context(source.convert("RGB"))
            resized_color = resources.enter_context(rgb.resize((width, height)))

        rows = []
        for y in range(height):
            row = ""

            for x in range(width):
                brightness = resized.getpixel((x, y))
                character = brightness_to_character(brightness, palette=palette)
                if color:
                    red, green, blue = resized_color.getpixel((x, y))
                    row += f"\033[38;2;{red};{green};{blue}m{character}"
                else:
                    row += character

            if color:
                row += "\033[0m"
            rows.append(row)

        return "\n".join(rows)
