#!/usr/bin/env python3
"""
agy-collect-wrapper.py
Antigravity CLI (agy) wrapper for generic web collection and article generation.
Strict adherence to my-skills issue #4 specifications.
"""

import sys
import os
import json
import subprocess
import argparse
from datetime import datetime

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
        
        # Parse output format json from agy
        try:
            data = json.loads(res.stdout)
            content = data.get("response", data.get("content", res.stdout))
            usage = data.get("usage", {})
            return "OK", content, usage
        except json.JSONDecodeError:
            # If not pure JSON wrapper, return stdout as content
            return "OK", res.stdout, {}

    except subprocess.TimeoutExpired:
        return "RATE_LIMITED", "Agy session timed out.", {}
    except Exception as e:
        return "FAILED", str(e), {}

def resolve_template_path(template_path, profile_path):
    """Resolve template_path relative to profile directory if it's a relative path."""
    if os.path.isabs(template_path):
        return os.path.normpath(template_path)
    profile_dir = os.path.dirname(os.path.abspath(profile_path))
    return os.path.normpath(os.path.join(profile_dir, template_path))

def main():
    parser = argparse.ArgumentParser(description="Antigravity CLI Generic Web Collection Wrapper")
    parser.add_argument("--profile", required=True, help="Path to collection profile JSON")
    parser.add_argument("--target-date", required=True, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--output", required=True, help="Path to output markdown file")
    parser.add_argument("--metadata-output", required=True, help="Path to output metadata JSON file")
    args = parser.parse_args()

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
    
    # max_items strictly required check
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

    template_path = resolve_template_path(raw_template_path, args.profile)

    if not os.path.exists(template_path):
        err_msg = f"Error: Resolved template path not found: {template_path} (from raw path: {raw_template_path})"
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

    # Session 1: Collection
    collection_prompt = f"""
You are an expert web research agent.
Target Date: {args.target_date}
Theme: {theme}
Sources / Guidelines: {json.dumps(sources, ensure_ascii=False)}
Constraints: Max items = {max_items}. Strict focus on the target date window.

Search the web and gather raw facts, news items, sources, URLs, and summaries relevant to the theme for the target date.
Provide a structured raw compilation of up to {max_items} items with titles, summaries, URLs, and key facts.
"""
    print(f"Running Session 1 (Collection) with model {model}...")
    s1_status, s1_content, s1_usage = run_agy_session(collection_prompt, model, effort)
    if s1_status != "OK":
        meta = {
            "status": s1_status,
            "target_date": args.target_date,
            "profile": os.path.basename(args.profile),
            "model": model,
            "session": "collection",
            "error_message": s1_content,
            "usage": {"collection": s1_usage},
            "timestamp": datetime.now().isoformat()
        }
        with open(args.metadata_output, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"Session 1 failed with status {s1_status}: {s1_content}", file=sys.stderr)
        sys.exit(1)

    # Session 2: Article Generation using Template
    generation_prompt = f"""
You are an expert technical writer and editor.
Target Date: {args.target_date}
Theme: {theme}

Here is the raw collected data from Session 1:
{s1_content}

Here is the output markdown template that you MUST strictly follow:
--- TEMPLATE START ---
{template_content}
--- TEMPLATE END ---

Instructions:
1. Replace all placeholders like [日付], [主要なポイント1], [ニュースタイトル1], [出典: 出典名 - タイトル](URL) etc., with real content derived from the collected data for target date {args.target_date}.
2. Ensure [日付] is replaced with {args.target_date}.
3. Produce complete, well-formatted Markdown matching the template structure precisely. Do not output conversational filler outside the markdown document.
"""
    print(f"Running Session 2 (Article Generation) with model {model}...")
    s2_status, s2_content, s2_usage = run_agy_session(generation_prompt, model, effort)
    if s2_status != "OK":
        meta = {
            "status": s2_status,
            "target_date": args.target_date,
            "profile": os.path.basename(args.profile),
            "model": model,
            "session": "generation",
            "error_message": s2_content,
            "usage": {"collection": s1_usage, "generation": s2_usage},
            "timestamp": datetime.now().isoformat()
        }
        with open(args.metadata_output, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"Session 2 failed with status {s2_status}: {s2_content}", file=sys.stderr)
        sys.exit(1)

    # Save generated article
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(s2_content)

    # Save metadata JSON
    meta = {
        "status": "OK",
        "target_date": args.target_date,
        "profile": os.path.basename(args.profile),
        "model": model,
        "effort": effort,
        "output_file": args.output,
        "usage": {
            "collection": s1_usage,
            "generation": s2_usage
        },
        "timestamp": datetime.now().isoformat()
    }
    with open(args.metadata_output, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated article at {args.output} and metadata at {args.metadata_output}")

if __name__ == "__main__":
    main()
