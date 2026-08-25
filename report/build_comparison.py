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

import difflib
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from .comparison_render import generate_markdown, generate_scorecard
except ImportError:
    from comparison_render import generate_markdown, generate_scorecard


# Models and their review files
MODELS = [
    ("gpt-oss-120b", "review-gpt-oss-120b.md", "baseline/review-baseline-gpt-oss-120b.md"),
    ("glm5.2", "review-glm5.2.md", "baseline/review-baseline-glm5.2.md"),
    ("mistral", "review-mistral-small-4-119b.md", "baseline/review-baseline-mistral-small-4-119b.md"),
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


def parse_review(content: str, track_section_file: bool = False) -> list[Finding]:
    """Unified parser for all review formats.
    
    Accepts:
    - #{2,4} for severity headings (### or ####)
    - **Location:** and **Location**: field formats (colon inside or outside bold)
    - file:line-range (e.g., server.c:188-189) -> line=188
    - lines 85, 127-128 (no file) -> line=85, file=None
    
    Args:
        content: Review markdown content
        track_section_file: If True, track ### filename.c section headings and
                           assign file to findings without explicit location
    
    Returns:
        List of Finding objects
    """
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

        # Track section headings if enabled (### filename.c)
        if track_section_file:
            section_match = re.match(r"^#{2,3}\s+([\w./-]+\.\w+)\s*$", line)
            if section_match:
                current_section_file = normalize_filename(section_match.group(1))
                i += 1
                continue

        # Match severity heading: ### [SEVERITY] Title or #### SEVERITY Title (brackets optional)
        heading_match = re.match(r"^#{2,4}\s+\[?(CRITICAL|HIGH|MEDIUM|LOW)\]?\s+(.+)$", line)
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

        if current_severity:
            # Match Location field: **Location:** or **Location**:
            loc_match = re.match(r"^\s*-\s*\*\*Location[:*]+\s*(.+)$", line)
            if loc_match:
                current_location = loc_match.group(1).strip()
                i += 1
                continue

            # Match Trigger field
            trigger_match = re.match(r"^\s*-\s*\*\*Trigger[:*]+\s*(.+)$", line)
            if trigger_match:
                current_trigger = trigger_match.group(1).strip()
                i += 1
                continue

            # Match Type field
            type_match = re.match(r"^\s*-\s*\*\*Type[:*]+\s*(.+)$", line)
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


def parse_gpt_oss_review(content: str) -> list[Finding]:
    """Parse gpt-oss-120b review format (#### [SEVERITY] Title)."""
    return parse_review(content, track_section_file=True)


def parse_glm52_review(content: str) -> list[Finding]:
    """Parse glm5.2 review format (### [SEVERITY] Title)."""
    return parse_review(content, track_section_file=True)


def parse_mistral_review(content: str) -> list[Finding]:
    """Parse mistral review format (#### [SEVERITY] Title, groups by file)."""
    return parse_review(content, track_section_file=True)


def parse_baseline_review(content: str) -> list[Finding]:
    """Parse baseline review format (### or #### [SEVERITY] Title)."""
    return parse_review(content, track_section_file=True)


def parse_review_file(filepath: Path) -> list[Finding]:
    """Parse a review file, auto-detecting format based on filename."""
    if not filepath.exists():
        return []

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    filename = filepath.name

    # Dispatch to appropriate parser (all now use unified parse_review)
    if "baseline" in filename:
        return parse_baseline_review(content)
    elif "gpt-oss" in filename:
        return parse_gpt_oss_review(content)
    elif "glm5.2" in filename or "glm52" in filename:
        return parse_glm52_review(content)
    elif "mistral" in filename:
        return parse_mistral_review(content)
    else:
        # Try unified parser
        return parse_review(content, track_section_file=True)


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
    model_findings: dict[str, list[Finding]],
) -> list[dict]:
    """
    Match findings across models by file+line proximity or keyword overlap.
    Returns a list of matched groups with which models found each issue.
    
    Args:
        model_findings: Dict mapping model_name -> list[Finding]
        
    Uses N-agnostic matching: first pass matches through the first model,
    second pass matches unmatched findings from other models (for 2/N consensus),
    third pass adds cross-file fallback for findings in "unspecified" vs named files.
    """
    # Group all findings by file
    by_file = {}
    for model_name, findings in model_findings.items():
        by_file[model_name] = group_findings_by_file(findings)

    all_files = set()
    for file_groups in by_file.values():
        all_files.update(file_groups.keys())

    matched_groups = []
    used_findings = set()

    # Get model names in order
    model_names = list(model_findings.keys())
    
    # Track unmatched findings for cross-file fallback
    unmatched_by_model: dict[str, list[tuple[str, Finding]]] = {m: [] for m in model_names}
    if not model_names:
        return []

    # Use first model as the anchor for matching
    anchor_model = model_names[0]
    anchor_by_file = by_file[anchor_model]

    for file in sorted(all_files):
        # For each finding in anchor model, try to match with other models
        anchor_file_findings = anchor_by_file.get(file, [])

        for i, anchor_f in enumerate(anchor_file_findings):
            if (file, i, anchor_model) in used_findings:
                continue

            group = {"file": file}
            for model_name in model_names:
                group[model_name] = None
            group[anchor_model] = anchor_f
            group["title"] = anchor_f.title
            used_findings.add((file, i, anchor_model))

            # Try to match with other models
            for other_model in model_names[1:]:
                other_file_findings = by_file[other_model].get(file, [])
                for j, other_f in enumerate(other_file_findings):
                    if (file, j, other_model) in used_findings:
                        continue
                    if other_f.line and anchor_f.line and abs(other_f.line - anchor_f.line) <= 10:
                        group[other_model] = other_f
                        used_findings.add((file, j, other_model))
                        break
                    if _keyword_overlap(other_f.title, anchor_f.title):
                        group[other_model] = other_f
                        used_findings.add((file, j, other_model))
                        break

            matched_groups.append(group)

        # Track unmatched findings for cross-file fallback
        for model_name in model_names:
            model_file_findings = by_file[model_name].get(file, [])
            for j, f in enumerate(model_file_findings):
                if (file, j, model_name) not in used_findings:
                    unmatched_by_model[model_name].append((file, f))

        # Second pass: Match unmatched findings from other models against each other
        for other_model in model_names[1:]:
            other_file_findings = by_file[other_model].get(file, [])
            for j, other_f in enumerate(other_file_findings):
                if (file, j, other_model) in used_findings:
                    continue

                # Try to match with remaining unmatched models
                for other_model2 in model_names[1:]:
                    if other_model2 == other_model:
                        continue
                    other_file_findings2 = by_file[other_model2].get(file, [])
                    for k, other_f2 in enumerate(other_file_findings2):
                        if (file, k, other_model2) in used_findings:
                            continue

                        # Match by line proximity or keyword overlap
                        if other_f.line and other_f2.line and abs(other_f.line - other_f2.line) <= 10:
                            matched_groups.append({
                                "file": file,
                                **{m: None for m in model_names},
                                other_model: other_f,
                                other_model2: other_f2,
                                "title": other_f.title,
                            })
                            used_findings.add((file, j, other_model))
                            used_findings.add((file, k, other_model2))
                            break
                        elif _keyword_overlap(other_f.title, other_f2.title):
                            matched_groups.append({
                                "file": file,
                                **{m: None for m in model_names},
                                other_model: other_f,
                                other_model2: other_f2,
                                "title": other_f.title,
                            })
                            used_findings.add((file, j, other_model))
                            used_findings.add((file, k, other_model2))
                            break

        # Add remaining unmatched findings
        for model_name in model_names:
            model_file_findings = by_file[model_name].get(file, [])
            for j, f in enumerate(model_file_findings):
                if (file, j, model_name) not in used_findings:
                    group = {"file": file, **{m: None for m in model_names}, "title": f.title}
                    group[model_name] = f
                    matched_groups.append(group)
                    used_findings.add((file, j, model_name))

    # Cross-file fallback pass: match unmatched findings across models using title similarity
    for model_name in model_names:
        for file1, finding1 in unmatched_by_model[model_name]:
            if not finding1.title:
                continue
            # Try to match against other models' unmatched findings
            for other_model in model_names:
                if other_model == model_name:
                    continue
                for file2, finding2 in unmatched_by_model[other_model]:
                    # Skip if already matched
                    if (file2, finding2, other_model) in used_findings:
                        continue
                    # Match by title similarity (cross-file fallback)
                    if _title_similarity(finding1.title, finding2.title) >= 0.4:
                        group = {
                            "file": finding1.file or finding2.file or "unspecified",
                            **{m: None for m in model_names},
                            model_name: finding1,
                            other_model: finding2,
                            "title": finding1.title,
                        }
                        matched_groups.append(group)
                        used_findings.add((file1, finding1, model_name))
                        used_findings.add((file2, finding2, other_model))
                        break

    return matched_groups


