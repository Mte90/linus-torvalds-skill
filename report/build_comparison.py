#!/usr/bin/env python3
"""
Build comparison.md from review files (with-skill and baseline).

Parses review files in different formats, extracts findings, and generates:
- Metrics table (word counts, finding counts by severity)
- Consensus matrix (cross-reference findings across models)
- Severity disagreement table
- Trigger coverage table
- With-skill vs baseline comparison

Run from repository root: python3 report/build_comparison.py
"""

import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# Models and their review files
MODELS = [
    ("gpt-oss-120b", "review-gpt-oss-120b.md", "review-baseline-gpt-oss-120b.md"),
    ("glm5.2", "review-glm5.2.md", "review-baseline-glm5.2.md"),
    ("mistral", "review-mistral.md", "review-baseline-mistral.md"),
]

SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def normalize_filename(name: str) -> str:
    """Normalize file names so 'server.c' and 'smallchat-server.c' match."""
    name = name.strip().lower()
    # Strip directory prefixes
    name = name.split("/")[-1]
    # Map short forms to canonical long forms
    aliases = {
        "server.c": "smallchat-server.c",
        "client.c": "smallchat-client.c",
    }
    return aliases.get(name, name)


def _extract_first_line(text: str) -> int | None:
    """Extract the first line number from a string like '188-189' or '143, 194, 248'."""
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


class Finding:
    """Represents a single finding from a review."""

    def __init__(self, severity, title, location, trigger=None, finding_type=None):
        self.severity = severity
        self.title = title
        self.location = location  # "file:line" or just "line"
        self.trigger = trigger
        self.finding_type = finding_type
        self.file = None
        self.line = None
        self._parse_location()

    def _parse_location(self):
        """Parse location into file and line components."""
        if not self.location:
            return
        loc = self.location.strip()

        # Format: "file:line" or "file:line-range" (e.g. "smallchat-server.c:188-189")
        file_match = re.match(r"^([\w./-]+\.\w+)\s*:\s*(.+)$", loc)
        if file_match:
            self.file = normalize_filename(file_match.group(1))
            line_part = file_match.group(2)
            self.line = _extract_first_line(line_part)
            return

        # Format: "lines 85, 127-128" or "line 45" (mistral style — no file)
        line_match = re.search(r"\d+", loc)
        if line_match:
            self.line = int(line_match.group())
            # File stays None — will be set by section tracking if available

    def __repr__(self):
        return f"Finding({self.severity}, {self.title[:40]}..., {self.location})"


def parse_gpt_oss_review(content: str) -> list[Finding]:
    """Parse gpt-oss-120b review format (#### [SEVERITY] Title)."""
    findings = []
    lines = content.split("\n")

    current_severity = None
    current_title = None
    current_location = None
    current_trigger = None
    current_type = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Match heading with severity: #### [CRITICAL] Title
        heading_match = re.match(r"^####\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+(.+)$", line)
        if heading_match:
            # Save previous finding
            if current_severity and current_title:
                findings.append(Finding(current_severity, current_title, current_location, current_trigger, current_type))

            current_severity = heading_match.group(1)
            current_title = heading_match.group(2).strip()
            current_location = None
            current_trigger = None
            current_type = None
            i += 1
            continue

        # Match fields within a finding
        if current_severity:
            loc_match = re.match(r"^\s*-\s*\*\*Location:\*\*\s*(.+)$", line)
            if loc_match:
                current_location = loc_match.group(1).strip()
                i += 1
                continue

            trigger_match = re.match(r"^\s*-\s*\*\*Trigger:\*\*\s*(.+)$", line)
            if trigger_match:
                current_trigger = trigger_match.group(1).strip()
                i += 1
                continue

            type_match = re.match(r"^\s*-\s*\*\*Type:\*\*\s*(.+)$", line)
            if type_match:
                current_type = type_match.group(1).strip()
                i += 1
                continue

        i += 1

    # Save last finding
    if current_severity and current_title:
        findings.append(Finding(current_severity, current_title, current_location, current_trigger, current_type))

    return findings


def parse_glm52_review(content: str) -> list[Finding]:
    """Parse glm5.2 review format (### [SEVERITY] Title)."""
    findings = []
    lines = content.split("\n")

    current_severity = None
    current_title = None
    current_location = None
    current_trigger = None
    current_type = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Match heading with severity: ### [CRITICAL] Title
        heading_match = re.match(r"^###\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+(.+)$", line)
        if heading_match:
            # Save previous finding
            if current_severity and current_title:
                findings.append(Finding(current_severity, current_title, current_location, current_trigger, current_type))

            current_severity = heading_match.group(1)
            current_title = heading_match.group(2).strip()
            current_location = None
            current_trigger = None
            current_type = None
            i += 1
            continue

        # Match fields within a finding
        if current_severity:
            loc_match = re.match(r"^\s*-\s*\*\*Location:\*\*\s*(.+)$", line)
            if loc_match:
                current_location = loc_match.group(1).strip()
                i += 1
                continue

            trigger_match = re.match(r"^\s*-\s*\*\*Trigger:\*\*\s*(.+)$", line)
            if trigger_match:
                current_trigger = trigger_match.group(1).strip()
                i += 1
                continue

            type_match = re.match(r"^\s*-\s*\*\*Type:\*\*\s*(.+)$", line)
            if type_match:
                current_type = type_match.group(1).strip()
                i += 1
                continue

        i += 1

    # Save last finding
    if current_severity and current_title:
        findings.append(Finding(current_severity, current_title, current_location, current_trigger, current_type))

    return findings


