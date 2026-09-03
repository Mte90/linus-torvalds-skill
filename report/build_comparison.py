#!/usr/bin/env python3
"""
Build comparison.md from review files (with-skill and baseline).

Parses review files in different formats, extracts findings, and generates:
- Metrics table (word counts, finding counts by severity)
- Consensus matrix (cross-reference findings across models)
- Severity disagreement table
- Trigger coverage table
- With-skill vs baseline comparison
- Ground-truth benchmark metrics (precision/recall/F1)

Run from repository root: python3 report/build_comparison.py
"""

import json
import re
from collections import defaultdict
from pathlib import Path

try:
    from .comparison_render import generate_markdown, generate_scorecard  # noqa: F401

except ImportError:
    from comparison_render import generate_markdown  # noqa: F401


# Models and their review files
MODELS = [
    ("gpt-oss-120b", "review-gpt-oss-120b.md", "baseline/review-baseline-gpt-oss-120b.md"),
    ("glm5.2", "review-glm5.2.md", "baseline/review-baseline-glm5.2.md"),
    (
        "mistral",
        "review-mistral-small-4-119b.md",
        "baseline/review-baseline-mistral-small-4-119b.md",
    ),
]

SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# Core-vs-trivia classifier: maps finding attributes to CORE/TRIVIA.
# CORE = correctness, memory-safety, or error-handling issues.
# TRIVIA = style, build, or documentation issues.
_CORE_CATEGORIES = {
    "correctness",
    "memory-safety",
    "error-handling",
    "bounds-check",
    "null-check",
    "return-value",
    "resource-leak",
    "race-condition",
    "overflow",
    "underflow",
    "use-after-free",
    "double-free",
    "uninitialized",
    "sigpipe",
    "fd-leak",
    "socket",
    "buffer",
}
_CORE_SEVERITIES = {"CRITICAL", "HIGH"}
_TRIVIA_CATEGORIES = {"style", "build", "docs", "performance", "convention"}
_TRIVIA_SEVERITIES = {
    "LOW"
}  # LOW severity findings are typically trivia unless they hit core categories


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

        # Format: bare filename (e.g. "smallchat-server.c") — no line number
        bare_file_match = re.match(r"^([\w./-]+\.\w+)$", loc)
        if bare_file_match:
            self.file = normalize_filename(bare_file_match.group(1))
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
                f = Finding(
                    current_severity, current_title, current_location, current_trigger, current_type
                )
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
        f = Finding(
            current_severity, current_title, current_location, current_trigger, current_type
        )
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


def _finding_richness(f: Finding) -> int:
    """Score how many fields a finding has populated (for dedup tie-breaking)."""
    return sum(1 for v in (f.location, f.trigger, f.finding_type, f.file, f.line) if v)


def classify_finding_core_vs_trivia(f: Finding) -> str:
    """Classify a finding as CORE or TRIVIA.

    CORE findings:
    - Severity is CRITICAL or HIGH, OR
    - Trigger/category maps to correctness/memory-safety/error-handling

    TRIVIA findings:
    - Severity is LOW and category is style/build/docs/performance/convention

    Args:
        f: Finding object with severity, trigger, and finding_type fields

    Returns:
        "CORE" or "TRIVIA"
    """
    # High/critical severity always CORE
    if f.severity in _CORE_SEVERITIES:
        return "CORE"

    # Check trigger text for core category keywords
    if f.trigger:
        trigger_lower = f.trigger.lower()
        for cat in _CORE_CATEGORIES:
            if cat in trigger_lower:
                return "CORE"

    # Check finding_type for core categories
    if f.finding_type:
        type_lower = f.finding_type.lower()
        for cat in _CORE_CATEGORIES:
            if cat in type_lower:
                return "CORE"

    # LOW severity with trivia category -> TRIVIA
    if f.severity in _TRIVIA_SEVERITIES:
        if f.trigger:
            trigger_lower = f.trigger.lower()
            for cat in _TRIVIA_CATEGORIES:
                if cat in trigger_lower:
                    return "TRIVIA"
        if f.finding_type:
            type_lower = f.finding_type.lower()
            for cat in _TRIVIA_CATEGORIES:
                if cat in type_lower:
                    return "TRIVIA"

    # Default: MEDIUM/LOW without explicit trivia markers -> CORE (conservative)
    return "CORE"


