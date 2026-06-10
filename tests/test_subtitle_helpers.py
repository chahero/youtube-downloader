import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app import (
    build_subtitle_filename,
    build_srt_from_word_timestamps,
    collect_word_timestamps_from_results,
    cleanup_orphan_subtitle_files,
    delete_subtitle_file_for_history,
    format_stt_exception,
    format_srt_timestamp,
    get_subtitle_status,
    parse_stt_grpc_server,
    read_subtitle_text_for_history,
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

    def test_parse_stt_grpc_server_splits_host_and_port(self):
        self.assertEqual(parse_stt_grpc_server("192.168.0.67:9031"), ("192.168.0.67", 9031))

    def test_format_stt_exception_summarizes_grpc_connectivity_error(self):
        message = (
            "<_MultiThreadedRendezvous of RPC that terminated with: "
            "status = StatusCode.UNAVAILABLE details = \"failed to connect to all addresses; "
            "last error: FAILED_PRECONDITION: ipv4:192.168.0.67:9031: connect failed: "
            "addr: ipv4:192.168.0.67:9031 error: No route to host\" >"
        )

        formatted = format_stt_exception(Exception(message))

        self.assertIn("STT 서버 연결 실패", formatted)
        self.assertIn("192.168.0.67:9031", formatted)
        self.assertIn("No route to host", formatted)
        self.assertNotIn("_MultiThreadedRendezvous", formatted)

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

    def test_delete_subtitle_file_for_history_removes_existing_file(self):
        class History:
            subtitle_filename = "video.srt"

        with TemporaryDirectory() as temp_dir:
            subtitle_path = Path(temp_dir) / "video.srt"
            subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

            deleted = delete_subtitle_file_for_history(History(), temp_dir)

            self.assertEqual(deleted, 1)
            self.assertFalse(subtitle_path.exists())

    def test_cleanup_orphan_subtitle_files_keeps_referenced_files(self):
        class History:
            def __init__(self, subtitle_filename):
                self.subtitle_filename = subtitle_filename

        with TemporaryDirectory() as temp_dir:
            kept_path = Path(temp_dir) / "kept.srt"
            orphan_path = Path(temp_dir) / "orphan.srt"
            kept_path.write_text("kept", encoding="utf-8")
            orphan_path.write_text("orphan", encoding="utf-8")

            deleted = cleanup_orphan_subtitle_files([History("kept.srt")], temp_dir)

            self.assertEqual(deleted, 1)
            self.assertTrue(kept_path.exists())
            self.assertFalse(orphan_path.exists())

    def test_read_subtitle_text_for_history_reads_existing_subtitle(self):
        class History:
            subtitle_filename = "video.srt"

        with TemporaryDirectory() as temp_dir:
            subtitle_path = Path(temp_dir) / "video.srt"
            subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

            text = read_subtitle_text_for_history(History(), temp_dir)

            self.assertIn("Hello", text)

    def test_read_subtitle_text_for_history_rejects_nested_filename(self):
        class History:
            subtitle_filename = "../video.srt"

        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                read_subtitle_text_for_history(History(), temp_dir)


if __name__ == "__main__":
    unittest.main()
