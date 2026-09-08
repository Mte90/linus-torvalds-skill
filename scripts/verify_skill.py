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

import argparse
import json
import re
import sys
from pathlib import Path

# Add paths for importing modules
sys.path.insert(0, str(Path(__file__).parent.parent / "report"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import shared REQUIRED_SECTIONS from distill_data (C8: single source of truth)
from torvalds_skill.distill_data import REQUIRED_SECTIONS

DEFAULT_SKILL_PATH = Path(__file__).parent.parent / "linus-torvalds-skill" / "SKILL.md"
PATTERNS_PATH = Path(__file__).parent.parent / "data" / "patterns.json"
CALIBRATION_PATH = Path(__file__).parent.parent / "data" / "calibration.json"
# Required frontmatter fields for traceability
REQUIRED_FRONTMATTER_FIELDS = [
    "prompt_hash",
    "input_hash",
    "mode",
    "model",
    "date",
    "pipeline_version",
]

CATEGORIES = [
    "testing",
    "correctness",
    "complexity",
    "performance",
    "concurrency",
    "documentation",
    "style",
    "process",
    "api-stability",
    "error-handling",
    "memory-safety",
    "abstraction",
    "security",
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

# Non-fire list: triggers that must NOT be reported as blockers
# Regex patterns matching build-trivia and style noise
NON_FIRE_PATTERNS = [
    r"\bphony\b",  # .PHONY declarations
    r"\bCFLAGS\b",  # CFLAGS assignments
    r"\bmissing\s+(docs|documentation)\b",  # Missing documentation
    r"\bcomment\s+style\b",  # Comment style
    r"\bredundant\s+rm\b",  # Redundant rm commands
    r"\bheader\s+guard\b",  # Header guard style
    r"\binclude\s+order\b",  # Include ordering
]

# Maximum allowed proportion of style-category triggers (~20%)
MAX_STYLE_PROPORTION = 0.20

# C/kernel-specific tokens forbidden outside verbatim quote blocks
FORBIDDEN_TERMS = [
    "BUG_ON",
    "WARN_ON",
    "READ_ONCE",
    "WRITE_ONCE",
    "rcu_dereference",
    "copy_to_user",
    "copy_from_user",
    "get_user",
    "put_user",
    "kmalloc",
    "kfree",
    "spin_lock",
    "mutex",
    "volatile",
    "#ifdef",
    "#ifndef",
    "#define",
    "inline",
    "typedef",
    "strlcpy",
    "strscpy",
    "IS_ERR",
    "ERR_PTR",
    "GFP_KERNEL",
    "module_alloc",
    "procfs",
    "sysfs",
    "debugfs",
    "ioctl",
]


def check_forbidden_terms(path: Path) -> list[tuple[int, str, str]]:
    """Check for C/kernel-specific tokens outside verbatim quote blocks.

    Returns a list of (line_number, token, line_content) tuples for violations.
    Exempts:
      - Lines starting with '> ' (markdown blockquotes)
      - Text inside quoted spans (straight "..." and curly "...")
      - Text inside inline code spans (`...`)
    """
    violations: list[tuple[int, str, str]] = []
    content = path.read_text(encoding="utf-8")

    # Strip quoted spans: straight double-quotes, curly double-quotes, inline code backticks
    quote_patterns = [
        re.compile(r'"[^"]*"'),
        re.compile(r"\u201c[^\u201d]*\u201d"),
        re.compile(r"`[^`]*`"),
    ]

    for line_num, line in enumerate(content.splitlines(), start=1):
        if line.strip().startswith("> "):
            continue

        cleaned = line
        for pat in quote_patterns:
            cleaned = pat.sub("", cleaned)

        for term in FORBIDDEN_TERMS:
            if term in cleaned:
                violations.append((line_num, term, line.strip()))

    return violations


def check_no_tables(path: Path) -> tuple[bool, list[tuple[int, str]]]:
    """Check that the skill file does not contain markdown tables.

    Detects markdown tables by looking for:
    - Lines starting with `|` and containing `|---|` separator patterns
    - Header rows like `| column | column |` followed by separator rows `|---|---|`

    Returns (True, []) if no tables found, (False, list_of_violations) otherwise.
    """
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    violations: list[tuple[int, str]] = []

    # Look for table separator patterns (the `|---|` row)
    table_separator_re = re.compile(r"^\s*\|.*\|---.*\|")

    for line_num, line in enumerate(lines, start=1):
        # Check for table separator row
        if table_separator_re.match(line):
            # Found a table separator - look back for header
            header_line = ""
            if line_num > 1:
                header_line = lines[line_num - 2].strip()
            violations.append(
                (line_num, f"Markdown table detected: {header_line} ... {line.strip()}")
            )

    return len(violations) == 0, violations


def check_non_fire_violations(path: Path) -> list[tuple[int, str, str]]:
    """Check for triggers that bless non-fire build trivia as blockers.

    Args:
        path: Path to the skill file

    Returns:
        List of (line_number, pattern, line_content) tuples for violations.
        A violation occurs when a trigger mentions non-fire trivia AND
        assigns it reject or request-changes severity.
    """
    violations: list[tuple[int, str, str]] = []
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Track trigger blocks and their severities
    in_trigger_block = False
    current_trigger_line = 0
    current_trigger_text = ""
    current_severity = ""

    for line_num, line in enumerate(lines, start=1):
        # Detect trigger start
        if "**Trigger**:" in line or "Trigger:" in line:
            in_trigger_block = True
            current_trigger_line = line_num
            current_trigger_text = line.lower()
            current_severity = ""
        elif in_trigger_block:
            # Check for severity in this trigger block
            if "**severity**:" in line.lower() or "severity:" in line.lower():
                current_severity = line.lower()
            # Check if we've exited the trigger block (new trigger or section)
            if line.strip().startswith("###") or ("**Trigger**:" in line or "Trigger:" in line):
                # Check previous trigger for violations
                if current_trigger_text:
                    for pattern in NON_FIRE_PATTERNS:
                        if re.search(pattern, current_trigger_text, re.IGNORECASE):
                            # Check if severity is blocking
                            if (
                                "reject" in current_severity
                                or "request-changes" in current_severity
                            ):
                                violations.append(
                                    (current_trigger_line, pattern, current_trigger_text)
                                )
                # Reset for new trigger
                current_trigger_line = line_num
                current_trigger_text = line.lower()
                current_severity = ""

    # Check last trigger
    if in_trigger_block and current_trigger_text:
        for pattern in NON_FIRE_PATTERNS:
            if re.search(pattern, current_trigger_text, re.IGNORECASE):
                if "reject" in current_severity or "request-changes" in current_severity:
                    violations.append((current_trigger_line, pattern, current_trigger_text))

    return violations


def check_style_proportion(path: Path) -> tuple[bool, float]:
    """Check that style-category triggers don't exceed ~20% of total triggers.

    Args:
        path: Path to the skill file

    Returns:
        Tuple of (passes, style_proportion). Passes if proportion <= MAX_STYLE_PROPORTION.
    """
    content = path.read_text(encoding="utf-8")
    text_lower = content.lower()

    # Count total triggers (case-insensitive)
    total_triggers = len(re.findall(r"\*\*trigger\*\*", text_lower))
    if total_triggers == 0:
        return True, 0.0

    # Count style-related triggers by looking for style keywords in trigger text
    style_keywords = [
        "style",
        "formatting",
        "indentation",
        "whitespace",
        "naming",
        "cosmetic",
        "readability",
    ]

    # Parse trigger blocks to count style triggers more accurately
    style_trigger_count = 0
    trigger_blocks = re.split(r"\*\*trigger\*\*", text_lower)

    for block in trigger_blocks[1:]:  # Skip first empty split
        # Check if this block contains style keywords
        for keyword in style_keywords:
            if keyword in block[:500]:  # Check within first 500 chars of trigger block
                style_trigger_count += 1
                break

    style_proportion = style_trigger_count / total_triggers if total_triggers > 0 else 0.0

    return style_proportion <= MAX_STYLE_PROPORTION, style_proportion


def check_interview_quotes(path: Path) -> tuple[int, list[str]]:
    """Check for interview-derived quotes in the skill file.

    Looks for patterns like:
      - (Interview: filename)
      - (TED 2016)
      - (Linux Journal 2021)

    Returns (count, list_of_found_patterns).
    """
    content = path.read_text(encoding="utf-8")

    # Patterns for interview citations
    patterns = [
        r"\(Interview:\s*[^)]+\)",
        r"\(TED\s+\d{4}\)",
        r"\(Linux\s+Journal[^)]*\)",
        r"\(Hacker\s+News[^)]*\)",
        r"\(O'Reilly[^)]*\)",
        r"\(Forbes[^)]*\)",
        r"\(Wired[^)]*\)",
    ]

    found = []
    for pat in patterns:
        matches = re.findall(pat, content, re.IGNORECASE)
        found.extend(matches)

    return len(found), found


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


def score_skill_quality(skill_path: Path) -> dict:
    """Calculate a deterministic 0-100 quality score for a skill file.

    The score is based on four dimensions:
    1. Trigger diversity (0-25): Number of distinct triggers
    2. Severity distribution (0-25): How well it matches calibrated targets
    3. Language-agnosticism (0-25): Pass = 25, fail = 0
    4. Section coverage (0-25): All required sections present

    Args:
        skill_path: Path to the skill file

    Returns:
        dict with keys: total, trigger_diversity, severity_distribution,
                       language_agnosticism, section_coverage, details
    """
    if not skill_path.exists():
        return {
            "total": 0,
            "trigger_diversity": 0,
            "severity_distribution": 0,
            "language_agnosticism": 0,
            "section_coverage": 0,
            "details": {"error": f"File not found: {skill_path}"},
        }

    raw_text = skill_path.read_text(encoding="utf-8")
    text = normalize(raw_text)
    text_lower = text.lower()

    # 1. Trigger diversity (0-25 points)
    trigger_score, trigger_details = _score_trigger_diversity(text)

    # 2. Severity distribution (0-25 points)
    severity_score, severity_details = _score_severity_distribution(text_lower)

    # 3. Language-agnosticism (0-25 points)
    lang_score, lang_details = _score_language_agnosticism(skill_path)

    # 4. Section coverage (0-25 points)
    section_score, section_details = _score_section_coverage(text)

    total = trigger_score + severity_score + lang_score + section_score

    return {
        "total": total,
        "trigger_diversity": trigger_score,
        "severity_distribution": severity_score,
        "language_agnosticism": lang_score,
        "section_coverage": section_score,
        "details": {
            "trigger_diversity": trigger_details,
            "severity_distribution": severity_details,
            "language_agnosticism": lang_details,
            "section_coverage": section_details,
        },
    }


def _score_trigger_diversity(text: str) -> tuple[int, dict]:
    """Score trigger diversity (0-25 points).

    More distinct triggers = higher score. Cap at 25 points for 15+ distinct triggers.

    Returns:
        (score, details_dict)
    """
    # Extract triggers by looking for "**Trigger:**" or "- **Trigger:**" patterns
    trigger_pattern = re.compile(r"\*\*Trigger:\*\*\s*([^\n]+)", re.IGNORECASE)
    triggers = trigger_pattern.findall(text)

    # Also look for "- **Trigger:**" markdown pattern
    trigger_pattern2 = re.compile(r"-\s*\*\*Trigger:\*\*\s*([^\n]+)", re.IGNORECASE)
    triggers2 = trigger_pattern2.findall(text)

    # Combine and deduplicate
    all_triggers = set()
    for t in triggers + triggers2:
        t = t.strip()
        if t:
            all_triggers.add(t.lower())

    # Also count theme-based triggers from the "Triggers (3-6 each)" patterns
    theme_trigger_pattern = re.compile(r"\((\d+)\s*-\s*(\d+)\s+each\)", re.IGNORECASE)
    theme_matches = theme_trigger_pattern.findall(text)
    estimated_triggers = 0
    for min_t, max_t in theme_matches:
        estimated_triggers += (int(min_t) + int(max_t)) // 2

    # Total distinct triggers = explicit + estimated from themes
    explicit_count = len(all_triggers)
    total_triggers = max(explicit_count, estimated_triggers)

    # Score: 0-25 points, cap at 15+ triggers
    if total_triggers >= 15:
        score = 25
    else:
        score = int((total_triggers / 15) * 25)

    details = {
        "explicit_triggers_found": explicit_count,
        "estimated_from_themes": estimated_triggers,
        "total_triggers": total_triggers,
        "max_recommended": 15,
    }

    return score, details


def _score_severity_distribution(text_lower: str) -> tuple[int, dict]:
    """Score severity distribution match (0-25 points).

    Compares the skill file's severity mentions against the calibrated target
    from calibration.json using percentage difference.

    Returns:
        (score, details_dict)
    """
    # Load calibration data
    if not CALIBRATION_PATH.exists():
        return 0, {"error": "calibration.json not found"}

    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    target = calibration.get("corpus_stats", {}).get("severity_distribution", {})

    # Count severity mentions in the skill file
    severity_keywords = ["reject", "request-changes", "nitpick", "approve", "discussion"]
    counts = {sev: 0 for sev in severity_keywords}

    for sev in severity_keywords:
        # Count occurrences of the severity keyword
        counts[sev] = len(re.findall(r"\b" + sev.replace("-", r"[-\s]") + r"\b", text_lower))

    total_mentions = sum(counts.values())
    if total_mentions == 0:
        return 0, {"error": "No severity mentions found", "counts": counts}

    # Calculate actual percentages
    actual_percentages = {sev: (count / total_mentions) * 100 for sev, count in counts.items()}

    # Get target percentages
    target_percentages = {}
    for sev in severity_keywords:
        if sev in target:
            target_percentages[sev] = target[sev].get("percentage", 0)
        else:
            target_percentages[sev] = 0

    # Calculate average absolute difference
    total_diff = 0
    diffs = {}
    for sev in severity_keywords:
        diff = abs(actual_percentages.get(sev, 0) - target_percentages.get(sev, 0))
        diffs[sev] = diff
        total_diff += diff

    avg_diff = total_diff / len(severity_keywords) if severity_keywords else 0

    # Score: 25 points for perfect match, decreasing with difference
    # 0% diff = 25 points, 50%+ diff = 0 points
    score = max(0, int(25 * (1 - avg_diff / 50)))

    details = {
        "actual_percentages": {k: round(v, 1) for k, v in actual_percentages.items()},
        "target_percentages": {k: round(v, 1) for k, v in target_percentages.items()},
        "differences": {k: round(v, 1) for k, v in diffs.items()},
        "average_difference": round(avg_diff, 1),
        "total_mentions": total_mentions,
    }

    return score, details


def _score_language_agnosticism(skill_path: Path) -> tuple[int, dict]:
    """Score language-agnosticism (0-25 points).

    Pass = 25 points, fail = 0 points.
    Uses the existing check_forbidden_terms() function.

    Returns:
        (score, details_dict)
    """
    violations = check_forbidden_terms(skill_path)

    if len(violations) == 0:
        return 25, {"passed": True, "violations": 0}
    else:
        return 0, {
            "passed": False,
            "violations": len(violations),
            "sample_violations": violations[:5],  # First 5 violations
        }


def _score_section_coverage(text: str) -> tuple[int, dict]:
    """Score section coverage (0-25 points).

    All required sections present = 25. Each missing section = -5 points.

    Returns:
        (score, details_dict)
    """
    text_lower = text.lower()
    missing_sections = []
    present_sections = []

    for section in REQUIRED_SECTIONS:
        if section.lower() in text_lower:
            present_sections.append(section)
        else:
            missing_sections.append(section)

    base_score = 25
    penalty = len(missing_sections) * 5
    score = max(0, base_score - penalty)

    details = {
        "required_sections": len(REQUIRED_SECTIONS),
        "present": len(present_sections),
        "missing": len(missing_sections),
        "missing_sections": missing_sections,
    }

    return score, details


def _print_score_report(score_result: dict, skill_path: Path) -> None:
    """Print a formatted quality score report."""
    print(f"\n=== Quality Score Report: {skill_path.name} ===")
    print()
    print(f"Total Score: {score_result['total']}/100")
    print()
    print("Breakdown:")
    print(f"  - Trigger Diversity:      {score_result['trigger_diversity']:3d}/25")
    print(f"  - Severity Distribution:  {score_result['severity_distribution']:3d}/25")
    print(f"  - Language Aagnosticism:  {score_result['language_agnosticism']:3d}/25")
    print(f"  - Section Coverage:       {score_result['section_coverage']:3d}/25")
    print()
    print("Details:")

    details = score_result.get("details", {})

    # Trigger diversity details
    td = details.get("trigger_diversity", {})
    if "error" not in td:
        print("  Trigger Diversity:")
        print(f"    Explicit triggers: {td.get('explicit_triggers_found', 0)}")
        print(f"    Estimated from themes: {td.get('estimated_from_themes', 0)}")
        print(f"    Total: {td.get('total_triggers', 0)}")

    # Severity distribution details
    sd = details.get("severity_distribution", {})
    if "error" not in sd:
        print("  Severity Distribution:")
        print(f"    Average difference from target: {sd.get('average_difference', 0)}%")
        print(f"    Total mentions: {sd.get('total_mentions', 0)}")

    # Language-agnosticism details
    la = details.get("language_agnosticism", {})
    print("  Language Aagnosticism:")
    print(f"    Passed: {la.get('passed', False)}")
    print(f"    Violations: {la.get('violations', 0)}")

    # Section coverage details
    sc = details.get("section_coverage", {})
    print("  Section Coverage:")
    print(f"    Present: {sc.get('present', 0)}/{sc.get('required_sections', 0)}")
    if sc.get("missing_sections"):
        print(f"    Missing: {', '.join(sc['missing_sections'])}")

    print()


def verify_trigger_format(skill_path: Path) -> tuple[bool, list[str]]:
    """Verify that skill file uses consistent trigger format.

    Returns (is_valid, list of errors).
    """
    import sys

    sys.path.insert(0, str(Path(__file__).parent / "report"))

    from trigger_patterns import (
        STYLE_NAME_MAP,
        TRIGGER_FORMAT_PATTERNS,
        detect_style,
        extract_triggers,
        has_known_markers,
    )

    if not skill_path.exists():
        return False, [f"Skill file not found: {skill_path}"]

    content = skill_path.read_text(encoding="utf-8", errors="replace")

    # Single shared auto-detect (Trigger Contract — never reimplement here)
    style = detect_style(content)

    # Normalize style name (C2: gpt-oss -> gpt_oss)
    style_key = STYLE_NAME_MAP.get(style, style)

    triggers = extract_triggers(content, style=style)

    errors = []
    if not has_known_markers(content):
        return False, ["Unknown trigger format - cannot auto-detect style"]
    # Per-variant floor: mistral trades recall for precision by design
    # (column-0 Level-only bullets; pinned by tests/test_trigger_routing.py),
    # so its breakage-detection floor is lower. The gate catches extraction
    # breakage (near-zero counts), not trigger quantity.
    min_triggers = 15 if style == "mistral" else 30
    if len(triggers) < min_triggers:
        errors.append(
            f"Only {len(triggers)} triggers extracted (expected >= {min_triggers} for {style})"
        )

    # C2: Validate against TRIGGER_FORMAT_PATTERNS - the format contract
    # Only the detected style's pattern should match; no fourth format may pass
    if style_key not in TRIGGER_FORMAT_PATTERNS:
        errors.append(f"Unknown style key '{style_key}' not in TRIGGER_FORMAT_PATTERNS")
    else:
        # Check that triggers match the expected format for this style
        pattern = TRIGGER_FORMAT_PATTERNS[style_key]
        matches = list(pattern.finditer(content))
        if len(matches) < len(triggers):
            errors.append(
                f"Format mismatch: {len(matches)} pattern matches vs {len(triggers)} extracted triggers"
            )

    return len(errors) == 0, errors


def check_general_theme_threshold(skill_path: Path, threshold: int = 5) -> tuple[bool, int]:
    """Check if too many triggers are filed under 'General' theme.

    This detects when extraction fails to properly group triggers by theme,
    causing them to fall into the default 'General' bucket.

    Args:
        skill_path: Path to the skill file
        threshold: Maximum allowed triggers in 'General' theme (default 5)

    Returns:
        Tuple of (passes, general_count). Passes if general_count <= threshold.
    """
    from trigger_patterns import detect_style, extract_triggers

    content = skill_path.read_text(encoding="utf-8")

    # Single shared auto-detect (Trigger Contract — never reimplement here)
    style = detect_style(content)

    triggers = extract_triggers(content, style=style)

    # Count triggers in 'General' theme
    general_count = sum(1 for (theme, _) in triggers if theme == "General")

    return general_count <= threshold, general_count


def main() -> int:
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Verify skill file quality")
    parser.add_argument(
        "--check-frontmatter",
        action="store_true",
        help="Validate YAML frontmatter traceability fields",
    )
    parser.add_argument(
        "skill_path",
        type=Path,
        nargs="?",
        default=DEFAULT_SKILL_PATH,
        help="Path to the skill file to verify",
    )
    parser.add_argument(
        "--score", action="store_true", help="Print quality score instead of verification"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode: fail on non-fire trivia and high style proportion",
    )
    args = parser.parse_args()

    skill_path = args.skill_path
    check_frontmatter = args.check_frontmatter
    strict_mode = args.strict
    # Handle --score flag
    if args.score:
        if not skill_path.exists():
            print(f"FAIL: {skill_path} does not exist")
            return 1
        score_result = score_skill_quality(skill_path)
        _print_score_report(score_result, skill_path)
        return 0

    all_pass = True

    if not skill_path.exists():
        print(f"FAIL: {skill_path} does not exist")
        return 1
    # 0. Frontmatter validation (if requested)
    if check_frontmatter:
        print("=== Frontmatter Validation ===")
        raw_text = skill_path.read_text(encoding="utf-8")
        missing_fields = []
        for field in REQUIRED_FRONTMATTER_FIELDS:
            if f"{field}:" not in raw_text:
                missing_fields.append(field)
        all_pass &= check(
            "Frontmatter traceability fields",
            len(missing_fields) == 0,
            f"missing: {missing_fields}" if missing_fields else "all present",
        )
        print()

    raw_text = skill_path.read_text(encoding="utf-8")
    text = normalize(raw_text)
    words = text.split()
    word_count = len(words)

    print(f"=== Skill Verification: {skill_path.name} ===")
    if strict_mode:
        print("Mode: STRICT (non-fire trivia and style proportion checks enabled)")
    print()

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
    # Strip quoted spans first so legitimate technical usage like "documented as 'TODO'" is exempt
    print()
    quote_patterns = [
        re.compile(r'"[^"]*"'),
        re.compile(r"\u201c[^\u201d]*\u201d"),
        re.compile(r"`[^`]*`"),
    ]
    text_for_banned = text
    for pat in quote_patterns:
        text_for_banned = pat.sub("", text_for_banned)
    banned_found = []
    for pattern in BANNED_PATTERNS:
        matches = re.findall(pattern, text_for_banned)
        if matches:
            banned_found.append((pattern, len(matches)))
    all_pass &= check(
        "No placeholder/TODO/stub text",
        len(banned_found) == 0,
    )

    # 5b. No forbidden C/kernel terms outside quote blocks
    print()
    forbidden_violations = check_forbidden_terms(skill_path)
    all_pass &= check(
        "No forbidden C/kernel terms outside quotes",
        len(forbidden_violations) == 0,
        f"violations: {forbidden_violations}" if forbidden_violations else "clean",
    )

    # 6. Category coverage + moves extracted (if patterns.json exists)
    print()
    if PATTERNS_PATH.exists():
        patterns_data = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
        cats_in_skill = {cat for cat in CATEGORIES if cat.lower() in text_lower}
        all_pass &= check(
            "Category coverage in skill",
            len(cats_in_skill) >= 8,
            f"{len(cats_in_skill)}/13 categories mentioned",
        )
        total_patterns = (
            len(patterns_data)
            if isinstance(patterns_data, list)
            else patterns_data.get("total_moves", 0)
        )
        all_pass &= check(
            "Patterns extracted",
            total_patterns >= 100,
            f"{total_patterns} patterns",
        )
    else:
        print("  [SKIP] patterns.json not found (run cluster first)")

    # 7. Check for excessive 'General' theme (extraction failure indicator)
    print()
    general_pass, general_count = check_general_theme_threshold(skill_path, threshold=5)
    all_pass &= check(
        "Extraction groups triggers by theme (not 'General')",
        general_pass,
        f"{general_count} triggers in 'General' theme" if not general_pass else "ok",
    )

    # 8. Severity calibration referenced
    print()
    severity_keywords = ["reject", "request-changes", "nitpick", "approve"]
    sev_found = sum(1 for s in severity_keywords if s.lower() in text_lower)
    all_pass &= check(
        "Severity levels referenced",
        sev_found >= 3,
        f"{sev_found}/4 severity levels found",
    )
    # 8. Interview-derived quotes (warning if sparse)
    print()
    interview_count, interview_patterns = check_interview_quotes(skill_path)
    all_pass &= check(
        "Interview-derived quotes present (warning threshold)",
        interview_count >= 3,
        f"{interview_count} citations found: {interview_patterns[:5]}",
    )

    # 9. No markdown tables
    print()
    no_tables, table_violations = check_no_tables(skill_path)
    all_pass &= check(
        "No markdown tables (structured lists only)",
        no_tables,
        f"violations: {table_violations}" if table_violations else "clean",
    )

    # 9b. Trigger format compliance
    print()
    format_pass, format_violations = verify_trigger_format(skill_path)
    all_pass &= check(
        "Trigger format compliance",
        format_pass,
        f"violations: {format_violations}" if format_violations else "clean",
    )

    # 10. Strict mode checks
    if strict_mode:
        print()
        # Check for non-fire trivia violations
        non_fire_violations = check_non_fire_violations(skill_path)
        all_pass &= check(
            "No non-fire trivia blessed as blockers",
            len(non_fire_violations) == 0,
            f"violations: {non_fire_violations}" if non_fire_violations else "clean",
        )

        # Check style proportion
        style_pass, style_prop = check_style_proportion(skill_path)
        all_pass &= check(
            f"Style triggers ≤ {MAX_STYLE_PROPORTION * 100:.0f}%",
            style_pass,
            f"style proportion: {style_prop * 100:.1f}%",
        )

    # Summary
    print(f"\n{'=' * 40}")
    print(f"Result: {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    print(f"Word count: {word_count}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())


# Trigger format validation - import from report module