def _dedup_findings(findings: list[Finding]) -> list[Finding]:
    """Collapse duplicate findings within a single review.

    Two findings are duplicates when they share the same file AND:
    - title similarity >= 0.35 (same bug, slightly different wording), or
    - title similarity >= 0.20 AND lines within ±3 (same location, similar title).
    Line proximity alone is insufficient — in small files, different bugs
    can be within ±10 lines of each other.
    The richer finding (more populated fields) wins; ties keep the first.
    """
    if len(findings) <= 1:
        return list(findings)

    kept: list[Finding] = []
    for f in findings:
        dup_idx = None
        for ki, kf in enumerate(kept):
            same_file = f.file and kf.file and f.file == kf.file
            if not same_file:
                continue
            title_sim = _title_similarity(f.title, kf.title)
            line_close = f.line and kf.line and abs(f.line - kf.line) <= 3
            if title_sim >= 0.30 or (title_sim >= 0.20 and line_close):
                dup_idx = ki
                break
        if dup_idx is None:
            kept.append(f)
        else:
            rival = kept[dup_idx]
            if _finding_richness(f) > _finding_richness(rival):
                kept[dup_idx] = f
    return kept


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
        findings = parse_baseline_review(content)
    elif "gpt-oss" in filename:
        findings = parse_gpt_oss_review(content)
    elif "glm5.2" in filename or "glm52" in filename:
        findings = parse_glm52_review(content)
    elif "mistral" in filename:
        findings = parse_mistral_review(content)
    else:
        findings = parse_review(content, track_section_file=True)

    return _dedup_findings(findings)


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
                        if (
                            other_f.line
                            and other_f2.line
                            and abs(other_f.line - other_f2.line) <= 10
                        ):
                            matched_groups.append(
                                {
                                    "file": file,
                                    **{m: None for m in model_names},
                                    other_model: other_f,
                                    other_model2: other_f2,
                                    "title": other_f.title,
                                }
                            )
                            used_findings.add((file, j, other_model))
                            used_findings.add((file, k, other_model2))
                            break
                        elif _keyword_overlap(other_f.title, other_f2.title):
                            matched_groups.append(
                                {
                                    "file": file,
                                    **{m: None for m in model_names},
                                    other_model: other_f,
                                    other_model2: other_f2,
                                    "title": other_f.title,
                                }
                            )
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
                    if _title_similarity(finding1.title, finding2.title) >= 0.30:
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
    """Calculate semantic similarity between two finding titles.

    Uses token-based Jaccard similarity on content words (stopwords removed).
    More robust than character-sequence matching for short technical titles
    that share domain terms (e.g., 'createClient') but describe different bugs.
    """
    stopwords = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "not",
        "no",
        "—",
        "that",
        "this",
    }
    words1 = set(re.findall(r"\b\w+\b", title1.lower())) - stopwords
    words2 = set(re.findall(r"\b\w+\b", title2.lower())) - stopwords
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def _keyword_overlap(title1: str, title2: str) -> bool:
    """Check if two titles share significant keywords.

    Returns True if titles match by:
    - At least 2 overlapping content words (after filtering stopwords), OR
    - Jaccard similarity ratio >= 0.3, OR
    - SequenceMatcher similarity >= 0.35
    """
    # First check sequence similarity (new fuzzy matching)
    if _title_similarity(title1, title2) >= 0.30:
        return True

    words1 = set(re.findall(r"\b\w+\b", title1.lower()))
    words2 = set(re.findall(r"\b\w+\b", title2.lower()))
    # Filter out common words
    common_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
    }
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


def find_severity_disagreements(
    matched_groups: list[dict], model_names: list[str] | None = None
) -> list[dict]:
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
                disagreements.append(
                    {
                        "title": group["title"],
                        "file": group["file"],
                        "severities": severities,
                    }
                )
    return disagreements


def extract_triggers(findings: list[Finding]) -> dict[str, int]:
    """Extract and count unique triggers from findings."""
    triggers = defaultdict(int)
    for f in findings:
        if f.trigger:
            triggers[f.trigger] += 1
    return dict(triggers)


