"""
LLM API interaction logic for the distillation process.

Contains functions for calling the LLM, detecting truncation, and patching
truncated outputs.
"""

import json
import time
import urllib.request
import urllib.error
import http.client
import sys
import threading
import hashlib
import os
from collections import OrderedDict
from pathlib import Path

from . import config
from .distill_prompts import DISTILL_SYSTEM_PROMPT


# Thread-safe in-memory cache with LRU eviction
_cache_lock = threading.Lock()


class _DiskCache:
    """Disk-backed LLM cache with TTL support.
    
    Stores entries in JSONL format: {"key": "<sha256>", "model": "...", "response": "...", "ts": <unix epoch>}
    Lazy loads the entire file into memory on first access, then keeps in sync with appends.
    """
    
    def __init__(self):
        self._cache_path = Path(config.LLM_CACHE_PATH)
        self._ttl_hours = config.LLM_CACHE_TTL_HOURS
        self._cache: dict[str, dict] = {}  # key -> {model, response, ts}
        self._loaded = False
        self._lock = threading.Lock()
    
    def _load(self):
        """Load cache from disk. Called once per process."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._cache.clear()
            if not self._cache_path.exists():
                self._loaded = True
                return
            
            # Read file line by line, skip corrupt last line
            with open(self._cache_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if all(k in entry for k in ('key', 'model', 'response', 'ts')):
                            self._cache[entry['key']] = {
                                'model': entry['model'],
                                'response': entry['response'],
                                'ts': entry['ts']
                            }
                    except json.JSONDecodeError:
                        # Skip corrupt lines (including partial last line)
                        continue
            self._loaded = True
    
    def get(self, key: str) -> tuple[str, str] | None:
        """Get cached entry if not expired. Returns (model, response) or None."""
        if self._ttl_hours <= 0:
            return None
        self._load()
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            # Check TTL
            if time.time() - entry['ts'] > self._ttl_hours * 3600:
                return None
            return (entry['model'], entry['response'])
    
    def set(self, key: str, model: str, response: str):
        """Append entry to disk cache and update in-memory cache."""
        if self._ttl_hours <= 0:
            return
        self._load()
        with self._lock:
            # Update in-memory cache
            self._cache[key] = {'model': model, 'response': response, 'ts': time.time()}
            # Append to disk (create parent dirs if needed)
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'key': key, 'model': model, 'response': response, 'ts': time.time()}) + '\n')
    
    def clear_expired(self):
        """Remove expired entries from in-memory cache."""
        if self._ttl_hours <= 0:
            return
        with self._lock:
            now = time.time()
            cutoff = now - self._ttl_hours * 3600
            self._cache = {k: v for k, v in self._cache.items() if v['ts'] > cutoff}


# Global disk cache instance
_disk_cache = _DiskCache()


class _WallClockTimeout:
    """Context manager enforcing a wall-clock timeout via a watchdog thread.

    Unlike signal.SIGALRM, this works even when the main thread is blocked
    inside C-level ssl.read() or urllib operations.
    """

    def __init__(self, seconds: int):
        self._seconds = seconds
        self._timer = None
        self._timed_out = False
        self._exc = None

    def _fire(self):
        self._timed_out = True
        self._exc = TimeoutError("wall-clock timeout exceeded")

    def __enter__(self):
        self._timer = threading.Timer(self._seconds, self._fire)
        self._timer.daemon = True
        self._timer.start()
        return self

    def __exit__(self, *exc_info):
        if self._timer is not None:
            self._timer.cancel()
        if self._timed_out:
            raise self._exc
        return False


def _detect_truncation(text: str, model: str) -> bool:
    """Detect if LLM output is truncated mid-sentence or mid-section.

    Returns True if the output appears incomplete:
    - Ends without proper closing (no terminal punctuation, no code fence close)
    - Token count is suspiciously low (< 500 for skill, < 800 for soul)
    - For GLM5.2: also checks for mid-word endings
    - Incomplete YAML frontmatter (starts with --- but no closing ---)
    - Incomplete markdown sections (last ## heading has no content after it)
    - Missing required skill sections (Reviewer Mindset, Review Triggers, Severity Decision Tree)
    - Cut-off sentences (ends mid-sentence with no period, no list item, no heading)
    """
    if not text or not text.strip():
        return True

    stripped = text.strip()
    
    # Check token count threshold
    # Rough estimate: 1 token ≈ 4 characters
    token_count = len(stripped) / 4
    is_skill = "skill" in model.lower() or "distill" in model.lower()
    is_soul = "soul" in model.lower()
    
    min_tokens = 500 if is_skill else (800 if is_soul else 500)
    if token_count < min_tokens:
        return True

    # Check for incomplete YAML frontmatter
    if stripped.startswith("---"):
        lines = stripped.split("\n")
        closing_count = sum(1 for line in lines if line.strip() == "---")
        if closing_count < 2:
            return True  # YAML frontmatter started but not closed
    
    # Check for incomplete markdown sections (last ## heading has no content)
    heading_positions = []
    for i, line in enumerate(stripped.split("\n")):
        if line.strip().startswith("## "):
            heading_positions.append(i)
    
    if len(heading_positions) >= 2:
        # Check if the last ## heading has content after it
        last_heading_line = heading_positions[-1]
        lines = stripped.split("\n")
        content_after_last_heading = "\n".join(lines[last_heading_line + 1:]).strip()
        # If no content or only whitespace after last heading, it's truncated
        if not content_after_last_heading or content_after_last_heading.startswith("## "):
            return True
    
    # Check for missing required skill sections
    required_sections = [
        "Reviewer Mindset",
        "Review Triggers", 
        "Severity Decision Tree"
    ]
    if is_skill:
        found_sections = sum(1 for section in required_sections if section in stripped)
        if found_sections < 1:
            return True  # At least one required section must be present
    
    # Check for cut-off sentences (ends mid-sentence)
    # Ends without period, not a list item, not a heading
    if stripped and not stripped.endswith((".", "!", "?", ")", "]", "`", "```", "---", "##", "#")):
        # Check if it ends mid-word or mid-sentence
        last_chars = stripped[-20:] if len(stripped) >= 20 else stripped
        # If ends with lowercase letter and no punctuation, likely cut off
        if last_chars and last_chars[-1].islower() and not any(c in last_chars[-5:] for c in ".!?"):
            return True

    # For GLM5.2, be stricter — must end with punctuation or code fence or section marker
    if "glm" in model.lower():
        if (stripped.endswith(".") or stripped.endswith("!") or 
            stripped.endswith("?") or stripped.endswith("```") or
            stripped.endswith("---") or stripped.endswith("##") or
            stripped.endswith("#")):
            return False  # Proper ending
        # Doesn't end properly for GLM
        return True
    
    # General check for other models
    proper_endings = (".", "!", "?", "```", "---", "##", "#")
    if any(stripped.endswith(ending) for ending in proper_endings):
        return False
    
    # Check if it ends mid-sentence (last word has no punctuation)
    words = stripped.split()
    if words:
        last_word = words[-1]
        # If last word doesn't end with punctuation and isn't a code element
        if not any(last_word.endswith(p) for p in (".", "!", "?", ")", "]", "`")):
            return True
    
    return False


def _patch_truncated_section(primary_text: str, fallback_text: str) -> str:
    """Merge truncated primary output with fallback tail.

    Finds the last complete section boundary in primary text, then appends
    everything after that point from the fallback output.
    """
    if not primary_text or not fallback_text:
        return fallback_text or primary_text or ""

    # Find section boundaries (markdown headers or --- separators)
    section_patterns = ["\n## ", "\n# ", "\n---", "\n### "]
    
    last_boundary_pos = 0
    for pattern in section_patterns:
        pos = primary_text.rfind(pattern)
        if pos > last_boundary_pos:
            last_boundary_pos = pos
    
    # If we found a boundary, extract the tail from fallback
    if last_boundary_pos > 0:
        # Get the section header from primary
        section_header = primary_text[last_boundary_pos:last_boundary_pos + 10].strip()
        
        # Find the same section in fallback
        fallback_section_pos = fallback_text.find(section_header)
        if fallback_section_pos != -1:
            # Check if fallback has more content after this section
            primary_tail = primary_text[last_boundary_pos:]
            fallback_tail = fallback_text[fallback_section_pos:]
            
            # If fallback is longer, append the difference
            if len(fallback_tail) > len(primary_tail):
                # Find where they diverge
                divergence = 0
                for i in range(min(len(primary_tail), len(fallback_tail))):
                    if primary_tail[i] != fallback_tail[i]:
                        divergence = i
                        break
                else:
                    divergence = len(primary_tail)
                
                # Append the missing part
                return primary_text[:last_boundary_pos + divergence] + fallback_tail[divergence:]
    
    # No clear section match, just return fallback
    return fallback_text


# Thread-local connection pool: a single HTTPConnection is not safe for
# concurrent use from multiple threads (parallel category distillation),
# so each thread gets its own pooled connection per host.
_tls = threading.local()


def _get_connection(host: str) -> http.client.HTTPSConnection:
    """Get or create a reusable HTTPS connection for the given host.

    Connections are stored per-thread to keep parallel workers isolated.
    Handles connection errors by discarding stale connections and retrying once.
    """
    # Parse host to get just the hostname (strip protocol and port for key)
    host_key = host.replace('https://', '').replace('http://', '').split('/')[0]

    pool = getattr(_tls, 'connections', None)
    if pool is None:
        pool = {}
        _tls.connections = pool

    conn = pool.get(host_key)

    # Check if connection is still usable
    if conn is not None:
        try:
            # Try to use the connection
            if conn.sock is None or conn.sock._closed:
                conn.close()
                conn = None
        except Exception:
            conn = None

    if conn is None:
        # Create new connection. Scheme must come from config.CHAT_URL — the
        # caller passes parsed.netloc (no scheme), so checking the host string
        # for "https://" always fails and silently produces an HTTPConnection
        # on port 80 against the HTTPS-only API (gateway answers 302).
        from urllib.parse import urlparse as _urlparse
        use_tls = _urlparse(config.CHAT_URL).scheme != "http"
        timeout = config.READ_TIMEOUT
        if use_tls:
            conn = http.client.HTTPSConnection(host_key, timeout=timeout)
        else:
            conn = http.client.HTTPConnection(host_key, timeout=timeout)
        pool[host_key] = conn

    return conn


def _call_llm(prompt: str, retries: int = None, model: str = None, system_prompt: str = None, wall_clock_override: int = None) -> str:
    """Call the LLM for the distillation step. Returns raw text.

    Uses SSE streaming so reasoning models (e.g. GLM5.2) that spend minutes
    on internal reasoning don't hit read timeouts — each token delta keeps
    the connection alive.

    Implements fallback chain for GLM5.2 truncation:
    mistral-small-4-119b → gpt-oss-120b → glm5.2
    
    Caches successful responses by prompt+model+system_prompt hash (max 200 entries).
    Cache is bypassed when retries=1 (explicit fresh attempt).
    
    Uses disk-backed cache with 24h TTL and thread-safe access.
    Reuses HTTPS connections across calls to avoid TCP/TLS handshake overhead.
    """
    from . import config
    
    # Module-level cache: {hash: response}
    # Using OrderedDict for LRU eviction
    if not hasattr(_call_llm, '_cache'):
        _call_llm._cache = OrderedDict()
        _call_llm._max_size = 200
    
    retries = retries if retries is not None else config.MAX_RETRIES
    sys_prompt = system_prompt if system_prompt is not None else DISTILL_SYSTEM_PROMPT

    # Cache key: hash of prompt + model + system_prompt
    cache_key = None
    if retries != 1:  # Bypass cache when retries=1 (explicit fresh attempt)
        cache_input = f"{prompt}\x00{model}\x00{sys_prompt}"
        cache_key = hashlib.sha256(cache_input.encode('utf-8')).hexdigest()
        
        # Thread-safe in-memory cache check
        with _cache_lock:
            if cache_key in _call_llm._cache:
                _call_llm._cache.move_to_end(cache_key)  # LRU touch
                print(f"cache hit (memory) for prompt hash {cache_key[:8]}...", file=sys.stderr)
                return _call_llm._cache[cache_key]
        
        # Check disk cache (thread-safe)
        disk_result = _disk_cache.get(cache_key)
        if disk_result is not None:
            disk_model, disk_response = disk_result
            # Load into memory cache
            with _cache_lock:
                if len(_call_llm._cache) >= _call_llm._max_size:
                    _call_llm._cache.popitem(last=False)
                _call_llm._cache[cache_key] = disk_response
                _call_llm._cache.move_to_end(cache_key)
            print(f"cache hit (disk) for prompt hash {cache_key[:8]}...", file=sys.stderr)
            return disk_response
        
        print(f"cache miss for prompt hash {cache_key[:8]}...", file=sys.stderr)
    
    # Fallback model chain for truncation recovery (exclude primary model to prevent self-fallback loops)
    all_fallback_models = ["mistral-small-4-119b", "gpt-oss-120b", "glm5.2"]
    primary_model = model or config.MODEL
    fallback_models = [m for m in all_fallback_models if m != primary_model]
    
    # Try primary model first, then fallbacks if truncation detected
    models_to_try = [primary_model]
    if primary_model not in fallback_models:
        models_to_try.extend(fallback_models)
    
    last_err = None
    primary_result = None
    
    for call_model in models_to_try:
        is_glm = "glm" in call_model.lower()
        
        payload = {
            "model": call_model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 16000,
            "stream": True,
        }
        
        # Per-read timeout: catches dead connections (no bytes for 120s).
        read_timeout = config.READ_TIMEOUT
        # Wall-clock timeout: catches keepalive-stalled SSE streams where
        # bytes arrive but no content is produced (GLM5.2 reasoning stalls).
        # Use wall_clock_override if provided (for per-category distill), otherwise compute from model/prompt
        wall_clock = wall_clock_override if wall_clock_override is not None else (config.WALL_CLOCK_GLM if is_glm else (config.WALL_CLOCK_LONG if len(prompt) > 50_000 else config.WALL_CLOCK_DEFAULT))
        model_retries = retries
        
        for attempt in range(model_retries):
            try:
                body = json.dumps(payload).encode("utf-8")
                
                # Use connection pooling - reuse HTTPS connection
                # Parse host from CHAT_URL
                from urllib.parse import urlparse
                parsed = urlparse(config.CHAT_URL)
                host = parsed.netloc
                path = parsed.path
                
                conn = _get_connection(host)
                
                content_parts = []
                with _WallClockTimeout(wall_clock):
                    # Send request using the pooled connection
                    conn.request("POST", path, body=body, headers=config.headers())
                    resp = conn.getresponse()

                    # Raw http.client does NOT raise on 4xx/5xx (unlike urlopen):
                    # an error body iterated as SSE yields nothing -> silent
                    # empty_response. Check status explicitly.
                    if resp.status >= 400:
                        err_body = resp.read(2000).decode(errors="replace")
                        resp.close()
                        raise RuntimeError(f"HTTP {resp.status} {resp.reason}: {err_body}")

                    # Read SSE stream line by line (preserves streaming behavior).
                    # Reasoning models (GLM5.2) stream delta.reasoning_content before
                    # delta.content; capture both so the token budget spent on
                    # reasoning is not silently discarded when content never arrives.
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
                                content_parts.append(reasoning)

                    resp.close()
                
                result = "".join(content_parts)
                if not result.strip():
                    last_err = RuntimeError("empty_response")
                    break
                
                # Check for truncation
                if _detect_truncation(result, call_model):
                    print(f"warning: truncation detected with {call_model}, returning partial result", file=sys.stderr)
                    # Return partial result immediately — don't retry same prompt with different model
                    # (same prompt → same truncation → wasted tokens)
                    # IMPORTANT: truncated responses are NOT cached to disk (they're model-specific failures)
                    if cache_key:
                        with _cache_lock:
                            if len(_call_llm._cache) >= _call_llm._max_size:
                                _call_llm._cache.popitem(last=False)  # evict least-recently-used
                            _call_llm._cache[cache_key] = result
                    return result
                
                # Success - no truncation
                if call_model != primary_model:
                    print(f"info: fallback model {call_model} succeeded", file=sys.stderr)
                    # Try to patch if we have a primary result
                    if primary_result is not None:
                        patched = _patch_truncated_section(primary_result, result)
                        # Cache the patched result (thread-safe)
                        if cache_key:
                            with _cache_lock:
                                if len(_call_llm._cache) >= _call_llm._max_size:
                                    _call_llm._cache.popitem(last=False)  # evict least-recently-used
                                _call_llm._cache[cache_key] = patched
                                _call_llm._cache.move_to_end(cache_key)
                            # Write to disk cache (only non-truncated responses)
                            _disk_cache.set(cache_key, call_model, patched)
                        return patched
                # Cache the result (thread-safe)
                if cache_key:
                    with _cache_lock:
                        if len(_call_llm._cache) >= _call_llm._max_size:
                            _call_llm._cache.popitem(last=False)  # evict least-recently-used
                        _call_llm._cache[cache_key] = result
                        _call_llm._cache.move_to_end(cache_key)
                    # Write to disk cache (only non-truncated responses)
                    _disk_cache.set(cache_key, call_model, result)
                return result
                
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, 
          http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError) as e:
                last_err = e
                
                # Handle connection errors by discarding stale connection
                if isinstance(e, (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError)):
                    from urllib.parse import urlparse
                    parsed = urlparse(config.CHAT_URL)
                    host_key = parsed.netloc
                    pool = getattr(_tls, 'connections', None)
                    if pool and host_key in pool:
                        try:
                            pool[host_key].close()
                        except Exception:
                            pass
                        del pool[host_key]
                    # Retry once with fresh connection
                    if attempt < model_retries - 1:
                        print(f"warning: connection error, retrying with fresh connection", file=sys.stderr)
                        continue
                
                time.sleep(config.RETRY_DELAY * (attempt + 1))
    
    # All models failed or truncated
    if primary_result is not None:
        print("warning: all models truncated, returning primary result", file=sys.stderr)
        return primary_result
    
    raise RuntimeError(f"LLM distill failed after {retries} retries: {last_err}")
