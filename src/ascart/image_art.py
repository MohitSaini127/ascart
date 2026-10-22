from PIL import Image

from ascart.converter import brightness_to_character


def inspect_image(path, width=80):
    with Image.open(path) as image:
        print("Size:", image.size)
        print("Color mode:", image.mode)

        grayscale = image.convert("L")
        print("Grayscale mode:", grayscale.mode)
        print("First pixel brightness:", grayscale.getpixel((0, 0)))

        aspect_ratio = image.height / image.width
        height = max(1, int(width * aspect_ratio * 0.5))
        resized = grayscale.resize((width, height))

        print("Resized size:", resized.size)

        for y in range(height):
            row = ""

            for x in range(width):
                brightness = resized.getpixel((x, y))
                row += brightness_to_character(brightness)

            print(row)
