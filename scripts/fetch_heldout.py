"""Fetch held-out LKML patch+review pairs for blind-review evaluation."""

from __future__ import annotations

import email
import gzip
import json
import mailbox
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Constants
ATOM_NS = "{http://www.w3.org/2005/Atom}"
LORE_BASE = "https://lore.kernel.org/all/"
USER_AGENT = "git/2.40.0"
CORPUS_PATH = Path("data/corpus.jsonl")
OUTPUT_PATH = Path("data/heldout_reviews.jsonl")
DATE_RANGE = "d:20260803..20261030"
TORVALDS_QUERY = f"f:torvalds@linux-foundation.org+AND+{DATE_RANGE}"
MIN_DIFF_LINES = 20
MIN_REVIEW_WORDS = 100
MAX_CANDIDATES = 200
REQUEST_DELAY = 1.0


def load_corpus_exclusions() -> set[str]:
    """Load message_ids from corpus.jsonl to exclude from held-out set."""
    exclusions: set[str] = set()
    if not CORPUS_PATH.exists():
        print(f"Warning: {CORPUS_PATH} not found, using empty exclusion set", file=sys.stderr)
        return exclusions

    with CORPUS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                msg_id = record.get("message_id", "")
                # Normalize: strip angle brackets for comparison
                if msg_id.startswith("<") and msg_id.endswith(">"):
                    msg_id = msg_id[1:-1]
                exclusions.add(msg_id)
            except json.JSONDecodeError:
                continue

    return exclusions


def normalize_message_id(msg_id: str) -> str:
    """Normalize message_id by stripping angle brackets."""
    msg_id = msg_id.strip()
    if msg_id.startswith("<") and msg_id.endswith(">"):
        msg_id = msg_id[1:-1]
    return msg_id


def search_lore_atom() -> list[tuple[str, str]]:
    """
    Search lore.kernel.org Atom API for Torvalds reviews.
    Returns list of (message_id, subject) tuples.
    """
    print("Searching lore.kernel.org Atom API...", file=sys.stderr)

    results: list[tuple[str, str]] = []
    base_url = f"{LORE_BASE}?q={TORVALDS_QUERY}&x=A"

    page_offset = 0
    while True:
        url = base_url if page_offset == 0 else f"{base_url}&o={page_offset}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    print(f"Error: HTTP {resp.status} from {url}", file=sys.stderr)
                    break

                xml_data = resp.read()
                root = ET.fromstring(xml_data)

                # Find all entries
                entries = root.findall(f"{ATOM_NS}entry")
                if not entries:
                    break

                for entry in entries:
                    # Extract link href
                    link_elem = entry.find(f"{ATOM_NS}link")
                    if link_elem is None:
                        continue

                    href = link_elem.get("href", "")
                    if not href:
                        continue

                    # Extract message_id from href like https://lore.kernel.org/all/<msgid>/
                    match = re.search(r"https://lore\.kernel\.org/all/([^/]+)/", href)
                    if not match:
                        continue

                    msg_id = match.group(1)
                    # Restore angle brackets if not present
                    if not (msg_id.startswith("<") and msg_id.endswith(">")):
                        msg_id = f"<{msg_id}>"

                    # Extract subject from title
                    title_elem = entry.find(f"{ATOM_NS}title")
                    subject = title_elem.text if title_elem is not None and title_elem.text else ""

                    results.append((msg_id, subject))

                # Check if we got fewer than 200 results (last page)
                if len(entries) < 200:
                    break

                page_offset += 200

        except urllib.error.URLError as e:
            print(f"Error fetching {url}: {e}", file=sys.stderr)
            break
        except ET.ParseError as e:
            print(f"Error parsing XML from {url}: {e}", file=sys.stderr)
            break

    return results


def filter_candidates(
    candidates: list[tuple[str, str]], exclusions: set[str]
) -> list[tuple[str, str]]:
    """
    Filter candidates: keep only Re: replies, dedup against corpus, limit to MAX_CANDIDATES.
    """
    filtered: list[tuple[str, str]] = []

    for msg_id, subject in candidates:
        # Must be a reply to a [PATCH ...] email — not a git pull or discussion
        if not re.match(r"Re:\s*\[PATCH", subject, re.IGNORECASE):
            continue

        # Normalize message_id for comparison
        normalized_id = normalize_message_id(msg_id)

        # Must not be in corpus
        if normalized_id in exclusions:
            continue

        filtered.append((msg_id, subject))

        if len(filtered) >= MAX_CANDIDATES:
            break

    return filtered


