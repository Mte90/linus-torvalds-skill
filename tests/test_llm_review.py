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
