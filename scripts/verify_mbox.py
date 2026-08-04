#!/usr/bin/env python3
"""
verify_mbox.py — validate data/lkml.mbox integrity and report stats.

Checks:
  - stdlib mailbox.mbox can open and iterate every message
  - every From: header contains "torvalds" (filter integrity)
  - Date header present and parseable on every message
  - Message-ID present on every message
  - mboxrd From_ separator line present before each message
  - date range (min/max), subject sample, byte size, sha256

Usage:
  python3 scripts/verify_mbox.py [path/to/mbox]
"""

import hashlib
import sys
import mailbox
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

MBOX = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "lkml.mbox"


def main():
    if not MBOX.exists():
        print(f"ERROR: {MBOX} not found")
        sys.exit(1)

    size = MBOX.stat().st_size
    print(f"=== {MBOX} ({size/1e6:.1f} MB) ===")

    # sha256
    h = hashlib.sha256()
    with MBOX.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print(f"sha256: {h.hexdigest()}")

    # Count From_ separator lines (mbox message boundaries)
    sep_count = 0
    with MBOX.open("rb") as f:
        for line in f:
            if line.startswith(b"From ") and b"@" in line[:80]:
                sep_count += 1
    print(f"From_ separator lines: {sep_count}")

    # Parse with stdlib mailbox
    box = mailbox.mbox(str(MBOX))
    total = len(box)
    print(f"mailbox.mbox parsed messages: {total}")

    if total == 0:
        print("ERROR: no messages parsed")
        sys.exit(1)

    missing_from = 0
    missing_date = 0
    missing_msgid = 0
    non_torvalds = 0
    dates = []
    subjects_sample = []
    addr_counts = {}

    for i, key in enumerate(box.keys()):
        msg = box[key]
        frm = msg.get("From", "")
        date_raw = msg.get("Date", "")
        msgid = msg.get("Message-ID", "")
        subj = msg.get("Subject", "")

        if not frm:
            missing_from += 1
        else:
            name, addr = parseaddr(frm)
            addr_counts[addr] = addr_counts.get(addr, 0) + 1
            if "torvalds" not in frm.lower():
                non_torvalds += 1
        if not date_raw:
            missing_date += 1
        else:
            try:
                dt = parsedate_to_datetime(date_raw)
                if dt:
                    dates.append(dt)
            except Exception:
                missing_date += 1
        if not msgid:
            missing_msgid += 1

        if i < 5 or i >= total - 3:
            subjects_sample.append((i, subj[:72]))

    print(f"\n--- integrity ---")
    print(f"missing From:     {missing_from}")
    print(f"missing Date:     {missing_date}")
    print(f"missing Msg-ID:   {missing_msgid}")
    print(f"non-torvalds:     {non_torvalds}")

    print(f"\n--- From addresses (top 5) ---")
    for addr, c in sorted(addr_counts.items(), key=lambda x: -x[1])[:5]:
        print(f"  {c:>6}  {addr}")

    # Normalize all datetimes to offset-aware (UTC) for comparison
    from datetime import timezone, timedelta
    aware_dates = []
    for d in dates:
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        aware_dates.append(d)
    if aware_dates:
        dmin = min(aware_dates)
        dmax = max(aware_dates)
        print(f"\n--- date range ---")
        print(f"  earliest: {dmin.isoformat()}")
        print(f"  latest:   {dmax.isoformat()}")
        years = {}
        for d in dates:
            years[d.year] = years.get(d.year, 0) + 1
        print(f"  by year: {dict(sorted(years.items()))}")

    print(f"\n--- subject sample (first 5, last 3) ---")
    for i, s in subjects_sample:
        print(f"  [{i:>5}] {s}")

    ok = (missing_from == 0 and missing_date == 0 and missing_msgid == 0 and non_torvalds == 0)
    print(f"\n{'OK' if ok else 'ISSUES FOUND'}: {total} messages, all headers intact, all from Torvalds")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
