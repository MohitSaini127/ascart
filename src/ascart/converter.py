DEFAULT_PALETTE = " .:-=+*#%@"
COLOR_PALETTE = "#%@"


def brightness_to_character(brightness, palette=DEFAULT_PALETTE):
    """Map an integer brightness from 0 through 255 into near-equal palette bands."""
    index = brightness * len(palette) // 256
    character = palette[index]
    return character