def extract_patch_info(msg: email.message.Message) -> dict[str, Any] | None:
    """
    Extract patch info from an email message.
    Returns dict with subject, diff, files, or None if not a patch.
    """
    subject = msg.get("Subject", "")

    # Check if this is a patch email (Subject starts with [PATCH])
    if "[PATCH" not in subject:
        return None

    # Get body text
    body = _get_email_body(msg)
    if not body:
        return None

    # Check for diff content
    diff_match = re.search(r"^diff --git", body, re.MULTILINE)
    if not diff_match:
        return None

    # Extract diff from first diff --git line
    diff_start = diff_match.start()
    diff_text = body[diff_start:]

    # Extract filenames from diff --git lines
    files = re.findall(r"^diff --git a/(.+) b/(.+)", diff_text, re.MULTILINE)
    unique_files = list(dict.fromkeys(f[1] for f in files))  # Keep second path, dedupe

    # Count diff lines
    diff_lines = len(diff_text.splitlines())

    return {
        "subject": subject,
        "diff": diff_text,
        "files": unique_files,
        "diff_lines": diff_lines,
    }


def extract_torvalds_review(
    msg: email.message.Message, target_msg_id: str
) -> dict[str, Any] | None:
    """
    Extract Torvalds review from an email message.
    Returns dict with subject, date, body, word_count, or None if not Torvalds.
    """
    from_header = msg.get("From", "")
    msg_id = msg.get("Message-ID", "")

    # Check if from Torvalds
    if "torvalds@" not in from_header:
        return None

    # Check if this matches the target message_id (or is in the thread)
    # For simplicity, we check if the message_id matches or is a reply
    # (normalized for comparison, though we don't use it strictly here)

    # Get body text
    body = _get_email_body(msg)
    if not body:
        return None

    subject = msg.get("Subject", "")
    date = msg.get("Date", "")

    # Count words
    word_count = len(body.split())

    return {
        "subject": subject,
        "date": date,
        "body": body,
        "word_count": word_count,
        "message_id": msg_id,
    }


def _get_email_body(msg: email.message.Message) -> str:
    """Extract body text from an email message, handling various encodings."""
    payload = msg.get_payload()

    if payload is None:
        return ""

    if isinstance(payload, str):
        return payload

    if isinstance(payload, list):
        # Multipart: concatenate all text parts
        parts = []
        for part in payload:
            if isinstance(part, email.message.Message):
                part_body = _get_email_body(part)
                if part_body:
                    parts.append(part_body)
        return "\n".join(parts)

    return str(payload)


def fetch_thread_mbox(msg_id: str) -> list[mailbox.mboxMessage] | None:
    """
    Fetch and parse a thread mbox from lore.kernel.org.
    Returns list of email messages, or None on failure.
    """
    # Normalize message_id for URL (remove angle brackets)
    normalized_id = normalize_message_id(msg_id)

    url = f"{LORE_BASE}{normalized_id}/t.mbox.gz"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                print(f"  HTTP {resp.status} for {url}", file=sys.stderr)
                return None

            compressed_data = resp.read()
            if not compressed_data:
                print(f"  Empty response for {url}", file=sys.stderr)
                return None

            # Decompress gzip
            try:
                mbox_data = gzip.decompress(compressed_data)
            except gzip.BadGzipFile:
                # Try raw decompression
                mbox_data = compressed_data

            # Write to temp file and parse
            with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".mbox") as tmp:
                tmp.write(mbox_data)
                tmp_path = tmp.name

            try:
                mbox = mailbox.mbox(tmp_path)
                messages = list(mbox)
                return messages
            except Exception as e:
                print(f"  Error parsing mbox: {e}", file=sys.stderr)
                return None
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    except urllib.error.URLError as e:
        print(f"  Fetch failed for {url}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Unexpected error for {url}: {e}", file=sys.stderr)
        return None


