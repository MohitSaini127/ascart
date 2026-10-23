import unittest

from ascart.border import COLOR_CODE, add_border


class BorderTests(unittest.TestCase):
    def test_rectangular_art(self):
        self.assertEqual(add_border("ab\ncd"), "+--+\n|ab|\n|cd|\n+--+")

    def test_unequal_rows_are_padded(self):
        self.assertEqual(add_border("abc\nx"), "+---+\n|abc|\n|x  |\n+---+")

    def test_trailing_spaces_and_blank_rows_are_preserved(self):
        self.assertEqual(add_border("x \n\n"), "+--+\n|x |\n|  |\n|  |\n+--+")

    def test_empty_art(self):
        self.assertEqual(add_border(""), "++\n||\n++")

    def test_color_codes_do_not_inflate_width(self):
        art = "\033[38;2;255;0;0mab\033[0m\nx"
        result = add_border(art)
        self.assertEqual(COLOR_CODE.sub("", result), add_border("ab\nx"))
        self.assertIn("\033[38;2;255;0;0mab", result)

    def test_color_is_reset_before_padding_and_right_border(self):
        result = add_border("\033[31mx\nabc")
        self.assertIn("x\033[0m  |", result)
        self.assertEqual(COLOR_CODE.sub("", result), add_border("x\nabc"))


if __name__ == "__main__":
    unittest.main()
