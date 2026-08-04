#!/usr/bin/env python3
"""
mbox_to_jsonl.py — convert data/lkml.mbox to data/corpus.jsonl.

Each line is one JSON object:
  {message_id, from_name, from_email, date, subject, in_reply_to, body}

Body cleaning:
  - strip quoted lines (>...)
  - strip signature (-- \n separator)
  - strip mailing-list footer blocks
  - strip trailing/leading whitespace, collapse blank runs

The mbox remains the source of truth; the JSONL is the fast working format.
"""

import hashlib
import json
import mailbox
import re
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MBOX = ROOT / "data" / "lkml.mbox"
JSONL = ROOT / "data" / "corpus.jsonl"

FOOTER_MARK = "_______________________________________________"
SIG_MARK = "-- \n"


def clean_body(raw: str) -> str:
    """Strip quotes, signature, footer; collapse whitespace."""
    lines = raw.split("\n")

    # Cut at signature separator
    out = []
    for line in lines:
        if line.strip() == "--" and len(out) > 0:
            break
        if line.startswith(">"):
            continue
        if line.strip().startswith(FOOTER_MARK.strip()):
            break
        out.append(line)

    text = "\n".join(out)
    # collapse 3+ blank lines to 1
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    if not MBOX.exists():
        raise SystemExit(f"mbox not found: {MBOX}")

    box = mailbox.mbox(str(MBOX))
    parser = BytesParser(policy=policy.default)

    total = 0
    h = hashlib.sha256()

    with JSONL.open("w", encoding="utf-8") as f:
        for key in box.keys():
            raw_bytes = box.get_bytes(key)
            msg = parser.parsebytes(raw_bytes)

            # headers
            from_raw = msg.get("From", "")
            name, addr = parseaddr(from_raw)
            date_raw = msg.get("Date", "")
            try:
                dt = parsedate_to_datetime(date_raw)
                date_iso = dt.isoformat() if dt else ""
            except Exception:
                date_iso = ""
            subject = msg.get("Subject", "")
            msg_id = msg.get("Message-ID", "").strip()
            in_reply_to = msg.get("In-Reply-To", "").strip() or None

            # body: first text/plain part
            body_raw = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body_raw = part.get_content()
                        break
            else:
                body_raw = msg.get_content()

            body = clean_body(body_raw)

            record = {
                "message_id": msg_id,
                "from_name": name,
                "from_email": addr,
                "date": date_iso,
                "subject": subject,
                "in_reply_to": in_reply_to,
                "body": body,
            }

            line = json.dumps(record, ensure_ascii=False)
            f.write(line + "\n")
            h.update((line + "\n").encode("utf-8"))
            total += 1

            if total % 5000 == 0:
                print(f"  {total} messages...")

    sha = h.hexdigest()
    size = JSONL.stat().st_size
    print(f"\nwrote {JSONL}")
    print(f"  {total} records, {size/1e6:.1f} MB, sha256={sha}")

    # update manifest with corpus.jsonl info
    manifest_path = ROOT / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["corpus_jsonl_path"] = "data/corpus.jsonl"
    manifest["corpus_jsonl_bytes"] = size
    manifest["corpus_jsonl_sha256"] = sha
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"updated {manifest_path}")


if __name__ == "__main__":
    main()
