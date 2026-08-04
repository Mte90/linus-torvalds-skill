#!/usr/bin/env python3
"""
fetch_torvalds_mbox.py

Download all Linus Torvalds emails from gmane.linux.kernel via NNTP
and write them to data/lkml.mbox in mboxrd format (true RFC822 with
full headers).

Two resumable phases:
  Phase 1: XHDR from across the whole group range → discover article
           numbers whose From: contains "torvalds". Checkpointed to
           data/article_numbers.txt.
  Phase 2: ARTICLE fetch for each discovered number → append to
           data/lkml.mbox in mboxrd format. Resume skips already-written
           messages.

Usage:
  python3 scripts/fetch_torvalds_mbox.py                 # run both phases
  python3 scripts/fetch_torvalds_mbox.py --phase discover # phase 1 only
  python3 scripts/fetch_torvalds_mbox.py --phase fetch    # phase 2 only
  python3 scripts/fetch_torvalds_mbox.py --batch-size 50000

No dependencies. Pure stdlib (nntplib was removed in 3.13; this uses
raw sockets).
"""

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

NNTP_HOST = "news.gmane.io"
NNTP_PORT = 119
GROUP = "gmane.linux.kernel"
AUTHOR_FILTER = "torvalds"  # case-insensitive substring match on From: header

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MBOX_PATH = DATA_DIR / "lkml.mbox"
NUMBERS_PATH = DATA_DIR / "article_numbers.txt"
MANIFEST_PATH = DATA_DIR / "manifest.json"
PROGRESS_PATH = DATA_DIR / "fetch_progress.json"

BATCH_SIZE = 50000  # articles per XHDR command
FETCH_DELAY = 0.0  # network RTT is the natural rate limiter
SOCKET_TIMEOUT = 60

# ─── NNTP client (raw socket) ────────────────────────────────────────────────


class NNTPClient:
    """Minimal NNTP client over raw sockets. nntplib was removed in 3.13."""

    def __init__(self, host, port, timeout):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""
        self._read_line()  # greeting

    def _read_line(self):
        while b"\r\n" not in self.buf:
            chunk = self.sock.recv(8192)
            if not chunk:
                raise ConnectionError("NNTP connection closed")
            self.buf += chunk
        line, _, self.buf = self.buf.partition(b"\r\n")
        return line.decode("utf-8", errors="replace")

    def _read_block(self):
        """Read until terminating lone '.' line. Returns raw bytes (unstuffed)."""
        while b"\r\n.\r\n" not in self.buf:
            chunk = self.sock.recv(16384)
            if not chunk:
                raise ConnectionError("NNTP connection closed mid-block")
            self.buf += chunk
        end = self.buf.index(b"\r\n.\r\n")
        block = self.buf[:end]
        self.buf = self.buf[end + 5 :]
        # Dot-unstuffing: lines starting with ".." → "."
        return block.replace(b"\r\n..", b"\r\n.")

    def command(self, cmd):
        self.sock.sendall((cmd + "\r\n").encode())
        line = self._read_line()
        code = line[:3]
        if code[0] == "4":
            raise RuntimeError(f"NNTP error: {line}")
        return line

    def command_block(self, cmd):
        """Command expecting a multiline response terminated by lone '.'."""
        self.sock.sendall((cmd + "\r\n").encode())
        line = self._read_line()
        code = line[:3]
        if code[0] == "4":
            raise RuntimeError(f"NNTP error: {line}")
        block = self._read_block()
        return line, block

    def group(self, name):
        line = self.command(f"GROUP {name}")
        parts = line.split()
        # "211 count first last name"
        return int(parts[1]), int(parts[2]), int(parts[3])

    def xhdr(self, header, low, high):
        line, block = self.command_block(f"XHDR {header} {low}-{high}")
        return block.decode("utf-8", errors="replace")

    def article(self, spec):
        line, block = self.command_block(f"ARTICLE {spec}")
        return block

    def quit(self):
        try:
            self.command("QUIT")
        except Exception:
            pass
        self.sock.close()


# ─── Phase 1: discover Torvalds article numbers ───────────────────────────────


def load_discovered():
    if NUMBERS_PATH.exists():
        nums = []
        for ln in NUMBERS_PATH.read_text().splitlines():
            ln = ln.strip()
            if ln:
                nums.append(int(ln))
        return nums
    return []


