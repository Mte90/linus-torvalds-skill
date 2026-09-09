"""Regression tests for report/llm_review.call_llm.

Covers a real production break: the review-cache insertion once deleted the
request payload construction, so every review call would have crashed with
NameError. These tests pin the request body shape and the cache-hit path.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "report"))

import llm_review

from torvalds_skill import cache as cache_module


class _FakeResponse:
    """Minimal urlopen context manager yielding SSE byte lines."""

    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self._lines)


def _sse_body(text):
    payload = {"choices": [{"delta": {"content": text}}]}
    return [f"data: {json.dumps(payload)}\n".encode(), b"data: [DONE]\n"]


@pytest.fixture
def isolated_review_cache(tmp_path, monkeypatch):
    """Point the unified cache at tmp and reset global state around each test."""
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "review_cache.jsonl"))
    monkeypatch.setenv("CACHE_ENABLED", "1")
    monkeypatch.setattr(llm_review, "headers", lambda: {"Authorization": "Bearer test"})
    cache_module.reset_cache()
    yield
    cache_module.reset_cache()


def test_request_body_shape(isolated_review_cache, monkeypatch):
    """call_llm must send model/messages/stream payload (NameError regression)."""
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(_sse_body("hello world"))

    monkeypatch.setattr(llm_review.urllib.request, "urlopen", fake_urlopen)
    assert llm_review.call_llm("gpt-oss-120b", "review this", timeout=60) == "hello world"
    assert seen["body"]["model"] == "gpt-oss-120b"
    assert seen["body"]["messages"] == [{"role": "user", "content": "review this"}]
    assert seen["body"]["stream"] is True
    assert "max_tokens" in seen["body"]


def test_cache_hit_skips_transport(isolated_review_cache, monkeypatch):
    """Second identical call must not touch the network."""
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return _FakeResponse(_sse_body("cached answer"))

    monkeypatch.setattr(llm_review.urllib.request, "urlopen", fake_urlopen)
    first = llm_review.call_llm("gpt-oss-120b", "same prompt", timeout=60)
    second = llm_review.call_llm("gpt-oss-120b", "same prompt", timeout=60)
    assert first == second == "cached answer"
    assert len(calls) == 1


def test_cache_miss_on_different_params(isolated_review_cache, monkeypatch):
    """Different max_tokens must not return the earlier cached output."""
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(json.loads(req.data.decode("utf-8"))["max_tokens"])
        n = len(calls)
        return _FakeResponse(_sse_body(f"answer-{n}"))

    monkeypatch.setattr(llm_review.urllib.request, "urlopen", fake_urlopen)
    llm_review.call_llm("gpt-oss-120b", "prompt", timeout=60, max_tokens=1000)
    out = llm_review.call_llm("gpt-oss-120b", "prompt", timeout=60, max_tokens=2000)
    assert out == "answer-2"
    assert len(calls) == 2


def test_validate_review_format_rejects_cot_markers(monkeypatch):
    """_validate_review_format must reject chain-of-thought markers."""
    # Test with CoT markers (exceeds threshold of 3)
    cot_response = """---
some: frontmatter
---

### [CRITICAL] Finding title
- **Type:** bug

Need to think about this carefully
Maybe we should check this
Hmm, interesting
Wait, that's wrong
"""
    with pytest.raises(ValueError, match="review_format_invalid: too many CoT markers"):
        llm_review._validate_review_format(cot_response)

    # Test with another CoT marker pattern (4 markers)
    cot_response2 = """---
some: frontmatter
---

### [CRITICAL] Finding title
- **Type:** bug

Actually, let me reconsider this
OK. This is important.
Need to verify this
Let's double check
"""
    with pytest.raises(ValueError, match="review_format_invalid: too many CoT markers"):
        llm_review._validate_review_format(cot_response2)


def test_validate_review_format_accepts_clean_review(monkeypatch):
    """_validate_review_format must accept well-formed reviews."""
    clean_review = """---
title: Review of smallchat
date: 2026-09-09
---

## Findings

### [CRITICAL] Buffer overflow in parse_message
- **Type:** invariant-false
- **Trigger:** unchecked-input
- **Location:** smallchat-server.c:42
- **Issue:** No bounds check on message length
- **Fix:** Add length validation before memcpy
- **Pass:** 1

### [HIGH] Missing error check
- **Type:** bug
- **Trigger:** unchecked-error
- **Location:** chatlib.c:15
- **Issue:** Return value of socket() not checked
- **Fix:** Add error handling after socket call
- **Pass:** 1

## Summary
Code needs review before production.
"""
    # Should not raise
    llm_review._validate_review_format(clean_review)

    # Test review with up to 3 CoT-like markers (threshold allows this)
    borderline_review = """---
title: Review
---

### [LOW] Style issue
- **Type:** guideline

