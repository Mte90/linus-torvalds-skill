#!/usr/bin/env python3
"""
llm_review.py — direct Regolo API caller for review pipeline.

Replaces opencode agent calls with streaming chat completions API.
Usage: python3 report/llm_review.py --model <model> --prompt-file <path> --out <path> [--timeout <sec>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# API configuration (mirrors src/torvalds_skill/config.py)
API_KEY = os.environ.get("REGOLO_API_KEY", "***REDACTED***")
HOST = "https://api.regolo.ai/v1"
CHAT_URL = "https://api.regolo.ai/v1/chat/completions"


def headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def call_llm(model: str, prompt: str, timeout: int = 600) -> str:
    """Call Regolo chat completions API with streaming. Returns accumulated text."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a code reviewer."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 16000,
        "stream": True,
    }

    print("streaming...", file=sys.stderr)
    
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(CHAT_URL, data=body, headers=headers(), method="POST")
    
    content_parts = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            chunk = json.loads(data_str)
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            text = delta.get("content")
            if text:
                content_parts.append(text)
    
    result = "".join(content_parts)
    word_count = len(result.split())
    print(f"done: {word_count} words", file=sys.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description="Call Regolo API for review generation")
    parser.add_argument("--model", required=True, help="Model label (e.g., gpt-oss-120b, glm5.2)")
    parser.add_argument("--prompt-file", required=True, help="Path to prompt file")
    parser.add_argument("--out", required=True, help="Path to output file")
    parser.add_argument("--timeout", type=int, default=None, help="Timeout in seconds")
    args = parser.parse_args()

    # Read prompt
    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        print(f"error: prompt file not found: {args.prompt_file}", file=sys.stderr)
        sys.exit(1)
    prompt = prompt_path.read_text()

    # Determine timeout (GLM models need longer)
    if args.timeout:
        timeout = args.timeout
    elif "glm" in args.model.lower():
        timeout = 1200
    else:
        timeout = 600

    # Call API with retry
    for attempt in range(2):
        try:
            response = call_llm(args.model, prompt, timeout)
            if not response.strip():
                print(f"warning: empty response (attempt {attempt + 1})", file=sys.stderr)
                if attempt == 0:
                    time.sleep(2)
                    continue
            # Write output
            Path(args.out).write_text(response)
            sys.exit(0)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"error: API call failed (attempt {attempt + 1}): {e}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
                continue
            sys.exit(1)

    sys.exit(1)


if __name__ == "__main__":
    main()