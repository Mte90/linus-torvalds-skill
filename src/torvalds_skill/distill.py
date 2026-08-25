"""
distill.py — final LLM call: sampled moves by category → skill markdown.

Takes patterns.json (now: sampled moves by category, not pre-clustered
patterns), formats them into a prompt, and asks the LLM to both:
1. Find recurring themes/patterns across the samples (semantic grouping)
2. Synthesize them into a reviewer skill

The LLM does the semantic grouping in one pass — far better than lexical
Jaccard on freeform LLM-generated principles.

The skill output is language-agnostic — it captures Torvalds' reviewing
METHOD, not his C/kernel-specific knowledge.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import config
from .audit import log_decision
from .distill_prompts import (
    DISTILL_SYSTEM_PROMPT,
    build_category_system_prompt,
    build_synthesis_system_prompt,
)
from .distill_llm import _call_llm, _detect_truncation, _patch_truncated_section
from .distill_sanitize import (
    SANITIZE_REPLACEMENTS,
    generalize_trigger,
    sanitize_skill,
    _strip_markdown_tables,
)


# Module-level data file cache: {path: (mtime, data)}
_data_cache: dict[tuple, tuple[float, object]] = {}


def _load_json_cached(path: Path) -> dict:
    """Load a JSON file with mtime-based caching.
    
    Returns cached data if the file hasn't changed since last load.
    """
    mtime = path.stat().st_mtime
    cache_key = (str(path.resolve()),)
    if cache_key in _data_cache:
        cached_mtime, cached_data = _data_cache[cache_key]
        if cached_mtime == mtime:
            return cached_data
    data = json.loads(path.read_text(encoding="utf-8"))
    _data_cache[cache_key] = (mtime, data)
    return data


def _format_calibration_for_prompt(calibration: dict, category: str = None) -> str:
    """Format calibration.json into a prompt section grounding severity in real stats.
    
    If category is provided, filter to show only that category's stats.
    """
    lines = []
    lines.append("=== SEVERITY CALIBRATION DATA (derived from the full corpus) ===")
    
    stats = calibration.get("corpus_stats", {})
    lines.append(f"Total moves in corpus: {stats.get('total_moves', 0)}")
    lines.append("")
    lines.append("Corpus-wide severity distribution:")
    for sev, d in stats.get("severity_distribution", {}).items():
        lines.append(f"  {sev}: {d['count']} ({d['percentage']}%)")
    lines.append("")

    if category:
        lines.append(f"Category-specific stats for '{category}':")
        if category in calibration.get("severity_by_category", {}):
            c = calibration["severity_by_category"][category]
            lines.append(f"  {category} (n={c['total']}):")
            lines.append(f"    reject: {c['reject_rate']}%")
            lines.append(f"    request-changes: {c['request_changes_rate']}%")
            lines.append(f"    nitpick: {c['nitpick_rate']}%")
            lines.append(f"    dominant: {c['dominant_severity']}")
        else:
            lines.append("  (no calibration data for this category)")
    else:
        lines.append("Severity distribution by category (P(severity | category)):")
        for cat, c in calibration.get("severity_by_category", {}).items():
            lines.append(f"  {cat} (n={c['total']}):")
            lines.append(f"    reject: {c['reject_rate']}%")
            lines.append(f"    request-changes: {c['request_changes_rate']}%")
            lines.append(f"    nitpick: {c['nitpick_rate']}%")
            lines.append(f"    dominant: {c['dominant_severity']}")
    
    lines.append("")
    lines.append("=== END CALIBRATION DATA ===")
    lines.append("")
    return "\n".join(lines)


def _format_moves_for_prompt(patterns: list) -> str:
    """Format sampled patterns into a prompt for the LLM."""
    lines = []

    total = len(patterns)
    categories = {}
    severities = {}
    sources = {}
    for p in patterns:
        cat = p.get("category", "unknown")
        sev = p.get("severity", "unknown")
        src = p.get("source", "email")
        categories[cat] = categories.get(cat, 0) + 1
        severities[sev] = severities.get(sev, 0) + 1
        sources[src] = sources.get(src, 0) + 1

    lines.append("Corpus statistics:")
    lines.append(f"  Total representative patterns: {total}")
    lines.append(f"  Source distribution: {json.dumps(sources)}")
    lines.append(f"  Category distribution: {json.dumps(categories)}")
    lines.append(f"  Severity distribution: {json.dumps(severities)}")
    lines.append("")

    by_category = {}
    for p in patterns:
        cat = p.get("category", "unknown")
        by_category.setdefault(cat, []).append(p)

    lines.append(f"Below are {total} representative review moves sampled from the corpus,")
    lines.append("grouped by category. The corpus combines email review moves and")
    lines.append("interview passages. Each pattern has a 'source' field (email or interview).")
    lines.append("Treat interview-sourced patterns with equal weight to email-sourced patterns.")
    lines.append("")
    lines.append("Find the recurring THEMES across these moves (not just within categories) and")
    lines.append("synthesize them into the skill.")
    lines.append("")

    for cat, moves in sorted(by_category.items()):
        lines.append(f"## Category: {cat} ({len(moves)} samples)")
        lines.append("")
        for i, m in enumerate(moves, 1):
            lines.append(f"### Move {i}")
            trigger = m.get('trigger', '')
            lines.append(f"Trigger: {generalize_trigger(trigger)}")
            lines.append(f"Principle: {m.get('principle', '')}")
            lines.append(f"Severity: {m.get('severity', '')}")
            lines.append(f"Source: {m.get('source', 'email')}")
            lines.append(f'Response (Torvalds\' words): "{m.get("quote", "")}"')
            lines.append("")

    return "\n".join(lines)


def _load_interview_data(project_root: Path) -> str:
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
        with open(md_file, "r", encoding="utf-8") as f:
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


def _load_interlocutor_variation_data(project_root: Path) -> str:
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
        with open(interlocutor_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        lines.append(f"- {record.get('description', '')}: {record.get('classification', '')}")
                    except json.JSONDecodeError:
                        continue
        lines.append("")
    
    # Load variation data
    if variation_path.exists():
        lines.append("### Variation Data (tone adaptation)")
        with open(variation_path, "r", encoding="utf-8") as f:
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


def _distill_category(category: str, patterns: list, model: str = None) -> str:
    """Generate a skill fragment for a single category.
    
    Stage 1 of two-stage distillation: focuses the LLM's attention on
    patterns within one category (~25 patterns) rather than all 350.
    
    Returns the generated fragment (markdown string) or empty string on error.
    """
    if not patterns:
        return ""
    
    # Build category-specific system prompt (subset of full prompt)
    category_system_prompt = build_category_system_prompt(category)

    # Format patterns for this category
    lines = []
    lines.append(f"Review moves from category: {category}")
    lines.append(f"Total patterns: {len(patterns)}")
    lines.append("")
    
    for i, p in enumerate(patterns, 1):
        trigger = p.get('trigger', '')
        lines.append(f"### Pattern {i}")
        lines.append(f"Trigger: {generalize_trigger(trigger)}")
        lines.append(f"Principle: {p.get('principle', '')}")
        lines.append(f"Severity: {p.get('severity', '')}")
        lines.append(f"Source: {p.get('source', 'email')}")
        lines.append(f'Response (Torvalds\' words): "{p.get("quote", "")}"')
        lines.append("")
    
    user_prompt = "\n".join(lines)
    
    try:
        print(f"  calling LLM for category: {category} ({len(patterns)} patterns)", flush=True)
        
        log_decision(
            "distill",
            category=category,
            model=model or config.MODEL,
            prompt_version="two-stage-v1",
            repair_attempts=0,
            pattern_count=len(patterns),
        )
        
        fragment = _call_llm(user_prompt, model=model, system_prompt=category_system_prompt, wall_clock_override=config.WALL_CLOCK_CATEGORY)
        return fragment
    except Exception as e:
        print(f"  error distilling category {category}: {e}", flush=True)
        return ""


def _run_categories_parallel(categories: list, patterns_by_category: dict, call_fn, model: str = None, max_workers: int = 3) -> tuple[dict, list]:
    """Run category distillation in parallel using ThreadPoolExecutor.
    
    Args:
        categories: List of category names in original order
        patterns_by_category: Dict mapping category name to pattern list
        call_fn: Function to call for each category (e.g., _distill_category)
        model: Model name to pass to call_fn
        max_workers: Maximum number of parallel workers
    
    Returns:
        Tuple of (fragments dict ordered by category, list of failed categories)
    """
    # Pre-initialize fragments in original category order
    fragments = {cat: None for cat in categories}
    failed_categories = []
    completed_count = 0
    total = len(categories)
    
    # Use as_completed for progress reporting, but assemble in original order
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks, mapping futures to category names
        future_to_category = {
            executor.submit(call_fn, cat, patterns_by_category[cat], model): cat
            for cat in categories
        }
        
        # Track completion in any order for progress
        for future in as_completed(future_to_category):
            category = future_to_category[future]
            completed_count += 1
            
            try:
                fragment = future.result()
                fragments[category] = fragment
                if fragment:
                    print(f"  [{completed_count}/{total}] {category}: done ({len(fragment)} chars)", flush=True)
                else:
                    print(f"  [{completed_count}/{total}] {category}: done (empty fragment)", flush=True)
                    failed_categories.append(category)
            except Exception as e:
                print(f"  [{completed_count}/{total}] {category}: FAILED ({e})", flush=True)
                failed_categories.append(category)
    
    return fragments, failed_categories

def _synthesize_skill(fragments: dict, calibration: dict, interview_data: str, 
                      iv_data: str, model: str = None) -> str:
    """Synthesize category fragments into final SKILL.md.
    
    Stage 2 of two-stage distillation: takes all 14 category fragments and
    synthesizes them into a coherent, unified skill document.
    
    Returns the synthesized SKILL.md content.
    """
    # Build synthesis system prompt
    synthesis_system_prompt = build_synthesis_system_prompt()

    # Build user prompt with all fragments and context
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("CATEGORY FRAGMENTS FOR SYNTHESIS")
    lines.append("=" * 80)
    lines.append("")
    
    # Add each category fragment
    for category, fragment in fragments.items():
        if fragment.strip():
            lines.append(f"{'=' * 80}")
            lines.append(f"CATEGORY: {category}")
            lines.append(f"{'=' * 80}")
            lines.append(fragment)
            lines.append("")
    
    lines.append("=" * 80)
    lines.append("ADDITIONAL CONTEXT")
    lines.append("=" * 80)
    lines.append("")
    
    # Add calibration data
    if calibration:
        lines.append(_format_calibration_for_prompt(calibration))
        lines.append("")
    
    # Add interview data
    if interview_data:
        lines.append("## INTERVIEW DATA (Linus' explicit definitions and mindset)")
        lines.append(interview_data)
        lines.append("")
    
    # Add interlocutor/variation data
    if iv_data:
        lines.append(iv_data)
        lines.append("")
    
    # Instructions for synthesis
    lines.append("=" * 80)
    lines.append("SYNTHESIS INSTRUCTIONS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Your task:")
    lines.append("1. Read all category fragments above")
    lines.append("2. Identify recurring themes ACROSS categories (not just within)")
    lines.append("3. Synthesize into the unified SKILL.md structure shown above")
    lines.append("4. Group triggers by SEMANTIC THEME, not by category labels")
    lines.append("5. Use interview quotes for definitions and mindset sections, citing each as (Interview: filename) or (TED YYYY) or (Linux Journal YYYY) etc.")
    lines.append("6. Use calibration stats for Severity Calibration and Decision Tree sections")
    lines.append("7. Ensure EVERY trigger is language-agnostic (apply translation table)")
    lines.append("8. Label every trigger with its type (invariant-true, invariant-false, etc.)")
    lines.append("9. Include at least 12 distinct trigger themes with 3-6 triggers each")
    lines.append("10. Complete ALL required sections in the output structure")
    lines.append("")
    lines.append("OUTPUT FORMAT: Start with YAML frontmatter (--- fences), then markdown body.")
    lines.append("DO NOT use markdown tables — use nested bullet lists instead.")
    lines.append("Target: 4000-7000 words total, comprehensive coverage of all sections.")
    
    user_prompt = "\n".join(lines)
    
    print("  synthesizing final skill from fragments...", flush=True)
    synthesized = _call_llm(user_prompt, model=model, system_prompt=synthesis_system_prompt)
    
    return synthesized


def _distill_single_call(patterns: list, calibration: dict, interview_data: str,
                          iv_data: str, model: str = None) -> str:
    """Generate skill in a single LLM call (pre-T4 behavior).

    Used when --single-call flag is set, primarily for GLM5.2 where
    15 per-category calls are impractical.
    """
    # Build user prompt with all patterns + context
    lines = []
    lines.append("=" * 80)
    lines.append("ALL REVIEW PATTERNS FOR SKILL GENERATION")
    lines.append("=" * 80)
    lines.append("")
    lines.append(_format_moves_for_prompt(patterns))
    lines.append("")

    if calibration:
        lines.append(_format_calibration_for_prompt(calibration))
        lines.append("")

    if interview_data:
        lines.append("## INTERVIEW DATA (Linus' explicit definitions and mindset)")
        lines.append(interview_data)
        lines.append("")

    if iv_data:
        lines.append(iv_data)
        lines.append("")

    lines.append("=" * 80)
    lines.append("INSTRUCTIONS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Generate a complete SKILL.md following the output structure in the system prompt.")
    lines.append("Use interview quotes for definitions and mindset sections, citing each as (Interview: filename) or (TED YYYY) etc.")
    lines.append("Ensure EVERY trigger is language-agnostic. Label every trigger with its type.")
    lines.append("Complete ALL required sections. Target: 4000-7000 words total.")
    lines.append("DO NOT use markdown tables — use nested bullet lists instead.")
    lines.append("OUTPUT FORMAT: Start with YAML frontmatter (--- fences), then markdown body.")

    user_prompt = "\n".join(lines)

    print(f"  calling LLM (single-call mode, {len(patterns)} patterns)...", flush=True)
    skill_md = _call_llm(user_prompt, model=model, system_prompt=DISTILL_SYSTEM_PROMPT)
    return skill_md


REQUIRED_SECTIONS = [
    "Reviewer Mindset",
    "Review Triggers",
    "Precedence and Priorities",
    "Decision Cards",
    "Key Definitions",
    "Anti-Patterns",
    "Voice and Tone",
    "Severity Calibration",
    "Severity Decision Tree",
]


def _repair_missing_sections(skill_md: str, model: str = None) -> str:
    """Detect missing required sections and generate each with a targeted LLM call.

    Reasoning models (GLM5.2) sometimes truncate before writing all sections.
    Rather than regenerating the whole skill (another 10-15 min, likely truncates
    again), this appends only the missing sections.
    """
    missing = [s for s in REQUIRED_SECTIONS if not re.search(rf"^#+\s+{re.escape(s)}\s*$", skill_md, re.MULTILINE)]
    if not missing:
        return skill_md

    print(f"repair: {len(missing)} missing section(s): {', '.join(missing)}", flush=True)

    for section in missing:
        prompt = (
            f"You are writing ONE section of a Linus Torvalds code-review skill.\n"
            f"Section title: {section}\n"
            f"Write ONLY this section, starting with a '## {section}' header.\n"
            f"Keep it concise (200-500 words). Use bullet lists, not tables.\n"
            f"Be language-agnostic — no C/kernel identifiers.\n"
        )
        if section == "Severity Decision Tree":
            prompt += (
                "Format as a nested if/then decision tree using bullet lists.\n"
                "Cover: correctness/security break → reject, API/memory break → reject,\n"
                "complexity without need → request-changes, improvement → approve,\n"
                "cosmetic → nitpick, else → discussion.\n"
            )
        elif section == "Severity Calibration":
            prompt += (
                "Reference corpus-wide severity distribution (reject ~24%,\n"
                "request-changes ~42%, nitpick ~7%, approve ~7%, discussion ~20%).\n"
            )

        generated = _call_llm(prompt, model=model, system_prompt=DISTILL_SYSTEM_PROMPT)
        if generated.strip():
            skill_md = skill_md.rstrip() + "\n\n" + generated.strip() + "\n"
            print(f"  repaired: {section}", flush=True)
        else:
            print(f"  WARNING: could not repair {section}", flush=True)

    return skill_md


def _validate_skill_structure(skill_text: str) -> list[str]:
    """Check that all required top-level sections exist as ## Section Name headings.
    
    Required sections: "Reviewer Mindset", "Review Triggers", "Severity Calibration", 
    "Severity Decision Tree", "Precedence and Priorities", "Decision Cards", 
    "Key Definitions", "Voice and Tone"
    
    Returns a list of missing section names (empty list = all present).
    Does NOT modify the skill text.
    """
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


def _validate_severity_consistency(skill_text: str, calibration: dict) -> list[str]:
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
    warnings = []
    
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
    actual_ratios = {
        sev: count / total_mentions 
        for sev, count in severity_counts.items()
    }
    
    for sev in ["reject", "nitpick", "request-changes"]:
        actual = actual_ratios.get(sev, 0)
        expected = expected_ratios.get(sev, 0)
        
        if expected > 0 and actual > 0:
            deviation = actual / expected
            if deviation > 2.0:
                warnings.append(
                    f"Severity '{sev}' over-represented: {actual*100:.1f}% in skill "
                    f"vs {expected*100:.1f}% expected ({deviation:.1f}x deviation)"
                )
            elif deviation < 0.5:
                warnings.append(
                    f"Severity '{sev}' under-represented: {actual*100:.1f}% in skill "
                    f"vs {expected*100:.1f}% expected ({deviation:.1f}x deviation)"
                )
        elif actual > 0 and expected == 0:
            warnings.append(
                f"Severity '{sev}' present in skill but no calibration data available"
            )
    
    return warnings


def distill_skill(patterns_path: Path, output_path: Path, top_n: int = 40, model: str = None,
                  calibration_path: Path = None, single_call: bool = False):
    """Read patterns.json, call LLM, sanitize, write skill markdown.

    Two-stage approach (default):
    Stage 1: For each of 14 categories, generate a category-specific fragment (~25 patterns each)
    Stage 2: Synthesize all fragments into final SKILL.md
    Total: 15 LLM calls max (14 categories + 1 synthesis)

    Single-call mode (--single-call):
    Bypasses per-category distillation. All patterns are formatted into one
    prompt and the LLM generates the skill in a single call. Use for GLM5.2
    where 15 calls × 7 min is impractical.

    If calibration_path is provided and exists, the calibration data is used
    to ground severity assignments in real corpus stats.
    """
    # Load interview data via the shared helper (eliminates duplication)
    interview_data = _load_interview_data(patterns_path.parent.parent)

    # Load interlocutor and variation data
    iv_data = _load_interlocutor_variation_data(patterns_path.parent.parent)

    # Load calibration data if available
    calibration = None
    if calibration_path and calibration_path.exists():
        calibration = _load_json_cached(calibration_path)
        print(f"loaded calibration from {calibration_path}")
    else:
        print("warning: no calibration data — skill will lack severity grounding")

    # Load patterns
    data = _load_json_cached(patterns_path)
    print(f"loaded {len(data)} patterns from {patterns_path}")

    # Group patterns by category
    by_category = {}
    for p in data:
        cat = p.get("category", "unknown")
        by_category.setdefault(cat, []).append(p)
    
    categories = sorted(by_category.keys())
    print(f"found {len(categories)} categories: {', '.join(categories)}")

    if single_call:
        # Single-call mode: format all patterns into one prompt, one LLM call
        print("\nsingle-call mode: generating skill in one LLM call...", flush=True)
        skill_md = _distill_single_call(data, calibration, interview_data, iv_data, model=model)
    else:
        # Two-stage mode: per-category distillation + synthesis
        # Stage 1: Distill each category
        print(f"\nStage 1: distilling {len(categories)} categories...", flush=True)
        fragments = {}
        
        # Determine max_workers from env var or default to 3
        # For non-glm5.2 models, force single worker to avoid rate limits
        env_workers = int(os.environ.get("DISTILL_MAX_WORKERS", 3))
        if model and "glm5.2" not in model.lower():
            max_workers = 1
        else:
            max_workers = env_workers
        
        # Filter out empty categories first
        non_empty_categories = [cat for cat in categories if by_category[cat]]
        empty_categories = [cat for cat in categories if not by_category[cat]]
        
        # Handle empty categories
        for cat in empty_categories:
            fragments[cat] = ""
        
        # Run parallel distillation for non-empty categories
        if non_empty_categories:
            non_empty_patterns = {cat: by_category[cat] for cat in non_empty_categories}
            fragments, failed_categories = _run_categories_parallel(
                non_empty_categories, non_empty_patterns, _distill_category, model=model, max_workers=max_workers
            )
            
            # Retry failed categories sequentially once
            if failed_categories:
                print(f"\nRetrying {len(failed_categories)} failed category/categories sequentially...", flush=True)
                still_failed = []
                for cat in failed_categories:
                    print(f"  retrying {cat}...", flush=True)
                    fragment = _distill_category(cat, by_category[cat], model=model)
                    if fragment:
                        fragments[cat] = fragment
                        print(f"    retry succeeded", flush=True)
                    else:
                        still_failed.append(cat)
                
                # Warn about categories that still failed
                if still_failed:
                    print(f"\nWARNING: {len(still_failed)} category/categories failed after retry and will be missing from synthesis:", 
                          file=sys.stderr)
                    for cat in still_failed:
                        print(f"  - {cat}", file=sys.stderr)
        else:
            fragments = {cat: "" for cat in categories}
        
        # Stage 2: Synthesize final skill
        print("\nStage 2: synthesizing final skill...", flush=True)
        skill_md = _synthesize_skill(fragments, calibration, interview_data, iv_data, model=model)
    
    # Post-process
    print("\npost-processing...")
    skill_md = sanitize_skill(skill_md)
    skill_md = _strip_markdown_tables(skill_md)
    skill_md = _repair_missing_sections(skill_md, model=model)

    # Validation: check structure and severity consistency
    missing_sections = _validate_skill_structure(skill_md)
    if missing_sections:
        print(f"  WARNING: missing sections after repair: {', '.join(missing_sections)}", 
              file=sys.stderr)
    
    if calibration:
        severity_warnings = _validate_severity_consistency(skill_md, calibration)
        for warning in severity_warnings:
            print(f"  WARNING: {warning}", file=sys.stderr)
    else:
        print("  WARNING: no calibration data — skipping severity consistency check", 
              file=sys.stderr)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(skill_md, encoding="utf-8")

    word_count = len(skill_md.split())
    print(f"skill written: {output_path} ({word_count} words)")
    return skill_md