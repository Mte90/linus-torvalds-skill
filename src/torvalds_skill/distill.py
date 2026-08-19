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

DISTILL_SYSTEM_PROMPT = """\
You are writing a code review skill based on the reviewing patterns of Linus Torvalds, \
distilled from thousands of his real code reviews on the Linux kernel mailing list.

═══════════════════════════════════════════════════════════════════════
INTERVIEW-DERIVED DEFINITIONS (from INTERVIEW DATA)
═══════════════════════════════════════════════════════════════════════

The INTERVIEW DATA section contains Linus Torvalds' explicit, reflective
statements about engineering philosophy — drawn from interviews and talks.
These are NOT code-review moves; they are his own definitions and mindset.

You MUST use interview quotes in these sections:

1. The "Key Definitions" section MUST contain at least 3 definitions grounded
   in interview quotes, cited as (Interview: filename) or (TED 2016) etc.
   Define: "good taste", "good code", "bad code", "special case", "data structure"
   using his own explanations.

2. The "Reviewer Mindset" section MUST reference at least 2 interview quotes
   about his philosophy. Explain WHY each attitude matters.

Quote interviews verbatim with attribution like: (TED 2016) or (Linux Journal 2021).
These quotes are EVIDENCE for definitions, not triggers. They do NOT replace
the moves-based triggers.

- Distinguish between his code-review voice (moves corpus) and his reflective
  voice (interviews) — both inform the method

═══════════════════════════════════════════════════════════════════════
CRITICAL RULE: TOTAL LANGUAGE AND PROJECT AGNOSTICISM
═══════════════════════════════════════════════════════════════════════

The skill must work for a reviewer reading Python, Go, Rust, TypeScript, Java, Haskell, \
or any other language. Torvalds reviews C kernel code, but his REVIEWING METHOD is \
universal. You must strip ALL C-specific and kernel-specific content from triggers \
and principles, keeping ONLY the underlying reviewing method.

TRIGGERS and PRINCIPLES must NEVER contain:
  - C types or keywords: int, char, void, struct, union, enum, typedef, const, volatile, \
    static, inline, register, auto
  - C macros or functions: BUG_ON, WARN_ON, READ_ONCE, WRITE_ONCE, copy_to_user, \
    copy_from_user, get_user, put_user, kmalloc, kfree, spin_lock, mutex, \
    rcu_dereference, smp_load_acquire, smp_store_release, mb(), wmb(), rmb()
  - C preprocessor directives: #ifdef, #ifndef, #define, #if, #endif, #pragma, #include
  - C control flow: goto (as a concept, not in quotes)
  - NULL (as a concept, not in quotes)
  - Kernel concepts: syscall, inode, dentry, superblock, sk_buff, task_struct, \
    file_operations, module_init, module_exit, __init, __exit
  - Kernel-specific identifiers: strlcpy, strscpy, kstrtol, kstrtoul, IS_ERR, \
    ERR_PTR, GFP_KERNEL, GFP_ATOMIC, pagefault_disable, preempt_disable
  - Linux-specific APIs: procfs, sysfs, debugfs, ioctl, ioctl numbers, \
    set_memory_x, module_alloc
  - Architecture-specific terms: x86, ARM, riscv, SMP, BKL, RCU (as a C macro), \
    barrier, smp

QUOTES (the "Response" field) are Torvalds' VERBATIM words and MUST be preserved \
exactly as written, including any C-specific terms they contain. The quotes \
ILLUSTRATE the voice and tone — they are evidence, not the trigger itself. Always \
introduce a quote with the generalized trigger, then show the original wording as \
an example.

TRANSLATION TABLE — when you encounter these in the data, generalize as shown:

  C/Kernel specific                           → Language-agnostic trigger
  ──────────────────────────────────────────────→────────────────────────────────────
  BUG_ON() / BUG()                            → Fatal assertion/panic used for a recoverable condition
  WARN_ON()                                   → Warning assertion that masks a real bug
  READ_ONCE / WRITE_ONCE                      → Unsynchronized access to shared mutable data
  volatile                                     → Relying on language semantics instead of explicit sync
  copy_to_user / copy_from_user               → Untrusted/external boundary crossing without validation
  spin_lock / mutex                            → Lock-based concurrency primitive
  rcu_dereference                              → Lock-free data access without memory ordering
  kmalloc / kfree                             → Manual memory allocation/deallocation
  strlcpy / strscpy                            → String/buffer copy without bounds safety
  __user annotation                            → Missing type-level ownership/safety annotation
  returning -EFAULT / -EINVAL                  → Returning magic error codes instead of typed errors
  #ifdef CONFIG_X                              → Compile-time conditional logic instead of runtime config
  goto cleanup                                 → Manual resource cleanup instead of RAII/defer/using
  struct file_operations                       → Interface/API contract change
  syscall ABI change                            → Public API/ABI breakage
  inline function                              → Premature optimization hint
  typedef struct                                → Type aliasing that hides the real type

This table is NOT exhaustive. Apply the SAME generalization logic to EVERY C/kernel \
term you encounter. If a trigger mentions ANY language-specific construct, rewrite it \
in terms of the BEHAVIOR or DESIGN problem it represents.

SELF-CHECK before writing each trigger:
  1. Does the trigger mention a type, function, macro, or keyword from a specific language?
     → If YES, rewrite it.
  2. Would this trigger make sense to a Python reviewer? A Rust reviewer? A Go reviewer?
     → If NO, rewrite it.
  3. Does the trigger describe a DESIGN problem (not a syntax problem)?
     → It should. Syntax problems are language-specific; design problems are universal.

═══════════════════════════════════════════════════════════════════════
SKILL QUALITIES
═══════════════════════════════════════════════════════════════════════

1. Language-agnostic — see the critical rule above. This is non-negotiable.
2. Four qualities of review rules — EVERY trigger must be ONE of these four types:
   a) **Invariant TRUE**: A condition that MUST always be true (e.g., "API must not break existing users without compelling reason"). State it as a verifiable condition.
   b) **Invariant FALSE**: A condition that MUST NEVER be true (e.g., "Never crash the system for a recoverable error"). State it as something to reject outright.
   c) **Precedence rule**: An explicit ordering when rules conflict (e.g., "Correctness > Performance > Complexity > Style", "Breaking users > Performance optimization", "Security > Convenience").
   d) **General guideline for identifiable pattern**: A concrete pattern that can be detected (e.g., "When you see X, flag it because Y"). Must have clear detection criteria, not vague advice.
3. Explicit precedence chain — state the hierarchy early in the skill:
   - Correctness (invariants, safety, no crashes) > Performance > Complexity > Style
   - Protecting existing users > Adding new features
   - Security > Convenience
   - Bisectability > Quick fixes
4. Concrete definitions — define key terms explicitly:
   - "Bug": A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.
   - "Hack" / "Workaround": A temporary fix that masks the root cause without addressing it.
   - "Patch": A code change (neutral term).
   - "Non-negotiable": A rule that has no exceptions (e.g., "Never break existing APIs without compelling reason").
5. Actionable. Every principle must tell the reviewer WHAT to do and WHEN. Not "be careful" but "when X appears, flag it because Y."
6. Grounded in real examples. Use the provided quotes — they show the voice and tone that IS part of the method. Preserve them verbatim.
7. Honest about what the data shows. Use the actual counts. Don't invent statistics.
8. Comprehensive. The skill should be a thorough reference, not a summary. Aim for 6000-9000 words. Cover each theme in depth with multiple examples.

═══════════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════════

You will receive raw review moves sampled from the corpus, grouped by category. \
Each move has: trigger (what prompted the review), principle (the underlying rule), \
response (Torvalds' actual words), severity, and date.

1. READ all the moves across all categories.
2. FIND recurring themes — principles that appear in multiple moves, even if phrased \
differently. Group them semantically, not lexically. "Don't break userspace" and \
"we don't break existing setups" are the same principle.
3. For each theme, pick the most representative quotes and triggers. Use multiple quotes \
per theme when they show different facets. GENERALIZE every trigger using the \
translation table and the self-check rules above.
4. LABEL each trigger with its type: invariant-true, invariant-false, precedence-rule, \
or general-guideline. Every trigger MUST be one of these four types — no soft guidelines.
5. ENFORCE the precedence chain: when rules conflict, correctness > performance > \
complexity > style. Make this explicit in the Precedence and Priorities section.
6. DEFINE key terms concretely: bug, hack, workaround, patch, non-negotiable. No \
vague language — each definition must be verifiable.
7. SYNTHESIZE the themes into the skill structure below.

The output MUST start with YAML frontmatter enclosed in --- fences, then the markdown body.

Output exactly this structure (replace the bracketed parts with real content):

---
name: linus-torvalds-skill
description: "[1-2 sentence description of what this skill teaches]"
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> [Brief description: what this skill is, what corpus it was distilled from, \
and the corpus size (use the provided stats). 2-3 sentences. State explicitly \
that the method is language- and project-agnostic.]

## Reviewer Mindset
[The 5-7 core attitudes that define the approach. Each with a one-line principle \
and a real Torvalds quote. Explain WHY each attitude matters.]

## Review Triggers
[Comprehensive catalog of "when you see X, flag it" patterns, grouped by semantic \
theme (not by the raw category labels — use themes you discover across categories). \
For EACH trigger provide:
- **Type**: invariant-true / invariant-false / precedence-rule / general-guideline
- **What to look for**: generalized, language-agnostic description of the pattern
- **Why it's a problem**: the underlying design principle being violated
- **Severity**: reject / request-changes / nitpick
- **Example (original wording)**: a real Torvalds quote showing how he handles it — \
introduce it with the generalized trigger, then show the verbatim quote
- 1-2 additional supporting quotes when available

EVERY trigger must pass the self-check: no language-specific terms, makes sense to \
reviewers in any language, describes a design problem. Cover at least 12 distinct \
trigger themes. Each theme should have 3-6 specific triggers. Label each trigger \
with its type (invariant-true, invariant-false, precedence-rule, or general-guideline).]

## Precedence and Priorities
[Explicit hierarchy of rules when they conflict. State clearly:
- Correctness (invariants, safety, no crashes) > Performance > Complexity > Style
- Protecting existing users > Adding new features
- Security > Convenience
- Bisectability > Quick fixes
- Measured performance > Theoretical optimization

For each priority rule, explain WHY it takes precedence and give a real quote \
showing Torvalds making that tradeoff. This section is CRITICAL — it resolves \
ambiguity when multiple rules apply.]

## Key Definitions
[Define key terms explicitly so there is no ambiguity:
- "Bug": A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.
- "Hack" / "Workaround": A temporary fix that masks the root cause without addressing it.
- "Patch": A code change (neutral term).
- "Non-negotiable": A rule that has no exceptions (e.g., "Never break existing APIs without compelling reason").
- "Recoverable error": A condition that can be handled gracefully without crashing.
- "API contract": The documented or implied behavior that external code depends on.

For each definition, give a real Torvalds quote showing how he uses the term.]
## Anti-Patterns
[What Torvalds consistently rejects: over-engineering, abstraction for its own sake, \
breaking existing users, cleverness without measurement, etc. For each anti-pattern:
- What it looks like (language-agnostic)
- Why it's wrong
- A real Torvalds quote
- What to do instead

Cover at least 8 anti-patterns.]

## Voice and Tone
[How Torvalds phrases feedback. The tone IS part of the method — certainty, directness, \
explaining the "why" after the "no". With real quotes. Cover:
- When to be blunt vs. when to explain
- How to phrase a rejection
- How to explain the reasoning
- When humor or analogy is appropriate
- How to handle repeated mistakes]

## Common Review Scenarios
[Walk through 5-8 concrete review scenarios showing the method in action. \
Each scenario should be described in LANGUAGE-AGNOSTIC terms (e.g., "a new public API \
that removes a previously available parameter" not "a syscall that changes its signature"):
- The situation (generalized)
- What to look for
- How to respond (with real Torvalds quotes as examples)
- The severity to assign

Scenarios should span different categories: performance, correctness, API design, \
error handling, concurrency, etc.]

## Decision Framework
[A decision tree or flowchart in text form: when reviewing code, what order to \
check things, when to reject vs. request changes, when to defer to maintainers, \
when to insist. Include the principles behind each decision point.]

## Severity Calibration
[Use the provided calibration statistics to GROUND severity assignments in the \
real corpus. For each category, state the empirical reject rate, request-changes \
rate, and nitpick rate as percentages. Explain what the data says about how \
Torvalds actually calibrates severity — e.g., "API-stability issues are rejected \
37.9% of the time, the highest of any category" or "style issues are nitpicked \
35.5% of the time but rarely rejected." Do NOT invent statistics — use the exact \
numbers provided in the calibration data. Group categories by their dominant \
severity and explain the pattern: which categories Torvalds treats as \
reject-first, which as fix-first, and which as discuss-only.]

## Severity Decision Tree
[A category-based decision tree derived from the calibration statistics. \
Present it as nested if/then rules using ONLY the category names and the \
empirical severity rates: "IF the issue is in category {category} AND it \
breaks existing users/APIs THEN reject (corpus reject rate: {X}%)" or "IF \
the issue is in category {category} AND it is a style/readability concern \
THEN nitpick (corpus nitpick rate: {X}%." Synthesize the rules into a \
simplified decision procedure: "To assign severity, check in order: (1) does \
the change break existing users/APIs? → reject; (2) does it introduce a \
correctness or memory-safety bug? → reject or request-changes depending on \
severity; (3) is it a style issue? → nitpick; etc." The decision tree must be \
language-agnostic — no C/kernel identifiers, no type names, no macro names.]

## Quick Reference Checklist
[A one-page checklist a reviewer can scan: "Before approving, verify:" with 15-20 \
concrete items grouped by theme. Every item must be language-agnostic.]

Keep the total output between 4000-7000 words. Be concise — every section must have real \
quotes from the data, but do not pad. Do not invent quotes — only use what is provided. \
If you need more examples for a theme, use the quotes you have and note the pattern. \
Prioritize completing ALL required sections over depth in any single section.

REMEMBER: The final test is simple — if a reviewer reading this skill could NOT tell \
whether it was distilled from C kernel reviews, Python web framework reviews, or Rust \
systems programming reviews, you have succeeded. The METHOD must shine through; the \
LANGUAGE must be invisible.
"""


