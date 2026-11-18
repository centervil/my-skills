import unittest
import os
import json
import tempfile
import shutil
import sys
import importlib.util

script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/agy-collect-wrapper.py"))
spec = importlib.util.spec_from_file_location("agy_collect_wrapper", script_path)
agy_collect_wrapper = importlib.util.module_from_spec(spec)
sys.modules["agy_collect_wrapper"] = agy_collect_wrapper
spec.loader.exec_module(agy_collect_wrapper)

from agy_collect_wrapper import extract_corpus_index, mechanical_dedup, normalize_url

class TestDedupPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create a mock report for 2026-11-16 containing Fugaku incident
        report_content = """# 2026年11月16日 サイバーセキュリティニュースまとめ
## 富岳ニュース
### 1. スパコン「富岳」に不正アクセス
$$出典: NEWSjp - スーパーコンピュータ「富岳」に不正アクセス$$ (https://news.jp/i/1495107964071723726)
"""
        self.reports_dir = os.path.join(self.test_dir, "security-news")
        os.makedirs(self.reports_dir, exist_ok=True)
        with open(os.path.join(self.reports_dir, "cybersecurity_news_2026-11-16.md"), "w", encoding="utf-8") as f:
            f.write(report_content)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_normalize_url(self):
        self.assertEqual(normalize_url("https://news.jp/i/12345/?utm_source=twitter"), "https://news.jp/i/12345")
        self.assertEqual(normalize_url("https://news.jp/i/12345/"), "https://news.jp/i/12345")

    def test_corpus_extraction(self):
        index = extract_corpus_index(self.reports_dir, "2026-11-17", 7)
        self.assertIn("https://news.jp/i/1495107964071723726", index["urls"])
        self.assertTrue(any("富岳" in k for k in index["keywords"]))

    def test_mechanical_dedup_exact_url(self):
        corpus_index = extract_corpus_index(self.reports_dir, "2026-11-17", 7)
        candidates = [
            {
                "title": "全く別のタイトルだがURLが同一",
                "url": "https://news.jp/i/1495107964071723726?ref=app",
                "snippet": "富岳関連の再掲記事"
            },
            {
                "title": "新しい脆弱性ニュース",
                "url": "https://example.com/new-vuln",
                "snippet": "全く新しい脆弱性"
            }
        ]
        kept, excluded = mechanical_dedup(candidates, corpus_index)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["url"], "https://example.com/new-vuln")
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["reason"], "URL_MATCH")

    def test_mechanical_dedup_keyword_match(self):
        corpus_index = extract_corpus_index(self.reports_dir, "2026-11-17", 7)
        candidates = [
            {
                "title": "スパコン富岳で不正アクセス発生の続報か",
                "url": "https://different-url.com/fugaku-hack",
                "snippet": "富岳の運用システムが不正アクセスを受けたと発表"
            }
        ]
        kept, excluded = mechanical_dedup(candidates, corpus_index)
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["reason"], "KEYWORD_MATCH")

if __name__ == "__main__":
    unittest.main()