def process_candidate(msg_id: str, subject: str, exclusions: set[str]) -> dict[str, Any] | None:
    """
    Process a single candidate thread.
    Returns held-out record dict, or None if it doesn't meet criteria.
    """
    print("  Fetching thread...", file=sys.stderr)

    messages = fetch_thread_mbox(msg_id)
    if not messages:
        return None

    # Find patch email and Torvalds review
    patch_info: dict[str, Any] | None = None
    torvalds_reviews: list[dict[str, Any]] = []

    for msg in messages:
        # Check if this is a patch email
        if not patch_info:
            patch_info = extract_patch_info(msg)

        # Check if this is a Torvalds review
        review = extract_torvalds_review(msg, msg_id)
        if review:
            torvalds_reviews.append(review)

    # Skip if no patch email
    if not patch_info:
        print("  Skipped: no patch email found", file=sys.stderr)
        return None

    # Skip if patch has fewer than MIN_DIFF_LINES
    if patch_info["diff_lines"] < MIN_DIFF_LINES:
        print(
            f"  Skipped: patch has only {patch_info['diff_lines']} diff lines (< {MIN_DIFF_LINES})",
            file=sys.stderr,
        )
        return None

    # Find Torvalds review with >= MIN_REVIEW_WORDS
    # If multiple, take the first one that meets the threshold
    # If none meet threshold, concatenate all
    qualifying_reviews = [r for r in torvalds_reviews if r["word_count"] >= MIN_REVIEW_WORDS]

    if not qualifying_reviews:
        # Concatenate all reviews
        if not torvalds_reviews:
            print("  Skipped: no Torvalds review found", file=sys.stderr)
            return None

        # Concatenate all reviews
        combined_body = "\n\n".join(r["body"] for r in torvalds_reviews)
        combined_word_count = len(combined_body.split())

        if combined_word_count < MIN_REVIEW_WORDS:
            print(
                f"  Skipped: combined review has only {combined_word_count} words (< {MIN_REVIEW_WORDS})",
                file=sys.stderr,
            )
            return None

        review_data = {
            "subject": torvalds_reviews[0]["subject"],
            "date": torvalds_reviews[0]["date"],
            "body": combined_body,
            "word_count": combined_word_count,
            "message_id": torvalds_reviews[0]["message_id"],
        }
    else:
        review_data = qualifying_reviews[0]

    # Check if this is a multi-patch series
    patch_subject = patch_info["subject"]
    if re.search(r"\[PATCH\s+\d+/\d+\]", patch_subject):
        print("  Skipped: multi-patch series", file=sys.stderr)
        return None

    # Build record
    thread_url = f"{LORE_BASE}{normalize_message_id(msg_id)}/T/"

    record = {
        "review_message_id": review_data["message_id"],
        "review_date": review_data["date"],
        "review_subject": review_data["subject"],
        "review_text": review_data["body"],
        "review_word_count": review_data["word_count"],
        "patch_message_id": msg_id,  # Use the candidate msg_id
        "patch_subject": patch_info["subject"],
        "patch_diff": patch_info["diff"],
        "patch_files": patch_info["files"],
        "patch_diff_lines": patch_info["diff_lines"],
        "thread_url": thread_url,
    }

    return record


def main() -> None:
    """Main entry point."""
    # Load corpus exclusions
    print("Loading corpus exclusions...", file=sys.stderr)
    exclusions = load_corpus_exclusions()
    print(f"  Loaded {len(exclusions)} corpus message_ids", file=sys.stderr)

    # Search lore.kernel.org
    candidates = search_lore_atom()
    print(f"  Found {len(candidates)} raw candidates", file=sys.stderr)

    # Filter candidates
    filtered = filter_candidates(candidates, exclusions)
    print(f"  Found {len(filtered)} candidates (after dedup and Re: filter)", file=sys.stderr)

    if not filtered:
        print("No candidates found. Exiting.", file=sys.stderr)
        return

    # Process each candidate
    records: list[dict[str, Any]] = []
    seen_review_ids: set[str] = set()

    for i, (msg_id, subject) in enumerate(filtered, 1):
        print(f"[{i}/{len(filtered)}] Processing {msg_id[:40]}...", file=sys.stderr)

        record = process_candidate(msg_id, subject, exclusions)

        if record:
            # Deduplicate: skip if we already saved a record from the same thread
            # (same review_message_id means same Torvalds review, same thread)
            review_id = record["review_message_id"]
            if review_id in seen_review_ids:
                print("  -> Skipped (duplicate thread)", file=sys.stderr)
            else:
                seen_review_ids.add(review_id)
                records.append(record)
                print(
                    f"  -> Saved (review: {record['review_word_count']}w, diff: {record['patch_diff_lines']}L, files: {len(record['patch_files'])})",
                    file=sys.stderr,
                )
        else:
            print("  -> Skipped", file=sys.stderr)

        # Delay between requests
        if i < len(filtered):
            time.sleep(REQUEST_DELAY)

    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(records)} held-out pairs to {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
