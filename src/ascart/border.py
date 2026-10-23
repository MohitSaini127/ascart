import re


COLOR_CODE = re.compile(r"\x1b\[[0-9;]*m")


def add_border(art):
    """Frame ASCII rows, measuring visible characters rather than color codes."""
    rows = art.split("\n")
    widths = [len(COLOR_CODE.sub("", row)) for row in rows]
    width = max(widths)
    edge = "+" + "-" * width + "+"
    framed = [edge]
    for row, visible_width in zip(rows, widths):
        reset = "\033[0m" if COLOR_CODE.search(row) else ""
        framed.append("|" + row + reset + " " * (width - visible_width) + "|")
    framed.append(edge)
    return "\n".join(framed)
