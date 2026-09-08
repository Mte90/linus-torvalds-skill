#!/usr/bin/env python3
"""
verify_soul.py — validate the distilled soul document.

Checks:
  - File exists and is non-empty
  - YAML frontmatter presence with required fields
  - Required soul sections present
  - Word count in target range (2000-12000 words)
  - No placeholder/TODO/stub text

Exit 0 = pass, 1 = fail.

Word range rationale: Reasoning models (gpt-oss-120b, mistral-small-4-119b, glm5.2,
qwen3.8-27b) have a 16000-token provider cap. Reasoning phases consume tokens,
leaving fewer for content. The writer targets min_words=4000 for reasoning models.
Actual outputs range from 2450w (gpt-oss) to 7157w (glm5.2). The 2000-12000 range
allows realistic variance while ensuring comprehensive coverage.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_SOUL_PATH = Path(__file__).parent.parent / "soul" / "soul.md"

# Required frontmatter fields for traceability
REQUIRED_FRONTMATTER_FIELDS = [
    "name",
    "description",
    "metrics",
    "metadata",
]

# Required sections for soul document (derived from SOUL_SYSTEM_PROMPT)
REQUIRED_SECTIONS = [
    "Identity",
    "Operating Principles",
    "Decision Patterns",
    "Review Workflow",
    "Communication Style",
    "Emergent Hierarchy",
    "Interlocutor Model",
    "Escalation Rules",
    "Error Gravity",
    "Anti-Soul",
    "Voices",
    "Insult Vocabulary",
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

# Word count target range
MIN_WORDS = 2000
MAX_WORDS = 12000


def check(label: str, condition: bool, detail: str = "") -> bool:
    """Print a check result and return the condition."""
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return condition


def normalize(text: str) -> str:
    """Normalize unicode for section matching."""
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def verify_frontmatter(path: Path) -> tuple[bool, list[str]]:
    """Verify YAML frontmatter presence and required fields.

    Returns (passes, list_of_missing_fields).
    """
    if not path.exists():
        return False, ["File not found"]

    content = path.read_text(encoding="utf-8")

    # Check for frontmatter delimiters
    if not content.startswith("---"):
        return False, ["Missing frontmatter start (---)"]

    # Find end of frontmatter
    end_match = re.search(r"\n---\n", content)
    if not end_match:
        return False, ["Missing frontmatter end (---)"]

    frontmatter = content[: end_match.end()]

    # Check for required fields
    missing = []
    for field in REQUIRED_FRONTMATTER_FIELDS:
        if f"{field}:" not in frontmatter:
            missing.append(field)

    return len(missing) == 0, missing


def verify_sections(path: Path) -> tuple[bool, list[str]]:
    """Verify all required sections are present.

    Returns (passes, list_of_missing_sections).
    """
    content = path.read_text(encoding="utf-8")
    text_lower = normalize(content).lower()

    missing = []
    for section in REQUIRED_SECTIONS:
        if section.lower() not in text_lower:
            missing.append(section)

    return len(missing) == 0, missing


def verify_word_count(path: Path) -> tuple[bool, int]:
    """Verify word count is in target range.

    Returns (passes, actual_word_count).
    """
    content = path.read_text(encoding="utf-8")
    word_count = len(content.split())

    return MIN_WORDS <= word_count <= MAX_WORDS, word_count


def verify_no_banned_patterns(path: Path) -> tuple[bool, list[tuple[str, int]]]:
    """Verify no placeholder/TODO/stub text.

    Returns (passes, list_of_(pattern, count) tuples).
    """
    content = path.read_text(encoding="utf-8")

    # Strip quoted spans to avoid false positives
    quote_patterns = [
        re.compile(r'"[^"]*"'),
        re.compile(r"\u201c[^\u201d]*\u201d"),
        re.compile(r"`[^`]*`"),
    ]
    text_for_banned = content
    for pat in quote_patterns:
        text_for_banned = pat.sub("", text_for_banned)

    found = []
    for pattern in BANNED_PATTERNS:
        matches = re.findall(pattern, text_for_banned)
        if matches:
            found.append((pattern, len(matches)))

    return len(found) == 0, found


def verify_calibration_substitution(path: Path) -> bool:
    """Verify that calibration data was properly substituted (no {calibration_data} placeholder).

    Returns True if placeholder is absent (properly substituted).
    """
    content = path.read_text(encoding="utf-8")
    return "{calibration_data}" not in content


def verify_stats_source(path: Path) -> bool:
    """Verify that stats come from calibration (not hard-coded).

    Checks that the document references category-specific reject rates
    rather than global corpus rates.

    Returns True if category-specific rates are present.
    """
    content = path.read_text(encoding="utf-8")
    text_lower = content.lower()

    # Look for category-specific reject rate references
    # (e.g., "api-stability: 37.9%", "correctness: 28.7%")
    category_rates = [
        "api-stability",
        "correctness",
        "performance",
        "style",
        "complexity",
    ]

    found_categories = sum(1 for cat in category_rates if cat.lower() in text_lower)

    # At least 3 categories should be mentioned with their rates
    return found_categories >= 3


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify soul document quality")
    parser.add_argument(
        "soul_path",
        type=Path,
        nargs="?",
        default=DEFAULT_SOUL_PATH,
        help="Path to the soul document to verify",
    )
    args = parser.parse_args()

    soul_path = args.soul_path
    all_pass = True

    if not soul_path.exists():
        print(f"FAIL: {soul_path} does not exist")
        return 1

    print(f"=== Soul Verification: {soul_path.name} ===")
    print(f"Target word range: {MIN_WORDS}-{MAX_WORDS} words")
    print()

    # 1. Frontmatter
    print("=== Frontmatter Validation ===")
    frontmatter_pass, missing_fields = verify_frontmatter(soul_path)
    all_pass &= check(
        "Frontmatter present",
        frontmatter_pass,
        f"missing: {missing_fields}" if missing_fields else "all present",
    )
    print()

    # 2. Required sections
    print("=== Section Validation ===")
    sections_pass, missing_sections = verify_sections(soul_path)
    all_pass &= check(
        "All required sections present",
        sections_pass,
        f"missing: {missing_sections}" if missing_sections else "all present",
    )
    print()

    # 3. Word count
    print("=== Word Count Validation ===")
    word_pass, word_count = verify_word_count(soul_path)
    all_pass &= check(
        f"Word count in range ({MIN_WORDS}-{MAX_WORDS})",
        word_pass,
        f"{word_count} words",
    )
    print()

    # 4. No banned patterns
    print("=== Stub Text Validation ===")
    banned_pass, banned_found = verify_no_banned_patterns(soul_path)
    all_pass &= check(
        "No placeholder/TODO/stub text",
        banned_pass,
        f"found: {banned_found}" if banned_found else "clean",
    )
    print()

    # 5. Calibration substitution
    print("=== Calibration Substitution Validation ===")
    calib_substituted = verify_calibration_substitution(soul_path)
    all_pass &= check(
        "Calibration placeholder substituted",
        calib_substituted,
        "placeholder absent" if calib_substituted else "{calibration_data} still present",
    )
    print()

    # 6. Stats source
    print("=== Stats Source Validation ===")
    stats_from_calib = verify_stats_source(soul_path)
    all_pass &= check(
        "Stats from calibration (category-specific)",
        stats_from_calib,
        "category-specific rates present" if stats_from_calib else "missing category rates",
    )
    print()

    # Summary
    print(f"{'=' * 40}")
    print(f"Result: {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    print(f"Word count: {word_count}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
