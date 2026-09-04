#!/usr/bin/env python3
"""
llm_review.py — direct LLM API caller for review pipeline.

Calls any OpenAI-compatible chat completions endpoint with streaming.
Usage: python3 report/llm_review.py --model <model> --prompt-file <path> --out <path> [--timeout <sec>]
"""

from __future__ import annotations

import argparse
import json
import signal
import sys

# Import config from the project package (adds .env loading + env var aliases)
import sys as _sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from pathlib import Path as _Path

_SRC = _Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in _sys.path:
    _sys.path.insert(0, str(_SRC))
from torvalds_skill import (  # noqa: E402  # import not at top due to sys.path manipulation
    config as project_config,
)

CHAT_URL = project_config.CHAT_URL


def headers() -> dict:
    return project_config.headers()


class _WallClockTimeout:
    """Context manager enforcing a wall-clock timeout via SIGALRM.

    urlopen(timeout=...) is per-read, not wall-clock — SSE keepalive
    bytes reset it indefinitely. This raises TimeoutError after the
    configured seconds regardless of streaming activity.
    """

    def __init__(self, seconds: int):
        self._seconds = seconds
        self._old_handler = None

    def __enter__(self):
        self._old_handler = signal.signal(signal.SIGALRM, self._handler)
        signal.alarm(self._seconds)
        return self

    def __exit__(self, *exc):
        signal.alarm(0)
        signal.signal(signal.SIGALRM, self._old_handler)
        return False

    @staticmethod
    def _handler(signum, frame):
        raise TimeoutError("wall-clock timeout exceeded")


def call_llm(model: str, prompt: str, timeout: int = 600) -> str:
    """Call OpenAI-compatible chat completions API with streaming. Returns accumulated text."""
    from torvalds_skill.profiles import get_profile

    profile = get_profile(model)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a code reviewer."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": profile.max_tokens,  # Default from profile (16000 for all known models)
        "stream": True,
    }
    # Reasoning models must keep their thinking phase (user requirement):
    # never disable it. Give them a larger budget instead so reasoning AND
    # content both fit without truncation.
    # Supported max_tokens per model (from profiles.py):
    #   gpt-oss-120b: 16000, glm5.2: 16000, mistral-small-4-119b: 16000
    if profile.reasoning:
        payload["max_tokens"] = profile.max_tokens

    print("streaming...", file=sys.stderr)

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(CHAT_URL, data=body, headers=headers(), method="POST")

    content_parts = []
    reasoning_parts = []
    read_timeout = getattr(project_config, "READ_TIMEOUT", 120) if project_config else 120
    with _WallClockTimeout(timeout):
        with urllib.request.urlopen(req, timeout=read_timeout) as resp:
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
                else:
                    # Reasoning models stream delta.reasoning_content during their
                    # thinking phase. Keep it SEPARATE from content: mixing it in
                    # prepends the entire chain-of-thought to the answer. It is
                    # used only as salvage when no content was produced at all
                    # (e.g. token budget exhausted by reasoning).
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        reasoning_parts.append(reasoning)

    result = "".join(content_parts)
    if not result.strip() and reasoning_parts:
        result = "".join(reasoning_parts)
    word_count = len(result.split())
    print(f"done: {word_count} words", file=sys.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description="Call LLM API for review generation")
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

    # Determine timeout from profile
    from torvalds_skill.profiles import get_profile

    profile = get_profile(args.model)
    if args.timeout:
        timeout = args.timeout
    else:
        timeout = profile.review_timeout

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
