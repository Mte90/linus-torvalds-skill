"""
extract.py — LLM extraction: email → review moves.

Calls an OpenAI-compatible chat completions endpoint.
One email per call. Returns structured JSON.

The prompt asks the LLM to extract "review moves":
  trigger  — what in the code/patch prompted the response
  principle — the general reviewing rule (language-agnostic)
  response  — how Torvalds phrases it (tone/voice preserved)
  severity  — reject | request-changes | nitpick | approve | discussion
  category  — one of the CATEGORIES from models.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config
from .audit import log_decision
from .models import EmailRecord

# Logger setup - idempotent (safe to call multiple times)
_LOGGER = logging.getLogger("torvalds_skill.extract")
_HANDLER = None

# Severity consistency validation word lists (extensible, case-insensitive)
HARD_LANGUAGE_INDICATORS = [
    "broken",
    "crash",
    "wrong",
    "incorrect",
    "bug",
    "error",
    "fail",
    "must",
    "should not",
    "cannot",
    "never",
    "always",
    "immediately",
    "critical",
    "fatal",
]

SOFT_LANGUAGE_INDICATORS = [
    "consider",
    "might",
    "could",
    "maybe",
    "perhaps",
    "nice to",
    "would be",
    "suggest",
    "optional",
    "minor",
    "cosmetic",
    "style",
]

# Severities that require hard language
STRICT_SEVERITIES = {"reject", "request-changes"}
# Severities that should not have hard language
LENIENT_SEVERITIES = {"nitpick"}


# Cache configuration - read at runtime, not import time
def _get_cache_enabled():
    """Check if cache is enabled."""
    return os.environ.get("EXTRACT_CACHE", "1") != "0"


def _get_cache_path():
    """Get cache path from environment."""
    return os.environ.get("EXTRACT_CACHE_PATH", "data/extract_cache.jsonl")


# Thread lock for cache access
_CACHE_LOCK = threading.Lock()
_CACHE_DATA: dict[str, dict] | None = None


def _get_logger():
    """Get logger with file handler, idempotent."""
    global _HANDLER
    if _HANDLER is None:
        Path("data").mkdir(parents=True, exist_ok=True)
        _HANDLER = logging.FileHandler("data/extract_errors.log")
        _HANDLER.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        _LOGGER.addHandler(_HANDLER)
        _LOGGER.setLevel(logging.ERROR)
    return _LOGGER


SYSTEM_PROMPT = """\
You are analyzing an email from Linus Torvalds on the Linux kernel mailing list.

Your job: extract the "review moves" — the actionable reviewing principles expressed in this email.

A review move has five fields:
- trigger: what in the code, patch, or proposal prompted this response (specific, concrete)
- principle: the general reviewing rule being applied (abstract it away from C/kernel specifics — make it language-agnostic so it applies to any code review)
- response: how Torvalds phrases his feedback (use his actual words where possible — the tone IS the signal)
- severity: one of "reject", "request-changes", "nitpick", "approve", "discussion"
- category: one of: api-stability, performance, correctness, complexity, style, process, error-handling, concurrency, memory-safety, abstraction, testing, documentation, other

