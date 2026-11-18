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

def mechanical_dedup(candidates, corpus_index):
    """Perform mechanical deduplication based on normalized URL, title similarity, and key entities."""
    kept = []
    excluded = []

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
            if len(kw) >= 3 and kw in c_text:
                keyword_hits += 1
                matched_keyword = kw

        # If key entities like organization / incident name match significantly
        if keyword_hits >= 2 or (any(org in c_text for org in ["富岳", "ミツモア", "大阪府"]) and any(org in "".join(corpus_index["titles"]) for org in ["富岳", "ミツモア", "大阪府"])):
            excluded.append({
                "candidate": c,
                "reason": "KEYWORD_MATCH",
                "matched_keyword": matched_keyword
            })
            continue

        kept.append(c)

    return kept, excluded

def fetch_article_body(url, timeout=10):
    """Fetch article body via HTTP GET, fallback to snippet if fails."""
    if not url or not url.startswith("http"):
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Compatible; MySkillsWebCollector/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="ignore")
            # Simple HTML tags removal
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:3000] # Cap raw body
    except Exception:
        return ""

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
    boundary_default = profile.get("boundary_default", "drop")
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

    # Step 1: Candidate Prior Collection (Pool size: max_items * 2 + 1, e.g. 7 for max_items=3)
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
    candidates = []
    try:
        # Clean markdown code blocks if any
        clean_json_str = s1_content.strip()
        if clean_json_str.startswith("```"):
            clean_json_str = re.sub(r'^```(?:json)?\s*', '', clean_json_str)
            clean_json_str = re.sub(r'\s*```$', '', clean_json_str)
        candidates = json.loads(clean_json_str)
        if not isinstance(candidates, list):
            candidates = candidates.get("candidates", [])
    except Exception:
        # Fallback regex search for json list
        try:
            m = re.search(r'\[\s*\{.*\}\s*\]', s1_content, re.DOTALL)
            if m:
                candidates = json.loads(m.group(0))
        except Exception:
            candidates = []

    # Step 2: Mechanical Dedup
    corpus_index = extract_corpus_index(reports_dir, args.target_date, dedup_days)
    kept_after_mech, mech_excluded = mechanical_dedup(candidates, corpus_index)

    # Step 3: Boundary Judgment (Batch via agy if needed, or apply default)
    # For ambiguous candidates (e.g. keywords partially overlap but not exact URL match)
    final_kept = []
    boundary_records = []
    
    # Identify boundary candidates (e.g. remaining kept items that need check)
    boundary_candidates = kept_after_mech
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
                        if boundary_default == "drop":
                            boundary_records.append({"candidate": cand, "judgment": "DROP_BOUNDARY", "reason": res.get("reason", "No confirmed new facts")})
                        else:
                            final_kept.append(cand)
                            boundary_records.append({"candidate": cand, "judgment": "KEEP_BOUNDARY_DEFAULT", "reason": "Default keep"})
            except Exception:
                # If json parse fails, apply default
                for cand in boundary_candidates:
                    if boundary_default == "drop":
                        boundary_records.append({"candidate": cand, "judgment": "DROP_BOUNDARY_ERROR", "reason": "JSON parse error, dropped by default"})
                    else:
                        final_kept.append(cand)
                        boundary_records.append({"candidate": cand, "judgment": "KEEP_BOUNDARY_ERROR", "reason": "JSON parse error, kept by default"})
        else:
            for cand in boundary_candidates:
                if boundary_default == "drop":
                    boundary_records.append({"candidate": cand, "judgment": "DROP_BOUNDARY_FAIL", "reason": "Session failed, dropped by default"})
                else:
                    final_kept.append(cand)
                    boundary_records.append({"candidate": cand, "judgment": "KEEP_BOUNDARY_FAIL", "reason": "Session failed, kept by default"})
    else:
        final_kept = boundary_candidates

    recollection_triggered = False
    recollection_usage = {}

    # Step 6: Insufficient Check & Re-collection (Max 1 time)
    if len(final_kept) < max_items:
        excluded_urls = [c.get("candidate", {}).get("url") for c in mech_excluded] + [c.get("candidate", {}).get("url") for c in boundary_records if "DROP" in c.get("judgment", "")]
        recollection_prompt = f"""
You are an expert web research agent.
Target Date: {args.target_date}
Theme: {theme}
We need additional items because previous candidates were deduplicated.
Excluded URLs to avoid: {json.dumps(excluded_urls)}
Please gather {max_items - len(final_kept)} NEW unique items for the target date using alternative queries/sources.
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
                    for ni in new_items:
                        if len(final_kept) < max_items and ni.get("url") not in excluded_urls:
                            final_kept.append(ni)
            except Exception:
                pass

    insufficient_flag = len(final_kept) < max_items
    if insufficient_flag and insufficient_fallback != "reduce":
        # Handle other fallback policies if required
        pass

    # Step 4: Fetch Article Bodies (Python side)
    enriched_candidates = []
    for cand in final_kept:
        url = cand.get("url", "")
        body = fetch_article_body(url)
        if not body:
            body = cand.get("snippet", "")
        cand_copy = dict(cand)
        cand_copy["fetched_body"] = body[:2000] # Cap to 2000 chars per design
        enriched_candidates.append(cand_copy)

    # Step 5: Article Generation based on fetched bodies
    generation_prompt = f"""
You are an expert technical writer and editor.
Target Date: {args.target_date}
Theme: {theme}

Here are the verified article bodies and data to base the report on:
{json.dumps(enriched_candidates, ensure_ascii=False)}

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

    # Save metadata JSON with extended audit records
    meta = {
        "status": "OK",
        "target_date": args.target_date,
        "profile": os.path.basename(args.profile),
        "model": model,
        "effort": effort,
        "output_file": args.output,
        "session_count": session_count,
        "insufficient": insufficient_flag,
        "final_item_count": len(final_kept),
        "dedup_records": {
            "mechanical_excluded": mech_excluded,
            "boundary_records": boundary_records
        },
        "recollection_triggered": recollection_triggered,
        "candidates_summary": enriched_candidates,
        "usage": usage_stats,
        "timestamp": datetime.now().isoformat()
    }
    with open(args.metadata_output, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated article at {args.output} and metadata at {args.metadata_output} (Total sessions: {session_count})")

if __name__ == "__main__":
    main()
