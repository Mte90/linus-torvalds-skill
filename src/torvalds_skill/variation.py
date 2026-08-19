"""
variation.py — extract context signals from LKML emails.

Extracts 4 context dimensions:
- thread_phase (rule-based): initial_review | iteration_n | final_decision
- urgency (rule-based): release_blocker | routine | post_release
- stakes (LLM): high | medium | low
- risk (LLM): safety_critical | correctness | cosmetic

Output: data/variation.jsonl (joinable to moves.jsonl on email_message_id)
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

import click

from . import config
from .models import EmailRecord

# Output paths
VARIATION_OUTPUT = Path(__file__).resolve().parent.parent.parent / "data" / "variation.jsonl"
VARIATION_CHECKPOINT = Path(__file__).resolve().parent.parent.parent / "data" / "variation_checkpoint.jsonl"

# Finality signals in subject line
FINALITY_SIGNALS = re.compile(
    r"\b(applied|merged|rejected|acked|pulled)\b",
    re.IGNORECASE
)

# Urgency signals in subject line
URGENCY_SIGNALS = re.compile(
    r"(-rc|merge\s+window|release\s+blocker|critical\s+fix)",
    re.IGNORECASE
)


def detect_thread_phase(headers: dict, subject: str) -> str:
    """
    Detect thread phase from headers and subject (rule-based, no LLM).

    Returns:
        - "initial_review": no In-Reply-To header
        - "iteration_n": has In-Reply-To, no finality signals
        - "final_decision": subject contains finality signals
    """
    in_reply_to = headers.get("In-Reply-To", "").strip()

    # No In-Reply-To = initial review
    if not in_reply_to:
        return "initial_review"

    # Has In-Reply-To, check for finality signals
    if FINALITY_SIGNALS.search(subject):
        return "final_decision"

    return "iteration_n"


def detect_urgency(headers: dict, subject: str) -> str:
    """
    Detect urgency from headers and subject (rule-based, no LLM).

    Returns:
        - "release_blocker": Date in -rcN window OR subject has urgency signals
        - "post_release": Date after final release, before next -rc1
        - "routine": otherwise

    Note: Uses Subject line "-rc" signals as primary detector, not hardcoded
    release dates.
    """
    # Check subject for urgency signals first
    if URGENCY_SIGNALS.search(subject):
        return "release_blocker"

    # Check date for -rc patterns (if date contains version info)
    date_str = headers.get("Date", "")
    if re.search(r"-rc\d", date_str):
        return "release_blocker"

    return "routine"


def _call_llm(email: EmailRecord, retries: int = None) -> dict:
    """
    Call the LLM API for one email to extract stakes and risk.
    Returns parsed JSON dict with stakes and risk fields.
    """
    retries = retries if retries is not None else config.MAX_RETRIES

    # Truncate body to 2000 chars as per spec
    body_truncated = email.body[:2000]

    user_content = (
        f"Subject: {email.subject}\n"
        f"Email Body (truncated to 2000 chars):\n"
        f"{body_truncated}"
    )

    payload = {
        "model": config.MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are analyzing a code-review email to classify context signals.\n\n"
                    "Classify this email on two dimensions:\n\n"
                    "1. stakes (consequence of being wrong):\n"
                    "   - high: security breach, data loss, system crash, user-facing breakage\n"
                    "   - medium: performance degradation, API instability, non-critical breakage\n"
                    "   - low: style, naming, formatting, cosmetic\n\n"
                    "2. risk (type of risk the code poses):\n"
                    "   - safety_critical: can cause crashes, data corruption, undefined behavior\n"
                    "   - correctness: logic errors, wrong behavior\n"
                    "   - cosmetic: style, formatting, naming only\n\n"
                    "Return ONLY valid JSON, no markdown:\n"
                    '{"stakes": "high|medium|low", "risk": "safety_critical|correctness|cosmetic"}\n\n'
                    "Rules:\n"
                    "- Use ONLY the provided categories\n"
                    "- Base classification on the email body content\n"
                    "- If unclear, default to 'medium' stakes and 'correctness' risk"
                )
            },
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


def extract_stakes_risk(email: EmailRecord) -> dict:
    """
    Extract stakes and risk from one email using LLM.
    Returns a dict with stakes and risk fields.
    """
    try:
        result = _call_llm(email)
        return {
            "stakes": result.get("stakes", "medium"),
            "risk": result.get("risk", "correctness"),
        }
    except Exception as e:
        return {
            "stakes": "medium",
            "risk": "correctness",
            "error": str(e),
        }


def extract_variation(email: EmailRecord) -> dict:
    """
    Extract all context signals from one email.
    Returns a dict with all 4 fields.
    """
    # Rule-based fields (no LLM)
    headers = {
        "In-Reply-To": email.in_reply_to or "",
        "Date": email.date,
        "Subject": email.subject,
    }

    thread_phase = detect_thread_phase(headers, email.subject)
    urgency = detect_urgency(headers, email.subject)

    # LLM-extracted fields (body analysis)
    stakes_risk = extract_stakes_risk(email)

    return {
        "email_message_id": email.message_id,
        "thread_phase": thread_phase,
        "urgency": urgency,
        "stakes": stakes_risk["stakes"],
        "risk": stakes_risk["risk"],
    }


def load_checkpoint() -> set:
    """Load processed message IDs from checkpoint file."""
    if not VARIATION_CHECKPOINT.exists():
        return set()

    processed = set()
    with open(VARIATION_CHECKPOINT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    processed.add(record.get("email_message_id"))
                except json.JSONDecodeError:
                    continue
    return processed


def save_checkpoint(record: dict):
    """Save one record to checkpoint file (append mode)."""
    with open(VARIATION_CHECKPOINT, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def run_variation(mbox_path: str, resume: bool = False) -> dict:
    """
    Main extraction loop: read mbox, extract variations, write JSONL.

    Args:
        mbox_path: Path to the mbox file (mboxrd format)
        resume: If True, skip already processed emails

    Returns:
        Dict with processing stats
    """
    from email import message_from_file
    from email.header import decode_header

    mbox_path = Path(mbox_path)
    if not mbox_path.exists():
        raise FileNotFoundError(f"Mbox file not found: {mbox_path}")

    # Load checkpoint if resuming
    processed_ids = load_checkpoint() if resume else set()

    # Open output file
    output_exists = VARIATION_OUTPUT.exists()
    mode = "a" if (resume and output_exists) else "w"

    total = 0
    done = 0
    skipped_checkpoint = 0
    skipped_short = 0
    errors = 0

    # Read all emails from mbox
    with open(mbox_path, "r", encoding="utf-8", errors="replace") as f:
        emails = list(message_from_file(f, headersonly=False))

    total = len(emails)
    print(f"Found {total} emails in {mbox_path}")

    with open(VARIATION_OUTPUT, mode, encoding="utf-8") as out_f:
        for i, msg in enumerate(emails, 1):
            # Extract headers
            subject_raw = msg.get("Subject", "")
            date_raw = msg.get("Date", "")
            in_reply_to_raw = msg.get("In-Reply-To", "")

            # Decode headers
            def decode_header_value(raw: str) -> str:
                if not raw:
                    return ""
                decoded_parts = []
                for part, encoding in decode_header(raw):
                    if isinstance(part, bytes):
                        try:
                            decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
                        except (TypeError, LookupError):
                            decoded_parts.append(part.decode("utf-8", errors="replace"))
                    else:
                        decoded_parts.append(part)
                return "".join(decoded_parts)

            subject = decode_header_value(subject_raw).strip()
            date = decode_header_value(date_raw).strip()
            in_reply_to = decode_header_value(in_reply_to_raw).strip()

            # Extract body
            body_parts = []
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        try:
                            body_parts.append(part.get_payload(decode=True).decode("utf-8", errors="replace"))
                        except Exception:
                            continue
            else:
                try:
                    body_parts.append(msg.get_payload(decode=True).decode("utf-8", errors="replace"))
                except Exception:
                    pass

            body = "\n".join(body_parts).strip()

            # Get message ID
            message_id = msg.get("Message-ID", "").strip()
            if not message_id:
                continue

            # Skip if already processed (checkpoint)
            if message_id in processed_ids:
                skipped_checkpoint += 1
                continue

            # Skip short emails (<50 words)
            word_count = count_words(body)
            if word_count < 50:
                skipped_short += 1
                continue

            # Create EmailRecord for LLM call
            email_record = EmailRecord(
                message_id=message_id,
                from_name="",
                from_email="",
                date=date,
                subject=subject,
                in_reply_to=in_reply_to or None,
                body=body,
            )

            # Extract variation
            try:
                variation = extract_variation(email_record)
                out_f.write(json.dumps(variation, ensure_ascii=False) + "\n")
                out_f.flush()

                # Save to checkpoint
                save_checkpoint(variation)

                done += 1

                # Progress every 100 emails
                if done % 100 == 0:
                    print(f"  {done}/{total} — {errors} errors")

                # Checkpoint every 1000 emails (already saving each, but log progress)
                if done % 1000 == 0:
                    print(f"  Checkpoint saved at {done} emails")

            except Exception as e:
                errors += 1
                print(f"  Error processing email {i}: {e}")

    print(f"\nDone: {done} emails processed")
    print(f"  Skipped (checkpoint): {skipped_checkpoint}")
    print(f"  Skipped (<50 words): {skipped_short}")
    print(f"  Errors: {errors}")

    return {
        "processed": done,
        "skipped_checkpoint": skipped_checkpoint,
        "skipped_short": skipped_short,
        "errors": errors,
    }


@click.command()
@click.option(
    "--mbox",
    default="data/lkml.mbox",
    help="Path to the mbox file (default: data/lkml.mbox)"
)
@click.option(
    "--resume",
    is_flag=True,
    default=False,
    help="Resume from checkpoint, skipping already processed emails"
)
def main(mbox: str, resume: bool):
    """Extract context signals from LKML emails.

    Reads an mbox file and extracts 4 context dimensions for each email:
    - thread_phase: initial_review | iteration_n | final_decision
    - urgency: release_blocker | routine | post_release
    - stakes: high | medium | low
    - risk: safety_critical | correctness | cosmetic

    Output is written to data/variation.jsonl (one JSON object per line).
    """
    print(f"Starting variation extraction from {mbox}")
    if resume:
        print("Resume mode: will skip already processed emails")

    result = run_variation(mbox, resume=resume)
    print(f"\nExtraction complete. Results written to {VARIATION_OUTPUT}")


if __name__ == "__main__":
    main()