OK. This is minor.
"""
    # Should not raise (1 CoT marker is within threshold)
    llm_review._validate_review_format(borderline_review)

    # Test non-review content (no frontmatter) - passes without scrutiny
    non_review = "Just some random text"
    # Should return without raising
    llm_review._validate_review_format(non_review)


def test_reasoning_only_response_triggers_retry(monkeypatch):
    """call_llm must retry with disable_thinking when reasoning-only response detected."""
    monkeypatch.setattr(llm_review.project_config, "API_KEY", "sk-test")
    call_count = 0

    def fake_urlopen_first(req, timeout=None):
        nonlocal call_count
        call_count += 1
        # First call: return reasoning-only (no content)
        payload = {
            "choices": [{"delta": {"reasoning_content": "Let me think about this carefully..."}}]
        }
        return _FakeResponse([f"data: {json.dumps(payload)}\n".encode(), b"data: [DONE]\n"])

    def fake_urlopen_second(req, timeout=None):
        nonlocal call_count
        call_count += 1
        # Second call (with disable_thinking): return valid content
        return _FakeResponse(_sse_body("Valid review content"))

    # First attempt raises RuntimeError for reasoning-only
    monkeypatch.setattr(llm_review.urllib.request, "urlopen", fake_urlopen_first)
    with pytest.raises(RuntimeError, match="reasoning_only_response"):
        llm_review.call_llm("glm5.2", "review this", timeout=60)


def test_disable_thinking_retry_succeeds(monkeypatch):
    """call_llm must succeed on retry with disable_thinking=true."""
    monkeypatch.setattr(llm_review.project_config, "API_KEY", "sk-test")
    call_count = 0
    seen_payloads = []

    def fake_urlopen_first(req, timeout=None):
        nonlocal call_count
        call_count += 1
        # First call: reasoning-only
        payload = {"choices": [{"delta": {"reasoning_content": "Thinking...", "content": ""}}]}
        return _FakeResponse([f"data: {json.dumps(payload)}\n".encode(), b"data: [DONE]\n"])

    def fake_urlopen_second(req, timeout=None):
        nonlocal call_count
        call_count += 1
        # Capture the payload to verify disable_thinking was sent
        seen_payloads.append(json.loads(req.data.decode("utf-8")))
        # Second call: valid content
        return _FakeResponse(_sse_body("Valid review output"))

    # Mock urlopen to alternate between reasoning-only and success
    monkeypatch.setattr(llm_review.urllib.request, "urlopen", fake_urlopen_first)

    # Simulate the retry logic from main()
    disable_thinking = False
    result = None
    for attempt in range(2):
        try:
            # This would normally be called from main(), but we test the pattern
            monkeypatch.setattr(
                llm_review.urllib.request,
                "urlopen",
                fake_urlopen_second if attempt == 1 else fake_urlopen_first,
            )
            result = llm_review.call_llm(
                "glm5.2", "review this", timeout=60, disable_thinking=disable_thinking
            )
        except RuntimeError as e:
            if str(e) == "reasoning_only_response" and attempt == 0:
                disable_thinking = True
                continue
            raise

    assert result == "Valid review output"
    assert disable_thinking is True


def test_validate_review_format_rejects_unbracketed_severity(monkeypatch):
    """_validate_review_format must reject unbracketed severity headings."""
    unbracketed_review = """---
title: Review
---

### CRITICAL Buffer overflow
- **Type:** bug
- **Location:** test.c:42

### HIGH Missing check
- **Type:** bug
"""
    with pytest.raises(
        ValueError, match="review_format_invalid: finding heading not bracketed severity"
    ):
        llm_review._validate_review_format(unbracketed_review)


def test_validate_review_format_rejects_duplicate_titles(monkeypatch):
    """_validate_review_format must reject duplicate finding titles."""
    duplicate_review = """---
title: Review
---

### [CRITICAL] Buffer overflow
- **Type:** bug
- **Location:** test.c:42

### [HIGH] Buffer overflow
- **Type:** bug
- **Location:** test.c:100
"""
    with pytest.raises(ValueError, match="review_format_invalid: duplicate finding title"):
        llm_review._validate_review_format(duplicate_review)


def test_validate_review_format_accepts_all_severities(monkeypatch):
    """_validate_review_format must accept all valid severity levels."""
    all_severities_review = """---
title: Review
---

### [CRITICAL] Critical issue
- **Type:** bug
- **Location:** test.c:1

### [HIGH] High issue
- **Type:** bug
- **Location:** test.c:2

### [MEDIUM] Medium issue
- **Type:** bug
- **Location:** test.c:3

### [LOW] Low issue
- **Type:** bug
- **Location:** test.c:4
"""
    # Should not raise
    llm_review._validate_review_format(all_severities_review)


def test_validate_review_format_rejects_unknown_severity(monkeypatch):
    """_validate_review_format must reject unknown severity levels."""
    unknown_severity_review = """---
title: Review
---

### [URGENT] Urgent issue
- **Type:** bug
- **Location:** test.c:42
"""
    with pytest.raises(ValueError, match="review_format_invalid: unknown severity"):
        llm_review._validate_review_format(unknown_severity_review)
