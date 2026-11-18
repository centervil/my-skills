#!/usr/bin/env python3
"""
rss_collect.py
Deterministic RSS/Atom feed collection script using standard libraries only.
Supports RSS 2.0, RSS 1.0 (RDF), and Atom feeds. Filters items by JST calendar day [00:00, 24:00).
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
html_parser_module = None
try:
    import html
except ImportError:
    pass
import re

JST = timezone(timedelta(hours=9))

def load_and_validate_feeds(feeds_file_path):
    """Load and validate feeds configuration file."""
    if not os.path.exists(feeds_file_path):
        raise FileNotFoundError(f"Feeds file not found: {feeds_file_path}")
    
    with open(feeds_file_path, "r", encoding="utf-8") as f:
        try:
            feeds = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in feeds file: {e}")

    if not isinstance(feeds, list):
        raise ValueError("Feeds configuration must be a JSON list of feed objects.")

    seen_ids = set()
    for idx, feed in enumerate(feeds):
        if not isinstance(feed, dict):
            raise ValueError(f"Feed at index {idx} must be an object.")
        
        # Check required fields
        for field in ["id", "name", "url", "region", "type", "enabled"]:
            if field not in feed:
                raise ValueError(f"Feed at index {idx} missing required field: '{field}'")
        
        fid = feed["id"]
        if not isinstance(fid, str) or not fid.strip():
            raise ValueError(f"Feed at index {idx} has invalid 'id': {fid}")
        if fid in seen_ids:
            raise ValueError(f"Duplicate feed id found: '{fid}'")
        seen_ids.add(fid)

        url = feed["url"]
        if not isinstance(url, str) or not url.startswith("http"):
            raise ValueError(f"Feed '{fid}' has invalid URL: {url}")

        region = feed["region"]
        if region not in ["domestic", "overseas"]:
            raise ValueError(f"Feed '{fid}' has invalid region '{region}'. Must be 'domestic' or 'overseas'.")

        enabled = feed["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError(f"Feed '{fid}' 'enabled' field must be boolean, got {type(enabled).__name__}")

    return feeds

def parse_date(date_str):
    """Parse date string into a timezone-aware datetime object (defaulting to UTC if no tz)."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()

    # 1. Try email parsedate (RFC 2822 / RSS pubDate)
    try:
        dt = parsedate_to_datetime(date_str)
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass

    # 2. Try ISO format / Atom updated/published
    try:
        # Handle 'Z' -> '+00:00'
        iso_str = date_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    # 3. Fallback regex patterns for common date strings (e.g., YYYY-MM-DD or YYYY/MM/DD)
    m = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?', date_str)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour = int(m.group(4)) if m.group(4) else 0
        minute = int(m.group(5)) if m.group(5) else 0
        second = int(m.group(6)) if m.group(6) else 0
        try:
            return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        except Exception:
            pass

    return None

