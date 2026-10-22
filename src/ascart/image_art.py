from PIL import Image


def inspect_image(path):
    with Image.open(path) as image:
        print("Size:", image.size)
        print("Color mode:", image.mode)
