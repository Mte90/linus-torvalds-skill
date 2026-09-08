"""Tests for unified cache module."""

import json
import time

import pytest

from torvalds_skill import cache


@pytest.fixture(autouse=True)
def isolated_cache_env(tmp_path, monkeypatch):
    """Isolate each test with its own cache file and reset global singleton."""
    # Set up isolated cache path
    cache_file = tmp_path / "test_cache.jsonl"
    monkeypatch.setenv("CACHE_PATH", str(cache_file))
    monkeypatch.setenv("CACHE_TTL_HOURS", "168")  # 7 days default
    monkeypatch.setenv("CACHE_ENABLED", "1")

    # Reset global cache singleton before test
    cache.reset_cache()

    yield cache_file

    # Reset after test to clean up for next test
    cache.reset_cache()


class TestCacheKeyComputation:
    """Test deterministic cache key computation."""

    def test_key_is_deterministic(self):
        """Same inputs produce same key."""
        key1 = cache._compute_key("extract", "model-1", "prompt text", {"temp": 0.1})
        key2 = cache._compute_key("extract", "model-1", "prompt text", {"temp": 0.1})
        assert key1 == key2

    def test_different_stage_different_key(self):
        """Different stages produce different keys."""
        key1 = cache._compute_key("extract", "model-1", "prompt", {})
        key2 = cache._compute_key("review", "model-1", "prompt", {})
        assert key1 != key2

    def test_different_model_different_key(self):
        """Different models produce different keys."""
        key1 = cache._compute_key("extract", "model-1", "prompt", {})
        key2 = cache._compute_key("extract", "model-2", "prompt", {})
        assert key1 != key2

    def test_different_params_different_key(self):
        """Different parameters produce different keys."""
        key1 = cache._compute_key("extract", "model-1", "prompt", {"max_tokens": 500})
        key2 = cache._compute_key("extract", "model-1", "prompt", {"max_tokens": 1000})
        assert key1 != key2

    def test_params_order_independent(self):
        """Param order doesn't affect key (sorted JSON)."""
        key1 = cache._compute_key("extract", "model-1", "prompt", {"a": 1, "b": 2})
        key2 = cache._compute_key("extract", "model-1", "prompt", {"b": 2, "a": 1})
        assert key1 == key2


class TestCacheHitAvoidsLlmCall:
    """Test that cache hits avoid LLM calls."""

    def test_cache_hit_returns_cached_response(self, tmp_path, monkeypatch):
        """Pre-populate cache; verify hit returns cached value without LLM call."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path before creating cache instance
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        # Create cache with pre-existing entry
        test_key = "test_key_123"
        cached_response = "cached response content"
        entry = {"key": test_key, "response": cached_response, "ts": time.time()}

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(json.dumps(entry) + "\n")

        # Reset global cache to pick up new path
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        # Create cache instance pointing to our file
        test_cache = cache_module.get_cache()

        # Verify hit
        result = test_cache.get(test_key)
        assert result == cached_response

    def test_cache_miss_returns_none(self, tmp_path, monkeypatch):
        """Empty cache returns None on lookup."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        result = test_cache.get("nonexistent_key")
        assert result is None


class TestCacheTTLExpiry:
    """Test cache TTL expiry behavior."""

    def test_expired_entry_ignored(self, tmp_path, monkeypatch):
        """Entry older than TTL is ignored."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path and TTL
        monkeypatch.setenv("CACHE_PATH", str(cache_path))
        monkeypatch.setenv("CACHE_TTL_HOURS", "24")

        # Create cache with old entry
        old_ts = time.time() - (25 * 3600)  # 25 hours ago
        entry = {"key": "old_key", "response": "old response", "ts": old_ts}

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(json.dumps(entry) + "\n")

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        # Old entry should be expired
        result = test_cache.get("old_key")
        assert result is None

    def test_fresh_entry_returns(self, tmp_path, monkeypatch):
        """Entry within TTL returns successfully."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        # Create cache with fresh entry
        entry = {"key": "fresh_key", "response": "fresh response", "ts": time.time()}

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(json.dumps(entry) + "\n")

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        # Fresh entry should return
        result = test_cache.get("fresh_key")
        assert result == "fresh response"

    def test_ttl_disabled_bypasses_cache(self, tmp_path, monkeypatch):
        """TTL=0 bypasses cache entirely."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path and TTL=0
        monkeypatch.setenv("CACHE_PATH", str(cache_path))
        monkeypatch.setenv("CACHE_TTL_HOURS", "0")

        # Write an entry
        entry = {"key": "any_key", "response": "any response", "ts": time.time()}

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(json.dumps(entry) + "\n")

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        # Should return None even with valid entry
        result = test_cache.get("any_key")
        assert result is None


class TestCacheClear:
    """Test cache clear functionality."""

    def test_clear_removes_all_entries(self, tmp_path, monkeypatch):
        """Clear removes all entries and truncates file."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        test_cache.set("key1", "response1")
        test_cache.set("key2", "response2")

        # Verify entries exist
        assert cache_path.exists()
        assert len(cache_path.read_text().strip().splitlines()) == 2

        # Clear cache
        count = test_cache.clear()
        assert count == 2

        # Verify cache is empty
        assert cache_path.exists()
        assert cache_path.read_text().strip() == ""
        assert test_cache.get("key1") is None


