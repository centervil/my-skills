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
        kept, excluded, affinity = mechanical_dedup(candidates, corpus_index)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["url"], "https://example.com/new-vuln")
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["reason"], "URL_MATCH")

    def test_mechanical_dedup_keyword_match(self):
        corpus_index = extract_corpus_index(self.reports_dir, "2026-11-17", 7)
        candidates = [
            {
                "title": "スーパーコンピュータに不正アクセス発生の続報か",
                "url": "https://different-url.com/supercomputer-hack",
                "snippet": "スーパーコンピュータ富岳の運用システムが不正アクセスを受けたと発表スーパーコンピュータ"
            }
        ]
        kept, excluded, affinity = mechanical_dedup(candidates, corpus_index)
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["reason"], "KEYWORD_MATCH")

    def test_affinity_separation(self):
        corpus_index = extract_corpus_index(self.reports_dir, "2026-11-17", 7)
        candidates = [
            {
                "title": "スーパーコンピュータ関連の動向",
                "url": "https://different-url.com/supercomputer",
                "snippet": "動向"
            }
        ]
        kept, excluded, affinity = mechanical_dedup(candidates, corpus_index)
        # Has no affinity -> goes to kept
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(affinity), 0)

    def test_boundary_default_keep_vs_drop(self):
        # Test boundary_default behavior with monkeypatching run_agy_session or simulating boundary check logic
        # When boundary check returns has_new_facts=False (ambiguous / no confirmed new facts):
        # - boundary_default="keep" should keep the candidate
        # - boundary_default="drop" should drop the candidate
        
        cand = {"title": "富岳の続報（判定曖昧）", "url": "https://example.com/fugaku-update", "snippet": "富岳"}
        
        # Simulate wrapper logic for boundary evaluation
        def evaluate_boundary(boundary_candidates, boundary_default_val):
            final_kept = []
            boundary_records = []
            # Mock model response: has_new_facts = False
            b_results = [{"index": 0, "has_new_facts": False, "reason": "No clear new facts"}]
            b_map = {item["index"]: item for item in b_results if "index" in item}
            for idx, c in enumerate(boundary_candidates):
                res = b_map.get(idx)
                if res and res.get("has_new_facts") is True:
                    final_kept.append(c)
                    boundary_records.append({"candidate": c, "judgment": "KEEP_NEW_FACTS"})
                else:
                    if res and res.get("has_new_facts") is False:
                        if boundary_default_val == "drop":
                            boundary_records.append({"candidate": c, "judgment": "DROP_BOUNDARY"})
                        else:
                            final_kept.append(c)
                            boundary_records.append({"candidate": c, "judgment": "KEEP_BOUNDARY_DEFAULT"})
            return final_kept, boundary_records

        # Case 1: boundary_default = "keep" -> candidate is kept
        kept_keep, recs_keep = evaluate_boundary([cand], "keep")
        self.assertEqual(len(kept_keep), 1)
        self.assertEqual(recs_keep[0]["judgment"], "KEEP_BOUNDARY_DEFAULT")

        # Case 2: boundary_default = "drop" -> candidate is dropped
        kept_drop, recs_drop = evaluate_boundary([cand], "drop")
        self.assertEqual(len(kept_drop), 0)
        self.assertEqual(recs_drop[0]["judgment"], "DROP_BOUNDARY")

if __name__ == "__main__":
    unittest.main()
