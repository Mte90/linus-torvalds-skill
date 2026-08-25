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
import re
import time
import urllib.request
import urllib.error
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

    Reads all .md files, concatenates them with headers, and truncates
    to ~120,000 chars (~13% of corpus) to avoid blowing the context window.

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
        content = md_file.read_text(encoding="utf-8")
        header = f"## Interview: {md_file.name}\n\n"
        file_content = header + content + "\n\n"
        file_chars = len(file_content)

        # Stop if adding this file would exceed the limit
        if total_chars + file_chars > max_chars and total_chars > 0:
            # Add partial content if we haven't added anything yet
            if total_chars == 0:
                lines.append(file_content[:max_chars])
                total_chars = max_chars
            break

        lines.append(file_content)
        total_chars += file_chars

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
        
        fragment = _call_llm(user_prompt, model=model, system_prompt=category_system_prompt)
        return fragment
    except Exception as e:
        print(f"  error distilling category {category}: {e}", flush=True)
        return ""


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
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        print(f"loaded calibration from {calibration_path}")
    else:
        print("warning: no calibration data — skill will lack severity grounding")

    # Load patterns
    data = json.loads(patterns_path.read_text(encoding="utf-8"))
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
        
        for i, cat in enumerate(categories, 1):
            cat_patterns = by_category[cat]
            if not cat_patterns:
                print(f"  [{i}/{len(categories)}] {cat}: skipping (0 patterns)", flush=True)
                fragments[cat] = ""
                continue
                
            print(f"  [{i}/{len(categories)}] {cat} ({len(cat_patterns)} patterns)...", flush=True)
            fragment = _distill_category(cat, cat_patterns, model=model)
            fragments[cat] = fragment
            
            if fragment:
                print(f"    generated {len(fragment)} chars", flush=True)
            else:
                print(f"    FAILED (empty fragment)", flush=True)

        # Stage 2: Synthesize final skill
        print("\nStage 2: synthesizing final skill...", flush=True)
        skill_md = _synthesize_skill(fragments, calibration, interview_data, iv_data, model=model)
    
    # Post-process
    print("\npost-processing...")
    skill_md = sanitize_skill(skill_md)
    skill_md = _strip_markdown_tables(skill_md)
    skill_md = _repair_missing_sections(skill_md, model=model)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(skill_md, encoding="utf-8")

    word_count = len(skill_md.split())
    print(f"skill written: {output_path} ({word_count} words)")
    return skill_md