def _call_llm(prompt: str, retries: int = None, model: str = None, system_prompt: str = None) -> str:
    """Call the LLM for the distillation step. Returns raw text.

    Uses SSE streaming so reasoning models (e.g. GLM5.2) that spend minutes
    on internal reasoning don't hit read timeouts — each token delta keeps
    the connection alive.
    """
    retries = retries if retries is not None else config.MAX_RETRIES
    sys_prompt = system_prompt if system_prompt is not None else DISTILL_SYSTEM_PROMPT

    effective_model = model or config.MODEL
    is_glm = "glm" in effective_model.lower()

    payload = {
        "model": effective_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 16000 if is_glm else 64000,
        "stream": True,
    }

    timeout = 600 if is_glm else 120

    last_err = None
    for attempt in range(retries):
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                config.CHAT_URL,
                data=body,
                headers=config.headers(),
                method="POST",
            )
            content_parts = []
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for raw in resp:
                    line = raw.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content")
                    if text:
                        content_parts.append(text)
            result = "".join(content_parts)
            if result.strip():
                return result
            last_err = RuntimeError("empty response")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(config.RETRY_DELAY * (attempt + 1))

    raise RuntimeError(f"LLM distill failed after {retries} retries: {last_err}")


def _format_calibration_for_prompt(calibration: dict) -> str:
    """Format calibration.json into a prompt section grounding severity in real stats."""
    lines = []
    lines.append("=== SEVERITY CALIBRATION DATA (derived from the full corpus) ===")
    lines.append("Use these EXACT numbers in the Severity Calibration and Severity Decision Tree sections.")
    lines.append("Do NOT invent statistics — cite the figures below.")
    lines.append("")

    stats = calibration.get("corpus_stats", {})
    lines.append(f"Total moves in corpus: {stats.get('total_moves', 0)}")
    lines.append("")
    lines.append("Corpus-wide severity distribution:")
    for sev, d in stats.get("severity_distribution", {}).items():
        lines.append(f"  {sev}: {d['count']} ({d['percentage']}%)")
    lines.append("")

    lines.append("Severity distribution by category (P(severity | category)):")
    for cat, c in calibration.get("severity_by_category", {}).items():
        lines.append(f"  {cat} (n={c['total']}):")
        lines.append(f"    reject: {c['reject_rate']}%")
        lines.append(f"    request-changes: {c['request_changes_rate']}%")
        lines.append(f"    nitpick: {c['nitpick_rate']}%")
        lines.append(f"    dominant: {c['dominant_severity']}")
    lines.append("")
    lines.append("")
    lines.append("=== END CALIBRATION DATA ===")
    lines.append("")
    return "\n".join(lines)