Rules:
- One email may contain zero, one, or many review moves.
- If the email has no review content (e.g. it's a merge confirmation, a scheduling note, or pure discussion with no reviewing principle), return an empty moves array.
- The principle MUST be abstracted away from C/kernel specifics. "Don't change a public struct without updating callers" becomes "Don't change a public interface without updating all callers".
- Keep the response field in Torvalds' own words — do not paraphrase the tone away.
- Be conservative: only extract a move if there is a clear, identifiable reviewing principle.

Return ONLY valid JSON, no markdown fences, in this exact format:
{"moves": [{"trigger": "...", "principle": "...", "response": "...", "severity": "...", "category": "..."}]}"""
# Add after line 101 (after SYSTEM_PROMPT)
BATCH_SYSTEM_PROMPT = """\
You are analyzing emails from Linus Torvalds on the Linux kernel mailing list.

Your job: extract the "review moves" — the actionable reviewing principles expressed in EACH email.

A review move has five fields:
- trigger: what in the code, patch, or proposal prompted this response (specific, concrete)
- principle: the general reviewing rule being applied (abstract it away from C/kernel specifics — make it language-agnostic so it applies to any code review)
- response: how Torvalds phrases his feedback (use his actual words where possible — the tone IS the signal)
- severity: one of "reject", "request-changes", "nitpick", "approve", "discussion"
- category: one of: api-stability, performance, correctness, complexity, style, process, error-handling, concurrency, memory-safety, abstraction, testing, documentation, other

Rules:
- You will receive {batch_size} emails. For EACH email, extract the review moves.
- Return a JSON array with one object per email, in the same order as the input.
- Each object must have the same structure as a single-email extraction: {{"moves": [...]}}
- If an email has no review moves, return an empty moves array for that email.
- One email may contain zero, one, or many review moves.
- If an email has no review content (e.g. it's a merge confirmation, a scheduling note, or pure discussion with no reviewing principle), return an empty moves array for that email.
- The principle MUST be abstracted away from C/kernel specifics.
- Keep the response field in Torvalds' own words — do not paraphrase the tone away.
- Be conservative: only extract a move if there is a clear, identifiable reviewing principle.

Return ONLY valid JSON, no markdown fences, in this exact format:
[{{"moves": [...]}}, {{"moves": [...]}}, ...]  // one object per email, in order"""


def _parse_batch_response(content: str, batch_size: int) -> list[dict]:
    """Parse JSON array response from batched LLM call.

    Args:
        content: Raw LLM response text (may include markdown fences)
        batch_size: Expected number of emails in the batch

    Returns:
        List of parsed dicts, one per email

    Raises:
        json.JSONDecodeError: If response is not valid JSON
        ValueError: If array length doesn't match batch_size
    """
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    text = text.strip()

    parsed = json.loads(text)

    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")

    if len(parsed) != batch_size:
        raise ValueError(f"Expected {batch_size} results, got {len(parsed)}")

    return parsed


def _get_cache_logger():
    """Get logger for cache operations."""
    logger = logging.getLogger("torvalds_skill.extract.cache")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def _compute_cache_key(model_name: str, prompt_text: str) -> str:
    """Compute SHA-256 cache key from model name and prompt text."""
    return hashlib.sha256(f"{model_name}:{prompt_text}".encode()).hexdigest()


def _load_cache() -> dict[str, dict]:
    """Load cache from JSONL file into memory. Returns empty dict if file doesn't exist or is empty."""
    global _CACHE_DATA
    if _CACHE_DATA is not None:
        return _CACHE_DATA

    cache = {}
    cache_path = Path(_get_cache_path())

    if not cache_path.exists():
        _CACHE_DATA = cache
        return cache

    try:
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    key = entry.get("key")
                    if key:
                        cache[key] = entry
                except json.JSONDecodeError:
                    # Skip corrupt lines silently
                    continue
    except OSError:
        # If we can't read the file, start with empty cache
        pass

    _CACHE_DATA = cache
    return cache


def _save_cache_entry(key: str, response: str):
    """Append a cache entry to the JSONL file. Thread-safe."""
    cache_path = Path(_get_cache_path())
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "key": key,
        "response": response,
        "ts": int(time.time()),
    }

    with _CACHE_LOCK:
        with open(cache_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Update in-memory cache
        if _CACHE_DATA is not None:
            _CACHE_DATA[key] = entry


def _get_cached_response(key: str) -> str | None:
    """Get cached response by key. Returns None if not found."""
    with _CACHE_LOCK:
        cache = _load_cache()
        entry = cache.get(key)
        if entry:
            return entry.get("response")
    return None


def _call_llm(email: EmailRecord, retries: int = None) -> dict:
    """Call the LLM API for one email. Returns parsed JSON dict."""
    retries = retries if retries is not None else config.MAX_RETRIES

    user_content = f"Subject: {email.subject}\nDate: {email.date}\n\n{email.body[:8000]}"

    prompt_hash = hashlib.sha256((SYSTEM_PROMPT + user_content).encode("utf-8")).hexdigest()

    log_decision(
        "extract",
        model=config.MODEL,
        prompt_hash=prompt_hash,
        params={"temperature": 0.1, "retries": retries},
        truncation_handling=len(email.body) > 8000,
    )

    payload = {
        "model": config.MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.CHAT_URL,
        data=body,
        headers=config.headers(),
        method="POST",
    )

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_json_response(content)
                # Store raw content on the parsed result for caching
                parsed["_raw_content"] = content
                return parsed
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = config.RETRY_DELAY * (attempt + 1) * 2 + random.uniform(
                    0, config.RETRY_DELAY
                )
                time.sleep(wait)
            elif e.code >= 500:
                time.sleep(
                    config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY)
                )
            else:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            time.sleep(config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY))
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            last_err = e
            time.sleep(config.RETRY_DELAY)

    raise RuntimeError(f"LLM call failed after {retries} retries: {last_err}")


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    text = text.strip()
    return json.loads(text)


