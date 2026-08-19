"""
interlocutor.py — LLM extraction: email → interlocutor context.

Calls an OpenAI-compatible chat completions endpoint.
One email per call. Returns structured JSON.

The prompt asks the LLM to classify recipients and detect behavioral signals:
  relationship_type — core_maintainer, subsystem_maintainer, regular_contributor, newcomer, peer_equal, external_stakeholder
  tone_shift_signal — more_formal, less_formal, equal, neutral
  delegation_signal — delegates, owns, defers, neutral
  confidence — high, medium, low
"""

from __future__ import annotations

import json
import random
import time
import urllib.request
import urllib.error
from pathlib import Path

from . import config
from .models import EmailRecord

INTERLOCUTOR_OUTPUT = Path("data/interlocutor.jsonl")
INTERLOCUTOR_CHECKPOINT = Path("data/interlocutor_checkpoint.jsonl")
SKIP_LIST_PATH = Path("data/skip_list.json")

SYSTEM_PROMPT = """\
You are analyzing a code-review mailing list email to classify recipients and detect behavioral signals.

Email Headers:
From: {from_header}
To: {to_header}
Cc: {cc_header}
Subject: {subject}
Message-ID: {message_id}
Date: {date}

Email Body (truncated to 2000 chars):
{body_truncated}

For EACH recipient in the To:/Cc: fields, extract:
1. recipient_name, recipient_email
2. relationship_type: core_maintainer, subsystem_maintainer, regular_contributor, newcomer, peer_equal, external_stakeholder
3. tone_shift_signal: more_formal, less_formal, equal, neutral
4. delegation_signal: delegates, owns, defers, neutral
5. confidence: high, medium, low

Return a JSON object with this exact structure:
{{"email_message_id": "{message_id}", "recipients": [{{...}}]}}

Rules:
- Use ONLY the provided categories
- If insufficient evidence, use "neutral" for tone/delegation and "low" for confidence
- Return ONLY valid JSON, no markdown, no explanation"""


def _call_llm(email: EmailRecord, retries: int = None) -> dict:
    """Call the LLM API for one email. Returns parsed JSON dict."""
    retries = retries if retries is not None else config.MAX_RETRIES

    body_truncated = email.body[:2000] if email.body else ""
    user_content = (
        f"Email Headers:\n"
        f"From: {email.from_name} <{email.from_email}>\n"
        f"To: {email.to}\n"
        f"Cc: {email.cc}\n"
        f"Subject: {email.subject}\n"
        f"Message-ID: {email.message_id}\n"
        f"Date: {email.date}\n\n"
        f"Email Body (truncated to 2000 chars):\n"
        f"{body_truncated}"
    )

    payload = {
        "model": config.MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(
                from_header=f"{email.from_name} <{email.from_email}>",
                to_header=email.subject.split('Re: ', 1)[-1] if 'Re: ' in email.subject else email.subject,
                cc_header="(see full headers)",
                subject=email.subject,
                message_id=email.message_id,
                date=email.date,
                body_truncated=body_truncated,
            )},
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


