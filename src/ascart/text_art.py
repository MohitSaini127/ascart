from pyfiglet import CharNotPrinted, FigletFont, figlet_format


def text_to_ascii(text, width=60, font="standard"):
    if font not in FigletFont.getFonts():
        raise ValueError(f"Unknown banner font: {font}")
    try:
        return figlet_format(text, font=font, width=width).rstrip("\n")
    except CharNotPrinted:
        raise ValueError("Width is too small for this banner; try a larger --width") from None