def _validate_severity_consistency(move: dict) -> tuple[bool, str]:
    """Validate that move severity matches the language intensity in description/trigger.

    Args:
        move: A move dict with at least 'severity' and 'description' (or 'trigger') keys.

    Returns:
        (is_consistent, reason) where reason is empty string if consistent.

    Logic:
        - If severity is "reject" or "request-changes" and description contains ONLY
          soft language (no hard language) → inconsistent
        - If severity is "nitpick" and description contains hard language (but no soft
          language) → inconsistent
        - Otherwise → consistent
    """
    severity = move.get("severity", "").lower()
    # Check both description and trigger fields
    description = move.get("description", "") or ""
    trigger = move.get("trigger", "") or ""
    text = (description + " " + trigger).lower()

    # Detect hard and soft language (case-insensitive, word boundary matching)
    has_hard_language = any(
        re.search(r"\b" + re.escape(phrase) + r"\b", text) for phrase in HARD_LANGUAGE_INDICATORS
    )
    has_soft_language = any(
        re.search(r"\b" + re.escape(phrase) + r"\b", text) for phrase in SOFT_LANGUAGE_INDICATORS
    )

    # Check for inconsistency
    if severity in STRICT_SEVERITIES:
        # Reject/request-changes should have hard language, not just soft
        if not has_hard_language and has_soft_language:
            return False, f"severity '{severity}' uses only soft language"
    elif severity in LENIENT_SEVERITIES:
        # Nitpick should not have hard language without soft language
        if has_hard_language and not has_soft_language:
            return False, f"severity '{severity}' uses hard language"

    return True, ""


def extract_moves(email: EmailRecord) -> dict:
    """Extract review moves from one email. Returns a dict with moves list."""
    # Input validation
    logger = _get_logger()

    # Stats tracking for severity warnings
    severity_warnings = 0

    # Check required fields exist and are non-empty strings
    if not email.body or not isinstance(email.body, str) or not email.body.strip():
        msg = "missing or empty body"
        logger.warning("Validation failed for %s: %s", getattr(email, "message_id", "unknown"), msg)
        return {
            "email_message_id": getattr(email, "message_id", "unknown"),
            "moves": [],
            "error": f"validation_failed: {msg}",
        }

    if (
        not email.message_id
        or not isinstance(email.message_id, str)
        or not email.message_id.strip()
    ):
        msg = "missing or empty message_id"
        logger.warning("Validation failed for %s: %s", getattr(email, "message_id", "unknown"), msg)
        return {
            "email_message_id": getattr(email, "message_id", "unknown"),
            "moves": [],
            "error": f"validation_failed: {msg}",
        }

    if not email.subject or not isinstance(email.subject, str) or not email.subject.strip():
        msg = "missing or empty subject"
        logger.warning("Validation failed for %s: %s", getattr(email, "message_id", "unknown"), msg)
        return {
            "email_message_id": getattr(email, "message_id", "unknown"),
            "moves": [],
            "error": f"validation_failed: {msg}",
        }

    if not email.from_name or not isinstance(email.from_name, str) or not email.from_name.strip():
        msg = "missing or empty from_name"
        logger.warning("Validation failed for %s: %s", getattr(email, "message_id", "unknown"), msg)
        return {
            "email_message_id": getattr(email, "message_id", "unknown"),
            "moves": [],
            "error": f"validation_failed: {msg}",
        }

    # Body length warnings (don't block extraction)
    body_len = len(email.body)
    if body_len <= 10:
        logger.warning("Very short body (%d chars) for message %s", body_len, email.message_id)
    elif body_len > 100000:
        logger.warning("Very long body (%d chars) for message %s", body_len, email.message_id)

    # Build user content for cache key computation
    user_content = f"Subject: {email.subject}\nDate: {email.date}\n\n{email.body[:8000]}"
    prompt_text = SYSTEM_PROMPT + user_content
    cache_key = _compute_cache_key(config.MODEL, prompt_text)

    # Check cache before calling LLM
    if _get_cache_enabled():
        cached_response = _get_cached_response(cache_key)
        if cached_response is not None:
            try:
                parsed = _parse_json_response(cached_response)
                moves = parsed.get("moves", [])
                cache_logger = _get_cache_logger()
                cache_logger.info(f"cache hit: {email.message_id} ({len(moves)} moves)")
                return {
                    "email_message_id": email.message_id,
                    "email_date": email.date,
                    "email_subject": email.subject,
                    "moves": moves,
                    "cached": True,
                }
            except (json.JSONDecodeError, KeyError):
                # Corrupt cache entry, fall through to LLM call
                pass

    try:
        result = _call_llm(email)
        moves = result.get("moves", [])

        # Validate severity consistency for each move
        for move in moves:
            is_consistent, reason = _validate_severity_consistency(move)
            if not is_consistent:
                severity_warnings += 1
                move_id = move.get("trigger", "unknown")[:50]
                logger.warning("Severity inconsistency detected for move '%s': %s", move_id, reason)

        # Cache all successful responses (including 0-move valid responses)
        if _get_cache_enabled():
            raw_response = result.get("_raw_content")
            if raw_response:
                _save_cache_entry(cache_key, raw_response)

        return {
            "email_message_id": email.message_id,
            "email_date": email.date,
            "email_subject": email.subject,
            "moves": moves,
            "severity_warnings": severity_warnings,
        }
    except Exception as e:
        logger = _get_logger()
        message_id = email.message_id or email.subject or "unknown"
        logger.error(
            "Extraction failed for %s: %s: %s",
            message_id,
            type(e).__name__,
            str(e),
        )
        return {
            "email_message_id": email.message_id,
            "email_date": email.date,
            "email_subject": email.subject,
            "moves": [],
            "error": str(e),
            "severity_warnings": severity_warnings,
        }


