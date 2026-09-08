"""
Unified LLM cache module for the torvalds-skill pipeline.

Provides disk-backed caching with configurable TTL for all LLM stages
(extract, distill, review). Cache keys are deterministic hashes of all
inputs that affect the output.

Key format rationale:
- stage: different stages produce different outputs (extract vs distill vs review)
- model: different models produce different outputs
- prompt_hash: SHA-256 of the full prompt text (content changes = different output)
- params_hash: SHA-256 of serialized params (temperature, max_tokens, etc.)
  → ensures different settings never return stale outputs

TTL decision: content-hash keys make time-based expiry redundant for correctness.
A key only returns valid results if inputs match exactly. Default TTL=7d is a
practical cleanup window, not a correctness requirement. Override knob exists.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any


def _get_cache_enabled() -> bool:
    """Check if cache is enabled via environment."""
    return os.environ.get("CACHE_ENABLED", "1") != "0"


def _get_cache_path() -> Path:
    """Get cache file path from environment or default."""
    return Path(os.environ.get("CACHE_PATH", "data/unified_cache.jsonl"))


def _get_cache_ttl_hours() -> int:
    """Get cache TTL in hours from environment. Default 7d (168h)."""
    # Content-hash keys make TTL redundant for correctness, but 7d is a
    # practical cleanup window. Override via CACHE_TTL_HOURS env var.
    return int(os.environ.get("CACHE_TTL_HOURS", "168"))  # 7 days default


def _compute_key(stage: str, model: str, prompt: str, params: dict[str, Any] | None = None) -> str:
    """Compute deterministic cache key from all inputs.

    Key components:
    - stage: extract, distill, review (different outputs)
    - model: model name (different models = different outputs)
    - prompt: full prompt text (SHA-256 hash)
    - params: temperature, max_tokens, etc. (SHA-256 hash of sorted JSON)

    Rationale: Every element that affects output is included. Different
    settings (e.g., max_tokens=500 vs max_tokens=1000) produce different
    keys, preventing stale outputs.
    """
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    if params:
        # Sort keys for deterministic serialization
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.sha256(params_str.encode("utf-8")).hexdigest()
    else:
        params_hash = hashlib.sha256(b"{}").hexdigest()

    # Combine all components with null separators
    key_input = f"{stage}\x00{model}\x00{prompt_hash}\x00{params_hash}"
    return hashlib.sha256(key_input.encode("utf-8")).hexdigest()


class UnifiedCache:
    """Thread-safe, disk-backed LLM cache with TTL support.

    Format: JSONL with entries {key, response, ts}
    - key: SHA-256 hash of (stage + model + prompt + params)
    - response: raw LLM response text
    - ts: Unix timestamp for TTL expiry

    Thread safety: File lock for writes, in-memory cache with lock for reads.
    Corrupt last line handling: gracefully skips invalid JSON on load.
    """

    def __init__(self):
        self._cache_path = _get_cache_path()
        self._ttl_hours = _get_cache_ttl_hours()
        self._cache: dict[str, dict] = {}
        self._loaded = False
        self._lock = threading.Lock()
        self._file_lock = threading.Lock()

    def _load(self) -> None:
        """Load cache from disk. Idempotent - only loads once."""
        if self._loaded:
            return

        with self._lock:
            if self._loaded:
                return

            self._cache.clear()

            if not self._cache_path.exists():
                self._loaded = True
                return

            try:
                with open(self._cache_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if all(k in entry for k in ("key", "response", "ts")):
                                self._cache[entry["key"]] = {
                                    "response": entry["response"],
                                    "ts": entry["ts"],
                                }
                        except json.JSONDecodeError:
                            # Skip corrupt lines (including truncated last line)
                            continue
            except OSError:
                # If we can't read the file, start with empty cache
                pass

            self._loaded = True

    def reload(self) -> None:
        """Force reload cache from disk. Use after external file modifications."""
        with self._lock:
            self._cache.clear()
            self._loaded = False
        self._load()

    def get(self, key: str) -> str | None:
        """Get cached response if not expired. Returns None if miss/expired."""
        # TTL=0 means cache disabled
        if self._ttl_hours <= 0:
            return None

        # Check if cache is enabled via environment
        if not _get_cache_enabled():
            return None

        self._load()

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            # Check TTL
            if time.time() - entry["ts"] > self._ttl_hours * 3600:
                return None

            return str(entry["response"])

    def set(self, key: str, response: str) -> None:
        """Append entry to disk cache and update in-memory cache."""
        # TTL=0 means cache disabled
        if self._ttl_hours <= 0:
            return

        # Check if cache is enabled via environment
        if not _get_cache_enabled():
            return

        self._load()

        with self._lock:
            # Update in-memory cache
            self._cache[key] = {"response": response, "ts": time.time()}

        # Append to disk (thread-safe with file lock)
        with self._file_lock:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "response": response, "ts": time.time()}) + "\n")

    def clear(self) -> int:
        """Clear all cache entries. Returns count of entries cleared."""
        self._load()

        with self._lock:
            count = len(self._cache)
            self._cache.clear()

        # Truncate file
        with self._file_lock:
            open(self._cache_path, "w", encoding="utf-8").close()

        return count

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        self._load()

        with self._lock:
            now = time.time()
            cutoff = now - self._ttl_hours * 3600 if self._ttl_hours > 0 else 0

            active = 0
            expired = 0
            for entry in self._cache.values():
                if entry["ts"] > cutoff:
                    active += 1
                else:
                    expired += 1

            return {
                "path": str(self._cache_path),
                "ttl_hours": self._ttl_hours,
                "total_entries": len(self._cache),
                "active_entries": active,
                "expired_entries": expired,
                "file_size_bytes": self._cache_path.stat().st_size
                if self._cache_path.exists()
                else 0,
            }

    def compact(self) -> int:
        """Remove expired entries and dedupe. Returns count of entries removed."""
        self._load()

        with self._lock:
            if not self._cache_path.exists():
                return 0

            original_lines = self._cache_path.read_text(encoding="utf-8").strip().splitlines()
            original_count = len([line for line in original_lines if line.strip()])

            now = time.time()
            cutoff = now - self._ttl_hours * 3600 if self._ttl_hours > 0 else 0

            # Keep only active entries, dedupe by key (last write wins)
            seen_keys: set[str] = set()
            kept_entries: list[dict] = []

            # Iterate in reverse to keep latest duplicates
            for line in original_lines:
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    key = entry.get("key")
                    ts = entry.get("ts", 0)

                    if key and ts > cutoff and key not in seen_keys:
                        seen_keys.add(key)
                        kept_entries.append(entry)
                except json.JSONDecodeError:
                    # Skip corrupt lines
                    continue

            # Rewrite file with deduped entries
            with self._file_lock:
                with open(self._cache_path, "w", encoding="utf-8") as f:
                    for entry in kept_entries:
                        f.write(json.dumps(entry) + "\n")

            # Update in-memory cache
            self._cache = {
                e["key"]: {"response": e["response"], "ts": e["ts"]} for e in kept_entries
            }

            # Return count of entries removed
            return original_count - len(kept_entries)


# Global cache instance
_cache: UnifiedCache | None = None
_cache_lock = threading.Lock()


def reset_cache() -> None:
    """Reset the global cache singleton. Use in tests for isolation."""
    global _cache
    _cache = None


def get_cache() -> UnifiedCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = UnifiedCache()
    return _cache


def cache_get(
    stage: str, model: str, prompt: str, params: dict[str, Any] | None = None
) -> str | None:
    """Get cached response by computed key. Returns None on miss."""
    if not _get_cache_enabled():
        return None

    cache = get_cache()
    key = _compute_key(stage, model, prompt, params)
    return cache.get(key)


def cache_set(
    stage: str, model: str, prompt: str, response: str, params: dict[str, Any] | None = None
) -> None:
    """Cache a response by computed key."""
    if not _get_cache_enabled():
        return

    cache = get_cache()
    key = _compute_key(stage, model, prompt, params)
    cache.set(key, response)


def cache_clear() -> int:
    """Clear all cache entries. Returns count cleared."""
    cache = get_cache()
    return cache.clear()


def cache_stats() -> dict[str, Any]:
    """Return cache statistics."""
    cache = get_cache()
    return cache.stats()


def cache_compact() -> int:
    """Remove expired entries and dedupe. Returns count removed."""
    cache = get_cache()
    return cache.compact()