def _title_similarity(title1: str, title2: str) -> float:
    """Calculate string similarity between two titles using SequenceMatcher.
    
    Returns a float between 0.0 and 1.0, where 1.0 means identical.
    Uses difflib.SequenceMatcher for fuzzy string comparison.
    """
    return difflib.SequenceMatcher(None, title1.lower(), title2.lower()).ratio()


def _keyword_overlap(title1: str, title2: str) -> bool:
    """Check if two titles share significant keywords.
    
    Returns True if titles match by:
    - At least 2 overlapping content words (after filtering stopwords), OR
    - Jaccard similarity ratio >= 0.3, OR
    - SequenceMatcher similarity >= 0.35
    """
    # First check sequence similarity (new fuzzy matching)
    if _title_similarity(title1, title2) >= 0.35:
        return True
    
    words1 = set(re.findall(r"\b\w+\b", title1.lower()))
    words2 = set(re.findall(r"\b\w+\b", title2.lower()))
    # Filter out common words
    common_words = {"the", "a", "an", "is", "are", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with"}
    words1 -= common_words
    words2 -= common_words
    if not words1 or not words2:
        return False
    overlap = words1 & words2
    # Require at least 2 overlapping words OR Jaccard ratio >= 0.3
    if len(overlap) >= 2:
        return True
    if len(words1 | words2) > 0:
        jaccard = len(overlap) / len(words1 | words2)
        return jaccard >= 0.3
    return False


def find_severity_disagreements(matched_groups: list[dict], model_names: list[str] | None = None) -> list[dict]:
    """Find cases where 2+ models found the same issue but assigned different severities.
    
    Args:
        matched_groups: List of matched finding groups
        model_names: Optional list of model names to check. If None, extracts from group keys.
    """
    disagreements = []
    for group in matched_groups:
        severities = []
        # Extract model names from group if not provided
        if model_names is None:
            model_names = [k for k in group.keys() if k not in ("file", "title")]
        
        for model_name in model_names:
            finding = group.get(model_name)
            if finding:
                severities.append((model_name, finding.severity))

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

    # Fuzzy matching: same bug may have different line numbers or slightly different titles
    # Track matched pairs (each baseline can only match one skill finding)
    matched_skill = set()
    matched_baseline = set()
    
    for si, skill_f in enumerate(skill_critical):
        if not skill_f.file or not skill_f.line:
            continue
        # Find best matching baseline critical
        best_score = -1
        best_j = None
        for bj, baseline_f in enumerate(baseline_critical):
            if bj in matched_baseline:
                continue
            if not baseline_f.file or not baseline_f.line:
                continue
            score = 0
            # Same file AND line within ±10 lines → match
            if skill_f.file == baseline_f.file and abs(skill_f.line - baseline_f.line) <= 10:
                score = 1.0
            # Same file AND title similarity >= 0.35 → match
            elif skill_f.file == baseline_f.file and _title_similarity(skill_f.title, baseline_f.title) >= 0.35:
                score = 0.8
            # Different file but title similarity >= 0.5 (cross-file fallback) → match
            elif _title_similarity(skill_f.title, baseline_f.title) >= 0.5:
                score = 0.6
            if score > best_score:
                best_score = score
                best_j = bj
        # Match if we found a good candidate
        if best_score >= 0.6 and best_j is not None:
            matched_skill.add(si)
            matched_baseline.add(best_j)
    
    # Compute overlap/skill_only/baseline_only from matched pairs
    overlap_count = len(matched_skill)
    skill_only_count = len(skill_critical) - len(matched_skill)
    baseline_only_count = len(baseline_critical) - len(matched_baseline)

    return {
        "model": model_name,
        "skill_total": len(skill_findings),
        "baseline_total": len(baseline_findings),
        "skill_critical": len(skill_critical),
        "baseline_critical": len(baseline_critical),
        "critical_overlap": overlap_count,
        "skill_only_critical": skill_only_count,
        "baseline_only_critical": baseline_only_count,
    }



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
    # Build dict of model_name -> findings for data-driven matching
    skill_findings_by_model = {}
    for model_name, skill_file, _ in MODELS:
        findings = all_findings.get(f"{model_name}_skill", [])
        skill_findings_by_model[model_name] = findings

    matched_groups = match_findings_across_models(skill_findings_by_model)

    # Find severity disagreements
    model_names = [m[0] for m in MODELS]
    severity_disagreements = find_severity_disagreements(matched_groups, model_names)

    # Generate markdown
    model_names = [m[0] for m in MODELS]
    markdown = generate_markdown(
        report_dir=report_dir,
        metrics=all_metrics,
        matched_groups=matched_groups,
        severity_disagreements=severity_disagreements,
        trigger_coverage=all_triggers,
        skill_vs_baseline=skill_vs_baseline_comparisons,
        missing_files=missing_files,
        model_names=model_names,
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