def parse_mistral_review(content: str) -> list[Finding]:
    """Parse mistral review format (#### [SEVERITY] Title, note: Location: without **)."""
    findings = []
    lines = content.split("\n")

    current_severity = None
    current_title = None
    current_location = None
    current_trigger = None
    current_type = None
    current_section_file = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Track ### filename.c section headings (mistral groups findings by file)
        section_match = re.match(r"^###\s+([\w./-]+\.\w+)\s*$", line)
        if section_match:
            current_section_file = normalize_filename(section_match.group(1))
            i += 1
            continue

        # Match heading with severity: #### [CRITICAL] Title
        heading_match = re.match(r"^####\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+(.+)$", line)
        if heading_match:
            # Save previous finding
            if current_severity and current_title:
                f = Finding(current_severity, current_title, current_location, current_trigger, current_type)
                if not f.file and current_section_file:
                    f.file = current_section_file
                findings.append(f)

            current_severity = heading_match.group(1)
            current_title = heading_match.group(2).strip()
            current_location = None
            current_trigger = None
            current_type = None
            i += 1
            continue

        # Match fields within a finding (note: mistral uses **Location**: not **Location:**)
        if current_severity:
            loc_match = re.match(r"^\s*-\s*\*\*Location\*\*:\s*(.+)$", line)
            if loc_match:
                current_location = loc_match.group(1).strip()
                i += 1
                continue

            trigger_match = re.match(r"^\s*-\s*\*\*Trigger\*\*:\s*(.+)$", line)
            if trigger_match:
                current_trigger = trigger_match.group(1).strip()
                i += 1
                continue

            type_match = re.match(r"^\s*-\s*\*\*Type\*\*:\s*(.+)$", line)
            if type_match:
                current_type = type_match.group(1).strip()
                i += 1
                continue

        i += 1

    # Save last finding
    if current_severity and current_title:
        f = Finding(current_severity, current_title, current_location, current_trigger, current_type)
        if not f.file and current_section_file:
            f.file = current_section_file
        findings.append(f)

    return findings


def parse_baseline_review(content: str) -> list[Finding]:
    """Parse baseline review format (### or #### [SEVERITY] Title)."""
    findings = []
    lines = content.split("\n")

    current_severity = None
    current_title = None
    current_location = None
    current_type = None
    current_section_file = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Track ## filename.c or ### filename.c section headings
        section_match = re.match(r"^#{2,3}\s+([\w./-]+\.\w+)\s*$", line)
        if section_match:
            current_section_file = normalize_filename(section_match.group(1))
            i += 1
            continue

        heading_match = re.match(r"^#{3,4}\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+(.+)$", line)
        if heading_match:
            # Save previous finding
            if current_severity and current_title:
                f = Finding(current_severity, current_title, current_location, None, current_type)
                if not f.file and current_section_file:
                    f.file = current_section_file
                findings.append(f)

            current_severity = heading_match.group(1)
            current_title = heading_match.group(2).strip()
            current_location = None
            current_type = None
            i += 1
            continue

        # Match fields within a finding
        if current_severity:
            loc_match = re.match(r"^\s*-\s*\*\*Location:\*\*\s*(.+)$", line)
            if loc_match:
                current_location = loc_match.group(1).strip()
                i += 1
                continue

            type_match = re.match(r"^\s*-\s*\*\*Type:\*\*\s*(.+)$", line)
            if type_match:
                current_type = type_match.group(1).strip()
                i += 1
                continue

        i += 1

    # Save last finding
    if current_severity and current_title:
        f = Finding(current_severity, current_title, current_location, None, current_type)
        if not f.file and current_section_file:
            f.file = current_section_file
        findings.append(f)

    return findings


def parse_review_file(filepath: Path) -> list[Finding]:
    """Parse a review file, auto-detecting format based on filename."""
    if not filepath.exists():
        return []

    content = filepath.read_text()
    filename = filepath.name

    # Dispatch to appropriate parser
    if "baseline" in filename:
        return parse_baseline_review(content)
    elif "gpt-oss" in filename:
        return parse_gpt_oss_review(content)
    elif "glm5.2" in filename or "glm52" in filename:
        return parse_glm52_review(content)
    elif "mistral" in filename:
        return parse_mistral_review(content)
    else:
        # Try all parsers
        findings = parse_gpt_oss_review(content)
        if not findings:
            findings = parse_glm52_review(content)
        if not findings:
            findings = parse_mistral_review(content)
        if not findings:
            findings = parse_baseline_review(content)
        return findings