def append_discovered(nums):
    with NUMBERS_PATH.open("a") as f:
        for n in nums:
            f.write(f"{n}\n")


def phase_discover(client, batch_size):
    count, first, last = client.group(GROUP)
    print(f"[discover] group={GROUP} total={count} first={first} last={last}")

    already = set(load_discovered())
    print(f"[discover] already discovered: {len(already)}")

    # Resume: find the highest article number already scanned.
    # Stored separately so we know where to continue.
    scan_progress = PROGRESS_PATH
    scan_pos = first
    if scan_progress.exists():
        try:
            st = json.loads(scan_progress.read_text())
            scan_pos = st.get("scan_pos", first)
        except Exception:
            pass
    if scan_pos < first:
        scan_pos = first
    print(f"[discover] resuming scan from {scan_pos}")

    low = scan_pos
    total_new = 0
    batch = 0
    t0 = time.time()

    while low <= last:
        high = min(low + batch_size - 1, last)
        try:
            text = client.xhdr("from", low, high)
        except RuntimeError as e:
            print(f"[discover] XHDR {low}-{high} error: {e} — retrying once")
            time.sleep(2)
            try:
                text = client.xhdr("from", low, high)
            except RuntimeError as e2:
                print(f"[discover] XHDR retry failed: {e2} — skipping batch")
                low = high + 1
                continue

        new_nums = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # format: "12345 <from value>"
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            try:
                num = int(parts[0])
            except ValueError:
                continue
            from_val = parts[1]
            if AUTHOR_FILTER in from_val.lower() and num not in already:
                new_nums.append(num)
                already.add(num)

        if new_nums:
            append_discovered(new_nums)
            total_new += len(new_nums)

        batch += 1
        scan_pos = high + 1
        scan_progress.write_text(json.dumps({"scan_pos": scan_pos}))

        if batch % 10 == 0 or low == first:
            elapsed = time.time() - t0
            scanned = scan_pos - first
            pct = scanned / (last - first + 1) * 100
            rate = scanned / elapsed if elapsed else 0
            eta = (last - scan_pos + 1) / rate if rate else 0
            print(
                f"[discover] batch {batch}: {low}-{high} | "
                f"new={total_new} total={len(already)} | "
                f"{pct:.1f}% | {rate:.0f} art/s | ETA {eta:.0f}s"
            )

        low = high + 1

    print(f"[discover] done. total torvalds articles: {len(already)}")
    return sorted(already)


# ─── Phase 2: fetch articles into mbox ───────────────────────────────────────


def count_mbox_messages(path):
    if not path.exists():
        return 0
    n = 0
    with path.open("rb") as f:
        for line in f:
            if line.startswith(b"From ") and b"@" in line[:80]:
                n += 1
    return n


def from_separator(msg):
    """Build the mbox From_ separator line: 'From <sender> <ctime>'."""
    from_header = msg.get("From", "")
    _, addr = parseaddr(from_header)
    if not addr:
        addr = "unknown@unknown"
    date_hdr = msg.get("Date", "")
    try:
        dt = parsedate_to_datetime(date_hdr)
        if dt is None:
            raise ValueError
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        datestr = dt.strftime("%a %b %d %H:%M:%S %Y")
    except Exception:
        datestr = datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Y")
    return f"From {addr} {datestr}\n"


def mboxrd_escape(raw_bytes):
    """mboxrd: escape 'From ' and '>From ' lines in body."""
    # Operate on the raw message bytes after headers.
    out = []
    for line in raw_bytes.split(b"\n"):
        if line.startswith(b"From ") or line.startswith(b">From "):
            out.append(b">" + line)
        else:
            out.append(line)
    return b"\n".join(out)


def write_message_to_mbox(mbox_fp, raw_article_bytes):
    """Parse one ARTICLE response and append as one mbox message (mboxrd)."""
    parser = BytesParser()
    msg = parser.parsebytes(raw_article_bytes)
    sep = from_separator(msg)
    # Reconstruct: separator + raw message with mboxrd body escaping + blank line
    # Split headers from body.
    header_end = raw_article_bytes.find(b"\r\n\r\n")
    if header_end == -1:
        header_end = raw_article_bytes.find(b"\n\n")
        if header_end == -1:
            return False
        headers = raw_article_bytes[:header_end]
        body = raw_article_bytes[header_end + 2 :]
    else:
        headers = raw_article_bytes[:header_end]
        body = raw_article_bytes[header_end + 4 :]

    # Normalize headers to \n, body keep as-is but escape From lines
    headers_text = headers.replace(b"\r\n", b"\n")
    body_escaped = mboxrd_escape(body.replace(b"\r\n", b"\n"))

    mbox_fp.write(sep.encode())
    mbox_fp.write(headers_text)
    mbox_fp.write(b"\n\n")
    mbox_fp.write(body_escaped)
    if not body_escaped.endswith(b"\n"):
        mbox_fp.write(b"\n")
    mbox_fp.write(b"\n")
    return True


