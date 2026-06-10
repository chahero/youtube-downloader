from pathlib import Path
import unittest


class TemplateUiTests(unittest.TestCase):
    def test_download_actions_use_distinct_icons_and_labels(self):
        template = Path("templates/index.html").read_text(encoding="utf-8")

        self.assertIn("contentDownload:", template)
        self.assertIn("subtitleDownload:", template)
        self.assertIn("'컨텐츠 다운로드'", template)
        self.assertIn("'자막 다운로드'", template)
        self.assertIn("icons.contentDownload", template)
        self.assertIn("icons.subtitleDownload", template)

    def test_auto_refresh_is_limited_to_pending_work(self):
        template = Path("templates/index.html").read_text(encoding="utf-8")

        self.assertIn("let shouldAutoRefresh = false;", template)
        self.assertIn("shouldAutoRefresh = hasPendingWork(data.items);", template)
        self.assertIn("if (shouldAutoRefresh)", template)
        self.assertIn("function hasPendingWork(items)", template)
        self.assertIn("subtitleStatus === 'queued' || subtitleStatus === 'processing'", template)


if __name__ == "__main__":
    unittest.main()
