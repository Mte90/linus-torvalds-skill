"""
extract_async.py — async LLM extraction: email → review moves.

Calls the LLM API concurrently using aiohttp.
One email per call (no batching).
Uses asyncio.Semaphore to limit concurrency.
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Any

import aiohttp

from . import config
from .models import EmailRecord


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


async def _call_llm_async(
    session: aiohttp.ClientSession,
    email: EmailRecord,
    semaphore: asyncio.Semaphore,
    retries: int = None,
) -> dict:
    """Call the LLM API for one email asynchronously. Returns parsed JSON dict."""
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

    last_err: Any = None
    for attempt in range(retries):
        async with semaphore:
            try:
                async with session.post(
                    config.CHAT_URL,
                    json=payload,
                    headers=config.headers(),
                    timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"]
                        return _parse_json_response(content)
                    elif resp.status == 429:
                        last_err = f"HTTP 429 (rate limit)"
                        wait = config.RETRY_DELAY * (attempt + 1) * 2 + random.uniform(0, config.RETRY_DELAY)
                        await asyncio.sleep(wait)
                    elif resp.status >= 500:
                        last_err = f"HTTP {resp.status}"
                        wait = config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY)
                        await asyncio.sleep(wait)
                    else:
                        last_err = f"HTTP {resp.status}"
                        raise RuntimeError(f"LLM API error: {resp.status}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_err = e
                wait = config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY)
                await asyncio.sleep(wait)
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                last_err = e
                await asyncio.sleep(config.RETRY_DELAY)

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


def _load_checkpoint(checkpoint_path: Path) -> set[str]:
    """Load email IDs that have already been processed."""
    if not checkpoint_path.exists():
        return set()

    processed = set()
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                processed.add(record["email_message_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return processed


def _load_skip_list(skip_list_path: Path) -> set[str]:
    """Load email IDs that had zero moves (skip list)."""
    if not skip_list_path.exists():
        return set()

    skipped = set()
    with open(skip_list_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            skipped = set(data.get("skipped_ids", []))
        except (json.JSONDecodeError, KeyError):
            pass
    return skipped


async def extract_moves_async(
    session: aiohttp.ClientSession,
    email: EmailRecord,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Extract review moves from one email asynchronously. Returns a dict with moves list."""
    try:
        result = await _call_llm_async(session, email, semaphore)
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


def _read_emails(input_path: Path, resume: bool, checkpoint_path: Path, skip_list_path: Path) -> list[EmailRecord]:
    """Read emails from input file (mbox or jsonl), applying resume logic."""
    checkpoint_ids = _load_checkpoint(checkpoint_path) if resume else set()
    skip_ids = _load_skip_list(skip_list_path) if resume else set()

    emails = []
    if input_path.suffix == ".jsonl":
        with open(input_path, "r", encoding="utf-8") as f:
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
                    if resume and email.message_id in checkpoint_ids:
                        continue
                    if resume and email.message_id in skip_ids:
                        continue
                    emails.append(email)
                except (json.JSONDecodeError, KeyError) as e:
                    continue
    else:
        import mailbox
        mbox = mailbox.mbox(input_path)
        for msg in mbox:
            message_id = msg.get("Message-ID", "")
            if not message_id:
                continue
            if resume and message_id in checkpoint_ids:
                continue
            if resume and message_id in skip_ids:
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

    return emails


async def process_email_with_delay(
    session: aiohttp.ClientSession,
    email: EmailRecord,
    semaphore: asyncio.Semaphore,
    delay: float,
) -> tuple[EmailRecord, dict]:
    """Process a single email with a random delay to avoid thundering-herd."""
    await asyncio.sleep(delay)
    result = await extract_moves_async(session, email, semaphore)
    return (email, result)


