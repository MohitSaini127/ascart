from PIL import Image

from ascart.converter import DEFAULT_PALETTE, brightness_to_character


def inspect_image(path, width=80, palette=DEFAULT_PALETTE):
    with Image.open(path) as image:
        grayscale = image.convert("L")

        aspect_ratio = image.height / image.width
        height = max(1, int(width * aspect_ratio * 0.5))
        resized = grayscale.resize((width, height))

        rows = []
        for y in range(height):
            row = ""

            for x in range(width):
                brightness = resized.getpixel((x, y))
                row += brightness_to_character(brightness, palette=palette)

            rows.append(row)

        return "\n".join(rows)
