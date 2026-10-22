def brightness_to_character(brightness):
    palette = " .:-=+*#%@"
    index = brightness * (len(palette) - 1) // 255
    character = palette[index]
    return character