async def extract_async(
    input_path: str,
    output_path: str,
    model: str = "gpt-oss-120b",
    max_workers: int = 20,
    resume: bool = False,
) -> int:
    """
    Extract review moves from emails using async LLM calls.

    Args:
        input_path: Path to input file (mbox or jsonl)
        output_path: Path to write JSONL output
        model: Model name to use (default: gpt-oss-120b)
        max_workers: Maximum concurrent LLM calls (default: 20)
        resume: If True, resume from checkpoint

    Returns:
        Count of extracted moves
    """
    input_file = Path(input_path)
    output_file = Path(output_path)
    checkpoint_path = output_file.parent / "checkpoint.jsonl"
    skip_list_path = output_file.parent / "skip_list.json"

    output_file.parent.mkdir(parents=True, exist_ok=True)

    emails = _read_emails(input_file, resume, checkpoint_path, skip_list_path)
    total = len(emails)

    if total == 0:
        print("No emails to process (all already processed or skipped)")
        return 0

    semaphore = asyncio.Semaphore(max_workers)
    done = 0
    errors = 0
    moves_count = 0
    checkpoint_batch: list[str] = []
    skip_batch: list[str] = []

    output_mode = "a" if resume else "w"
    async with aiohttp.ClientSession() as session:
        tasks = []
        for email in emails:
            delay = random.uniform(0.5, 2.0)
            task = asyncio.create_task(
                process_email_with_delay(session, email, semaphore, delay)
            )
            tasks.append(task)

        with open(output_file, output_mode, encoding="utf-8") as f:
            for coro in asyncio.as_completed(tasks):
                email, result = await coro
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
                done += 1

                if result.get("error"):
                    errors += 1
                else:
                    moves = result.get("moves", [])
                    if moves:
                        moves_count += len(moves)
                    else:
                        skip_batch.append(result["email_message_id"])

                checkpoint_batch.append(result["email_message_id"])

                if done % 100 == 0:
                    print(f"  {done}/{total} — {moves_count} moves, {errors} errors")

                if len(checkpoint_batch) >= 100:
                    with open(checkpoint_path, "a", encoding="utf-8") as cf:
                        for pid in checkpoint_batch:
                            cf.write(json.dumps({"email_message_id": pid}) + "\n")
                    checkpoint_batch = []

                    if skip_batch:
                        with open(skip_list_path, "w", encoding="utf-8") as sf:
                            existing_skips = set()
                            if skip_list_path.exists():
                                try:
                                    with open(skip_list_path, "r", encoding="utf-8") as ef:
                                        data = json.load(ef)
                                        existing_skips = set(data.get("skipped_ids", []))
                                except (json.JSONDecodeError, KeyError):
                                    pass
                            existing_skips.update(skip_batch)
                            json.dump({"skipped_ids": list(existing_skips)}, sf, indent=2)
                        skip_batch = []

    if checkpoint_batch:
        with open(checkpoint_path, "a", encoding="utf-8") as cf:
            for pid in checkpoint_batch:
                cf.write(json.dumps({"email_message_id": pid}) + "\n")

    if skip_batch:
        existing_skips = set()
        if skip_list_path.exists():
            try:
                with open(skip_list_path, "r", encoding="utf-8") as ef:
                    data = json.load(ef)
                    existing_skips = set(data.get("skipped_ids", []))
            except (json.JSONDecodeError, KeyError):
                pass
        existing_skips.update(skip_batch)
        with open(skip_list_path, "w", encoding="utf-8") as sf:
            json.dump({"skipped_ids": list(existing_skips)}, sf, indent=2)

    print(f"done: {done} emails, {moves_count} moves, {errors} errors")
    return moves_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract review moves from emails using async LLM calls"
    )
    parser.add_argument(
        "--input",
        default="data/corpus.jsonl",
        help="Input file path (mbox or jsonl) (default: data/corpus.jsonl)"
    )
    parser.add_argument(
        "--output",
        default="data/moves_async.jsonl",
        help="Output JSONL file path (default: data/moves_async.jsonl)"
    )
    parser.add_argument(
        "--model",
        default="gpt-oss-120b",
        help="Model name to use (default: gpt-oss-120b)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=20,
        help="Maximum concurrent LLM calls (default: 20)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint, skipping already-processed emails"
    )

    args = parser.parse_args()

    count = asyncio.run(
        extract_async(
            args.input,
            args.output,
            args.model,
            args.max_workers,
            args.resume,
        )
    )
    print(f"Extracted {count} moves total")