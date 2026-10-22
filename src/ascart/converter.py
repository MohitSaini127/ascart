DEFAULT_PALETTE = " .:-=+*#%@"
COLOR_PALETTE = "#%@"


def brightness_to_character(brightness, palette=DEFAULT_PALETTE):
    index = brightness * (len(palette) - 1) // 255
    character = palette[index]
    return character