def _match_findings_fuzzy(
    skill_findings: list[Finding],
    baseline_findings: list[Finding],
) -> tuple[list[dict], list[Finding], list[Finding]]:
    """Fuzzy-match findings between skill and baseline.

    Returns:
        - matched_pairs: list of {"baseline": Finding|None, "skill": Finding|None, "title": str, "file": str}
        - baseline_only: findings only in baseline (skill missed)
        - skill_only: findings only with skill (skill added)

    Matching rules:
        - Same file AND line within ±10 lines → match
        - Same file AND title similarity >= 0.30 → match
        - Different file but title similarity >= 0.5 (cross-file fallback) → match
    Each baseline finding can match at most one skill finding (greedy best-score).
    """
    matched_pairs = []
    matched_skill = set()
    matched_baseline = set()

    # Build candidate pairs with scores
    candidates = []
    for si, skill_f in enumerate(skill_findings):
        if not skill_f.file or not skill_f.line:
            continue
        for bj, baseline_f in enumerate(baseline_findings):
            if not baseline_f.file or not baseline_f.line:
                continue
            score = 0
            # Same file AND line within ±10 lines → match
            if skill_f.file == baseline_f.file and abs(skill_f.line - baseline_f.line) <= 10:
                score = 1.0
            # Same file AND title similarity >= 0.30 → match
            elif (
                skill_f.file == baseline_f.file
                and _title_similarity(skill_f.title, baseline_f.title) >= 0.30
            ):
                score = 0.8
            # Different file but title similarity >= 0.5 (cross-file fallback) → match
            elif _title_similarity(skill_f.title, baseline_f.title) >= 0.5:
                score = 0.6
            if score >= 0.6:
                candidates.append((score, si, bj, skill_f, baseline_f))

    # Sort by score descending (greedy best-score matching)
    candidates.sort(key=lambda x: -x[0])

    # Greedy matching: each baseline can only match one skill finding
    for _score, si, bj, skill_f, baseline_f in candidates:
        if si in matched_skill or bj in matched_baseline:
            continue
        matched_skill.add(si)
        matched_baseline.add(bj)
        matched_pairs.append(
            {
                "baseline": baseline_f,
                "skill": skill_f,
                "title": skill_f.title,
                "file": skill_f.file or baseline_f.file or "unspecified",
            }
        )

    # Build baseline_only and skill_only lists
    baseline_only = [
        baseline_findings[bj] for bj in range(len(baseline_findings)) if bj not in matched_baseline
    ]
    skill_only = [
        skill_findings[si] for si in range(len(skill_findings)) if si not in matched_skill
    ]

    return matched_pairs, baseline_only, skill_only


def extract_skill_triggers(skill_path: Path) -> list[str]:
    """Extract all trigger texts from the skill markdown file.

    Extracts from two formats:
    - **Trigger:** *<trigger text>* (Level 1 and Level 3 triggers)
    - **Triggers (3‑6 each)**: 1. *<trigger text>* – ... <br>2. *<trigger text>* – ... (Level 2)

    Returns deduplicated list of trigger description strings.
    """
    if not skill_path.exists():
        return []

    content = skill_path.read_text(encoding="utf-8", errors="replace")
    triggers = set()

    # Format 1: **Trigger:** *<trigger text>*
    for match in re.finditer(r"\*\*Trigger:\*\*\s*\*([^*]+)\*", content):
        trigger_text = match.group(1).strip()
        if trigger_text:
            triggers.add(trigger_text)

    # Format 2: **Triggers (3‑6 each)**: 1. *<trigger text>* – ... <br>2. *<trigger text>* – ...
    for match in re.finditer(
        r"\*\*Triggers \(3‑6 each\)\*\*:\s*(.+?)(?=\n\s*\n|\n\s*-\s*\*\*Theme|\n\s*####|\Z)",
        content,
        re.DOTALL,
    ):
        triggers_block = match.group(1)
        # Split on <br>
        for part in triggers_block.split("<br>"):
            # Match numbered triggers: N. *<trigger text>*
            for trig_match in re.finditer(r"\d+\.\s*\*([^*]+)\*", part):
                trigger_text = trig_match.group(1).strip()
                # Strip the " – <example>" suffix if present
                trigger_text = re.sub(r"\s*–.*$", "", trigger_text)
                if trigger_text:
                    triggers.add(trigger_text)

    return list(triggers)