def count_severities(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity."""
    counts = {sev: 0 for sev in SEVERITIES}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    return counts


def group_findings_by_file(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Group findings by source file (normalized)."""
    groups = defaultdict(list)
    for f in findings:
        key = normalize_filename(f.file) if f.file else "unspecified"
        groups[key].append(f)
    return dict(groups)


def match_findings_across_models(
    gpt_findings: list[Finding],
    glm_findings: list[Finding],
    mistral_findings: list[Finding],
) -> list[dict]:
    """
    Match findings across models by file+line proximity or keyword overlap.
    Returns a list of matched groups with which models found each issue.
    """
    # Group all findings by file
    gpt_by_file = group_findings_by_file(gpt_findings)
    glm_by_file = group_findings_by_file(glm_findings)
    mistral_by_file = group_findings_by_file(mistral_findings)

    all_files = set(gpt_by_file.keys()) | set(glm_by_file.keys()) | set(mistral_by_file.keys())

    matched_groups = []
    used_findings = set()

    for file in sorted(all_files):
        gpt_file_findings = gpt_by_file.get(file, [])
        glm_file_findings = glm_by_file.get(file, [])
        mistral_file_findings = mistral_by_file.get(file, [])

        # For each finding in glm (most comprehensive), try to match with others
        for i, glm_f in enumerate(glm_file_findings):
            if (file, i, "glm") in used_findings:
                continue

            group = {
                "file": file,
                "gpt": None,
                "glm": glm_f,
                "mistral": None,
                "title": glm_f.title,
            }
            used_findings.add((file, i, "glm"))

            # Try to match with gpt by line proximity
            if glm_f.line:
                for j, gpt_f in enumerate(gpt_file_findings):
                    if (file, j, "gpt") in used_findings:
                        continue
                    if gpt_f.line and abs(gpt_f.line - glm_f.line) <= 10:
                        group["gpt"] = gpt_f
                        used_findings.add((file, j, "gpt"))
                        break
                    # Also match by keyword overlap in title
                    if _keyword_overlap(gpt_f.title, glm_f.title):
                        group["gpt"] = gpt_f
                        used_findings.add((file, j, "gpt"))
                        break

            # Try to match with mistral
            if glm_f.line:
                for j, mis_f in enumerate(mistral_file_findings):
                    if (file, j, "mistral") in used_findings:
                        continue
                    if mis_f.line and abs(mis_f.line - glm_f.line) <= 10:
                        group["mistral"] = mis_f
                        used_findings.add((file, j, "mistral"))
                        break
                    if _keyword_overlap(mis_f.title, glm_f.title):
                        group["mistral"] = mis_f
                        used_findings.add((file, j, "mistral"))
                        break

            matched_groups.append(group)

        # Add unmatched gpt findings
        for j, gpt_f in enumerate(gpt_file_findings):
            if (file, j, "gpt") not in used_findings:
                matched_groups.append({
                    "file": file,
                    "gpt": gpt_f,
                    "glm": None,
                    "mistral": None,
                    "title": gpt_f.title,
                })
                used_findings.add((file, j, "gpt"))

        # Add unmatched mistral findings
        for j, mis_f in enumerate(mistral_file_findings):
            if (file, j, "mistral") not in used_findings:
                matched_groups.append({
                    "file": file,
                    "gpt": None,
                    "glm": None,
                    "mistral": mis_f,
                    "title": mis_f.title,
                })
                used_findings.add((file, j, "mistral"))

    return matched_groups


def _keyword_overlap(title1: str, title2: str) -> bool:
    """Check if two titles share significant keywords."""
    words1 = set(re.findall(r"\b\w+\b", title1.lower()))
    words2 = set(re.findall(r"\b\w+\b", title2.lower()))
    # Filter out common words
    common_words = {"the", "a", "an", "is", "are", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with"}
    words1 -= common_words
    words2 -= common_words
    if not words1 or not words2:
        return False
    overlap = words1 & words2
    return len(overlap) >= 2


def find_severity_disagreements(matched_groups: list[dict]) -> list[dict]:
    """Find cases where 2+ models found the same issue but assigned different severities."""
    disagreements = []
    for group in matched_groups:
        severities = []
        if group["gpt"]:
            severities.append(("gpt-oss-120b", group["gpt"].severity))
        if group["glm"]:
            severities.append(("glm5.2", group["glm"].severity))
        if group["mistral"]:
            severities.append(("mistral", group["mistral"].severity))

        if len(severities) >= 2:
            unique_sevs = set(s[1] for s in severities)
            if len(unique_sevs) > 1:
                disagreements.append({
                    "title": group["title"],
                    "file": group["file"],
                    "severities": severities,
                })
    return disagreements


def extract_triggers(findings: list[Finding]) -> dict[str, int]:
    """Extract and count unique triggers from findings."""
    triggers = defaultdict(int)
    for f in findings:
        if f.trigger:
            triggers[f.trigger] += 1
    return dict(triggers)


def compare_skill_vs_baseline(
    skill_findings: list[Finding],
    baseline_findings: list[Finding] | None,
    model_name: str,
) -> dict:
    """Compare with-skill vs baseline findings for a model.

    Pass None for baseline_findings when the baseline file is missing
    (not yet generated). The returned dict uses "N/A" string sentinels
    so downstream rendering shows "N/A" instead of zeros.
    """
    skill_critical = [f for f in skill_findings if f.severity == "CRITICAL"]

    if baseline_findings is None:
        return {
            "model": model_name,
            "skill_total": len(skill_findings),
            "baseline_total": "N/A",
            "skill_critical": len(skill_critical),
            "baseline_critical": "N/A",
            "critical_overlap": "N/A",
            "skill_only_critical": "N/A",
            "baseline_only_critical": "N/A",
        }

    baseline_critical = [f for f in baseline_findings if f.severity == "CRITICAL"]

    # Check if baseline found the same critical bugs
    skill_critical_lines = {(f.file, f.line) for f in skill_critical if f.file and f.line}
    baseline_critical_lines = {(f.file, f.line) for f in baseline_critical if f.file and f.line}

    overlap = skill_critical_lines & baseline_critical_lines
    skill_only = skill_critical_lines - baseline_critical_lines
    baseline_only = baseline_critical_lines - skill_critical_lines

    return {
        "model": model_name,
        "skill_total": len(skill_findings),
        "baseline_total": len(baseline_findings),
        "skill_critical": len(skill_critical),
        "baseline_critical": len(baseline_critical),
        "critical_overlap": len(overlap),
        "skill_only_critical": len(skill_only),
        "baseline_only_critical": len(baseline_only),
    }


def generate_markdown(
    report_dir: Path,
    metrics: dict,
    matched_groups: list[dict],
    severity_disagreements: list[dict],
    trigger_coverage: dict,
    skill_vs_baseline: list[dict],
    missing_files: list[str],
) -> str:
    """Generate the complete comparison.md content."""
    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append("title: Model Comparison — SmallChat Review")
    lines.append(f"date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    lines.append("codebase: antirez/smallchat")
    lines.append("models: gpt-oss-120b, glm5.2, mistral-small-4-119b")
    lines.append("skill: linus-torvalds-skill (language-agnostic)")
    lines.append("method: static review, skill triggers applied per source file")
    lines.append("---")
    lines.append("")

    # Title and intro
    lines.append("# Model Comparison — SmallChat Review")
    lines.append("")
    lines.append("Three models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill and soul. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.")
    lines.append("")

    # Metrics Summary table
    lines.append("## Metrics Summary")
    lines.append("")
    lines.append("| Metric | gpt-oss-120b | glm5.2 | mistral |")
    lines.append("|--------|:------------:|:------:|:-------:|")

    for metric_name in ["findings", "CRITICAL", "HIGH", "MEDIUM", "LOW", "words"]:
        row = [metric_name.replace("_", " ").title()]
        for model_key in ["gpt-oss-120b", "glm5.2", "mistral"]:
            m = metrics.get(model_key, {})
            skill_metrics = m.get("skill", {})
            val = skill_metrics.get(metric_name, "N/A")
            row.append(str(val))
        lines.append(f"| {' | '.join(row)} |")

    lines.append("")
    lines.append("**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.")
    lines.append("")

    # Warning about missing files
    if missing_files:
        lines.append("⚠️ **Note:** The following review files were missing and skipped:")
        for f in missing_files:
            lines.append(f"- {f}")
        lines.append("")

    # Consensus Matrix
    lines.append("---")
    lines.append("")
    lines.append("## Finding Consensus Matrix")
    lines.append("")
    lines.append("Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.")
    lines.append("")

    # Group by file
    files_in_matrix = set(g["file"] for g in matched_groups if g["file"] != "unspecified")
    if "unspecified" in set(g["file"] for g in matched_groups):
        files_in_matrix = list(files_in_matrix) + ["unspecified"]

    row_num = 1
    for file in sorted(files_in_matrix):
        lines.append(f"### {file}")
        lines.append("")
        lines.append("| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |")
        lines.append("|---|-------|:-------:|:------:|:-------:|:---------:|")

        file_groups = [g for g in matched_groups if g["file"] == file]
        for group in file_groups:
            gpt_mark = f"✓ ({group['gpt'].severity})" if group["gpt"] else "✗"
            glm_mark = f"✓ ({group['glm'].severity})" if group["glm"] else "✗"
            mis_mark = f"✓ ({group['mistral'].severity})" if group["mistral"] else "✗"

            # Determine consensus
            found_count = sum([bool(group["gpt"]), bool(group["glm"]), bool(group["mistral"])])
            if found_count == 3:
                consensus = "3/3"
            elif found_count == 2:
                consensus = "2/3"
            elif found_count == 1:
                if group["gpt"]:
                    consensus = "gpt-oss only"
                elif group["glm"]:
                    consensus = "glm5.2 only"
                else:
                    consensus = "mistral only"
            else:
                consensus = "—"

            title = group["title"][:50] + "..." if len(group["title"]) > 50 else group["title"]
            lines.append(f"| {row_num} | {title} | {gpt_mark} | {glm_mark} | {mis_mark} | {consensus} |")
            row_num += 1

        lines.append("")

    # Severity Disagreement Table
    lines.append("---")
    lines.append("")
    lines.append("## Severity Disagreement Table")
    lines.append("")
    lines.append("Cases where 2+ models found the same issue but assigned different severities:")
    lines.append("")

    if severity_disagreements:
        lines.append("| Issue | gpt-oss | glm5.2 | mistral |")
        lines.append("|-------|:-------:|:------:|:-------:|")
        for d in severity_disagreements:
            title = d["title"][:40] + "..." if len(d["title"]) > 40 else d["title"]
            sev_row = []
            for model in ["gpt-oss-120b", "glm5.2", "mistral"]:
                found = next((s for m, s in d["severities"] if m == model), None)
                sev_row.append(found if found else "—")
            lines.append(f"| {title} | {sev_row[0]} | {sev_row[1]} | {sev_row[2]} |")
    else:
        lines.append("*No severity disagreements found.*")
    lines.append("")

    # Trigger Coverage Table
    lines.append("---")
    lines.append("")
    lines.append("## Trigger Coverage Comparison")
    lines.append("")
    lines.append("Which skill triggers fired in each review:")
    lines.append("")

    # Get all unique triggers
    all_triggers = set()
    for model_data in trigger_coverage.values():
        all_triggers.update(model_data.keys())

    if all_triggers:
        lines.append("| Trigger theme | gpt-oss | glm5.2 | mistral |")
        lines.append("|---------------|:-------:|:------:|:-------:|")

        for trigger in sorted(all_triggers):
            gpt_count = trigger_coverage.get("gpt-oss-120b", {}).get(trigger, 0)
            glm_count = trigger_coverage.get("glm5.2", {}).get(trigger, 0)
            mis_count = trigger_coverage.get("mistral", {}).get(trigger, 0)

            gpt_mark = f"✓ ({gpt_count})" if gpt_count > 0 else "✗"
            glm_mark = f"✓ ({glm_count})" if glm_count > 0 else "✗"
            mis_mark = f"✓ ({mis_count})" if mis_count > 0 else "✗"

            # Truncate trigger name for display
            trigger_display = trigger[:30] + "..." if len(trigger) > 30 else trigger
            lines.append(f"| {trigger_display} | {gpt_mark} | {glm_mark} | {mis_mark} |")
    else:
        lines.append("*No trigger data available.*")
    lines.append("")

    # With-Skill vs Baseline Comparison
    lines.append("---")
    lines.append("")
    lines.append("## With-Skill vs Baseline Comparison")
    lines.append("")
    lines.append("For each model, comparing findings with the skill vs without (baseline):")
    lines.append("")

    lines.append("| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |")
    lines.append("|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|")

    for comparison in skill_vs_baseline:
        model = comparison["model"]
        baseline_total = comparison["baseline_total"]
        skill_total = comparison["skill_total"]
        baseline_crit = comparison["baseline_critical"]
        skill_crit = comparison["skill_critical"]
        overlap = comparison["critical_overlap"]
        skill_only = comparison["skill_only_critical"]
        baseline_only = comparison["baseline_only_critical"]

        if baseline_total == "N/A":
            value = "baseline not yet generated"
        elif not isinstance(skill_only, int) or not isinstance(baseline_only, int):
            value = "N/A"
        else:
            net = skill_only - baseline_only
            if net > 0:
                value = f"yes (+{net} net critical: {skill_only} found, {baseline_only} lost)"
            elif net == 0:
                value = f"neutral (0 net: {skill_only} found, {baseline_only} lost)"
            else:
                value = f"no ({net} net critical: {skill_only} found, {baseline_only} lost)"

        lines.append(f"| {model} | {baseline_total} | {skill_total} | {baseline_crit} | {skill_crit} | {overlap} | {skill_only} | {baseline_only} | {value} |")

    lines.append("")

    # Qualitative analysis — generated from data
    lines.append("---")
    lines.append("")
    lines.append("## Qualitative Analysis")
    lines.append("")

    # --- Accuracy Scoring (consensus-based) ---
    # A finding found by 2+ models is treated as a confirmed real bug.
    # A finding found by only 1 model is "unverified" (could be real or false positive).
    model_keys = ["gpt-oss-120b", "glm5.2", "mistral"]
    model_short = {"gpt-oss-120b": "gpt", "glm5.2": "glm", "mistral": "mis"}

    confirmed_per_model = {k: 0 for k in model_keys}
    unverified_per_model = {k: 0 for k in model_keys}
    unique_per_model = {k: 0 for k in model_keys}

    for group in matched_groups:
        found_count = sum([bool(group["gpt"]), bool(group["glm"]), bool(group["mistral"])])
        if found_count >= 2:
            if group["gpt"]:
                confirmed_per_model["gpt-oss-120b"] += 1
            if group["glm"]:
                confirmed_per_model["glm5.2"] += 1
            if group["mistral"]:
                confirmed_per_model["mistral"] += 1
        elif found_count == 1:
            if group["gpt"]:
                unverified_per_model["gpt-oss-120b"] += 1
                unique_per_model["gpt-oss-120b"] += 1
            elif group["glm"]:
                unverified_per_model["glm5.2"] += 1
                unique_per_model["glm5.2"] += 1
            else:
                unverified_per_model["mistral"] += 1
                unique_per_model["mistral"] += 1

    lines.append("### Consensus-Based Accuracy")
    lines.append("")
    lines.append("Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).")
    lines.append("")
    lines.append("| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |")
    lines.append("|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|")
    for mk in model_keys:
        total = confirmed_per_model[mk] + unverified_per_model[mk]
        rate = f"{confirmed_per_model[mk] / total * 100:.0f}%" if total > 0 else "N/A"
        lines.append(f"| {mk} | {total} | {confirmed_per_model[mk]} | {unverified_per_model[mk]} | {rate} |")
    lines.append("")

    # --- Severity Calibration ---
    lines.append("### Severity Calibration")
    lines.append("")
    if severity_disagreements:
        lines.append("Cases where 2+ models found the same issue but assigned different severities:")
        lines.append("")
        lines.append("| Issue | gpt-oss | glm5.2 | mistral |")
        lines.append("|-------|:-------:|:------:|:-------:|")
        for d in severity_disagreements:
            title = d["title"][:40] + "..." if len(d["title"]) > 40 else d["title"]
            sev_map = dict(d["severities"])
            gpt_s = sev_map.get("gpt-oss-120b", "—")
            glm_s = sev_map.get("glm5.2", "—")
            mis_s = sev_map.get("mistral", "—")
            lines.append(f"| {title} | {gpt_s} | {glm_s} | {mis_s} |")
        lines.append("")
        lines.append(f"Total severity disagreements: {len(severity_disagreements)}. Lower is better — it means the model's severity assessment aligns with the consensus.")
        lines.append("")
    else:
        lines.append("No severity disagreements detected — all models that found the same issue assigned the same severity.")
        lines.append("")

    # --- Unique Findings ---
    lines.append("### Unique Findings (Single-Model Discoveries)")
    lines.append("")
    lines.append("Findings reported by only one model. These represent either unique insight or false positives:")
    lines.append("")
    lines.append("| Model | Unique Findings |")
    lines.append("|-------|:--------------:|")
    for mk in model_keys:
        lines.append(f"| {mk} | {unique_per_model[mk]} |")
    lines.append("")
    lines.append("A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.")
    lines.append("")

    # --- With-Skill vs Baseline Impact ---
    lines.append("### With-Skill vs Baseline: Skill Impact")
    lines.append("")
    lines.append("How the skill changed each model's review:")
    lines.append("")
    for svb in skill_vs_baseline:
        model = svb["model"]
        bt, st = svb["baseline_total"], svb["skill_total"]
        bc, sc = svb["baseline_critical"], svb["skill_critical"]
        soc = svb["skill_only_critical"]
        boc = svb["baseline_only_critical"]
        lines.append(f"**{model}:** Baseline {bt} findings ({bc} CRITICAL) → With-skill {st} findings ({sc} CRITICAL). "
                     f"Skill found {soc} critical bug(s) the baseline missed; baseline found {boc} critical bug(s) the skill missed.")
        lines.append("")

    # Honest tradeoff analysis: does the skill narrow focus at the cost of coverage?
    lines.append("#### Skill Tradeoff Analysis")
    lines.append("")
    lines.append("The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). "
                 "This filters noise but can also suppress valid findings. Net critical impact per model:")
    lines.append("")
    lines.append("| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |")
    lines.append("|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|")
    for svb in skill_vs_baseline:
        model = svb["model"]
        soc = svb["skill_only_critical"]
        boc = svb["baseline_only_critical"]
        bt, st = svb["baseline_total"], svb["skill_total"]
        if isinstance(soc, int) and isinstance(boc, int):
            net = soc - boc
            net_str = f"{net:+d}" if net != 0 else "0"
        else:
            net_str = "N/A"
        if isinstance(bt, int) and isinstance(st, int):
            delta = st - bt
            delta_str = f"{delta:+d}" if delta != 0 else "0"
        else:
            delta_str = "N/A"
        lines.append(f"| {model} | {soc} | {boc} | {net_str} | {delta_str} |")
    lines.append("")
    lines.append("**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. "
                 "A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. "
                 "A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.")
    lines.append("")

    # Per-model read: dynamic narrative based on net critical and finding delta
    lines.append("**Per-model read:**")
    for svb in skill_vs_baseline:
        model = svb["model"]
        soc = svb["skill_only_critical"]
        boc = svb["baseline_only_critical"]
        bt, st = svb["baseline_total"], svb["skill_total"]
        if not isinstance(soc, int) or not isinstance(boc, int):
            lines.append(f"- **{model}:** Baseline not available for comparison.")
            continue
        net = soc - boc
        if isinstance(bt, int) and isinstance(st, int):
            delta = st - bt
        else:
            delta = None
        if bt == 0 and net > 0:
            lines.append(f"- **{model}:** Clear win. Baseline found nothing; skill added {net} critical bug(s). The skill unlocked review capability this model didn't have without it.")
        elif net > 0:
            cut = f"cut {abs(delta)} findings" if delta is not None and delta < 0 else "added findings"
            lines.append(f"- **{model}:** Net positive. The skill {cut} and added {net} critical bug(s) the baseline missed.")
        elif net < 0:
            cut = f"cut {abs(delta)} findings" if delta is not None and delta < 0 else "changed finding count"
            lines.append(f"- **{model}:** Net negative on critical coverage. The skill {cut} and suppressed {boc} critical(s) the baseline caught, while only adding {soc} new critical. The skill narrowed focus too aggressively — the {boc} lost critical(s) are a real coverage gap worth investigating.")
        else:
            if delta is not None and delta < 0:
                lines.append(f"- **{model}:** Neutral on criticals. The skill filtered noise (cut {abs(delta)} findings) without losing critical coverage.")
            else:
                lines.append(f"- **{model}:** Neutral. No net change in critical coverage.")
    lines.append("")

    # --- Trigger Coverage Analysis ---
    lines.append("### Trigger Coverage Analysis")
    lines.append("")
    lines.append("Which skill triggers each model fired:")
    lines.append("")
    for mk in model_keys:
        tc = trigger_coverage.get(mk, {})
        trigger_count = sum(tc.values()) if tc else 0
        distinct_triggers = len(tc) if tc else 0
        lines.append(f"**{mk}:** {distinct_triggers} distinct triggers fired, {trigger_count} total trigger firings.")
        if tc:
            top_triggers = sorted(tc.items(), key=lambda x: -x[1])[:3]
            trigger_summary = ", ".join(f"{t} ({c}x)" for t, c in top_triggers)
            lines.append(f"  Top triggers: {trigger_summary}")
        lines.append("")

    # --- Verdict ---
    lines.append("### Verdict")
    lines.append("")
    # Score: confirmed findings + skill-only criticals - severity disagreements
    # Precompute per-model disagreement counts from the severities list
    model_disagreements = {mk: 0 for mk in model_keys}
    for d in severity_disagreements:
        sev_map = dict(d["severities"])
        unique_sevs = set(sev_map.values())
        if len(unique_sevs) > 1:
            for mk in model_keys:
                if mk in sev_map:
                    model_disagreements[mk] += 1

    scores = {}
    for mk in model_keys:
        confirmed = confirmed_per_model[mk]
        soc = 0
        boc = 0
        for svb in skill_vs_baseline:
            if svb["model"] == mk:
                soc = svb["skill_only_critical"]
                boc = svb["baseline_only_critical"]
                break
        soc_score = soc if isinstance(soc, int) else 0
        boc_score = boc if isinstance(boc, int) else 0
        # Net critical impact: reward skill-only discoveries, penalize baseline-only (coverage gaps)
        scores[mk] = confirmed + soc_score - boc_score - model_disagreements[mk]

    winner = max(scores, key=scores.get)
    lines.append(f"Based on consensus-confirmed findings, net critical impact (skill-only minus baseline-only), and severity calibration:")
    lines.append("")
    lines.append("| Model | Confirmed | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |")
    lines.append("|-------|:---------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|")
    for mk in model_keys:
        confirmed = confirmed_per_model[mk]
        soc = 0
        boc = 0
        for svb in skill_vs_baseline:
            if svb["model"] == mk:
                soc = svb["skill_only_critical"]
                boc = svb["baseline_only_critical"]
                break
        soc_int = soc if isinstance(soc, int) else 0
        boc_int = boc if isinstance(boc, int) else 0
        net = soc_int - boc_int
        net_str = f"{net:+d}" if net != 0 else "0"
        lines.append(f"| {mk} | {confirmed} | {soc} | {boc} | {net_str} | {model_disagreements[mk]} | {scores[mk]} |")
    lines.append("")
    lines.append("**Scoring:** `confirmed + skill_only_critical - baseline_only_critical - severity_disagreements`. "
                 "The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.")
    lines.append("")

    # Honest read: dynamic narrative based on scores
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    winner_model, winner_score = sorted_scores[0]
    lines.append("**Honest read:** ", )
    # Build per-model summary for the honest read
    model_summaries = []
    for mk in model_keys:
        confirmed = confirmed_per_model[mk]
        soc = 0
        boc = 0
        for svb in skill_vs_baseline:
            if svb["model"] == mk:
                soc = svb["skill_only_critical"] if isinstance(svb["skill_only_critical"], int) else 0
                boc = svb["baseline_only_critical"] if isinstance(svb["baseline_only_critical"], int) else 0
                break
        net = soc - boc
        if net > 0:
            model_summaries.append(f"{mk} gained {net} critical coverage")
        elif net < 0:
            model_summaries.append(f"{mk} lost {abs(net)} critical coverage")
        else:
            model_summaries.append(f"{mk} broke even on criticals")
    # Determine if there's a clear winner or a tie
    if len(sorted_scores) > 1 and sorted_scores[0][1] == sorted_scores[1][1]:
        tied = [m for m, s in sorted_scores if s == sorted_scores[0][1]]
        lines.append(f"{', '.join(tied)} tie for the top score ({winner_score}). "
                     "The skill helps differently per model — see the per-model read above for the tradeoff details.")
    else:
        lines.append(f"{winner_model} wins clearly with score {winner_score}. ")
        # Describe runner-up situation
        runner_up, runner_score = sorted_scores[1]
        if runner_score == winner_score:
            lines.append(f"Tied with {runner_up}.")
        else:
            lines.append(f"{runner_up} follows at {runner_score}.")
        lines.append(" The skill helps differently per model — see the per-model read above for the tradeoff details.")
    lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point."""
    # Determine paths
    script_dir = Path(__file__).parent
    report_dir = script_dir
    repo_root = script_dir.parent

    # Track missing files
    missing_files = []

    # Parse all review files
    all_metrics = {}
    all_findings = {}
    all_triggers = {}
    skill_vs_baseline_comparisons = []

    for model_name, skill_file, baseline_file in MODELS:
        skill_path = report_dir / skill_file
        baseline_path = report_dir / baseline_file

        # Parse with-skill review
        if skill_path.exists():
            skill_findings = parse_review_file(skill_path)
            skill_metrics = {
                "words": len(skill_path.read_text().split()),
                "findings": len(skill_findings),
            }
            for sev in SEVERITIES:
                skill_metrics[sev] = sum(1 for f in skill_findings if f.severity == sev)
            all_metrics[model_name] = {"skill": skill_metrics}
            all_findings[f"{model_name}_skill"] = skill_findings
            all_triggers[model_name] = extract_triggers(skill_findings)
        else:
            missing_files.append(str(skill_path))
            all_metrics[model_name] = {"skill": {"words": "N/A", "findings": "N/A", **{sev: "N/A" for sev in SEVERITIES}}}
            all_findings[f"{model_name}_skill"] = []

        # Parse baseline review
        if baseline_path.exists():
            baseline_findings = parse_review_file(baseline_path)
            baseline_metrics = {
                "words": len(baseline_path.read_text().split()),
                "findings": len(baseline_findings),
            }
            for sev in SEVERITIES:
                baseline_metrics[sev] = sum(1 for f in baseline_findings if f.severity == sev)
            all_metrics[model_name]["baseline"] = baseline_metrics
            all_findings[f"{model_name}_baseline"] = baseline_findings
        else:
            missing_files.append(str(baseline_path))
            all_metrics[model_name]["baseline"] = {"words": "N/A", "findings": "N/A", **{sev: "N/A" for sev in SEVERITIES}}
            all_findings[f"{model_name}_baseline"] = None

        # Compare skill vs baseline
        skill_findings = all_findings.get(f"{model_name}_skill", [])
        baseline_findings = all_findings.get(f"{model_name}_baseline")
        comparison = compare_skill_vs_baseline(skill_findings, baseline_findings, model_name)
        skill_vs_baseline_comparisons.append(comparison)

    # Generate consensus matrix (with-skill only)
    gpt_findings = all_findings.get("gpt-oss-120b_skill", [])
    glm_findings = all_findings.get("glm5.2_skill", [])
    mistral_findings = all_findings.get("mistral_skill", [])

    matched_groups = match_findings_across_models(gpt_findings, glm_findings, mistral_findings)

    # Find severity disagreements
    severity_disagreements = find_severity_disagreements(matched_groups)

    # Generate markdown
    markdown = generate_markdown(
        report_dir=report_dir,
        metrics=all_metrics,
        matched_groups=matched_groups,
        severity_disagreements=severity_disagreements,
        trigger_coverage=all_triggers,
        skill_vs_baseline=skill_vs_baseline_comparisons,
        missing_files=missing_files,
    )

    # Write output
    output_path = report_dir / "comparison.md"
    output_path.write_text(markdown)

    print(f"Generated {output_path}")
    if missing_files:
        print(f"Warning: {len(missing_files)} review files were missing:")
        for f in missing_files:
            print(f"  - {f}")


if __name__ == "__main__":
    main()