def extract_batch(emails, output_path, append=False, batch_size=1, batch_retry=True):
    """Extract moves from a batch of emails, writing to JSONL.

    Args:
        emails: List of email records to process
        output_path: Path to output JSONL file
        append: If True, append to existing file; otherwise overwrite
        batch_size: Number of emails per LLM call (1 = sequential)
        batch_retry: If True, retry failed batches with individual emails
    """
    mode = "a" if append else "w"
    total = len(emails)
    done = 0
    errors = 0
    moves_count = 0

    # Use batch extraction if batch_size > 1
    if batch_size > 1:
        results = extract_moves_batch(emails, batch_size, batch_retry)
    else:
        # Sequential extraction (original behavior)
        results = [extract_moves(email) for email in emails]

    with open(output_path, mode, encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
            done += 1
            if result.get("error"):
                errors += 1
            else:
                moves_count += len(result.get("moves", []))

            if done % 100 == 0:
                print(f"  {done}/{total} — {moves_count} moves, {errors} errors")

    print(f"done: {done} emails, {moves_count} moves, {errors} errors")
    return {"processed": done, "moves": moves_count, "errors": errors}


def _call_llm_batch(emails, batch_size, retries=None):
    """Call the LLM API for a batch of emails. Returns list of parsed JSON dicts."""
    retries = retries if retries is not None else config.MAX_RETRIES

    # Build batch user content
    batch_content = ""
    for i, email in enumerate(emails):
        batch_content += (
            f"\n\n=== EMAIL {i + 1}/{batch_size} ===\n"
            f"Subject: {email.subject}\n"
            f"Date: {email.date}\n\n"
            f"{email.body[:8000]}\n"
        )

    prompt_text = BATCH_SYSTEM_PROMPT.format(batch_size=batch_size) + batch_content
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    log_decision(
        "extract_batch",
        model=config.MODEL,
        prompt_hash=prompt_hash,
        params={"temperature": 0.1, "batch_size": batch_size, "retries": retries},
        truncation_handling=any(len(e.body) > 8000 for e in emails),
    )

    payload = {
        "model": config.MODEL,
        "messages": [
            {"role": "system", "content": BATCH_SYSTEM_PROMPT.format(batch_size=batch_size)},
            {"role": "user", "content": batch_content},
        ],
        "temperature": 0.1,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.CHAT_URL,
        data=body,
        headers=config.headers(),
        method="POST",
    )

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_batch_response(content, batch_size)
                # Store raw content on each result for caching
                for result in parsed:
                    result["_raw_content"] = content
                return parsed
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = config.RETRY_DELAY * (attempt + 1) * 2 + random.uniform(
                    0, config.RETRY_DELAY
                )
                time.sleep(wait)
            elif e.code >= 500:
                time.sleep(
                    config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY)
                )
            else:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            time.sleep(config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY))
        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
            # Parse errors or batch length mismatch
            last_err = e
            time.sleep(config.RETRY_DELAY)

    raise RuntimeError(f"LLM batch call failed after {retries} retries: {last_err}")