def phase_fetch(client, numbers):
    # NNTP ARTICLE requires a group to be selected first.
    client.group(GROUP)
    total = len(numbers)
    print(f"[fetch] {total} articles to fetch")

    # Resume: count messages already in mbox.
    have = count_mbox_messages(MBOX_PATH)
    print(f"[fetch] mbox already has {have} messages")
    if have >= total:
        print("[fetch] nothing to do")
        return have
    to_fetch = numbers[have:]
    print(f"[fetch] fetching {len(to_fetch)} new messages")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written = have
    t0 = time.time()
    with MBOX_PATH.open("ab") as fp:
        for i, num in enumerate(to_fetch):
            try:
                raw = client.article(str(num))
            except RuntimeError as e:
                print(f"[fetch] ARTICLE {num} error: {e} — retrying once")
                time.sleep(2)
                try:
                    raw = client.article(str(num))
                except RuntimeError as e2:
                    print(f"[fetch] ARTICLE {num} retry failed: {e2} — skipping")
                    continue
            except (ConnectionError, socket.timeout, OSError) as e:
                print(f"[fetch] connection error on {num}: {e} — reconnecting")
                client = reconnect()
                try:
                    raw = client.article(str(num))
                except Exception as e2:
                    print(f"[fetch] ARTICLE {num} after reconnect failed: {e2}")
                    continue

            ok = write_message_to_mbox(fp, raw)
            if ok:
                written += 1
            fp.flush()

            if (i + 1) % 50 == 0 or (i + 1) == len(to_fetch):
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed else 0
                print(
                    f"[fetch] {written}/{total} "
                    f"({written * 100 // total}%) | "
                    f"{rate:.1f} msg/s | "
                    f"last={num}"
                )

            time.sleep(FETCH_DELAY)

    print(f"[fetch] done. mbox has {written} messages")
    return written


# ─── Manifest ────────────────────────────────────────────────────────────────


def write_manifest(numbers, source="gmane-nntp"):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    total_bytes = 0
    if MBOX_PATH.exists():
        total_bytes = MBOX_PATH.stat().st_size
        with MBOX_PATH.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    manifest = {
        "source": source,
        "nntp_host": NNTP_HOST,
        "nntp_port": NNTP_PORT,
        "group": GROUP,
        "author_filter": AUTHOR_FILTER,
        "article_count": len(numbers),
        "mbox_path": str(MBOX_PATH.relative_to(PROJECT_ROOT)),
        "mbox_bytes": total_bytes,
        "mbox_sha256": h.hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"[manifest] written to {MANIFEST_PATH}")
    print(json.dumps(manifest, indent=2))


# ─── Orchestration ────────────────────────────────────────────────────────────


def connect():
    return NNTPClient(NNTP_HOST, NNTP_PORT, SOCKET_TIMEOUT)


def reconnect():
    print("[reconnect] establishing new NNTP connection")
    time.sleep(3)
    c = connect()
    c.group(GROUP)
    return c


def main():
    ap = argparse.ArgumentParser(description="Fetch Torvalds emails from gmane NNTP → mbox")
    ap.add_argument("--phase", choices=["discover", "fetch", "all"], default="all")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    numbers = []
    client = connect()

    try:
        if args.phase in ("discover", "all"):
            numbers = phase_discover(client, args.batch_size)
        if args.phase in ("fetch", "all"):
            if not numbers:
                numbers = load_discovered()
                numbers.sort()
            if not numbers and args.phase == "fetch":
                print("No article numbers found. Run --phase discover first.")
                sys.exit(1)
            phase_fetch(client, numbers)
    finally:
        try:
            client.quit()
        except Exception:
            pass

    # Manifest after fetch (or discover-only)
    final_numbers = load_discovered()
    final_numbers.sort()
    write_manifest(final_numbers)


if __name__ == "__main__":
    main()
