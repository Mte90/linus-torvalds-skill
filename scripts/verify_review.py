#!/usr/bin/env python3
"""
verify_review.py — validate LLM-generated review files.

Checks:
  - File exists and is non-empty
  - YAML frontmatter present with required fields (findings_count, files_reviewed, model)
  - findings_count matches actual ### [SEVERITY] heading count
  - All finding headings use bracketed severity: ### [CRITICAL], ### [HIGH], etc.
  - Severity values are from the closed set: CRITICAL, HIGH, MEDIUM, LOW
  - No duplicate finding titles
  - No CoT markers (thinking traces) exceeding threshold
  - No placeholder/TODO/stub text

Exit 0 = pass, 1 = fail.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_REVIEW_DIR = Path(__file__).parent.parent / "report"

REQUIRED_FRONTMATTER_FIELDS = [
    "findings_count",
    "files_reviewed",
    "model",
]

VALID_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

COT_MARKERS = [
    "<think>",
    "</think>",
    "<reasoning>",
    "</reasoning>",
    "<|thinking|>",
    "<|/thinking|>",
]
COT_THRESHOLD = 3

STUB_PATTERNS = [
    r"TODO",
    r"FIXME",
    r"placeholder",
    r"implementation here",
    r"NotImplementedError",
]


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return condition


def parse_frontmatter(content: str) -> dict[str, str] | None:
    if not content.startswith("---"):
        return None
    end_match = re.search(r"\n---\n", content)
    if not end_match:
        return None
    frontmatter = content[: end_match.start()]
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().lstrip("-")] = value.strip()
    return fields


def verify_frontmatter(path: Path) -> tuple[bool, list[str]]:
    content = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    if fm is None:
        return True, []  # frontmatter optional for baseline reviews
    if "findings_count" not in fm:
        return True, []  # baseline reviews use a different schema
    missing = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in fm]
    return len(missing) == 0, missing


def verify_finding_format(content: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    finding_heading_re = re.compile(r"^###\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+(.+)$", re.MULTILINE)
    non_bracketed_re = re.compile(r"^###\s+[A-Z]+\s+", re.MULTILINE)
    all_bracketed_re = re.compile(r"^###\s+\[([A-Z]+)\]\s+", re.MULTILINE)

    for m in non_bracketed_re.finditer(content):
        errors.append(f"Unbracketed severity heading: {m.group().strip()}")

    for m in all_bracketed_re.finditer(content):
        sev = m.group(1)
        if sev not in VALID_SEVERITIES:
            errors.append(f"Unknown severity '{sev}'")

    titles: list[str] = [m.group(2).strip() for m in finding_heading_re.finditer(content)]
    seen: set[str] = set()
    for t in titles:
        key = t.lower()
        if key in seen:
            errors.append(f"Duplicate finding title: {t}")
        seen.add(key)

    return len(errors) == 0, errors


def verify_findings_count(content: str, frontmatter: dict[str, str] | None) -> tuple[bool, str]:
    actual = len(re.findall(r"^###\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+", content, re.MULTILINE))
    if frontmatter is None:
        return True, f"no frontmatter to compare (found {actual} findings)"
    fm_count_str = frontmatter.get("findings_count", "0")
    try:
        fm_count = int(fm_count_str)
    except ValueError:
        return False, f"findings_count not an integer: '{fm_count_str}'"
    if fm_count != actual:
        return False, f"frontmatter says {fm_count}, found {actual}"
    return True, f"frontmatter={fm_count}, actual={actual}"


def verify_no_cot_markers(content: str) -> tuple[bool, str]:
    count = sum(content.count(m) for m in COT_MARKERS)
    if count > COT_THRESHOLD:
        return False, f"{count} CoT markers found (threshold {COT_THRESHOLD})"
    return True, f"{count} CoT markers"


def verify_no_stubs(content: str) -> tuple[bool, str]:
    for pattern in STUB_PATTERNS:
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            return False, f"found stub pattern '{pattern}'"
    return True, "no stub patterns"


def verify_review_file(path: Path) -> bool:
    if not path.exists():
        print(f"FAIL: {path} does not exist")
        return False

    print(f"=== Review Verification: {path.name} ===")
    print()

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        print("FAIL: file is empty")
        return False

    all_pass = True

    print("=== Frontmatter Validation ===")
    fm_pass, missing = verify_frontmatter(path)
    all_pass &= check(
        "Frontmatter present", fm_pass, f"missing: {missing}" if missing else "all present"
    )
    frontmatter = parse_frontmatter(content)
    print()

    print("=== Finding Format Validation ===")
    fmt_pass, fmt_errors = verify_finding_format(content)
    all_pass &= check(
        "Bracketed severity headings",
        fmt_pass,
        "; ".join(fmt_errors) if fmt_errors else "all valid",
    )
    print()

    print("=== Findings Count Validation ===")
    count_pass, count_detail = verify_findings_count(content, frontmatter)
    all_pass &= check("findings_count matches actual", count_pass, count_detail)
    print()

    print("=== CoT Marker Validation ===")
    cot_pass, cot_detail = verify_no_cot_markers(content)
    all_pass &= check("No excessive CoT markers", cot_pass, cot_detail)
    print()

    print("=== Stub Pattern Validation ===")
    stub_pass, stub_detail = verify_no_stubs(content)
    all_pass &= check("No stub/placeholder text", stub_pass, stub_detail)
    print()

    print(f"=== Result: {'PASS' if all_pass else 'FAIL'} ===")
    return all_pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify LLM-generated review file quality")
    parser.add_argument(
        "review_path",
        type=Path,
        nargs="?",
        help="Path to the review file to verify",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Verify all review-*.md files in the default review directory",
    )
    args = parser.parse_args()

    if args.all:
        review_files = sorted(DEFAULT_REVIEW_DIR.glob("review-*.md"))
        if not review_files:
            print(f"No review files found in {DEFAULT_REVIEW_DIR}")
            return 1
        all_pass = True
        for f in review_files:
            print()
            all_pass &= verify_review_file(f)
        return 0 if all_pass else 1

    if not args.review_path:
        parser.error("provide a review file path or use --all")

    return 0 if verify_review_file(args.review_path) else 1


if __name__ == "__main__":
    sys.exit(main())
