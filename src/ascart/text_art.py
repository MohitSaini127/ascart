from pyfiglet import CharNotPrinted, FigletFont, figlet_format


def text_to_ascii(text, width=60, font="standard"):
    if font == "ascart-left":
        return left_slanted_text(text, width)
    if font not in FigletFont.getFonts():
        raise ValueError(f"Unknown banner font: {font}")
    try:
        return figlet_format(text, font=font, width=width).rstrip("\n")
    except CharNotPrinted:
        raise ValueError("Width is too small for this banner; try a larger --width") from None


def left_slanted_text(text, width=60):
    row_count = len(text_to_ascii("M", width=1000).splitlines())
    padding = (row_count - 1) // 2
    if width <= padding:
        raise ValueError("Width is too small for this banner; try a larger --width")
    banner = text_to_ascii(text, width=width - padding)
    rows = []
    for index, row in enumerate(banner.splitlines()):
        offset = (index % row_count) // 2
        rows.append(" " * offset + row.rstrip())
    return "\n".join(rows)