class TestCacheStats:
    """Test cache statistics."""

    def test_stats_returns_correct_counts(self, tmp_path, monkeypatch):
        """Stats returns accurate active/expired counts."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path and TTL
        monkeypatch.setenv("CACHE_PATH", str(cache_path))
        monkeypatch.setenv("CACHE_TTL_HOURS", "24")

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        # Add fresh entry
        test_cache.set("fresh_key", "fresh response")

        # Add expired entry manually
        old_entry = {
            "key": "old_key",
            "response": "old response",
            "ts": time.time() - (25 * 3600),
        }
        with open(cache_path, "a") as f:
            f.write(json.dumps(old_entry) + "\n")

        # Reload to pick up manual entry
        test_cache._loaded = False
        test_cache._load()

        stats = test_cache.stats()
        assert stats["active_entries"] == 1
        assert stats["expired_entries"] == 1
        assert stats["total_entries"] == 2


class TestCacheCompact:
    """Test cache compaction (dedupe + remove expired)."""

    def test_compact_removes_expired_and_dedupes(self, tmp_path, monkeypatch):
        """Compact removes expired entries and deduplicates keys."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path and TTL
        monkeypatch.setenv("CACHE_PATH", str(cache_path))
        monkeypatch.setenv("CACHE_TTL_HOURS", "24")

        # Write entries with duplicates and expired
        entries = [
            {"key": "key1", "response": "response1_v1", "ts": time.time() - (25 * 3600)},  # expired
            {"key": "key2", "response": "response2_v1", "ts": time.time()},  # fresh
            {"key": "key2", "response": "response2_v2", "ts": time.time()},  # duplicate, fresh
            {"key": "key3", "response": "response3", "ts": time.time()},  # fresh
        ]

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        # Compact
        removed = test_cache.compact()

        # Should have removed 2 entries (1 expired + 1 duplicate)
        assert removed == 2

        # Verify only 2 unique fresh entries remain
        stats = test_cache.stats()
        assert stats["active_entries"] == 2


class TestCorruptLineHandling:
    """Test handling of corrupt cache lines."""

    def test_corrupt_last_line_skipped(self, tmp_path, monkeypatch):
        """Truncated JSON last line doesn't crash loading."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        # Write valid entry + corrupt last line
        valid_entry = {
            "key": "valid_key",
            "response": "valid response",
            "ts": time.time(),
        }

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(json.dumps(valid_entry) + "\n")
            f.write('{"corrupt": ')  # Invalid JSON

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        # Should load without crashing
        result = test_cache.get("valid_key")
        assert result == "valid response"

    def test_empty_lines_skipped(self, tmp_path, monkeypatch):
        """Empty lines in cache file are skipped."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        valid_entry = {
            "key": "valid_key",
            "response": "valid response",
            "ts": time.time(),
        }

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(json.dumps(valid_entry) + "\n\n\n")

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        result = test_cache.get("valid_key")
        assert result == "valid response"


class TestCacheEnvironment:
    """Test cache environment variable behavior."""

    def test_cache_disabled_via_env(self, tmp_path, monkeypatch):
        """CACHE_ENABLED=0 bypasses cache."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path and disable cache
        monkeypatch.setenv("CACHE_PATH", str(cache_path))
        monkeypatch.setenv("CACHE_ENABLED", "0")

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        # Should return None even with valid entry
        test_cache.set("key1", "response1")
        result = test_cache.get("key1")
        assert result is None


class TestThreadSafeCache:
    """Test thread safety of cache operations."""

    def test_concurrent_cache_writes(self, tmp_path, monkeypatch):
        """Multiple threads can safely write to cache."""
        cache_path = tmp_path / "cache.jsonl"

        # Set cache path
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        import threading

        # Reset global cache
        from torvalds_skill import cache as cache_module

        cache_module._cache = None

        test_cache = cache_module.get_cache()

        errors = []

        def write_key(i):
            try:
                test_cache.set(f"thread_key_{i}", f"response_{i}")
            except Exception as e:
                errors.append(e)

        # Spawn 10 threads
        threads = [threading.Thread(target=write_key, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0

        # All 10 keys present
        stats = test_cache.stats()
        assert stats["active_entries"] == 10
