"""Tests for extraction caching in extract.py.

Verifies cache hit/miss behavior, error handling, and environment configuration.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from torvalds_skill.extract import (
    _compute_cache_key,
    _load_cache,
    _save_cache_entry,
    _get_cached_response,
    extract_moves,
    extract_batch,
    SYSTEM_PROMPT,
)
from torvalds_skill.models import EmailRecord


@pytest.fixture(autouse=True)
def reset_cache_state():
    """Reset cache state before each test to ensure isolation."""
    from torvalds_skill import extract
    extract._CACHE_DATA = None
    yield
    # Clean up after test
    extract._CACHE_DATA = None


@pytest.fixture
def isolated_cache(tmp_path):
    """Provide a completely isolated cache environment for each test."""
    cache_file = tmp_path / "cache.jsonl"
    
    # Patch the environment to use our isolated cache
    with patch.dict(os.environ, {"EXTRACT_CACHE_PATH": str(cache_file)}):
        # Reset cache state
        from torvalds_skill import extract
        extract._CACHE_DATA = None
        yield cache_file
        # Clean up
        extract._CACHE_DATA = None


def _make_email(
    message_id: str = "test@example.com",
    subject: str = "Re: Some patch",
    body: str = "This code is broken. You cannot free the buffer before the last use. That is a use-after-free bug.",
) -> EmailRecord:
    return EmailRecord(
        message_id=message_id,
        from_name="Linus Torvalds",
        from_email="torvalds@linux.org",
        date="2024-01-01",
        subject=subject,
        in_reply_to="parent@example.com",
        body=body,
    )


class TestCacheKeyComputation:
    """Test cache key computation."""

    def test_key_is_deterministic(self):
        """Same inputs produce same key."""
        key1 = _compute_cache_key("model-1", "prompt text")
        key2 = _compute_cache_key("model-1", "prompt text")
        assert key1 == key2

    def test_different_model_different_key(self):
        """Different model names produce different keys."""
        key1 = _compute_cache_key("model-1", "prompt text")
        key2 = _compute_cache_key("model-2", "prompt text")
        assert key1 != key2

    def test_different_prompt_different_key(self):
        """Different prompt text produces different keys."""
        key1 = _compute_cache_key("model-1", "prompt text A")
        key2 = _compute_cache_key("model-1", "prompt text B")
        assert key1 != key2


class TestCacheHitAvoidsLlmCall:
    """Test that cache hits avoid LLM calls."""

    def test_cache_hit_avoids_llm_call(self, isolated_cache):
        """Pre-populate cache with hash of known prompt; verify no API call happens."""
        cache_file = isolated_cache
        email = _make_email(message_id="unique-cache-test-1@example.com")
        
        from torvalds_skill import config
        
        user_content = (
            f"Subject: {email.subject}\n"
            f"Date: {email.date}\n\n"
            f"{email.body[:8000]}"
        )
        prompt_text = SYSTEM_PROMPT + user_content
        cache_key = _compute_cache_key(config.MODEL, prompt_text)
        
        cached_response = '{"moves": [{"trigger": "cached-trigger", "principle": "cached-principle", "response": "cached-response", "severity": "reject", "category": "correctness"}]}'
        entry = {"key": cache_key, "response": cached_response, "ts": 1234567890}
        cache_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.return_value = {"moves": [{"trigger": "should-not-appear"}]}
            
            result = extract_moves(email)
            
            mock_call.assert_not_called()
            
            assert len(result["moves"]) == 1
            assert result["moves"][0]["trigger"] == "cached-trigger"
            assert result.get("cached") is True


class TestCacheMissCallsLlmAndPersists:
    """Test that cache misses call LLM and persist results."""

    def test_cache_miss_calls_llm_and_persists(self, isolated_cache):
        """Empty cache; mocked LLM returns valid response; verify call happened and cache file updated."""
        cache_file = isolated_cache
        email = _make_email(message_id="unique-cache-test-2@example.com")
        
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.return_value = {
                "moves": [{"trigger": "new-trigger", "principle": "new-principle"}],
                "_raw_content": '{"moves": [{"trigger": "new-trigger", "principle": "new-principle"}]}',
            }
            
            result = extract_moves(email)
            
            mock_call.assert_called_once()
            
            assert len(result["moves"]) == 1
            assert result["moves"][0]["trigger"] == "new-trigger"
            assert "cached" not in result or result.get("cached") is not True
        
        assert cache_file.exists()
        lines = cache_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        
        entry = json.loads(lines[0])
        assert "key" in entry
        assert "response" in entry
        assert "ts" in entry


class TestZeroMoveResponseCached:
    """Test that 0-move valid responses are cached."""

    def test_zero_move_response_cached(self, isolated_cache):
        """LLM returns valid response with 0 moves; verify it IS cached to avoid re-fetching."""
        cache_file = isolated_cache
        email = _make_email(message_id="unique-cache-test-3@example.com")
        
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.return_value = {
                "moves": [],
                "_raw_content": '{"moves": []}',
            }
            
            result = extract_moves(email)
            
            mock_call.assert_called_once()
            assert result["moves"] == []
        
        # 0-move valid responses should be cached to avoid re-fetching
        assert cache_file.exists()
        lines = cache_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert "key" in entry
        assert "response" in entry

    def test_error_result_not_cached(self, isolated_cache):
        """LLM call raises exception; verify nothing written to cache."""
        cache_file = isolated_cache
        email = _make_email(message_id="unique-cache-test-4@example.com")
        
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.side_effect = RuntimeError("LLM timeout")
            
            result = extract_moves(email)
            
            assert "error" in result
            assert result["moves"] == []
        
        assert not cache_file.exists()


class TestCorruptLineSkipped:
    """Test that corrupt cache lines are handled gracefully."""

    def test_corrupt_line_skipped(self, isolated_cache):
        """Corrupt last JSON line doesn't crash cache loading."""
        cache_file = isolated_cache
        
        valid_entry = {"key": "valid-key", "response": '{"moves": []}', "ts": 123}
        cache_file.write_text(
            json.dumps(valid_entry) + "\n" + "not valid json at all\n",
            encoding="utf-8"
        )
        
        cache = _load_cache()
        assert "valid-key" in cache
        assert cache["valid-key"]["response"] == '{"moves": []}'

    def test_empty_lines_skipped(self, isolated_cache):
        """Empty lines in cache file are skipped."""
        cache_file = isolated_cache
        
        valid_entry = {"key": "valid-key", "response": '{"moves": []}', "ts": 123}
        cache_file.write_text(
            json.dumps(valid_entry) + "\n\n\n",
            encoding="utf-8"
        )
        
        cache = _load_cache()
        assert "valid-key" in cache