def clean_html_snippet(raw_html, max_len=300):
    """Remove HTML tags, decode entities, and truncate snippet."""
    if not raw_html:
        return ""
    # Remove script and style elements
    text = re.sub(r'<script[^>]*>.*?</script>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Unescape HTML entities
    try:
        text = html.unescape(text)
    except Exception:
        pass
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "..."
    return text

def fetch_and_parse_feed(feed, target_date_str):
    """Fetch and parse a single RSS/Atom feed for items within the target JST date window [00:00, 24:00)."""
    feed_id = feed["id"]
    feed_url = feed["url"]
    feed_name = feed["name"]

    result_meta = {
        "feed_id": feed_id,
        "feed_name": feed_name,
        "url": feed_url,
        "status": "OK",
        "window_candidates_count": 0,
        "unknown_date_count": 0,
        "total_items_scanned": 0,
        "oldest_item_date": None,
        "latest_item_date": None,
        "error_message": ""
    }

    try:
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (Compatible; MySkillsRSSCollector/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()
    except Exception as e:
        result_meta["status"] = "HTTP_ERROR"
        result_meta["error_message"] = str(e)
        return [], result_meta

    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        result_meta["status"] = "PARSE_ERROR"
        result_meta["error_message"] = str(e)
        return [], result_meta

    # Determine target JST day window [00:00, 24:00)
    try:
        t_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        window_start_jst = datetime(t_date.year, t_date.month, t_date.day, 0, 0, 0, tzinfo=JST)
        window_end_jst = window_start_jst + timedelta(days=1)
    except ValueError:
        result_meta["status"] = "INVALID_TARGET_DATE"
        result_meta["error_message"] = f"Invalid target date format: {target_date_str}"
        return [], result_meta

    candidates = []
    items = []

    # Detect feed format: RSS 2.0 (channel/item), RSS 1.0 (rdf:RDF/item), Atom (feed/entry)
    root_tag = root.tag.split('}')[-1].lower()
    
    if root_tag == 'rss':
        channel = root.find('channel')
        if channel is not None:
            items = channel.findall('item')
    elif 'rdf' in root_tag or root_tag == 'rdf':
        items = root.findall('{http://purl.org/rss/1.0/}item')
        if not items:
            items = root.findall('.//{http://purl.org/rss/1.0/}item')
        if not items:
            items = root.findall('item')
        if not items:
            items = root.findall('.//item')
        if not items:
            # Namespace agnostic search for item in rdf
            for elem in root.iter():
                if elem.tag.split('}')[-1].lower() == 'item':
                    items.append(elem)
    elif root_tag == 'feed': # Atom
        # Handle namespace for Atom
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('atom:entry', ns)
        if not items:
            items = root.findall('entry')
    else:
        # Fallback: search for item or entry anywhere
        items = root.findall('.//item') + root.findall('.//entry')

    result_meta["total_items_scanned"] = len(items)
    item_dates = []

    for item in items:
        # Extract title, link, date, description/content namespace-agnostically (by local name)
        title = ""
        for child in item:
            tag_name = child.tag.split('}')[-1].lower()
            if tag_name == 'title':
                if child.text and child.text.strip():
                    title = child.text.strip()
                    break
        if not title:
            # Fallback direct find
            title_elem = item.find('title')
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()
        if not title:
            continue

        # Link extraction namespace-agnostically
        link = ""
        for child in item:
            tag_name = child.tag.split('}')[-1].lower()
            if tag_name == 'link':
                if child.text and child.text.strip():
                    link = child.text.strip()
                    break
                elif 'href' in child.attrib:
                    link = child.attrib['href'].strip()
                    break
        if not link:
            link_elem = item.find('link')
            if link_elem is not None:
                if link_elem.text and link_elem.text.strip():
                    link = link_elem.text.strip()
                elif 'href' in link_elem.attrib:
                    link = link_elem.attrib['href'].strip()
        if not link and 'about' in item.attrib:
            link = item.attrib['about'].strip()

        if not link:
            continue

        # Date extraction (pubDate, dc:date, published, updated) namespace-agnostically
        date_str = ""
        for child in item:
            tag_name = child.tag.split('}')[-1].lower()
            if tag_name in ['date', 'pubdate', 'published', 'updated']:
                if child.text and child.text.strip():
                    date_str = child.text.strip()
                    break
        if not date_str:
            for date_tag in ['pubDate', 'date', 'published', 'updated', '{http://purl.org/dc/elements/1.1/}date']:
                d_elem = item.find(date_tag)
                if d_elem is not None and d_elem.text and d_elem.text.strip():
                    date_str = d_elem.text.strip()
                    break

        parsed_dt = parse_date(date_str)
        if not parsed_dt:
            result_meta["unknown_date_count"] += 1
            continue

        # Track item dates for metadata
        item_dates.append(parsed_dt)

        # Convert to JST for window comparison
        dt_jst = parsed_dt.astimezone(JST)

        if window_start_jst <= dt_jst < window_end_jst:
            # Extract description / summary / content namespace-agnostically
            raw_desc = ""
            for child in item:
                tag_name = child.tag.split('}')[-1].lower()
                if tag_name in ['description', 'summary', 'content', 'encoded']:
                    if child.text and child.text.strip():
                        raw_desc = child.text.strip()
                        break
            if not raw_desc:
                for desc_tag in ['description', 'summary', 'content', '{http://purl.org/rss/1.0/modules/content/}encoded']:
                    desc_elem = item.find(desc_tag)
                    if desc_elem is not None and desc_elem.text and desc_elem.text.strip():
                        raw_desc = desc_elem.text.strip()
                        break

            snippet = clean_html_snippet(raw_desc, max_len=300)

            candidates.append({
                "title": title,
                "url": link,
                "published_date": dt_jst.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "source_name": feed_name,
                "snippet": snippet,
                "origin": "rss",
                "feed_id": feed_id
            })

    if item_dates:
        oldest = min(item_dates).astimezone(JST)
        latest = max(item_dates).astimezone(JST)
        result_meta["oldest_item_date"] = oldest.strftime("%Y-%m-%d %H:%M:%S %Z")
        result_meta["latest_item_date"] = latest.strftime("%Y-%m-%d %H:%M:%S %Z")

    result_meta["window_candidates_count"] = len(candidates)
    return candidates, result_meta

def collect_all_rss(feeds_file_path, target_date_str):
    """Collect candidates from all enabled feeds in feeds file.
    Returns: (all_candidates, feed_results_summary)
    """
    feeds = load_and_validate_feeds(feeds_file_path)
    enabled_feeds = [f for f in feeds if f.get("enabled", True)]

    all_candidates = []
    feed_results = []

    for feed in enabled_feeds:
        cands, meta = fetch_and_parse_feed(feed, target_date_str)
        feed_results.append(meta)
        if cands:
            all_candidates.extend(cands)

    return all_candidates, feed_results

def main():
    parser = argparse.ArgumentParser(description="Deterministic RSS/Atom feed collection CLI")
    parser.add_argument("--feeds-file", required=True, help="Path to feeds configuration JSON file")
    parser.add_argument("--target-date", required=True, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--output", required=True, help="Path to output JSON file for collected candidates")
    parser.add_argument("--metadata-output", help="Path to output metadata JSON file for feed execution results")
    args = parser.parse_args()

    try:
        candidates, feed_results = collect_all_rss(args.feeds_file, args.target_date)
        
        # Save candidates
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(candidates, f, ensure_ascii=False, indent=2)

        if args.metadata_output:
            meta = {
                "target_date": args.target_date,
                "feeds_file": args.feeds_file,
                "total_candidates": len(candidates),
                "feed_results": feed_results,
                "timestamp": datetime.now().isoformat()
            }
            with open(args.metadata_output, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"RSS collection completed successfully. Collected {len(candidates)} candidates from {len(feed_results)} feeds.")
    except Exception as e:
        print(f"Error during RSS collection: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
