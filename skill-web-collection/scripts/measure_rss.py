#!/usr/bin/env python3
"""
measure_rss.py
Deterministic measurement script for RSS feeds collection and fetchability across target dates (2026-11-17 and 2026-11-16).
Outputs results to .verify-issue12/measurement.json.
"""

import sys
import os
import json
import importlib.util
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from rss_collect import load_and_validate_feeds, fetch_and_parse_feed

wrapper_path = os.path.join(script_dir, "agy-collect-wrapper.py")
spec = importlib.util.spec_from_file_location("agy_collect_wrapper", wrapper_path)
agy_collect_wrapper = importlib.util.module_from_spec(spec)
sys.modules["agy_collect_wrapper"] = agy_collect_wrapper
spec.loader.exec_module(agy_collect_wrapper)
fetch_article_body = agy_collect_wrapper.fetch_article_body

def measure_date(feeds_file, target_date_str, fetchable_min_chars=600):
    feeds = load_and_validate_feeds(feeds_file)
    enabled_feeds = [f for f in feeds if f.get("enabled", True)]

    feed_measurements = []
    total_window_candidates = 0
    total_fetchable_count = 0

    for feed in enabled_feeds:
        cands, meta = fetch_and_parse_feed(feed, target_date_str)
        
        # Evaluate fetchability for each candidate in window
        fetchable_in_feed = 0
        cand_details = []
        for c in cands:
            url = c.get("url", "")
            fetched, source_status, status_code, body_source, length = fetch_article_body(url, browser_fallback=False)
            is_fetchable = (200 <= status_code < 300) and (length >= fetchable_min_chars)
            if is_fetchable:
                fetchable_in_feed += 1
            
            cand_details.append({
                "title": c.get("title"),
                "url": url,
                "fetchable": is_fetchable,
                "fetch_reason": source_status,
                "fetch_status": status_code,
                "body_length": length
            })

        meta["fetchable_count"] = fetchable_in_feed
        meta["candidates_evaluated"] = cand_details
        feed_measurements.append(meta)

        total_window_candidates += meta["window_candidates_count"]
        total_fetchable_count += fetchable_in_feed

    return {
        "target_date": target_date_str,
        "total_window_candidates": total_window_candidates,
        "total_fetchable_count": total_fetchable_count,
        "feed_results": feed_measurements
    }

def main():
    verify_dir = "/home/devuser/workspace/my-skills/.verify-issue12"
    os.makedirs(verify_dir, exist_ok=True)

    feeds_file = "/home/devuser/workspace/my-skills/skill-web-collection/profiles/cybersecurity_feeds.json"
    
    dates = ["2026-11-17", "2026-11-16"]
    results = {}

    for d in dates:
        print(f"Measuring RSS feeds for target date: {d}...")
        results[d] = measure_date(feeds_file, d)

    measurement_output_path = os.path.join(verify_dir, "measurement.json")
    with open(measurement_output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Measurement complete. Results saved to {measurement_output_path}")

if __name__ == "__main__":
    main()