class TestCacheDisabledViaEnv:
    """Test cache can be disabled via environment variable."""

    def test_cache_disabled_via_env(self, isolated_cache):
        """EXTRACT_CACHE=0 bypasses everything."""
        cache_file = isolated_cache
        email = _make_email(message_id="unique-cache-test-5@example.com")
        
        with patch.dict(os.environ, {"EXTRACT_CACHE": "0"}):
            with patch("torvalds_skill.extract._call_llm") as mock_call:
                mock_call.return_value = {
                    "moves": [{"trigger": "test"}],
                    "_raw_content": '{"moves": [{"trigger": "test"}]}',
                }
                
                result = extract_moves(email)
                
                mock_call.assert_called_once()
                assert "cached" not in result
            
            assert not cache_file.exists()


class TestDifferentPromptSameEmailMisses:
    """Test that different prompts produce cache misses."""

    def test_different_prompt_same_email_misses(self, isolated_cache):
        """Same email body but changed prompt template produces different key (miss)."""
        cache_file = isolated_cache
        email = _make_email(message_id="unique-cache-test-6@example.com")
        
        from torvalds_skill import config
        different_prompt = SYSTEM_PROMPT + "MODIFIED: " + (
            f"Subject: {email.subject}\n"
            f"Date: {email.date}\n\n"
            f"{email.body[:8000]}"
        )
        different_key = _compute_cache_key(config.MODEL, different_prompt)
        
        cached_response = '{"moves": [{"trigger": "old-prompt-trigger"}]}'
        entry = {"key": different_key, "response": cached_response, "ts": 1234567890}
        cache_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.return_value = {
                "moves": [{"trigger": "new-trigger"}],
                "_raw_content": '{"moves": [{"trigger": "new-trigger"}]}',
            }
            
            result = extract_moves(email)
            
            mock_call.assert_called_once()
            assert result["moves"][0]["trigger"] == "new-trigger"
            assert "cached" not in result or result.get("cached") is not True


class TestCacheThreadSafety:
    """Test thread safety of cache operations."""

    def test_concurrent_cache_access(self, isolated_cache):
        """Multiple threads can safely access cache."""
        cache_file = isolated_cache
        
        import threading
        
        errors = []
        
        def save_entry(i):
            try:
                _save_cache_entry(f"thread-key-{i}", f'{{"moves": [{{"trigger": "t{i}"}}]}}')
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=save_entry, args=(i,)) for i in range(10)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        
        assert cache_file.exists()
        lines = cache_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 10


class TestCacheWithExtractBatch:
    """Test cache behavior with batch extraction."""

    def test_batch_uses_cache(self, isolated_cache):
        """Batch extraction uses cache for cached emails."""
        cache_file = isolated_cache
        
        email1 = _make_email(message_id="unique-cache-cached@example.com")
        # Use different body for email2 so it has a different cache key
        email2 = EmailRecord(
            message_id="unique-cache-not-cached@example.com",
            from_name="Linus Torvalds",
            from_email="torvalds@linux.org",
            date="2024-01-01",
            subject="Re: Different patch",
            in_reply_to="parent@example.com",
            body="This is a completely different email body that will have a different cache key.",
            to="",
            cc="",
        )
        
        from torvalds_skill import config
        
        user_content = (
            f"Subject: {email1.subject}\n"
            f"Date: {email1.date}\n\n"
            f"{email1.body[:8000]}"
        )
        prompt_text = SYSTEM_PROMPT + user_content
        cache_key = _compute_cache_key(config.MODEL, prompt_text)
        
        cached_response = '{"moves": [{"trigger": "from-cache"}]}'
        entry = {"key": cache_key, "response": cached_response, "ts": 1234567890}
        cache_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        
        out_file = isolated_cache.parent / "output.jsonl"
        
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.return_value = {
                "moves": [{"trigger": "from-llm"}],
                "_raw_content": '{"moves": [{"trigger": "from-llm"}]}',
            }
            
            result = extract_batch([email1, email2], str(out_file))
            
            assert mock_call.call_count == 1
            assert result["processed"] == 2
        
        lines = out_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        
        results = [json.loads(line) for line in lines]
        assert results[0]["moves"][0]["trigger"] == "from-cache"
        assert results[1]["moves"][0]["trigger"] == "from-llm"