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

import json
import random
import time
import urllib.request
import urllib.error

from . import config
from .models import EmailRecord, ReviewMove

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


def _call_llm(email: EmailRecord, retries: int = None) -> dict:
    """Call the LLM API for one email. Returns parsed JSON dict."""
    retries = retries if retries is not None else config.MAX_RETRIES

    user_content = (
        f"Subject: {email.subject}\n"
        f"Date: {email.date}\n\n"
        f"{email.body[:8000]}"
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
                return _parse_json_response(content)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = config.RETRY_DELAY * (attempt + 1) * 2 + random.uniform(0, config.RETRY_DELAY)
                time.sleep(wait)
            elif e.code >= 500:
                time.sleep(config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY))
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


def extract_moves(email: EmailRecord) -> dict:
    """Extract review moves from one email. Returns a dict with moves list."""
    try:
        result = _call_llm(email)
        moves = result.get("moves", [])
        return {
            "email_message_id": email.message_id,
            "email_date": email.date,
            "email_subject": email.subject,
            "moves": moves,
        }
    except Exception as e:
        return {
            "email_message_id": email.message_id,
            "email_date": email.date,
            "email_subject": email.subject,
            "moves": [],
            "error": str(e),
        }


def extract_batch(emails, output_path, append=False):
    """Extract moves from a batch of emails, writing to JSONL."""
    mode = "a" if append else "w"
    total = len(emails)
    done = 0
    errors = 0
    moves_count = 0

    with open(output_path, mode, encoding="utf-8") as f:
        for email in emails:
            result = extract_moves(email)
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