def _load_skip_list() -> set[str]:
    """Load skip list from JSON file."""
    if not SKIP_LIST_PATH.exists():
        return set()
    ids = set()
    try:
        for line in SKIP_LIST_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                ids.add(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return ids


def _load_existing_message_ids(output_path: Path) -> set[str]:
    """Load message IDs already processed in output file."""
    if not output_path.exists():
        return set()
    ids = set()
    try:
        for line in output_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                data = json.loads(line)
                if "email_message_id" in data:
                    ids.add(data["email_message_id"])
    except (json.JSONDecodeError, OSError):
        pass
    return ids


def _save_checkpoint(processed_ids: set[str], checkpoint_path: Path):
    """Persist processed email IDs for crash recovery."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        for msg_id in sorted(processed_ids):
            f.write(msg_id + "\n")


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def extract_interlocutor(email: EmailRecord) -> dict:
    """Extract interlocutor data from one email. Returns a dict with recipients list."""
    try:
        result = _call_llm(email)
        recipients = result.get("recipients", [])
        return {
            "email_message_id": email.message_id,
            "email_date": email.date,
            "email_subject": email.subject,
            "recipients": recipients,
        }
    except Exception as e:
        return {
            "email_message_id": email.message_id,
            "email_date": email.date,
            "email_subject": email.subject,
            "recipients": [],
            "error": str(e),
        }


def run_interlocutor(
    mbox_path: str = "data/lkml.mbox",
    resume: bool = False,
    checkpoint_interval: int = 1000,
):
    """Extract interlocutor data from emails in mbox file.

    Args:
        mbox_path: Path to mbox file (mboxrd format)
        resume: If True, skip already-processed emails
        checkpoint_interval: Save checkpoint every N emails
    """
    import mailbox

    mbox_path = Path(mbox_path)
    if not mbox_path.exists():
        print(f"error: {mbox_path} not found")
        return

    # Load existing processed IDs
    done_ids = set()
    if resume:
        done_ids = _load_existing_message_ids(INTERLOCUTOR_OUTPUT)
        if done_ids:
            print(f"  resuming: {len(done_ids)} already done")

    # Load skip list
    skip_ids = _load_skip_list()
    if skip_ids:
        print(f"  skip list: {len(skip_ids)} known emails to skip")

    # Open mbox and iterate
    print(f"reading {mbox_path}...")
    mbox = mailbox.mbox(str(mbox_path))

    total = len(mbox)
    processed = 0
    errors = 0
    recipients_count = 0
    skipped_body = 0
    skipped_existing = 0
    skipped_in_skip_list = 0

    start_time = time.time()
    processed_ids = set()

    # Load checkpoint if resuming
    if resume and INTERLOCUTOR_CHECKPOINT.exists():
        checkpoint_ids = set(
            line.strip() for line in INTERLOCUTOR_CHECKPOINT.read_text().splitlines() if line.strip()
        )
        print(f"  checkpoint: {len(checkpoint_ids)} emails from previous run")

    mode = "a" if resume else "w"
    with open(INTERLOCUTOR_OUTPUT, mode, encoding="utf-8") as f:
        for i, message in enumerate(mbox):
            # Parse email
            from_header = message.get("From", "")
            to_header = message.get("To", "")
            cc_header = message.get("Cc", "")
            subject = message.get("Subject", "")
            message_id = message.get("Message-ID", "")
            date = message.get("Date", "")

            if not message_id:
                continue

            # Skip if already processed
            if message_id in done_ids:
                skipped_existing += 1
                continue

            # Skip if in skip list
            if message_id in skip_ids:
                skipped_in_skip_list += 1
                continue

            # Extract body
            body = ""
            if message.is_multipart():
                for part in message.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                        except Exception:
                            pass
            else:
                try:
                    body = message.get_payload(decode=True).decode("utf-8", errors="ignore")
                except Exception:
                    body = str(message.get_payload() or "")

            # Skip emails with body <50 words
            if _count_words(body) < 50:
                skipped_body += 1
                continue

            # Create EmailRecord
            from_parts = from_header.rsplit("<", 1)
            from_name = from_parts[0].strip() if len(from_parts) > 1 else ""
            from_email = from_parts[1].rstrip(">").strip() if len(from_parts) > 1 else from_header

            email = EmailRecord(
                message_id=message_id,
                from_name=from_name,
                from_email=from_email,
                date=date,
                subject=subject,
                in_reply_to=None,
                body=body,
                to=to_header,
                cc=cc_header,
            )

            # Extract interlocutor data
            result = extract_interlocutor(email)
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()

            processed += 1
            if result.get("error"):
                errors += 1
            else:
                n_recipients = len(result.get("recipients", []))
                recipients_count += n_recipients

            # Track processed ID
            if result.get("email_message_id"):
                processed_ids.add(result["email_message_id"])

            if processed % 100 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 else 0
                print(
                    f"  {processed}/{total} — "
                    f"{recipients_count} recipients, {errors} errors — "
                    f"{rate:.1f}/s, ETA {eta:.0f}s"
                )

            # Save checkpoint
            if processed % checkpoint_interval == 0 and processed > 0:
                _save_checkpoint(processed_ids, INTERLOCUTOR_CHECKPOINT)
                print(f"  checkpoint: {len(processed_ids)} emails persisted")

    elapsed = time.time() - start_time
    print(
        f"done: {processed} emails, {recipients_count} recipients, "
        f"{errors} errors in {elapsed:.0f}s"
    )
    print(f"  skipped (body <50 words): {skipped_body}")
    print(f"  skipped (already processed): {skipped_existing}")
    print(f"  skipped (skip list): {skipped_in_skip_list}")
    print(f"  → {INTERLOCUTOR_OUTPUT}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="torvalds_skill.interlocutor",
        description="Extract interlocutor context from LKML emails",
    )
    parser.add_argument(
        "--mbox",
        type=str,
        default="data/lkml.mbox",
        help="Path to mbox file (default: data/lkml.mbox)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip already-processed emails",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=1000,
        help="Save checkpoint every N emails (default: 1000)",
    )

    args = parser.parse_args()

    print(f"config: model={config.MODEL}, host={config.HOST}")

    run_interlocutor(
        mbox_path=args.mbox,
        resume=args.resume,
        checkpoint_interval=args.checkpoint_interval,
    )


if __name__ == "__main__":
    main()