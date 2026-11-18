#!/usr/bin/env python3
"""
agy-collect-wrapper.py
Antigravity CLI (agy) wrapper for generic web collection, mechanical dedup,
batch boundary judgment, article body fetching, re-collection, and structured article generation.
Strict adherence to my-skills issue #7 specifications.
"""

import sys
import os
import json
import subprocess
import argparse
import re
from datetime import datetime, timedelta
import urllib.request
from urllib.parse import urlparse, urlunparse

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)
try:
    from rss_collect import collect_all_rss, load_and_validate_feeds
except ImportError:
    collect_all_rss = None
    load_and_validate_feeds = None

def classify_error(stderr_text):
    """Classify error into RATE_LIMITED, AUTH_REQUIRED, or FAILED."""
    lower = stderr_text.lower()
    if any(k in lower for k in ["429", "resource_exhausted", "rate", "quota", "exhausted"]):
        return "RATE_LIMITED"
    if any(k in lower for k in ["auth", "login", "credential", "unauthorized", "token"]):
        return "AUTH_REQUIRED"
    return "FAILED"

def check_agy_auth():
    """Check if agy is authenticated and responsive."""
    try:
        res = subprocess.run(["agy", "models"], capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            err_type = classify_error(res.stderr)
            return err_type, res.stderr
        return "OK", ""
    except subprocess.TimeoutExpired:
        return "FAILED", "Timeout while checking agy authentication."
    except Exception as e:
        return "FAILED", str(e)

def run_agy_session(prompt, model, effort, timeout_sec=600):
    """Run a single agy session with print mode and return (status, content/error, usage_dict)."""
    cmd = [
        "agy",
        "--model", model,
        "--effort", effort,
        "--output-format", "json",
        "-p", prompt
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        if res.returncode != 0:
            err_type = classify_error(res.stderr + "\n" + res.stdout)
            return err_type, res.stderr or res.stdout, {}
        
        try:
            data = json.loads(res.stdout)
            content = data.get("response", data.get("content", res.stdout))
            usage = data.get("usage", {})
            return "OK", content, usage
        except json.JSONDecodeError:
            return "OK", res.stdout, {}

    except subprocess.TimeoutExpired:
        return "RATE_LIMITED", "Agy session timed out.", {}
    except Exception as e:
        return "FAILED", str(e), {}

def resolve_path(path_str, profile_path):
    """Resolve path relative to profile directory if it's a relative path."""
    if os.path.isabs(path_str):
        return os.path.normpath(path_str)
    profile_dir = os.path.dirname(os.path.abspath(profile_path))
    return os.path.normpath(os.path.join(profile_dir, path_str))

def normalize_url(url):
    """Normalize URL by removing tracking params and trailing slash."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        # Remove query / fragment
        clean_parsed = parsed._replace(query="", fragment="")
        path = clean_parsed.path.rstrip("/")
        normalized = urlunparse(clean_parsed._replace(path=path))
        return normalized
    except Exception:
        return url.strip().rstrip("/")

def extract_corpus_index(reports_dir, target_date_str, days_count=7):
    """Extract corpus index (URLs, titles, key entities) from prior reports."""
    index = {
        "urls": set(),
        "titles": [],
        "keywords": set()
    }
    if not reports_dir or not os.path.exists(reports_dir):
        return index

    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        return index

    # Read reports from reports_dir strictly BEFORE target_date, up to days_count
    for i in range(1, days_count + 1):
        d = target_date - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        # Match files containing d_str
        for filename in os.listdir(reports_dir):
            if d_str in filename and filename.endswith(".md"):
                filepath = os.path.join(reports_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Extract URLs using regex or markdown link pattern [text](url)
                        urls = re.findall(r'\((https?://[^\s)]+)\)', content)
                        for u in urls:
                            index["urls"].add(normalize_url(u))
                        
                        # Extract headings or titles
                        lines = content.splitlines()
                        for line in lines:
                            if line.startswith("#"):
                                clean_title = line.lstrip("#").strip()
                                index["titles"].append(clean_title)
                                # Extract potential keywords (nouns, CVE, orgs)
                                words = re.findall(r'[一-龠ぁ-んァ-ンa-zA-Z0-9\-]+', clean_title)
                                for w in words:
                                    if len(w) >= 2:
                                        index["keywords"].add(w)
                except Exception:
                    pass
    return index

def has_affinity(candidate, corpus_index):
    """Check if candidate has affinity with corpus (partial key, org name, title vocabulary overlap)."""
    title = candidate.get("title", "")
    snippet = candidate.get("snippet", "")
    url = candidate.get("url", "")
    c_text = (title + " " + snippet + " " + url)

    # Check URL domain match or path token match
    try:
        parsed_url = urlparse(url)
        netloc = parsed_url.netloc
        for cu in corpus_index.get("urls", set()):
            try:
                c_parsed = urlparse(cu)
                if netloc and c_parsed.netloc and netloc == c_parsed.netloc:
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # Check keyword / org match
    corpus_keywords = corpus_index.get("keywords", set())
    for kw in corpus_keywords:
        if len(kw) >= 2 and kw in c_text:
            return True

    return False

def mechanical_dedup(candidates, corpus_index):
    """Perform mechanical deduplication based on normalized URL, title similarity, and key entities.
    Returns: (kept, excluded, affinity_candidates)
    """
    kept = []
    excluded = []
    affinity_candidates = []

    for c in candidates:
        url = c.get("url", "")
        norm_url = normalize_url(url)
        title = c.get("title", "")
        snippet = c.get("snippet", "")
        
        # 1. URL exact match check
        if norm_url and norm_url in corpus_index["urls"]:
            excluded.append({
                "candidate": c,
                "reason": "URL_MATCH",
                "matched_with": norm_url
            })
            continue

        # 2. Keyword / Entity overlap check
        matched_keyword = None
        c_text = (title + " " + snippet)
        keyword_hits = 0
        corpus_keywords = corpus_index.get("keywords", set())
        for kw in corpus_keywords:
            if len(kw) >= 2 and kw in c_text:
                keyword_hits += 1
                matched_keyword = kw

        # If key entities overlap significantly via corpus keywords (e.g. 2 or more matching keywords)
        if keyword_hits >= 2:
            excluded.append({
                "candidate": c,
                "reason": "KEYWORD_MATCH",
                "matched_keyword": matched_keyword
            })
            continue

        # 3. Check affinity
        if has_affinity(c, corpus_index):
            affinity_candidates.append(c)
        else:
            kept.append(c)

    return kept, excluded, affinity_candidates

def fetch_article_body(url, timeout=10, browser_fallback=False):
    """Fetch article body via HTTP GET (Stage 1), diagnose status and extraction.
    If HTTP 403 and browser_fallback is True, try Playwright (Stage 2).
    Returns: (text, fetch_reason, status_code, body_source, length)
    """
    if not url or not url.startswith("http"):
        return "", "INVALID_URL", 0, "snippet_fallback", 0

    # Stage 1: HTTP GET
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Compatible; MySkillsWebCollector/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            html = response.read().decode("utf-8", errors="ignore")
            
            # Better extraction for article content
            article_match = re.search(r'<article[^>]*>(.*?)</article>', html, flags=re.DOTALL | re.IGNORECASE)
            main_match = re.search(r'<main[^>]*>(.*?)</main>', html, flags=re.DOTALL | re.IGNORECASE)
            
            raw_target = html
            if article_match:
                raw_target = article_match.group(1)
            elif main_match:
                raw_target = main_match.group(1)

            text = re.sub(r'<script[^>]*>.*?</script>', '', raw_target, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            length = len(text)
            if length < 100:
                text_full = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                text_full = re.sub(r'<style[^>]*>.*?</style>', '', text_full, flags=re.DOTALL | re.IGNORECASE)
                text_full = re.sub(r'<[^>]+>', ' ', text_full)
                text_full = re.sub(r'\s+', ' ', text_full).strip()
                if len(text_full) > length:
                    text = text_full
                    length = len(text)

            fetch_reason = "OK"
            if length < 600:
                fetch_reason = "TOO_SHORT"

            return text[:2000], fetch_reason, status_code, "http", length
    except urllib.error.HTTPError as e:
        status_code = e.code
        # Stage 2: Browser fallback on HTTP 403 if enabled
        if status_code == 403 and browser_fallback:
            pw_text, pw_status = fetch_via_playwright(url, timeout=timeout)
            if pw_text and len(pw_text) >= 100:
                pw_reason = "OK" if len(pw_text) >= 600 else "TOO_SHORT"
                return pw_text[:2000], pw_reason, 200, "browser", len(pw_text)
            else:
                return "", "BROWSER_FAIL", 403, "snippet_fallback", 0
        elif status_code == 404:
            return "", "HTTP_404", 404, "snippet_fallback", 0
        elif status_code == 403:
            return "", "HTTP_403", 403, "snippet_fallback", 0
        else:
            return "", "HTTP_ERROR", status_code, "snippet_fallback", 0
    except Exception as e:
        return "", "HTTP_ERROR", 0, "snippet_fallback", 0

def fetch_via_playwright(url, timeout=15):
    """Fetch article body using Playwright if available."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            html = page.content()
            browser.close()
            
            # Clean HTML
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text, "SUCCESS"
    except Exception:
        return "", "FAILED"

def main():
    parser = argparse.ArgumentParser(description="Antigravity CLI Generic Web Collection Wrapper with Dedup & Pipeline")
    parser.add_argument("--profile", required=True, help="Path to collection profile JSON")
    parser.add_argument("--target-date", required=True, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--output", required=True, help="Path to output markdown file")
    parser.add_argument("--metadata-output", required=True, help="Path to output metadata JSON file")
    args = parser.parse_args()

    session_count = 0
    usage_stats = {}

    # 1. Check auth first
    auth_status, auth_msg = check_agy_auth()
    if auth_status != "OK":
        meta = {
            "status": auth_status,
            "target_date": args.target_date,
            "profile": args.profile,
            "error_message": auth_msg,
            "timestamp": datetime.now().isoformat()
        }
        with open(args.metadata_output, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"Error: Authentication failed with status {auth_status}: {auth_msg}", file=sys.stderr)
        sys.exit(1)

    # 2. Load profile
    if not os.path.exists(args.profile):
        print(f"Error: Profile not found at {args.profile}", file=sys.stderr)
        sys.exit(1)

    with open(args.profile, "r", encoding="utf-8") as f:
        profile = json.load(f)

    theme = profile.get("theme", "")
    sources = profile.get("sources", [])
    constraints = profile.get("constraints", {})
    
    if "max_items" not in constraints or constraints["max_items"] is None:
        err_msg = "Error: constraints.max_items is strictly required in profile JSON."
        meta = {
            "status": "FAILED",
            "target_date": args.target_date,
            "profile": os.path.basename(args.profile),
            "error_message": err_msg,
            "timestamp": datetime.now().isoformat()
        }
        with open(args.metadata_output, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(err_msg, file=sys.stderr)
        sys.exit(1)

    max_items = constraints["max_items"]
    model = profile.get("model", "gemini-3.8-flash-low")
    effort = profile.get("effort", "low")
    raw_template_path = profile.get("template_path", "")

    # Dedup & profile configs
    dedup_cfg = profile.get("dedup", {})
    reports_dir_rel = dedup_cfg.get("reports_dir", "")
    reports_dir = resolve_path(reports_dir_rel, args.profile) if reports_dir_rel else ""
    dedup_days = dedup_cfg.get("days", 7)
    boundary_default = profile.get("boundary_default", "keep")
    insufficient_fallback = profile.get("insufficient_fallback", "reduce")

    if not raw_template_path:
        err_msg = "Error: template_path is not specified in profile JSON."
        meta = {
            "status": "FAILED",
            "target_date": args.target_date,
            "profile": os.path.basename(args.profile),
            "error_message": err_msg,
            "timestamp": datetime.now().isoformat()
        }
        with open(args.metadata_output, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(err_msg, file=sys.stderr)
        sys.exit(1)

    template_path = resolve_path(raw_template_path, args.profile)
    if not os.path.exists(template_path):
        err_msg = f"Error: Resolved template path not found: {template_path}"
        meta = {
            "status": "FAILED",
            "target_date": args.target_date,
            "profile": os.path.basename(args.profile),
            "error_message": err_msg,
            "timestamp": datetime.now().isoformat()
        }
        with open(args.metadata_output, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(err_msg, file=sys.stderr)
        sys.exit(1)

    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    # Step 1: Candidate Prior Collection (RSS prioritized if feeds_file is configured)
    feeds_file_rel = profile.get("feeds_file", "")
    feeds_file = resolve_path(feeds_file_rel, args.profile) if feeds_file_rel else ""
    
    candidates = []
    feed_results = []
    rss_collection_used = False

    if feeds_file and os.path.exists(feeds_file):
        rss_collection_used = True
        print(f"Collecting candidates from RSS feeds file: {feeds_file}...")
        try:
            candidates, feed_results = collect_all_rss(feeds_file, args.target_date)
            for c in candidates:
                if "origin" not in c:
                    c["origin"] = "rss"
        except Exception as e:
            print(f"Error during RSS collection: {e}", file=sys.stderr)
            feed_results = [{"status": "ERROR", "error_message": str(e)}]
            candidates = []
    else:
        pool_size = max_items * 2 + 1
        collection_prompt = f"""
You are an expert web research agent.
Target Date: {args.target_date}
Theme: {theme}
Sources / Guidelines: {json.dumps(sources, ensure_ascii=False)}
Constraints: Gather up to {pool_size} candidate items (strictly within or relevant to the target date window).

Output the candidates strictly as a JSON array of objects with the following keys for each item:
- "title": string
- "url": string
- "published_date": string
- "source_name": string
- "snippet": string
Return ONLY valid JSON array containing the candidates, without any extra markdown wrappers or conversational text if possible.
"""
        print(f"Running Session 1 (Candidate Collection) with model {model}...")
        session_count += 1
        s1_status, s1_content, s1_usage = run_agy_session(collection_prompt, model, effort)
        usage_stats["collection"] = s1_usage

        if s1_status != "OK":
            meta = {
                "status": s1_status,
                "target_date": args.target_date,
                "profile": os.path.basename(args.profile),
                "model": model,
                "session": "collection",
                "error_message": s1_content,
                "session_count": session_count,
                "usage": usage_stats,
                "timestamp": datetime.now().isoformat()
            }
            with open(args.metadata_output, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            sys.exit(1)

        # Parse candidate items from JSON output
        try:
            clean_json_str = s1_content.strip()
            if clean_json_str.startswith("```"):
                clean_json_str = re.sub(r'^```(?:json)?\s*', '', clean_json_str)
                clean_json_str = re.sub(r'\s*```$', '', clean_json_str)
            candidates = json.loads(clean_json_str)
            if not isinstance(candidates, list):
                candidates = candidates.get("candidates", [])
        except Exception:
            try:
                m = re.search(r'\[\s*\{.*\}\s*\]', s1_content, re.DOTALL)
                if m:
                    candidates = json.loads(m.group(0))
            except Exception:
                candidates = []

        for c in candidates:
            if "origin" not in c:
                c["origin"] = "agy"

    candidates_total_count = len(candidates)

    # Step 2: Mechanical Dedup
    corpus_index = extract_corpus_index(reports_dir, args.target_date, dedup_days)
    kept_after_mech, mech_excluded, affinity_candidates = mechanical_dedup(candidates, corpus_index)

    # Step 3: Fetchability Check on dedup survivors (Stage 1 / Stage 2)
    fetchable_min_chars = profile.get("fetchable_min_chars", 600)
    browser_fallback_enabled = profile.get("browser_fallback", False)

    def evaluate_candidates_fetchability(cand_list):
        evaluated = []
        for cand in cand_list:
            url = cand.get("url", "")
            fetched, source_status, status_code, body_source, length = fetch_article_body(url, browser_fallback=browser_fallback_enabled)
            is_fetchable = (200 <= status_code < 300) and (length >= fetchable_min_chars)
            
            cand_copy = dict(cand)
            cand_copy["fetchable"] = is_fetchable
            cand_copy["fetch_reason"] = source_status
            cand_copy["fetch_status"] = status_code
            cand_copy["body_length"] = length
            if is_fetchable:
                cand_copy["fetched_body"] = fetched[:2000]
                cand_copy["body_source"] = body_source
                cand_copy["snippet_only"] = False
            else:
                cand_copy["fetched_body"] = cand.get("snippet", "")
                cand_copy["body_source"] = "snippet_fallback"
                cand_copy["snippet_only"] = True
            evaluated.append(cand_copy)
        return evaluated

    evaluated_kept_after_mech = evaluate_candidates_fetchability(kept_after_mech)
    evaluated_affinity = evaluate_candidates_fetchability(affinity_candidates)

    fetchable_survivors = [c for c in evaluated_kept_after_mech if c.get("fetchable")] + [c for c in evaluated_affinity if c.get("fetchable")]
    all_dedup_survivors = evaluated_kept_after_mech + evaluated_affinity

    recollection_triggered = False
    recollection_reason = ""
    recollection_usage = {}

    # Step 4: Re-collection (Trigger: fetchable count < max_items or dedup survivors count < max_items, max 1 time)
    if len(fetchable_survivors) < max_items or len(all_dedup_survivors) < max_items:
        if len(fetchable_survivors) < max_items:
            recollection_reason = f"fetchable_shortage: {len(fetchable_survivors)}/{max_items}"
        else:
            recollection_reason = f"dedup_survivors_shortage: {len(all_dedup_survivors)}/{max_items}"

        excluded_urls = [c.get("url") for c in candidates]
        recollection_prompt = f"""
You are an expert web research agent.
Target Date: {args.target_date}
Theme: {theme}
We need additional items because previous candidates were deduplicated or failed fetchable check.
Excluded URLs to avoid: {json.dumps(excluded_urls)}
Please gather {max_items * 2} NEW unique items for the target date using alternative queries/sources.
Output strictly as a JSON array of objects with keys: "title", "url", "published_date", "source_name", "snippet".
"""
        print(f"Running Re-collection Session with model {model}...")
        session_count += 1
        rc_status, rc_content, rc_usage = run_agy_session(recollection_prompt, model, effort)
        recollection_triggered = True
        usage_stats["recollection"] = rc_usage

        if rc_status == "OK":
            try:
                rc_clean = rc_content.strip()
                if rc_clean.startswith("```"):
                    rc_clean = re.sub(r'^```(?:json)?\s*', '', rc_clean)
                    rc_clean = re.sub(r'\s*```$', '', rc_clean)
                new_items = json.loads(rc_clean)
                if isinstance(new_items, list):
                    candidates_total_count += len(new_items)
                    for nc in new_items:
                        if "origin" not in nc:
                            nc["origin"] = "agy"
                    # Apply mechanical dedup and fetchability to new items
                    new_kept, new_mech_exc, new_affinity = mechanical_dedup(new_items, corpus_index)
                    mech_excluded.extend(new_mech_exc)
                    evaluated_new_kept = evaluate_candidates_fetchability(new_kept)
                    evaluated_new_affinity = evaluate_candidates_fetchability(new_affinity)
                    
                    evaluated_kept_after_mech.extend(evaluated_new_kept)
                    evaluated_affinity.extend(evaluated_new_affinity)
                    all_dedup_survivors = evaluated_kept_after_mech + evaluated_affinity
            except Exception:
                pass
    else:
        recollection_reason = f"not_triggered: sufficient fetchable ({len(fetchable_survivors)}) and survivors ({len(all_dedup_survivors)}) >= {max_items}"

    # Step 5: Boundary Judgment (1 time on final pool of affinity candidates)
    final_kept = [c for c in evaluated_kept_after_mech if c.get("fetchable")] + [c for c in evaluated_kept_after_mech if not c.get("fetchable")] # non-affinity kept items
    boundary_records = []
    
    boundary_candidates = evaluated_affinity
    if boundary_candidates and reports_dir:
        boundary_prompt = f"""
You are an expert fact-checker.
Target Date: {args.target_date}
Evaluate the following candidate news items against prior reporting to determine if they contain "NEW FACTS" (続報・新事実あり) or are "mere duplicates/re-posts" (単なる再掲).
Candidates: {json.dumps(boundary_candidates, ensure_ascii=False)}

For each candidate, return a JSON array of objects with keys:
- "index": integer (0-based index of candidate)
- "has_new_facts": boolean (true if new facts / updates exist, false otherwise)
- "reason": string
Return ONLY valid JSON array.
"""
        print(f"Running Boundary Judgment Session with model {model}...")
        session_count += 1
        b_status, b_content, b_usage = run_agy_session(boundary_prompt, model, effort)
        usage_stats["boundary_judgment"] = b_usage

        if b_status == "OK":
            try:
                b_clean = b_content.strip()
                if b_clean.startswith("```"):
                    b_clean = re.sub(r'^```(?:json)?\s*', '', b_clean)
                    b_clean = re.sub(r'\s*```$', '', b_clean)
                b_results = json.loads(b_clean)
                b_map = {item["index"]: item for item in b_results if "index" in item}
                for idx, cand in enumerate(boundary_candidates):
                    res = b_map.get(idx)
                    if res and res.get("has_new_facts") is True:
                        final_kept.append(cand)
                        boundary_records.append({"candidate": cand, "judgment": "KEEP_NEW_FACTS", "reason": res.get("reason")})
                    else:
                        if res and res.get("has_new_facts") is False:
                            if boundary_default == "drop":
                                boundary_records.append({"candidate": cand, "judgment": "DROP_BOUNDARY", "reason": res.get("reason", "No confirmed new facts")})
                            else:
                                final_kept.append(cand)
                                boundary_records.append({"candidate": cand, "judgment": "KEEP_BOUNDARY_DEFAULT", "reason": "Default keep"})
                        else:
                            final_kept.append(cand)
                            boundary_records.append({"candidate": cand, "judgment": "KEEP_UNJUDGED", "reason": "Not explicitly dropped by model, kept"})
            except Exception:
                for cand in boundary_candidates:
                    final_kept.append(cand)
                    boundary_records.append({"candidate": cand, "judgment": "KEEP_BOUNDARY_ERROR_SKIPPED", "reason": "JSON parse error, boundary check skipped and kept by safety default"})
                usage_stats["boundary_judgment_error"] = "JSON parse error"
        else:
            for cand in boundary_candidates:
                final_kept.append(cand)
                boundary_records.append({"candidate": cand, "judgment": "KEEP_BOUNDARY_FAIL_SKIPPED", "reason": f"Session failed ({b_status}), boundary check skipped and kept by safety default"})
            usage_stats["boundary_judgment_error"] = f"Session failed: {b_status}"
    else:
        for cand in boundary_candidates:
            final_kept.append(cand)

    # Step 6: Selection (Fetchable items first, then snippet fallback items up to max_items)
    fetchable_pool = [c for c in final_kept if c.get("fetchable")]
    snippet_pool = [c for c in final_kept if not c.get("fetchable")]

    final_selected = (fetchable_pool + snippet_pool)[:max_items]
    final_fetchable_count = sum(1 for c in final_selected if c.get("fetchable"))

    insufficient_flag = final_fetchable_count < max_items
    insufficient_reason = f"fetchable_shortage: {final_fetchable_count}/{max_items}" if insufficient_flag else "none"

    # Step 7: Article Generation based on selected candidates
    generation_prompt = f"""
You are an expert technical writer and editor.
Target Date: {args.target_date}
Theme: {theme}

Here are the verified article bodies and data to base the report on:
{json.dumps(final_selected, ensure_ascii=False)}

Here is the output markdown template that you MUST strictly follow:
--- TEMPLATE START ---
{template_content}
--- TEMPLATE END ---

Instructions:
1. Replace all placeholders like [日付], [主要なポイント1], [ニュースタイトル1], [出典: 出典名 - タイトル](URL) etc., with real content derived ONLY from the provided verified article bodies for target date {args.target_date}.
2. Ensure [日付] is replaced with {args.target_date}.
3. Produce complete, well-formatted Markdown matching the template structure precisely. Do not output conversational filler outside the markdown document.
"""
    print(f"Running Session 2 (Article Generation) with model {model}...")
    session_count += 1
    s2_status, s2_content, s2_usage = run_agy_session(generation_prompt, model, effort)
    usage_stats["generation"] = s2_usage

    if s2_status != "OK":
        meta = {
            "status": s2_status,
            "target_date": args.target_date,
            "profile": os.path.basename(args.profile),
            "model": model,
            "session": "generation",
            "error_message": s2_content,
            "session_count": session_count,
            "usage": usage_stats,
            "timestamp": datetime.now().isoformat()
        }
        with open(args.metadata_output, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        sys.exit(1)

    # Save generated article
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(s2_content)

    # Save metadata JSON with extended audit records and summary statistics
    dedup_survivors_count = len(all_dedup_survivors)
    fetchable_rate_val = (len(fetchable_survivors) / dedup_survivors_count) if dedup_survivors_count > 0 else 0.0

    origin_breakdown = {"rss": 0, "agy": 0}
    for c in final_selected:
        orig = c.get("origin", "agy")
        if orig in origin_breakdown:
            origin_breakdown[orig] += 1
        else:
            origin_breakdown[orig] = 1

    meta = {
        "status": "OK",
        "target_date": args.target_date,
        "profile": os.path.basename(args.profile),
        "model": model,
        "effort": effort,
        "output_file": args.output,
        "session_count": session_count,
        "rss_collection_used": rss_collection_used,
        "feed_results": feed_results,
        "origin_breakdown": origin_breakdown,
        "insufficient": insufficient_flag,
        "insufficient_reason": insufficient_reason,
        "candidates_total": candidates_total_count,
        "dedup_survivors_count": dedup_survivors_count,
        "fetchable_count": len(fetchable_survivors),
        "fetchable_rate": f"{len(fetchable_survivors)}/{dedup_survivors_count} ({round(fetchable_rate_val * 100, 2)}%)",
        "fetchable_rate_numerator": len(fetchable_survivors),
        "fetchable_rate_denominator": dedup_survivors_count,
        "recollection_triggered": recollection_triggered,
        "recollection_reason": recollection_reason,
        "final_composition": {
            "fetchable_count": final_fetchable_count,
            "snippet_fallback_count": len(final_selected) - final_fetchable_count,
            "total_selected": len(final_selected)
        },
        "final_item_count": len(final_selected),
        "dedup_records": {
            "mechanical_excluded": mech_excluded,
            "boundary_records": boundary_records
        },
        "candidates_summary": final_selected,
        "usage": usage_stats,
        "timestamp": datetime.now().isoformat()
    }
    with open(args.metadata_output, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated article at {args.output} and metadata at {args.metadata_output} (Total sessions: {session_count})")

if __name__ == "__main__":
    main()
