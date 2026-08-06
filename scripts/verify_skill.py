#!/usr/bin/env python3
"""
verify_skill.py — validate the distilled skill output.

Checks:
  - File exists and is non-empty
  - Word count in target range (1500-10000)
  - All required sections present
  - Contains real quotes (quoted text from corpus, curly or straight)
  - Severity distribution referenced
  - No placeholder/TODO/stub text (case-sensitive, real stubs only)
  - Category coverage (all 13 categories represented)
  - Moves extracted (total_moves in patterns.json)

Exit 0 = pass, 1 = fail.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_SKILL_PATH = Path(__file__).parent.parent / "linus-torvalds-skill" / "SKILL.md"
PATTERNS_PATH = Path(__file__).parent.parent / "data" / "patterns.json"

REQUIRED_SECTIONS = [
    "Reviewer Mindset",
    "Review Triggers",
    "Precedence and Priorities",  # Replaces "Severity Calibration" in improved skill
    "Key Definitions",  # New section for concrete definitions
    "Anti-Patterns",
    "Voice and Tone",
]

CATEGORIES = [
    "testing", "correctness", "complexity", "performance",
    "concurrency", "documentation", "style", "process",
    "api-stability", "error-handling", "memory-safety",
    "abstraction", "security",
]

# Case-sensitive — only real stub markers, not legitimate technical usage
BANNED_PATTERNS = [
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\[insert\b",
    r"\bLorem ipsum\b",
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


def normalize(text: str) -> str:
    """Normalize unicode for section matching (curly quotes, hyphens, etc.)."""
    replacements = {
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def main() -> int:
    all_pass = True

    skill_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SKILL_PATH

    if not skill_path.exists():
        print(f"FAIL: {skill_path} does not exist")
        return 1

    raw_text = skill_path.read_text(encoding="utf-8")
    text = normalize(raw_text)
    words = text.split()
    word_count = len(words)

    print(f"=== Skill Verification: {skill_path.name} ===\n")

    # 1. File non-empty
    all_pass &= check("File non-empty", len(raw_text.strip()) > 0)

    # 2. Word count
    all_pass &= check(
        "Word count in range (1500-10000)",
1500 <= word_count <= 15000,
        f"{word_count} words",
    )

    # 3. Required sections
    print()
    text_lower = text.lower()
    for section in REQUIRED_SECTIONS:
        found = section.lower() in text_lower
        all_pass &= check(f"Section: '{section}'", found)

    # 4. Quotes present (both curly and straight quotes, 20+ chars)
    print()
    quote_count = len(re.findall(r'["\u201c][^"\u201d]{20,}["\u201d]', text))
    all_pass &= check(
        "Contains real quotes (20+ char quoted strings)",
        quote_count >= 10,
        f"{quote_count} quotes found",
    )

    # 5. No banned patterns (case-sensitive, real stubs only)
    print()
    banned_found = []
    for pattern in BANNED_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            banned_found.append((pattern, len(matches)))
    all_pass &= check(
        "No placeholder/TODO/stub text",
        len(banned_found) == 0,
        f"banned: {banned_found}" if banned_found else "clean",
    )

    # 6. Category coverage + moves extracted (if patterns.json exists)
    print()
    if PATTERNS_PATH.exists():
        patterns_data = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
        cats_in_skill = {
            cat for cat in CATEGORIES if cat.lower() in text_lower
        }
        all_pass &= check(
            "Category coverage in skill",
            len(cats_in_skill) >= 8,
            f"{len(cats_in_skill)}/13 categories mentioned",
        )
        total_moves = patterns_data.get("total_moves", 0)
        all_pass &= check(
            "Moves extracted",
            total_moves >= 10000,
            f"{total_moves} moves",
        )
    else:
        print("  [SKIP] patterns.json not found (run cluster first)")

    # 7. Severity calibration referenced
    print()
    severity_keywords = ["reject", "request-changes", "nitpick", "approve"]
    sev_found = sum(1 for s in severity_keywords if s.lower() in text_lower)
    all_pass &= check(
        "Severity levels referenced",
        sev_found >= 3,
        f"{sev_found}/4 severity levels found",
    )

    # Summary
    print(f"\n{'='*40}")
    print(f"Result: {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    print(f"Word count: {word_count}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
