from PIL import Image

from ascart.converter import DEFAULT_PALETTE, brightness_to_character


def inspect_image(
    path, width=80, palette=DEFAULT_PALETTE, background="dark", max_height=None, color=False
):
    if background == "light":
        palette = palette[::-1]

    with Image.open(path) as image:
        grayscale = image.convert("L")

        aspect_ratio = image.height / image.width
        height = max(1, int(width * aspect_ratio * 0.5))
        if max_height is not None and height > max_height:
            height = max_height
            width = max(1, min(width, int(height / (aspect_ratio * 0.5))))
        resized = grayscale.resize((width, height))
        if color:
            resized_color = image.convert("RGB").resize((width, height))

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