def _format_moves_for_prompt(data: dict) -> str:
    """Format sampled moves by category into a prompt for the LLM."""
    lines = []
    lines.append("Corpus statistics:")
    lines.append(f"  Total review moves extracted: {data['total_moves']}")
    lines.append(f"  Category distribution: {json.dumps(data['categories'])}")
    lines.append(f"  Severity distribution: {json.dumps(data['severity_distribution'])}")
    lines.append("")

    samples_by_category = data.get("samples_by_category", {})
    total_samples = sum(len(v) for v in samples_by_category.values())
    lines.append(f"Below are {total_samples} representative review moves sampled from the corpus,")
    lines.append("grouped by category. Each move shows what triggered the review, the principle,")
    lines.append("Torvalds' actual response, the severity, and the date.")
    lines.append("")
    lines.append("Find the recurring THEMES across these moves (not just within categories) and")
    lines.append("synthesize them into the skill.")
    lines.append("")

    for cat, moves in samples_by_category.items():
        lines.append(f"## Category: {cat} ({len(moves)} samples)")
        lines.append("")
        for i, m in enumerate(moves, 1):
            lines.append(f"### Move {i}")
            lines.append(f"Trigger: {m['trigger']}")
            lines.append(f"Principle: {m['principle']}")
            lines.append(f"Severity: {m['severity']}")
            lines.append(f"Date: {m['date']}")
            lines.append(f'Response (Torvalds\' words): "{m["response"]}"')
            lines.append("")

    return "\n".join(lines)


