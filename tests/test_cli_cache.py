"""Tests for CLI cache commands."""

import json
import os
import time

from torvalds_skill import cli


class TestCacheStatsCommand:
    """Test cache stats CLI command."""

    def test_cache_stats_command(self, tmp_path, monkeypatch, capsys):
        """cache stats shows cache information."""
        cache_path = tmp_path / "cache.jsonl"

        # Set up cache path
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        # Add some entries
        from torvalds_skill import cache as cache_module

        test_cache = cache_module.UnifiedCache()
        test_cache._cache_path = cache_path
        test_cache._ttl_hours = 168

        test_cache.set("key1", "response1")
        test_cache.set("key2", "response2")

        # Reset cache instance to pick up new path
        cache_module._cache = None

        # Run stats command
        import sys

        old_argv = sys.argv
        sys.argv = ["torvalds_skill", "cache", "stats"]

        try:
            cli.main()
        finally:
            sys.argv = old_argv

        # Verify output
        captured = capsys.readouterr()
        assert "Cache path" in captured.out or str(cache_path) in captured.out


class TestCacheClearCommand:
    """Test cache clear CLI command."""

    def test_cache_clear_command(self, tmp_path, monkeypatch, capsys):
        """cache clear removes all entries."""
        cache_path = tmp_path / "cache.jsonl"

        # Set up cache path
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        # Add some entries
        from torvalds_skill import cache as cache_module

        test_cache = cache_module.UnifiedCache()
        test_cache._cache_path = cache_path
        test_cache._ttl_hours = 168

        test_cache.set("key1", "response1")
        test_cache.set("key2", "response2")

        # Reset cache instance
        cache_module._cache = None

        # Run clear command
        import sys

        old_argv = sys.argv
        sys.argv = ["torvalds_skill", "cache", "clear"]

        try:
            cli.main()
        finally:
            sys.argv = old_argv

        # Verify cache is empty
        assert not cache_path.exists() or cache_path.read_text().strip() == ""


class TestCacheCompactCommand:
    """Test cache compact CLI command."""

    def test_cache_compact_command(self, tmp_path, monkeypatch, capsys):
        """cache compact removes expired entries."""
        cache_path = tmp_path / "cache.jsonl"

        # Set up cache path BEFORE importing cache module
        monkeypatch.setenv("CACHE_PATH", str(cache_path))
        monkeypatch.setenv("CACHE_TTL_HOURS", "24")  # 24 hour TTL for this test

        # Add expired entry directly to file (25 hours old, exceeds 24h TTL)
        old_entry = {
            "key": "old_key",
            "response": "old response",
            "ts": time.time() - (25 * 3600),
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(json.dumps(old_entry) + "\n")

        # Import cache module AFTER setting env var
        from torvalds_skill import cache as cache_module

        # Reset cache instance to pick up new path and TTL
        cache_module._cache = None

        # Run compact command
        import sys

        old_argv = sys.argv
        sys.argv = ["torvalds_skill", "cache", "compact"]

        try:
            cli.main()
        finally:
            sys.argv = old_argv

        # Verify expired entry removed by checking file directly
        lines = [line for line in cache_path.read_text().strip().splitlines() if line.strip()]
        assert len(lines) == 0  # All entries should be removed (expired)


class TestExtractNoCacheFlag:
    """Test --no-cache flag on extract stage."""

    def test_no_cache_flag_sets_env(self, monkeypatch):
        """--no-cache flag sets CACHE_ENABLED=0."""
        # Mock stage_extract to avoid actual extraction
        called_with_args = []

        def mock_stage_extract(sample, workers, resume):
            called_with_args.append((sample, workers, resume))

        monkeypatch.setattr(cli, "stage_extract", mock_stage_extract)

        # Set --no-cache flag
        import sys

        old_argv = sys.argv
        sys.argv = ["torvalds_skill", "extract", "--no-cache", "--sample", "10"]

        try:
            cli.main()
        finally:
            sys.argv = old_argv

        # Verify CACHE_ENABLED was set to 0
        assert os.environ.get("CACHE_ENABLED") == "0"


class TestExtractFreshFlag:
    """Test --fresh flag on extract stage."""

    def test_fresh_flag_clears_cache_and_disables(self, tmp_path, monkeypatch):
        """--fresh flag clears cache and sets CACHE_ENABLED=0."""
        cache_path = tmp_path / "cache.jsonl"
        monkeypatch.setenv("CACHE_PATH", str(cache_path))

        # Add some entries
        from torvalds_skill import cache as cache_module

        test_cache = cache_module.UnifiedCache()
        test_cache._cache_path = cache_path
        test_cache._ttl_hours = 168

        test_cache.set("key1", "response1")

        # Reset cache instance
        cache_module._cache = None

        # Mock stage_extract
        called = []

        def mock_stage_extract(sample, workers, resume):
            called.append(True)

        monkeypatch.setattr(cli, "stage_extract", mock_stage_extract)

        # Set --fresh flag
        import sys

        old_argv = sys.argv
        sys.argv = ["torvalds_skill", "extract", "--fresh", "--sample", "10"]

        try:
            cli.main()
        finally:
            sys.argv = old_argv

        # Verify cache was cleared and disabled
        assert not cache_path.exists() or cache_path.read_text().strip() == ""
        assert os.environ.get("CACHE_ENABLED") == "0"