def match_finding_to_trigger(finding: Finding, triggers: list[str]) -> tuple[str | None, float]:
    """Find the best-matching skill trigger for a finding.

    Uses keyword overlap to find semantically relevant triggers.
    Returns:
        (matched_trigger_text, similarity_score) or (None, 0.0) if no triggers
    """
    if not triggers:
        return None, 0.0

    # Extract keywords from finding title (content words, not stopwords)
    stopwords = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "not",
        "no",
        "that",
        "this",
        "when",
        "while",
        "without",
        "into",
        "from",
        "by",
        "as",
        "be",
    }
    finding_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", finding.title.lower())) - stopwords

    best_trigger = None
    best_score = 0.0

    for trigger in triggers:
        trigger_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", trigger.lower())) - stopwords
        if not trigger_words:
            continue
        # Jaccard similarity on content words
        intersection = finding_words & trigger_words
        union = finding_words | trigger_words
        if union:
            score = len(intersection) / len(union)
            if score > best_score:
                best_score = score
                best_trigger = trigger

    # Threshold for "covered": at least some keyword overlap
    if best_score >= 0.05:  # Very lenient - just needs some overlap
        return best_trigger, best_score
    return None, best_score


def analyze_trigger_effectiveness(
    baseline_findings: list[Finding],
    skill_findings: list[Finding],
) -> dict:
    """Analyze per-trigger effectiveness metrics.

    For each trigger, computes:
    - Times fired: how many skill findings mapped to this trigger
    - True positives: how many of those also matched a baseline finding
    - Precision: true positives / times fired (how often the trigger finds real bugs)
    - Recall: true positives / total baseline findings (how much of baseline coverage this trigger captures)

    Args:
        baseline_findings: Findings from the baseline run
        skill_findings: Findings from the skill run (each should have trigger mapped)

    Returns:
        Dict with keys:
        - triggers: list of dicts with keys: trigger, fires, true_positives, precision, recall
        - summary: dict with keys: total_triggers, total_fires, overall_precision, overall_recall
    """
    if not skill_findings:
        return {
            "triggers": [],
            "summary": {
                "total_triggers": 0,
                "total_fires": 0,
                "overall_precision": 0.0,
                "overall_recall": 0.0,
            },
        }

    # Map each baseline finding to a unique key for matching
    baseline_keys = set()
    for bf in baseline_findings:
        if bf.file and bf.line:
            baseline_keys.add((bf.file, bf.line))
        elif bf.title:
            # Fallback: use title as key if no location
            baseline_keys.add(("__title__", bf.title))

    # Group skill findings by trigger
    trigger_fires: dict[str | None, list[Finding]] = defaultdict(list)
    for sf in skill_findings:
        trigger_key = sf.trigger if sf.trigger else "unmatched"
        trigger_fires[trigger_key].append(sf)

    # Compute per-trigger metrics
    trigger_metrics = []
    total_true_positives = 0
    total_fires = 0

    for trigger, fires in trigger_fires.items():
        fires_count = len(fires)
        total_fires += fires_count

        # Count true positives (skill finding matched a baseline finding)
        true_positives = 0
        for sf in fires:
            # Check if this skill finding matches any baseline finding
            if sf.file and sf.line:
                if (sf.file, sf.line) in baseline_keys:
                    true_positives += 1
            elif sf.title:
                # Fallback: check by title similarity
                for bf in baseline_findings:
                    if _title_similarity(sf.title, bf.title) >= 0.30:
                        true_positives += 1
                        break

        total_true_positives += true_positives

        # Precision: true positives / times fired
        precision = true_positives / fires_count if fires_count > 0 else 0.0

        # Recall: true positives / total baseline findings
        # This measures how much of the baseline coverage this trigger captures
        recall = true_positives / len(baseline_findings) if baseline_findings else 0.0

        trigger_display = trigger if trigger else "unmatched"
        trigger_metrics.append(
            {
                "trigger": trigger_display,
                "fires": fires_count,
                "true_positives": true_positives,
                "precision": precision,
                "recall": recall,
            }
        )

    # Sort by true positives descending (most effective triggers first)
    trigger_metrics.sort(key=lambda x: (-x["true_positives"], -x["fires"]))

    # Overall metrics
    overall_precision = total_true_positives / total_fires if total_fires > 0 else 0.0
    overall_recall = total_true_positives / len(baseline_findings) if baseline_findings else 0.0

    return {
        "triggers": trigger_metrics,
        "summary": {
            "total_triggers": len(trigger_metrics),
            "total_fires": total_fires,
            "overall_precision": overall_precision,
            "overall_recall": overall_recall,
        },
    }