SANITIZE_REPLACEMENTS = {
    "BUG_ON": "fatal assertion",
    "WARN_ON": "warning assertion",
    "READ_ONCE": "unsynchronized read",
    "WRITE_ONCE": "unsynchronized write",
    "spin_lock": "lock primitive",
    "mutex": "lock primitive",
    "volatile": "implicit language semantics",
    "sysfs": "system interface",
    "procfs": "system interface",
    "debugfs": "system interface",
    "ioctl": "interface call",
    "kmalloc": "manual allocation",
    "kfree": "manual deallocation",
    "#ifdef": "compile-time conditional",
    "#ifndef": "compile-time conditional",
    "#define": "compile-time definition",
    "typedef": "type alias",
    "noinline": "no-optimization attribute",
    "inline": "premature optimization hint",
    "copy_to_user": "boundary crossing",
    "copy_from_user": "boundary crossing",
    "rcu_dereference": "lock-free access",
    "strlcpy": "string copy",
    "strscpy": "string copy",
    "IS_ERR": "error check",
    "ERR_PTR": "error pointer",
    "GFP_KERNEL": "allocation flag",
    "module_alloc": "module allocation",
}

_QUOTE_SPAN_RE = re.compile(r'("[^"]*"|\u201c[^\u201d]*\u201d|`[^`]*`)')


