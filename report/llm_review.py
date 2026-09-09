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
import time
import urllib.error
import urllib.request
from pathlib import Path

# Import unified cache
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from torvalds_skill import cache as llm_cache  # noqa: E402
from torvalds_skill import (  # noqa: E402  # import not at top due to sys.path manipulation
    config as project_config,
)

CHAT_URL = project_config.CHAT_URL


def _validate_review_format(response: str) -> None:
    """Validate review format with strict checks.

    Raises ValueError on any format violation:
    - Finding headings must be bracketed: ### [SEVERITY]
    - Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW
    - No duplicate finding titles
    - CoT markers must not exceed threshold (3)
    """
    import re

    if not response.strip():
        raise ValueError("review_format_invalid: empty response")

    # Only validate responses that look like reviews (frontmatter present)
    if not response.startswith("---"):
        return  # Non-review content passes without scrutiny

    lines = response.splitlines()

    # 1. Check finding format: all ### headings must be bracketed severity
    finding_heading_re = re.compile(r"^###\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+(.+)$")
    non_bracketed_finding_re = re.compile(
        r"^###\s+[A-Z]+\s+"
    )  # Matches ### SEVERITY without brackets
    all_severity_re = re.compile(
        r"^###\s+\[([A-Z]+)\]\s+"
    )  # Matches ### [SEVERITY] to check valid set

    finding_titles = []
    for line in lines:
        # Check for unbracketed severity headings (### CRITICAL instead of ### [CRITICAL])
        if non_bracketed_finding_re.match(line):
            raise ValueError("review_format_invalid: finding heading not bracketed severity")

        # Check for bracketed headings with invalid severity
        bracket_match = all_severity_re.match(line)
        if bracket_match:
            severity = bracket_match.group(1)
            if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                raise ValueError(f"review_format_invalid: unknown severity '{severity}'")
            # Extract title for duplicate check
            title_match = finding_heading_re.match(line)
            if title_match:
                finding_titles.append(title_match.group(2).strip())

    # 2. Check for duplicate finding titles
    seen_titles = set()
    for title in finding_titles:
        if title in seen_titles:
            raise ValueError(f"review_format_invalid: duplicate finding title '{title}'")
        seen_titles.add(title)

    # 3. Check CoT markers (threshold: 3)
    cot_markers = (
        "Need ",
        "Let's ",
        "Maybe ",
        "OK.",
        "Hmm",
        "Wait,",
        "Actually",
    )
    cot_count = sum(1 for line in lines if line.strip().startswith(cot_markers))
    if cot_count > 3:
        raise ValueError(f"review_format_invalid: too many CoT markers ({cot_count} > 3)")


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


def call_llm(
    model: str,
    prompt: str,
    timeout: int = 600,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    disable_thinking: bool = False,
) -> str:
    """Call OpenAI-compatible chat completions API with streaming. Returns accumulated text.

    Uses unified cache with key = SHA(stage + model + prompt + params).
    Cache bypass: set CACHE_ENABLED=0 env var.

    When disable_thinking=True, sends chat_template_kwargs={"enable_thinking": false}
    to suppress the thinking phase. Used as fallback when a reasoning model exhausts
    its token budget on internal deliberation (reasoning_only_response).
    """
    from torvalds_skill.profiles import get_profile

    profile = get_profile(model)

    # max_tokens: use provided value or fall back to profile
    if max_tokens is None:
        max_tokens = getattr(profile, "review_max_tokens", None) or profile.max_tokens

    # Compute cache key from all inputs that affect output
    params = {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "disable_thinking": disable_thinking,
    }
    cache_key = llm_cache._compute_key("review", model, prompt, params)

    # Check cache first (if enabled)
    if llm_cache._get_cache_enabled():
        cached = llm_cache.get_cache().get(cache_key)
        if cached is not None:
            print(f"cache hit (review): {cache_key[:8]}...", file=sys.stderr)
            return cached

    print("streaming...", file=sys.stderr)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if disable_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
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
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        reasoning_parts.append(reasoning)

    result = "".join(content_parts)
    if not result.strip() and reasoning_parts:
        print(
            "warning: reasoning-only response detected (no content produced). "
            "Do not use chain-of-thought as review output.",
            file=sys.stderr,
        )
        raise RuntimeError("reasoning_only_response")

    try:
        _validate_review_format(result)
    except ValueError as e:
        print(
            f"warning: review format validation failed: {e}. Response not cached.",
            file=sys.stderr,
        )
        raise RuntimeError("review_format_invalid") from e

    word_count = len(result.split())
    print(f"done: {word_count} words", file=sys.stderr)

    # Cache successful non-empty responses
    if result.strip() and llm_cache._get_cache_enabled():
        llm_cache.get_cache().set(cache_key, result)

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

    # Call API with retry. First attempt uses the model's native reasoning mode.
    # If the model exhausts its token budget on reasoning (reasoning_only_response),
    # the second attempt disables the thinking phase via chat_template_kwargs.
    disable_thinking = False
    for attempt in range(2):
        try:
            response = call_llm(args.model, prompt, timeout, disable_thinking=disable_thinking)
            if not response.strip():
                print(f"warning: empty response (attempt {attempt + 1})", file=sys.stderr)
                if attempt == 0:
                    time.sleep(2)
                    continue
            # Write output
            Path(args.out).write_text(response)
            sys.exit(0)
        except RuntimeError as e:
            if str(e) == "reasoning_only_response" and attempt == 0:
                print(
                    "retrying with reasoning disabled (enable_thinking=false)",
                    file=sys.stderr,
                )
                disable_thinking = True
                continue
            print(f"error: API call failed (attempt {attempt + 1}): {e}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
                continue
            sys.exit(1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"error: API call failed (attempt {attempt + 1}): {e}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
                continue
            sys.exit(1)

    sys.exit(1)


if __name__ == "__main__":
    main()