def compare_skill_vs_baseline(
    skill_findings: list[Finding],
    baseline_findings: list[Finding] | None,
    model_name: str,
    skill_triggers: list[str] | None = None,
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
            "matched_pairs": [],
            "baseline_only_all": [],
            "skill_only_all": [],
            # Focus metrics (new)
            "skill_core_pct": "N/A",
            "baseline_core_pct": "N/A",
            "focus_drift_warning": False,
            "critical_focus_failure": False,
        }

    baseline_critical = [f for f in baseline_findings if f.severity == "CRITICAL"]

    # Fuzzy matching for CRITICAL findings (existing logic, unchanged)
    matched_skill_critical = set()
    matched_baseline_critical = set()

    for si, skill_f in enumerate(skill_critical):
        if not skill_f.file or not skill_f.line:
            continue
        # Find best matching baseline critical
        best_score = -1
        best_j = None
        for bj, baseline_f in enumerate(baseline_critical):
            if bj in matched_baseline_critical:
                continue
            if not baseline_f.file or not baseline_f.line:
                continue
            score = 0
            # Same file AND line within ±10 lines → match
            if skill_f.file == baseline_f.file and abs(skill_f.line - baseline_f.line) <= 10:
                score = 1.0
            # Same file AND title similarity >= 0.35 → match
            elif (
                skill_f.file == baseline_f.file
                and _title_similarity(skill_f.title, baseline_f.title) >= 0.30
            ):
                score = 0.8
            # Different file but title similarity >= 0.5 (cross-file fallback) → match
            elif _title_similarity(skill_f.title, baseline_f.title) >= 0.5:
                score = 0.6
            if score > best_score:
                best_score = score
                best_j = bj
        # Match if we found a good candidate
        if best_score >= 0.6 and best_j is not None:
            matched_skill_critical.add(si)
            matched_baseline_critical.add(best_j)

    # Compute overlap/skill_only/baseline_only from matched pairs
    overlap_count = len(matched_skill_critical)
    skill_only_count = len(skill_critical) - len(matched_skill_critical)
    baseline_only_count = len(baseline_critical) - len(matched_baseline_critical)

    # Match ALL findings (not just criticals) using the same fuzzy matching logic
    matched_pairs_all, baseline_only_all, skill_only_all = _match_findings_fuzzy(
        skill_findings, baseline_findings
    )

    # Match findings to skill triggers for coverage analysis
    baseline_only_with_coverage = []
    for f in baseline_only_all:
        matched_trigger, similarity = match_finding_to_trigger(f, skill_triggers or [])
        baseline_only_with_coverage.append(
            {
                "finding": f,
                "matched_trigger": matched_trigger,
                "similarity": similarity,
            }
        )

    skill_only_with_coverage = []
    for f in skill_only_all:
        matched_trigger, similarity = match_finding_to_trigger(f, skill_triggers or [])
        skill_only_with_coverage.append(
            {
                "finding": f,
                "matched_trigger": matched_trigger,
                "similarity": similarity,
            }
        )

    # Compute focus metrics: % CORE among with-skill findings, % CORE among baseline-only misses
    skill_core_count = sum(
        1 for f in skill_findings if classify_finding_core_vs_trivia(f) == "CORE"
    )
    skill_core_pct = (skill_core_count / len(skill_findings) * 100) if skill_findings else 0.0

    baseline_only_core_count = sum(
        1 for f in baseline_only_all if classify_finding_core_vs_trivia(f) == "CORE"
    )
    baseline_core_pct = (
        (baseline_only_core_count / len(baseline_only_all) * 100) if baseline_only_all else 0.0
    )

    # Focus drift gate: with-skill CORE% < 50% → FOCUS DRIFT warning
    focus_drift_warning = skill_core_pct < 50.0

    # Critical focus failure gate: baseline-only contains any CRITICAL while skill-only is majority trivia
    skill_only_core_count = sum(
        1 for f in skill_only_all if classify_finding_core_vs_trivia(f) == "CORE"
    )
    skill_only_trivia_count = len(skill_only_all) - skill_only_core_count
    baseline_only_critical_count = sum(1 for f in baseline_only_all if f.severity == "CRITICAL")

    critical_focus_failure = (
        baseline_only_critical_count > 0
        and skill_only_all
        and skill_only_trivia_count > skill_only_core_count
    )

    return {
        "model": model_name,
        "skill_total": len(skill_findings),
        "baseline_total": len(baseline_findings),
        "skill_critical": len(skill_critical),
        "baseline_critical": len(baseline_critical),
        "critical_overlap": overlap_count,
        "skill_only_critical": skill_only_count,
        "baseline_only_critical": baseline_only_count,
        "matched_pairs": matched_pairs_all,
        "baseline_only_all": baseline_only_all,
        "skill_only_all": skill_only_all,
        "baseline_only_with_coverage": baseline_only_with_coverage,
        "skill_only_with_coverage": skill_only_with_coverage,
        # Focus metrics (new)
        "skill_core_pct": skill_core_pct,
        "baseline_core_pct": baseline_core_pct,
        "focus_drift_warning": focus_drift_warning,
        "critical_focus_failure": critical_focus_failure,
    }