def sanitize_skill(text: str) -> str:
    """Replace forbidden C/kernel terms in unquoted text, preserving quotes and inline code."""
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        if line.lstrip().startswith('> '):
            out.append(line)
            continue
        parts = _QUOTE_SPAN_RE.split(line)
        for i, part in enumerate(parts):
            if i % 2 == 1:
                continue
            for term, repl in SANITIZE_REPLACEMENTS.items():
                part = part.replace(term, repl)
            parts[i] = part
        out.append(''.join(parts))
    return ''.join(out)


def _load_interview_data(project_root: Path) -> str:
    """Load all interview transcripts from data/interviews/ directory.

    Reads all .md files, concatenates them with headers, and truncates
    to ~120,000 chars (~13% of corpus) to avoid blowing the context window.

    Returns the concatenated string, or empty string if the directory doesn't exist.
    """
    interviews_dir = project_root / "data" / "interviews"
    if not interviews_dir.exists():
        return ""

    max_chars = 120000
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


def distill_skill(patterns_path: Path, output_path: Path, top_n: int = 40, model: str = None,
                  calibration_path: Path = None):
    """Read patterns.json, call LLM, sanitize, write skill markdown.

    If calibration_path is provided and exists, the calibration data is appended
    to the prompt so the LLM grounds severity assignments in real corpus stats.
    """
    # Load interview data via the shared helper (eliminates duplication)
    interview_data = _load_interview_data(patterns_path.parent.parent)

    data = json.loads(patterns_path.read_text(encoding="utf-8"))

    prompt = _format_moves_for_prompt(data)

    if calibration_path and calibration_path.exists():
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        prompt = prompt + "\n" + _format_calibration_for_prompt(calibration)
        print(f"loaded calibration from {calibration_path}")
    else:
        print("warning: no calibration data — skill will lack severity grounding")

    # Load interview transcripts (explicit definitions and mindset statements)
    if interview_data:
        prompt = prompt + "\n\n## INTERVIEW DATA (Linus' explicit definitions and mindset)\n" + interview_data
        print(f"loaded interview data ({len(interview_data)} chars)")
    else:
        print("warning: no interview data — skill will lack explicit definitions")

    print(f"calling LLM with {len(prompt)} chars of move data...")
    print(f"  ({sum(len(v) for v in data.get('samples_by_category', {}).values())} sampled moves)")
    if model:
        print(f"  (model override: {model})")

    skill_md = _call_llm(prompt, model=model)
    skill_md = sanitize_skill(skill_md)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(skill_md, encoding="utf-8")

    word_count = len(skill_md.split())
    print(f"skill written: {output_path} ({word_count} words)")
    return skill_md