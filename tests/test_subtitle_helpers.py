import unittest

from app import build_subtitle_filename, get_subtitle_status


class SubtitleHelperTests(unittest.TestCase):
    def test_build_subtitle_filename_sanitizes_reserved_characters(self):
        filename = build_subtitle_filename(42, 'a/b:c*?"<>|.webm')
        self.assertEqual(filename, "42-a_b_c______.srt")

    def test_build_subtitle_filename_handles_blank_source(self):
        filename = build_subtitle_filename(7, "")
        self.assertEqual(filename, "7-subtitle.srt")

    def test_get_subtitle_status_defaults_to_none(self):
        class History:
            subtitle_status = None

        self.assertEqual(get_subtitle_status(History()), "none")


if __name__ == "__main__":
    unittest.main()