def extract_moves_batch(emails, batch_size=1, batch_retry=True):
    """Extract moves from a batch of emails with optional batching and retry.

    Args:
        emails: List of email records to process
        batch_size: Number of emails per LLM call (1 = sequential)
        batch_retry: If True, retry failed batches with individual emails

    Returns:
        List of extraction results, one per email
    """
    results = []
    total = len(emails)

    # Process emails in batches
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_emails = emails[batch_start:batch_end]
        actual_batch_size = len(batch_emails)

        # If batch_size is 1, use sequential extraction
        if actual_batch_size == 1:
            result = extract_moves(batch_emails[0])
            results.append(result)
            continue

        # Try batch extraction
        try:
            batch_results = _call_llm_batch(batch_emails, actual_batch_size)

            # Convert batch results to individual result format
            for i, email in enumerate(batch_emails):
                batch_result = batch_results[i]
                moves = batch_result.get("moves", [])

                # Validate severity consistency
                severity_warnings = 0
                for move in moves:
                    is_consistent, reason = _validate_severity_consistency(move)
                    if not is_consistent:
                        severity_warnings += 1

                result = {
                    "email_message_id": email.message_id,
                    "email_date": email.date,
                    "email_subject": email.subject,
                    "moves": moves,
                    "severity_warnings": severity_warnings,
                    "cached": False,
                }
                results.append(result)

        except (json.JSONDecodeError, ValueError, RuntimeError) as e:
            # Batch failed
            logger = _get_logger()
            logger.warning(
                "Batch extraction failed for %d emails: %s. %s.",
                actual_batch_size,
                type(e).__name__,
                str(e),
            )

            if batch_retry:
                # Fall back to sequential extraction for failed batch
                logger.info("Retrying %d emails sequentially...", actual_batch_size)
                for email in batch_emails:
                    result = extract_moves(email)
                    results.append(result)
            else:
                # Return error results for all emails in batch
                for email in batch_emails:
                    results.append(
                        {
                            "email_message_id": email.message_id,
                            "email_date": email.date,
                            "email_subject": email.subject,
                            "moves": [],
                            "error": f"batch_failed: {str(e)}",
                            "severity_warnings": 0,
                        }
                    )

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract review moves from emails using LLM")
    parser.add_argument(
        "--input",
        default="data/corpus.jsonl",
        help="Input file path (mbox or jsonl) (default: data/corpus.jsonl)",
    )
    parser.add_argument(
        "--output",
        default="data/moves.jsonl",
        help="Output JSONL file path (default: data/moves.jsonl)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Number of emails per LLM call (default: 1 = sequential)",
    )
    parser.add_argument(
        "--batch-retry",
        action="store_true",
        default=True,
        help="Retry failed batches with individual emails (default: True)",
    )
    parser.add_argument(
        "--no-batch-retry", action="store_true", help="Disable retry for failed batches"
    )
    parser.add_argument(
        "--append", action="store_true", help="Append to output file instead of overwriting"
    )

    args = parser.parse_args()

    # Read emails from input file
    input_file = Path(args.input)

    if input_file.suffix == ".jsonl":
        emails = []
        with open(input_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    email = EmailRecord(
                        message_id=d["message_id"],
                        from_name=d.get("from_name", ""),
                        from_email=d.get("from_email", ""),
                        date=d.get("date", ""),
                        subject=d.get("subject", ""),
                        in_reply_to=d.get("in_reply_to"),
                        body=d.get("body", ""),
                        to=d.get("to", ""),
                        cc=d.get("cc", ""),
                    )
                    emails.append(email)
                except (json.JSONDecodeError, KeyError):
                    continue
    else:
        import mailbox

        mbox = mailbox.mbox(input_file)
        emails = []
        for msg in mbox:
            message_id = msg.get("Message-ID", "")
            if not message_id:
                continue

            subject = msg.get("Subject", "")
            date = msg.get("Date", "")
            body = str(msg.get_payload(decode=True), errors="ignore")

            email = EmailRecord(
                message_id=message_id,
                from_name="",
                from_email=msg.get("From", ""),
                date=date,
                subject=subject,
                in_reply_to=msg.get("In-Reply-To"),
                body=body,
                to=msg.get("To", ""),
                cc=msg.get("Cc", ""),
            )
            emails.append(email)

    print(f"Loaded {len(emails)} emails from {args.input}")

    # Disable batch retry if --no-batch-retry is specified
    batch_retry = args.batch_retry and not args.no_batch_retry

    # Extract moves
    extract_batch(
        emails,
        args.output,
        append=args.append,
        batch_size=args.batch_size,
        batch_retry=batch_retry,
    )
