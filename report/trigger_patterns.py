"""Shared trigger pattern definitions for skill extraction and verification.

This module provides regex patterns and extraction functions that are used by
both report/build_comparison.py and scripts/verify_skill.py to ensure
consistent trigger matching across the pipeline.
"""

import re
from collections.abc import Iterator


def extract_triggers_gpt_oss(content: str) -> Iterator[tuple[str, str]]:
    """Extract triggers from gpt-oss style (SKILL.md format).

    Format: ### Number. Title headings with - **What to look for:** blocks.

    Yields:
        (title, description) pairs where title is the theme/heading and
        description is the "What to look for" text.
    """
    # Extract theme headings (### Number. Title)
    theme_pattern = re.compile(r"^###\s+\d+\.\s*(.+)$", re.MULTILINE)

    # Match "  **What to look for:** description" (with leading spaces, no dash)
    what_to_look_pattern = re.compile(
        r"^\s+\*\*What to look for:\*\*\s+(.+)$",
        re.MULTILINE,
    )

    current_theme = "General"

    # Find all theme and what-to-look-for positions
    theme_matches = list(theme_pattern.finditer(content))
    what_matches = list(what_to_look_pattern.finditer(content))

    current_theme_idx = 0
    current_theme = "General"

    for what_match in what_matches:
        # Find the nearest preceding theme
        while (
            current_theme_idx + 1 < len(theme_matches)
            and theme_matches[current_theme_idx + 1].start() < what_match.start()
        ):
            current_theme_idx += 1
            current_theme = theme_matches[current_theme_idx].group(1).strip()

        what_text = what_match.group(1).strip()
        if what_text:
            yield (current_theme, what_text)


def extract_triggers_glm(content: str) -> Iterator[tuple[str, str]]:
    """Extract triggers from GLM style (SKILL-GLM.md format).

    Format: **Trigger**: text without italics, organized by themes.

    Yields:
        (title, description) pairs where title is the theme and
        description is the trigger text.
    """
    # Extract theme headings (#### Theme: X)
    theme_pattern = re.compile(r"^####\s+Theme:\s*(.+)$", re.MULTILINE)

    # Extract triggers: **Trigger**: text (no italics)
    trigger_pattern = re.compile(r"\*\*Trigger\*\*:\s*(.+?)(?:\n|$)")

    current_theme = "General"

    for line in content.split("\n"):
        theme_match = theme_pattern.match(line.strip())
        if theme_match:
            current_theme = theme_match.group(1).strip()
            continue

        trigger_match = trigger_pattern.search(line)
        if trigger_match:
            trigger_text = trigger_match.group(1).strip()
            if trigger_text:
                yield (current_theme, trigger_text)


def extract_triggers_mistral(content: str) -> Iterator[tuple[str, str]]:
    """Extract triggers from Mistral style (SKILL-Mistral.md format).

    Format: - **Title** bullets organized by levels.

    CRITICAL FIX (C4): Only extract top-level bullets (column 0) within "Level" sections.
    The original pattern over-matched:
    1. Any bold bullet including nested field labels (Type, Severity, Example, etc.)
    2. Bullets outside Level sections (Key Definitions, Reviewer Mindset, etc.)

    C4 Fix: Match only bullets at column 0 (^- not ^\\s*-) AND only within Level sections.
    This excludes nested field labels which are indented with 2 spaces.

    Yields:
        (title, description) pairs where title is the bullet text and
        description is empty (Mistral format uses title as the trigger).
    """
    # Extract level headings (### Level X: ...)
    level_pattern = re.compile(r"^###\s+Level\s+\d+:\s*(.+)$", re.MULTILINE)

    # Extract bullet triggers: - **Title** at column 0 only (no leading whitespace)
    # This excludes nested field labels like "  - **Type**:" which have 2-space indent
    bullet_pattern = re.compile(r"^-\s*\*\*(.+?)\*\*")

    # Field labels to skip (these are nested under triggers, not triggers themselves)
    FIELD_LABELS = ("Type:", "Severity:", "What to look for:", "Why it's a problem:", "Example:")

    current_level = "General"
    in_level_section = False  # C4: Track if we're inside a Level section

    for line in content.split("\n"):
        level_match = level_pattern.match(line.strip())
        if level_match:
            current_level = level_match.group(1).strip()
            in_level_section = True  # C4: Entering a Level section
            continue

        # Check for section end (new ### heading that's not a Level)
        if line.strip().startswith("###") and not line.strip().startswith("### Level"):
            in_level_section = False  # C4: Exiting Level section
            continue

        bullet_match = bullet_pattern.match(line)  # C4: Match only column-0 bullets
        if bullet_match and in_level_section:  # C4: Only yield if in Level section
            bullet_text = bullet_match.group(1).strip()
            # Skip field labels (shouldn't match due to column-0 constraint, but be safe)
            if bullet_text and not bullet_text.startswith(FIELD_LABELS):
                yield (current_level, bullet_text)


def extract_triggers(content: str, style: str = "auto") -> list[tuple[str, str]]:
    """Extract all triggers from a skill file.

    Args:
        content: Skill markdown content
        style: One of "gpt-oss", "glm", "mistral", or "auto" to auto-detect

    Returns:
        List of (title, description) tuples
    """
    if style == "auto":
        # Auto-detect based on content patterns
        if "**What to look for:**" in content:
            style = "gpt-oss"
        elif "**Trigger**:" in content and "#### Theme:" in content:
            style = "glm"
        elif re.search(r"^\s*-\s*\*\*.+?\*\*\s*$", content, re.MULTILINE):
            style = "mistral"
        else:
            style = "gpt-oss"  # Default

    if style == "gpt-oss":
        return list(extract_triggers_gpt_oss(content))
    elif style == "glm":
        return list(extract_triggers_glm(content))
    elif style == "mistral":
        return list(extract_triggers_mistral(content))
    else:
        return []


# Regex patterns for verification (used by verify_skill.py)
TRIGGER_FORMAT_PATTERNS = {
    "gpt_oss": re.compile(r"\*\*What to look for\*\*:\s*(.+)", re.IGNORECASE),
    "glm": re.compile(r"\*\*Trigger\*\*:\s*(.+)", re.IGNORECASE),
    "mistral": re.compile(r"^\s*-\s*\*\*(.+?)\*\*\s*$", re.MULTILINE),
}

# Unified trigger format for distillation output
UNIFIED_TRIGGER_FORMAT = """- **Trigger**: <language-agnostic description of the pattern>
  - **Type**: invariant-true | invariant-false | precedence-rule | general-guideline
  - **What to look for**: concrete detection criteria
  - **Why it's a problem**: underlying design principle being violated
  - **Severity**: reject | request-changes | nitpick | discussion
  - **Example**: "[verbatim Torvalds quote]"
"""
