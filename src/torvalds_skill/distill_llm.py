"""
LLM API interaction logic for the distillation process.

Contains functions for calling the LLM, detecting truncation, and patching
truncated outputs.
"""

import hashlib
import http.client
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict

from . import config
from .cache import cache_get, cache_set
from .distill_prompts import DISTILL_SYSTEM_PROMPT

# Thread-safe in-memory cache with LRU eviction
_cache_lock = threading.Lock()
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


def _detect_truncation(text: str, doc_type: str = "skill", strict: bool | None = None) -> bool:
    """Detect if LLM output is truncated mid-sentence or mid-section.

    Args:
        text: The LLM output text to check
        doc_type: Type of document being generated ("skill" or "soul")
        strict: If True, use stricter truncation detection (mid-word endings, reasoning-model rules).
                If None, inferred from doc_type (soul=True, skill=False).

    Returns True if the output appears incomplete:
    - Ends without proper closing (no terminal punctuation, no code fence close)
    - Token count is suspiciously low (< 500 for skill, < 800 for soul)
    - For strict mode: also checks for mid-word endings
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
    is_skill = doc_type == "skill"
    is_soul = doc_type == "soul"

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
        content_after_last_heading = "\n".join(lines[last_heading_line + 1 :]).strip()
        # If no content or only whitespace after last heading, it's truncated
        if not content_after_last_heading or content_after_last_heading.startswith("## "):
            return True

    # Check for missing required skill sections
    required_sections = ["Reviewer Mindset", "Review Triggers", "Severity Decision Tree"]
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

    # Strict mode: use stricter truncation detection (mid-word endings, reasoning-model rules).
    # If not explicitly set, infer from doc_type: soul=True, skill=False.
    if strict is None:
        strict = doc_type == "soul"

    if strict:
        proper_endings = (".", "!", "?", "```", "---", "##", "#", "*")
        if any(stripped.endswith(ending) for ending in proper_endings):
            return False  # Proper ending
        # Doesn't end properly for reasoning model
        return True

    # General check for other models
    proper_endings = (".", "!", "?", "```", "---", "##", "#", "*")
    if any(stripped.endswith(ending) for ending in proper_endings):
        return False

    # Check if it ends mid-sentence (last word has no punctuation)
    words = stripped.split()
    if words:
        last_word = words[-1]
        # If last word doesn't end with punctuation and isn't a code element
        if not any(last_word.endswith(p) for p in (".", "!", "?", ")", "]", "`", "*")):
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
        section_header = primary_text[last_boundary_pos : last_boundary_pos + 10].strip()

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
                return primary_text[: last_boundary_pos + divergence] + fallback_tail[divergence:]

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
    host_key = host.replace("https://", "").replace("http://", "").split("/")[0]

    pool = getattr(_tls, "connections", None)
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

    return conn  # type: ignore[return-value]


def _call_llm(
    prompt: str,
    retries: int | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    wall_clock_override: int | None = None,
    max_tokens_override: int | None = None,
    doc_type: str = "skill",
) -> str:
    """Call the LLM for the distillation step. Returns raw text.

    Uses SSE streaming so slow reasoning models that spend minutes
    on internal reasoning don't hit read timeouts — each token delta keeps
    the connection alive.

    Implements the profile fallback chain for reasoning-model truncation
    (see profile.fallback_models for the default order).

    Caches successful responses by prompt+model+system_prompt hash (max 200 entries).
    Cache is bypassed when retries=1 (explicit fresh attempt).

    Uses disk-backed cache with 24h TTL and thread-safe access.
    Reuses HTTPS connections across calls to avoid TCP/TLS handshake overhead.
    """
    from . import config

    # Module-level cache: {hash: response}
    # Using OrderedDict for LRU eviction
    if not hasattr(_call_llm, "_cache"):
        _call_llm._cache = OrderedDict()  # type: ignore[attr-defined]
        _call_llm._max_size = 200  # type: ignore[attr-defined]

    retries = retries if retries is not None else config.MAX_RETRIES
    sys_prompt = system_prompt if system_prompt is not None else DISTILL_SYSTEM_PROMPT

    # Cache key: hash of prompt + model + system_prompt
    cache_key = None
    if retries != 1:  # Bypass cache when retries=1 (explicit fresh attempt)
        cache_input = f"{prompt}\x00{model}\x00{sys_prompt}"
        cache_key = hashlib.sha256(cache_input.encode("utf-8")).hexdigest()

        # Thread-safe in-memory cache check
        with _cache_lock:
            cache = getattr(_call_llm, "_cache", None)  # type: ignore[attr-defined]
            if cache and cache_key in cache:
                cache.move_to_end(cache_key)  # LRU touch  # type: ignore[attr-defined]
                print(f"cache hit (memory) for prompt hash {cache_key[:8]}...", file=sys.stderr)
                return str(cache[cache_key])  # type: ignore[attr-defined, no-any-return]

        # Check disk cache (thread-safe)
        disk_result = cache_get("distill", model, prompt, {"system_prompt": sys_prompt})
        if disk_result is not None:
            disk_response = disk_result
            # Load into memory cache
            with _cache_lock:
                if len(_call_llm._cache) >= _call_llm._max_size:  # type: ignore[attr-defined]
                    _call_llm._cache.popitem(last=False)  # type: ignore[attr-defined]
                _call_llm._cache[cache_key] = disk_response  # type: ignore[attr-defined]
                _call_llm._cache.move_to_end(cache_key)  # type: ignore[attr-defined]
            print(f"cache hit (disk) for prompt hash {cache_key[:8]}...", file=sys.stderr)
            return disk_response

        print(f"cache miss for prompt hash {cache_key[:8]}...", file=sys.stderr)

    # Fallback model chain from profile (exclude primary model to prevent self-fallback loops)
    primary_model = model or config.MODEL
    from .profiles import get_profile

    primary_profile = get_profile(primary_model)
    fallback_models = [m for m in primary_profile.fallback_models if m != primary_model]

    # Try primary model first, then fallbacks if truncation detected
    models_to_try = [primary_model]
    if primary_model not in fallback_models:
        models_to_try.extend(fallback_models)

    last_err = None
    primary_result: str | None = None
    primary_truncated = False

    for call_model in models_to_try:
        # Get profile for this model to check if it's a reasoning model
        call_profile = get_profile(call_model)
        is_reasoning = call_profile.reasoning

        payload = {
            "model": call_model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": call_profile.max_tokens,  # Default from profile (16000 for all known models)
            "stream": True,
        }
        # Reasoning models must keep their thinking phase (user requirement):
        # never disable it. Instead, give them a larger token budget so
        # reasoning AND content both fit without truncation.
        # Supported max_tokens per model (from profiles.py):
        #   gpt-oss-120b: 16000, glm5.2: 16000, mistral-small-4-119b: 16000
        if is_reasoning:
            payload["max_tokens"] = call_profile.max_tokens
        # Caller can override max_tokens (e.g., soul generation needs more
        # tokens than the distill default to reach 8000+ words).
        if max_tokens_override is not None:
            payload["max_tokens"] = max_tokens_override

        # Per-read timeout: catches dead connections (no bytes for 120s).
        # Wall-clock timeout: catches keepalive-stalled SSE streams where
        # bytes arrive but no content is produced (reasoning model stalls).
        # Use wall_clock_override if provided (for per-category distill), otherwise compute from model/prompt
        wall_clock = (
            wall_clock_override
            if wall_clock_override is not None
            else (
                call_profile.review_timeout // 2
                if is_reasoning  # Approximate from profile
                else (config.WALL_CLOCK_LONG if len(prompt) > 50_000 else config.WALL_CLOCK_DEFAULT)
            )
        )
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
                reasoning_parts = []
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
                    # Reasoning models stream delta.reasoning_content during their
                    # thinking phase. Keep it SEPARATE from content: mixing it in
                    # prepends the entire chain-of-thought to the answer. It is
                    # used only as salvage when no content was produced at all.
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

                    resp.close()

                result = "".join(content_parts)
                if not result.strip() and reasoning_parts:
                    # Salvage guard: reasoning-only response indicates the model
                    # returned thinking without content. This is a warning condition
                    # — raise max_tokens and retry rather than saving raw thinking.
                    print(
                        "warning: reasoning-only response detected (no content produced). "
                        "This indicates the model returned chain-of-thought without answer. "
                        "Retry with increased max_tokens.",
                        file=sys.stderr,
                    )
                    # Signal to caller that this attempt should be retried
                    last_err = RuntimeError("reasoning_only_response")
                    continue
                if not result.strip():
                    last_err = RuntimeError("empty_response")
                    break
                if not result.strip():
                    last_err = RuntimeError("empty_response")
                    break

                # Check for truncation (doc_type="skill" for distill output, strict=False for skill)
                if _detect_truncation(
                    result, doc_type=doc_type, strict=call_profile.strict_truncation
                ):
                    # Policy: return partial result on truncation (don't retry with same prompt)
                    # Rationale: same prompt → same truncation → wasted tokens
                    # IMPORTANT: truncated responses are NOT cached to disk (they're model-specific failures)
                    if call_model == primary_model:
                        primary_result = result
                        primary_truncated = True
                    print(
                        f"warning: truncation detected with {call_model}, returning partial result",
                        file=sys.stderr,
                    )
                    if cache_key:
                        with _cache_lock:
                            if len(_call_llm._cache) >= _call_llm._max_size:  # type: ignore[attr-defined]
                                _call_llm._cache.popitem(last=False)  # type: ignore[attr-defined]  # evict least-recently-used
                            _call_llm._cache[cache_key] = result  # type: ignore[attr-defined]
                    return result

                # Success - no truncation
                if call_model != primary_model and primary_truncated:
                    print(
                        f"info: fallback model {call_model} succeeded, patching primary result",
                        file=sys.stderr,
                    )
                    # Patch fallback result with primary truncated output
                    patched: str = _patch_truncated_section(primary_result, result)  # type: ignore[arg-type]
                    # Cache the patched result (thread-safe)
                    if cache_key:
                        with _cache_lock:
                            if len(_call_llm._cache) >= _call_llm._max_size:  # type: ignore[attr-defined]
                                _call_llm._cache.popitem(last=False)  # type: ignore[attr-defined]  # evict least-recently-used
                            _call_llm._cache[cache_key] = patched  # type: ignore[attr-defined]
                            _call_llm._cache.move_to_end(cache_key)  # type: ignore[attr-defined]
                        # Write to disk cache (only non-truncated responses)
                        cache_set("distill", model, prompt, patched, {"system_prompt": sys_prompt})
                    return patched
                # Cache the result (thread-safe)
                if cache_key:
                    with _cache_lock:
                        if len(_call_llm._cache) >= _call_llm._max_size:  # type: ignore[attr-defined]
                            _call_llm._cache.popitem(last=False)  # type: ignore[attr-defined]  # evict least-recently-used
                        _call_llm._cache[cache_key] = result  # type: ignore[attr-defined]
                        _call_llm._cache.move_to_end(cache_key)  # type: ignore[attr-defined]
                    # Write to disk cache (only non-truncated responses)
                    cache_set("distill", model, prompt, result, {"system_prompt": sys_prompt})
                return result

            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                http.client.RemoteDisconnected,
                ConnectionResetError,
                BrokenPipeError,
            ) as e:
                last_err = e  # type: ignore[assignment]

                # Handle connection errors by discarding stale connection
                if isinstance(
                    e, (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError)
                ):
                    from urllib.parse import urlparse

                    parsed = urlparse(config.CHAT_URL)
                    host_key = parsed.netloc
                    pool = getattr(_tls, "connections", None)
                    if pool and host_key in pool:
                        try:
                            pool[host_key].close()
                        except Exception:
                            pass
                        del pool[host_key]
                    # Retry once with fresh connection
                    if attempt < model_retries - 1:
                        print(
                            "warning: connection error, retrying with fresh connection",
                            file=sys.stderr,
                        )
                        continue

                time.sleep(config.RETRY_DELAY * (attempt + 1))

    # All models failed or truncated
    if primary_result is not None:
        print("warning: all models truncated, returning primary result", file=sys.stderr)
        return primary_result

    raise RuntimeError(f"LLM distill failed after {retries} retries: {last_err}")
