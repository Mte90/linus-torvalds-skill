"""Data loading helpers for distill.py — extracted to reduce module size."""

from __future__ import annotations

import json
from pathlib import Path


def load_json_cached(path: Path) -> dict | list:
    """Load JSON file with basic caching (reads file, returns parsed data)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, (dict, list)), f"JSON at {path} must be object or array"
    return data


def load_severity_weights(calibration_path: Path | None) -> dict[str, float]:
    """Load severity weights from calibration data for weighted sampling.

    Returns weights dict mapping severity names to float multipliers.
    Default weights if calibration not available.
    """
    if calibration_path and calibration_path.exists():
        with open(calibration_path, encoding="utf-8") as f:
            calibration = json.load(f)
        weights = calibration.get("severity_weights", {})
        if weights:
            return {k: float(v) for k, v in weights.items()}

    # Default weights: reject ≈3x, request-changes ≈2x, nitpick ≈1x
    return {"reject": 3.0, "request-changes": 2.0, "nitpick": 1.0}


def load_interview_data(project_root: Path) -> str:
    """Load all interview transcripts from data/interviews/ directory.

    Reads all .md files line-by-line, concatenates them with headers, and truncates
    to ~200,000 chars to avoid blowing the context window. Reads line-by-line
    to avoid OOM when files are very large.

    Returns the concatenated string, or empty string if the directory doesn't exist.
    """
    interviews_dir = project_root / "data" / "interviews"
    if not interviews_dir.exists():
        return ""

    max_chars = 200000
    lines = []
    total_chars = 0

    # Sort files for deterministic ordering
    for md_file in sorted(interviews_dir.glob("*.md")):
        header = f"## Interview: {md_file.name}\n\n"
        header_chars = len(header)

        # Check if header alone would exceed limit
        if total_chars + header_chars > max_chars:
            # Add partial header if we haven't started yet
            if total_chars == 0:
                remaining = max_chars - total_chars
                if remaining > 0:
                    lines.append(header[:remaining])
                total_chars = max_chars
            break

        # Read line-by-line to avoid loading entire file into memory
        with open(md_file, encoding="utf-8") as f:
            file_lines = []
            file_chars = header_chars

            for line in f:
                line_chars = len(line)
                if total_chars + file_chars + line_chars > max_chars:
                    # Add partial line if it fits, then stop
                    remaining = max_chars - total_chars - file_chars
                    if remaining > 0:
                        file_lines.append(line[:remaining])
                    # We've hit the limit
                    break
                file_lines.append(line)
                file_chars += line_chars

            file_content = header + "".join(file_lines) + "\n\n"

            # If this is the first file and we have content, add it
            if total_chars == 0 or total_chars + len(file_content) <= max_chars:
                lines.append(file_content)
                total_chars += len(file_content)
            elif total_chars == 0:
                # First file but too large - add partial
                remaining = max_chars - total_chars
                if remaining > 0:
                    lines.append(file_content[:remaining])
                total_chars = max_chars

    return "".join(lines)


def load_interlocutor_variation_data(project_root: Path) -> str:
    """Load interlocutor and variation data from JSONL files.

    Reads data/interlocutor.jsonl (recipient classification) and
    data/variation.jsonl (tone variation) and formats them into a prompt section.

    Returns the concatenated string, or empty string if files don't exist.
    """
    data_dir = project_root / "data"
    interlocutor_path = data_dir / "interlocutor.jsonl"
    variation_path = data_dir / "variation.jsonl"

    lines = []

    # Load interlocutor data
    if interlocutor_path.exists():
        lines.append("### Interlocutor Data (recipient classification)")
        with open(interlocutor_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        lines.append(
                            f"- {record.get('description', '')}: {record.get('classification', '')}"
                        )
                    except json.JSONDecodeError:
                        continue
        lines.append("")

    # Load variation data
    if variation_path.exists():
        lines.append("### Variation Data (tone adaptation)")
        with open(variation_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        lines.append(f"- {record.get('scenario', '')}: {record.get('tone', '')}")
                    except json.JSONDecodeError:
                        continue
        lines.append("")

    if not lines:
        return ""

    return "## INTERLOCUTOR AND VARIATION DATA\n\n" + "\n".join(lines)


def validate_skill_structure(skill_text: str) -> list[str]:
    """Check that all required top-level sections exist as ## Section Name headings.

    Required sections: "Reviewer Mindset", "Review Triggers", "Severity Calibration",
    "Severity Decision Tree", "Precedence and Priorities", "Decision Cards",
    "Key Definitions", "Voice and Tone"

    Returns a list of missing section names (empty list = all present).
    Does NOT modify the skill text.
    """
    import re

    required = [
        "Reviewer Mindset",
        "Review Triggers",
        "Severity Calibration",
        "Severity Decision Tree",
        "Precedence and Priorities",
        "Decision Cards",
        "Key Definitions",
        "Voice and Tone",
    ]

    missing = []
    for section in required:
        pattern = rf"^##\s+{re.escape(section)}\s*$"
        if not re.search(pattern, skill_text, re.MULTILINE):
            missing.append(section)

    return missing


def validate_severity_consistency(skill_text: str, calibration: dict) -> list[str]:
    """Validate severity distribution in skill text against calibration statistics.

    1. Extracts severity labels from the skill text (looks for words like "reject",
       "nitpick", "critical", "warning" in trigger descriptions)
    2. Compares the frequency of each severity against the calibration statistics
    3. Returns a list of warning strings if any severity is dramatically
       over/under-represented (>2x deviation from expected ratio)
    4. Does NOT modify the skill text — just reports warnings

    The calibration dict has structure:
    {"severity_by_category": {"correctness": {"reject": 45, "nitpick": 12, ...}, ...}, ...}
    """
    import re

    warnings: list[str] = []

    if not calibration:
        return warnings

    # Extract severity mentions from skill text
    severity_patterns = {
        "reject": r"\b(reject|rejection|rejecting|critical|blocker|must-fix|breaking)\b",
        "nitpick": r"\b(nitpick|nit|cosmetic|style|minor|trivial|optional)\b",
        "request-changes": r"\b(request.?changes|revision|improve|refactor|rework)\b",
    }

    severity_counts = {}
    for sev, pattern in severity_patterns.items():
        matches = re.findall(pattern, skill_text, re.IGNORECASE)
        severity_counts[sev] = len(matches)

    total_mentions = sum(severity_counts.values())
    if total_mentions == 0:
        return warnings

    # Get calibration statistics
    severity_by_category = calibration.get("severity_by_category", {})
    if not severity_by_category:
        return warnings

    # Compute expected ratios from calibration
    expected_ratios = {"reject": 0.0, "nitpick": 0.0, "request-changes": 0.0}
    total_cal = 0

    for cat_data in severity_by_category.values():
        # Use percentages if available
        if "percentages" in cat_data:
            for sev in expected_ratios.keys():
                sev_key = sev if sev != "request-changes" else "request_changes"
                rate_key = f"{sev_key}_rate"
                if rate_key in cat_data:
                    expected_ratios[sev] += cat_data[rate_key] / 100.0
                    total_cal += 1

    if total_cal > 0:
        for sev in expected_ratios:
            expected_ratios[sev] /= total_cal

    # Compare actual vs expected
    actual_ratios = {sev: count / total_mentions for sev, count in severity_counts.items()}

    for sev in ["reject", "nitpick", "request-changes"]:
        actual = actual_ratios.get(sev, 0)
        expected = expected_ratios.get(sev, 0)

        if expected > 0 and actual > 0:
            deviation = actual / expected
            if deviation > 2.0:
                warnings.append(
                    f"Severity '{sev}' over-represented: {actual * 100:.1f}% in skill "
                    f"vs {expected * 100:.1f}% expected ({deviation:.1f}x deviation)"
                )
            elif deviation < 0.5:
                warnings.append(
                    f"Severity '{sev}' under-represented: {actual * 100:.1f}% in skill "
                    f"vs {expected * 100:.1f}% expected ({deviation:.1f}x deviation)"
                )
        elif actual > 0 and expected == 0:
            warnings.append(f"Severity '{sev}' present in skill but no calibration data available")

    return warnings
