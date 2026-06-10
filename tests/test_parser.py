import unittest

from app.parser import LineParser


class LineParserTests(unittest.TestCase):
    def test_received_page_pose_to_you_is_page(self) -> None:
        parsed = LineParser().parse_line("In a page-pose to you, Carmody waves.")

        self.assertTrue(parsed.is_page)
        self.assertTrue(any(span.style == "page_received" for span in parsed.spans))


if __name__ == "__main__":
    unittest.main()