# Benchmark functions (defined after Finding class)

BENCHMARK_SEVERITY_MAP = {
    "reject": "CRITICAL",
    "request-changes": "HIGH",
    "nitpick": "MEDIUM",
}


def load_benchmark(benchmark_path: Path) -> list[dict] | None:
    """Load benchmark JSONL file.

    Returns None if file doesn't exist (graceful skip).
    """
    if not benchmark_path.exists():
        return None

    records = []
    with open(benchmark_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip malformed lines
                continue
    return records


def match_finding_to_benchmark(
    finding: Finding, benchmark_records: list[dict], line_tolerance: int = 10
) -> dict | None:
    """Match a finding to a benchmark record.

    Matching rules:
    - Same file AND line within ±line_tolerance → match
    - Same file AND category match AND title/trigger keyword overlap → match

    Returns matched benchmark record or None.
    """
    if not finding.file or not finding.line:
        return None

    normalized_file = normalize_filename(finding.file)

    for record in benchmark_records:
        rec_file = normalize_filename(record.get("file", ""))
        rec_line = record.get("line")

        if not rec_file or not rec_line:
            continue

        # Same file AND line within tolerance
        if normalized_file == rec_file and abs(finding.line - rec_line) <= line_tolerance:
            return record

        # Same file AND category match AND keyword overlap (fallback)
        finding_category = finding.trigger or finding.title
        rec_trigger = record.get("trigger", "")
        if (
            normalized_file == rec_file
            and _keyword_overlap(finding_category, rec_trigger)
            and abs(finding.line - rec_line) <= line_tolerance * 2
        ):
            return record

    return None


def compute_benchmark_metrics(findings: list[Finding], benchmark_records: list[dict]) -> dict:
    """Compute precision, recall, F1 against benchmark ground truth.

    Returns dict with:
    - precision: benchmark hits / total findings
    - recall: benchmark hits / total benchmark records
    - f1: harmonic mean of precision and recall
    - hits: list of matched benchmark IDs
    - misses: list of unmatched benchmark IDs
    - severity_match_rate: % of hits where severity matches
    """
    if not benchmark_records:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "hits": [],
            "misses": [r["id"] for r in benchmark_records],
            "severity_match_rate": 0.0,
            "total_findings": len(findings),
            "total_benchmark": len(benchmark_records),
        }

    matched_benchmark_ids = set()
    matched_severities = []

    for finding in findings:
        matched_record = match_finding_to_benchmark(finding, benchmark_records)
        if matched_record:
            bid = matched_record.get("id")
            if bid and bid not in matched_benchmark_ids:
                matched_benchmark_ids.add(bid)
                # Check severity match
                finding_sev = finding.severity.lower()
                rec_sev = matched_record.get("severity", "").lower()
                # Map benchmark severity to our scale for comparison
                mapped_rec_sev = BENCHMARK_SEVERITY_MAP.get(rec_sev, rec_sev).lower()
                if finding_sev == rec_sev or finding_sev == mapped_rec_sev:
                    matched_severities.append(bid)

    hits = sorted(matched_benchmark_ids)
    misses = sorted(
        [r["id"] for r in benchmark_records if r.get("id") not in matched_benchmark_ids]
    )

    # Precision: how many of our findings hit benchmark
    precision = len(hits) / len(findings) if findings else 0.0

    # Recall: how many benchmark records we found
    recall = len(hits) / len(benchmark_records) if benchmark_records else 0.0

    # F1
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Severity match rate
    severity_match_rate = len(matched_severities) / len(hits) if hits else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "hits": hits,
        "misses": misses,
        "severity_match_rate": severity_match_rate,
        "total_findings": len(findings),
        "total_benchmark": len(benchmark_records),
    }


