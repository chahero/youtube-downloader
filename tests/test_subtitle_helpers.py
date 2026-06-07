import unittest

from app import (
    build_subtitle_filename,
    build_srt_from_word_timestamps,
    collect_word_timestamps_from_results,
    format_srt_timestamp,
    get_subtitle_status,
)


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

    def test_format_srt_timestamp_uses_subtitle_timestamp_format(self):
        self.assertEqual(format_srt_timestamp(3723456), "01:02:03,456")

    def test_build_srt_from_word_timestamps_groups_words_by_duration_and_punctuation(self):
        words = [
            {"word": "Hello", "start_time": 160, "end_time": 480},
            {"word": ",", "start_time": 480, "end_time": 480},
            {"word": "this", "start_time": 1120, "end_time": 1120},
            {"word": "is", "start_time": 1360, "end_time": 1360},
            {"word": "short", "start_time": 1760, "end_time": 2000},
            {"word": ".", "start_time": 2000, "end_time": 2000},
            {"word": "Next", "start_time": 5200, "end_time": 5600},
            {"word": "line", "start_time": 5680, "end_time": 6000},
            {"word": ".", "start_time": 6000, "end_time": 6000},
        ]

        srt = build_srt_from_word_timestamps(words)

        self.assertIn("00:00:00,160 --> 00:00:02,000\nHello, this is short.", srt)
        self.assertIn("00:00:05,200 --> 00:00:06,000\nNext line.", srt)

    def test_collect_word_timestamps_from_results_includes_every_result(self):
        results = [
            {"alternatives": [{"words": [{"word": "First", "start_time": 0, "end_time": 400}]}]},
            {"alternatives": [{"words": [{"word": "Second", "start_time": 1200, "end_time": 1800}]}]},
        ]

        words = collect_word_timestamps_from_results(results)

        self.assertEqual([word["word"] for word in words], ["First", "Second"])


if __name__ == "__main__":
    unittest.main()
