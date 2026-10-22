from pyfiglet import CharNotPrinted, figlet_format


def text_to_ascii(text, width=60):
    try:
        return figlet_format(text, font="standard", width=width).rstrip("\n")
    except CharNotPrinted:
        raise ValueError("Width is too small for this banner; try a larger --width") from None