def main():
    """Main entry point."""
    # Determine paths
    script_dir = Path(__file__).parent
    report_dir = script_dir
    repo_root = script_dir.parent

    # Load benchmark (graceful skip if missing)
    benchmark_path = repo_root / "data" / "benchmark.jsonl"
    benchmark_records = load_benchmark(benchmark_path)
    benchmark_missing = benchmark_records is None
    if benchmark_missing:
        print("Warning: benchmark.jsonl not found, skipping ground-truth metrics")

    # Extract skill triggers once
    skill_path = repo_root / "linus-torvalds-skill" / "SKILL.md"
    skill_triggers = extract_skill_triggers(skill_path)

    # Track missing files
    missing_files = []

    # Parse all review files
    all_metrics = {}
    all_findings = {}
    all_triggers = {}
    skill_vs_baseline_comparisons = []
    trigger_effectiveness = {}

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
            all_metrics[model_name] = {
                "skill": {"words": "N/A", "findings": "N/A", **{sev: "N/A" for sev in SEVERITIES}}
            }
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
            all_metrics[model_name]["baseline"] = {
                "words": "N/A",
                "findings": "N/A",
                **{sev: "N/A" for sev in SEVERITIES},
            }
            all_findings[f"{model_name}_baseline"] = None

        # Compare skill vs baseline
        skill_findings = all_findings.get(f"{model_name}_skill", [])
        baseline_findings = all_findings.get(f"{model_name}_baseline")
        comparison = compare_skill_vs_baseline(
            skill_findings, baseline_findings, model_name, skill_triggers
        )
        skill_vs_baseline_comparisons.append(comparison)

        # Compute trigger effectiveness for this model
        if baseline_findings is not None:
            trigger_effectiveness[model_name] = analyze_trigger_effectiveness(
                baseline_findings, skill_findings
            )
        else:
            trigger_effectiveness[model_name] = {
                "triggers": [],
                "summary": {
                    "total_triggers": 0,
                    "total_fires": 0,
                    "overall_precision": 0.0,
                    "overall_recall": 0.0,
                },
            }

    # Generate consensus matrix (with-skill only)
    # Build dict of model_name -> findings for data-driven matching
    skill_findings_by_model = {}
    for model_name, _skill_file, _ in MODELS:
        findings = all_findings.get(f"{model_name}_skill", [])
        skill_findings_by_model[model_name] = findings

    matched_groups = match_findings_across_models(skill_findings_by_model)

    # Find severity disagreements
    model_names = [m[0] for m in MODELS]
    severity_disagreements = find_severity_disagreements(matched_groups, model_names)

    # Compute benchmark metrics for each model's findings
    benchmark_metrics = {}
    if benchmark_records is not None:
        for key, findings in all_findings.items():
            model_name = key.replace("_skill", "").replace("_baseline", "")
            benchmark_metrics[key] = compute_benchmark_metrics(findings, benchmark_records)

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
        trigger_effectiveness=trigger_effectiveness,
        benchmark_records=benchmark_records,
        benchmark_metrics=benchmark_metrics,
    )

    # Write output
    output_path = report_dir / "comparison.md"
    output_path.write_text(markdown)

    print(f"Generated {output_path}")
    if missing_files:
        print(f"Warning: {len(missing_files)} review files were missing:")
        for f in missing_files:
            print(f"  - {f}")
    if benchmark_missing:
        print("Note: Ground-truth benchmark section skipped (data/benchmark.jsonl not found)")


if __name__ == "__main__":
    main()
