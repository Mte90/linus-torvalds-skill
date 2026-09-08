#!/usr/bin/env python3
"""
llm_review.py — direct LLM API caller for review pipeline.

Calls any OpenAI-compatible chat completions endpoint with streaming.
Usage: python3 report/llm_review.py --model <model> --prompt-file <path> --out <path> [--timeout <sec>]
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import sys

# Import config from the project package (adds .env loading + env var aliases)
import sys as _sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from pathlib import Path as _Path

# Import unified cache
_SRC = _Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in _sys.path:
    _sys.path.insert(0, str(_SRC))
from torvalds_skill import cache as llm_cache  # noqa: E402
from torvalds_skill import (  # noqa: E402  # import not at top due to sys.path manipulation
    config as project_config,
)

CHAT_URL = project_config.CHAT_URL


def _validate_review_format(response: str) -> bool:
    """Check that review response is not contaminated with chain-of-thought.

    Only applies when the response looks like a review (starts with frontmatter).
    Short non-review responses (e.g. test mocks) pass without scrutiny.
    """
    if not response.strip():
        return False
    # Only validate responses that look like reviews (frontmatter present)
    if not response.startswith("---"):
        return True
    lines = response.splitlines()
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
    return cot_count <= 3


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
    to suppress the reasoning phase. Used as fallback when a reasoning model exhausts
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
        "timeout": timeout,
        "disable_thinking": disable_thinking,
    }
    cache_key = llm_cache._compute_key("review", model, prompt, params)

    # Check cache first (if enabled)
    if llm_cache._get_cache_enabled():
        cached = llm_cache.get_cache().get(cache_key)
        if cached is not None:
            print(f"cache hit (review): {cache_key[:8]}...", file=_sys.stderr)
            return cached

    print("streaming...", file=_sys.stderr)

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
            file=_sys.stderr,
        )
        raise RuntimeError("reasoning_only_response")

    if not _validate_review_format(result):
        print(
            "warning: review format validation failed (possible CoT contamination). "
            "Response not cached.",
            file=_sys.stderr,
        )
        raise RuntimeError("review_format_invalid")

    word_count = len(result.split())
    print(f"done: {word_count} words", file=_sys.stderr)

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
            response = call_llm(
                args.model, prompt, timeout, disable_thinking=disable_thinking
            )
            if not response.strip():
                print(f"warning: empty response (attempt {attempt + 1})", file=_sys.stderr)
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
                    file=_sys.stderr,
                )
                disable_thinking = True
                continue
            print(f"error: API call failed (attempt {attempt + 1}): {e}", file=_sys.stderr)
            if attempt == 0:
                time.sleep(2)
                continue
            sys.exit(1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"error: API call failed (attempt {attempt + 1}): {e}", file=_sys.stderr)
            if attempt == 0:
                time.sleep(2)
                continue
            sys.exit(1)

    sys.exit(1)


if __name__ == "__main__":
    main()
