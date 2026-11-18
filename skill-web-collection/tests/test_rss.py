import unittest
import os
import json
import tempfile
import shutil
import sys
import importlib.util

script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/rss_collect.py"))
spec = importlib.util.spec_from_file_location("rss_collect", script_path)
rss_collect = importlib.util.module_from_spec(spec)
sys.modules["rss_collect"] = rss_collect
spec.loader.exec_module(rss_collect)

from rss_collect import load_and_validate_feeds, fetch_and_parse_feed, parse_date, clean_html_snippet

class TestFeedValidation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_valid_feeds(self):
        valid_data = [
            {
                "id": "feed1",
                "name": "Feed 1",
                "url": "https://example.com/feed1.xml",
                "region": "domestic",
                "type": "media",
                "enabled": True,
                "notes": "test"
            }
        ]
        path = os.path.join(self.test_dir, "feeds.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(valid_data, f)
        
        feeds = load_and_validate_feeds(path)
        self.assertEqual(len(feeds), 1)
        self.assertEqual(feeds[0]["id"], "feed1")

    def test_missing_required_field(self):
        invalid_data = [
            {
                "id": "feed1",
                "name": "Feed 1",
                # missing "url"
                "region": "domestic",
                "type": "media",
                "enabled": True
            }
        ]
        path = os.path.join(self.test_dir, "feeds.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(invalid_data, f)
        
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_feeds(path)
        self.assertIn("missing required field", str(ctx.exception))

    def test_duplicate_id(self):
        invalid_data = [
            {"id": "same", "name": "F1", "url": "https://ex.com/1", "region": "domestic", "type": "media", "enabled": True},
            {"id": "same", "name": "F2", "url": "https://ex.com/2", "region": "overseas", "type": "media", "enabled": True}
        ]
        path = os.path.join(self.test_dir, "feeds.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(invalid_data, f)
        
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_feeds(path)
        self.assertIn("Duplicate feed id", str(ctx.exception))

    def test_invalid_url(self):
        invalid_data = [
            {"id": "f1", "name": "F1", "url": "ftp://ex.com/1", "region": "domestic", "type": "media", "enabled": True}
        ]
        path = os.path.join(self.test_dir, "feeds.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(invalid_data, f)
        
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_feeds(path)
        self.assertIn("invalid URL", str(ctx.exception))

    def test_invalid_enabled_type(self):
        invalid_data = [
            {"id": "f1", "name": "F1", "url": "https://ex.com/1", "region": "domestic", "type": "media", "enabled": "true"} # string instead of bool
        ]
        path = os.path.join(self.test_dir, "feeds.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(invalid_data, f)
        
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_feeds(path)
        self.assertIn("enabled' field must be boolean", str(ctx.exception))


class TestRSSParsingAndWindow(unittest.TestCase):
    def test_parse_date(self):
        # RFC 2822
        dt = parse_date("Mon, 17 Nov 2026 10:00:00 GMT")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 11)
        self.assertEqual(dt.day, 17)

        # ISO format
        dt2 = parse_date("2026-11-17T10:00:00Z")
        self.assertIsNotNone(dt2)
        self.assertEqual(dt2.hour, 10)

        # Invalid date
        self.assertIsNone(parse_date("not-a-date"))

    def test_clean_html_snippet(self):
        html_content = "<p>Hello <b>World</b> &amp; welcome to security news.</p><script>alert('bad');</script>"
        cleaned = clean_html_snippet(html_content, max_len=50)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("script", cleaned)
        self.assertIn("Hello World & welcome", cleaned)

    def test_feed_parsing_rss2_and_jst_window(self):
        # Mocking urllib.request.urlopen or testing fetch_and_parse_feed via monkeypatching urllib
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Security Feed</title>
            <item>
              <title>Target Day Item (JST)</title>
              <link>https://example.com/item1</link>
              <pubDate>Mon, 16 Nov 2026 16:00:00 GMT</pubDate> <!-- 16 Nov 16:00 GMT = 17 Nov 01:00 JST -->
              <description>Item inside target JST day window [00:00, 24:00).</description>
            </item>
            <item>
              <title>Outside Target Day Item</title>
              <link>https://example.com/item2</link>
              <pubDate>Sun, 15 Nov 2026 16:00:00 GMT</pubDate> <!-- 16 Nov 01:00 JST (Outside 17 Nov) -->
              <description>Item outside window.</description>
            </item>
            <item>
              <title>Unknown Date Item</title>
              <link>https://example.com/item3</link>
              <pubDate>invalid-date-format</pubDate>
              <description>Should be excluded due to unknown date.</description>
            </item>
          </channel>
        </rss>
        """

        feed_def = {
            "id": "test_feed",
            "name": "Test Feed",
            "url": "https://example.com/feed.xml",
            "region": "domestic",
            "type": "media",
            "enabled": True
        }

        # Monkeypatch urllib.request.urlopen
        class MockResponse:
            def __init__(self, content):
                self.content = content.encode("utf-8")
            def read(self):
                return self.content
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        original_urlopen = rss_collect.urllib.request.urlopen
        try:
            rss_collect.urllib.request.urlopen = lambda req, timeout=15: MockResponse(rss_xml)
            
            candidates, meta = fetch_and_parse_feed(feed_def, "2026-11-17")
            
            self.assertEqual(meta["status"], "OK")
            self.assertEqual(meta["total_items_scanned"], 3)
            self.assertEqual(meta["window_candidates_count"], 1)
            self.assertEqual(meta["unknown_date_count"], 1)
            
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["title"], "Target Day Item (JST)")
            self.assertEqual(candidates[0]["url"], "https://example.com/item1")
            self.assertEqual(candidates[0]["origin"], "rss")
            self.assertEqual(candidates[0]["feed_id"], "test_feed")
        finally:
            rss_collect.urllib.request.urlopen = original_urlopen

    def test_feed_parsing_rss1_rdf_dc_date(self):
        rss_rdf = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF
          xmlns="http://purl.org/rss/1.0/"
          xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
          xmlns:dc="http://purl.org/dc/elements/1.1/">
          <channel rdf:about="https://scan.netsecurity.ne.jp/rss/index.rdf">
            <title>ScanNetSecurity</title>
            <link>https://scan.netsecurity.ne.jp/</link>
          </channel>
          <item rdf:about="https://scan.netsecurity.ne.jp/article/2026/11/17/55555.html">
            <title>RDF Target Day Item</title>
            <link>https://scan.netsecurity.ne.jp/article/2026/11/17/55555.html</link>
            <dc:date>2026-11-17T12:00:00+09:00</dc:date>
            <description>RDF item description with dc:date.</description>
          </item>
          <item rdf:about="https://scan.netsecurity.ne.jp/article/2026/11/17/unknown.html">
            <title>RDF Unknown Date Item</title>
            <link>https://scan.netsecurity.ne.jp/article/2026/11/17/unknown.html</link>
            <dc:date>invalid-date-string</dc:date>
            <description>RDF item with invalid date to test unknown_date_count.</description>
          </item>
        </rdf:RDF>
        """

        feed_def = {
            "id": "scannetsecurity",
            "name": "ScanNetSecurity",
            "url": "https://scan.netsecurity.ne.jp/rss/index.rdf",
            "region": "domestic",
            "type": "media",
            "enabled": True
        }

        # Monkeypatch urllib.request.urlopen
        class MockResponse:
            def __init__(self, content):
                self.content = content.encode("utf-8")
            def read(self):
                return self.content
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        original_urlopen = rss_collect.urllib.request.urlopen
        try:
            rss_collect.urllib.request.urlopen = lambda req, timeout=15: MockResponse(rss_rdf)
            
            candidates, meta = fetch_and_parse_feed(feed_def, "2026-11-17")
            
            self.assertEqual(meta["status"], "OK")
            self.assertEqual(meta["total_items_scanned"], 2)
            self.assertEqual(meta["window_candidates_count"], 1)
            self.assertEqual(meta["unknown_date_count"], 1)
            
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["title"], "RDF Target Day Item")
            self.assertEqual(candidates[0]["url"], "https://scan.netsecurity.ne.jp/article/2026/11/17/55555.html")
            self.assertEqual(candidates[0]["origin"], "rss")
            self.assertEqual(candidates[0]["feed_id"], "scannetsecurity")
        finally:
            rss_collect.urllib.request.urlopen = original_urlopen

    def test_feed_failure_isolation(self):
        feed_def = {
            "id": "broken_feed",
            "name": "Broken Feed",
            "url": "https://example.com/broken.xml",
            "region": "domestic",
            "type": "media",
            "enabled": True
        }

        original_urlopen = rss_collect.urllib.request.urlopen
        try:
            def mock_fail(req, timeout=15):
                raise rss_collect.urllib.error.URLError("Connection refused")
            rss_collect.urllib.request.urlopen = mock_fail

            candidates, meta = fetch_and_parse_feed(feed_def, "2026-11-17")
            self.assertEqual(meta["status"], "HTTP_ERROR")
            self.assertIn("Connection refused", meta["error_message"])
            self.assertEqual(len(candidates), 0)
        finally:
            rss_collect.urllib.request.urlopen = original_urlopen

if __name__ == "__main__":
    unittest.main()
