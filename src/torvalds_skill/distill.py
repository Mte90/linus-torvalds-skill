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
The corpus combines 38,000+ email review moves and 500+ interview passages, sampled into 350 representative patterns. \
Each pattern has a `source` field indicating whether it comes from email ("source: email") or interview ("source: interview"). \
Treat interview-sourced patterns with equal weight to email-sourced patterns — both are valid evidence of Torvalds' reviewing method. \
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

**CRITICAL FORMATTING RULE: DO NOT USE MARKDOWN TABLES**
- All multi-field entries MUST use structured nested bullet lists
- NEVER use `| column | column |` table syntax
- Example of CORRECT format:
  ```
  - **Trigger**: description
    - Severity: level
    - Principle: explanation
  ```
- Example of INCORRECT format (FORBIDDEN):
  ```
  | Trigger | Severity | Principle |
  |---------|----------|----------|
  | foo     | high     | bar      |
  ```

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

FORMAT REQUIREMENT: Use structured nested bullet lists for all triggers. DO NOT use \
markdown tables. Example of correct format:

```
### Theme: Assertion Misuse
- **Trigger**: Fatal assertion used for recoverable condition
  - **Type**: invariant-false
  - **What to look for**: panic/crash in code paths that should handle errors gracefully
  - **Why it's a problem**: Recoverable errors must be handled without crashing
  - **Severity**: reject
  - **Example**: "This is fundamentally broken. You don't BUG_ON() a condition that \
    can happen from bad user input."
```

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

## Voice and Tone
[How Torvalds phrases feedback. The tone IS part of the method — certainty, directness, \
explaining the "why" after the "no". With real quotes. Cover:
- When to be blunt vs. when to explain
- How to phrase a rejection
- How to explain the reasoning
- When humor or analogy is appropriate
- How to handle repeated mistakes]

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
reject-first, which as fix-first, and which as discuss-only.

FORMAT REQUIREMENT: Use structured nested bullet lists for category statistics. \
DO NOT use markdown tables. Example of correct format:

```
- **Category: api-stability** (n=42)
  - reject: 37.9%
  - request-changes: 45.2%
  - nitpick: 16.9%
  - dominant: reject
  - Pattern: Highest reject rate — API breaks are non-negotiable
```
]

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
language-agnostic — no C/kernel identifiers, no type names, no macro names.

FORMAT REQUIREMENT: Use structured nested bullet lists for decision rules. \
DO NOT use markdown tables. Example of correct format:

```
### Severity Decision Procedure
1. Check for API/ABI breaks
   - IF breaks existing users/APIs → reject (37.9% reject rate for api-stability)
   - IF adds new public symbols without justification → request-changes
2. Check for correctness issues
   - IF introduces bug/crash → reject
   - IF potential bug (uninitialized data, off-by-one) → request-changes
3. Check for style/readability
   - IF style inconsistency → nitpick (35.5% nitpick rate for style)
```
]

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


def _detect_truncation(text: str, model: str) -> bool:
    """Detect if LLM output is truncated mid-sentence or mid-section.

    Returns True if the output appears incomplete:
    - Ends without proper closing (no terminal punctuation, no code fence close)
    - Token count is suspiciously low (< 500 for skill, < 800 for soul)
    - For GLM5.2: also checks for mid-word endings
    """
    if not text or not text.strip():
        return True

    stripped = text.strip()
    
    # Check token count threshold
    # Rough estimate: 1 token ≈ 4 characters
    token_count = len(stripped) / 4
    is_skill = "skill" in model.lower() or "distill" in model.lower()
    is_soul = "soul" in model.lower()
    
    min_tokens = 500 if is_skill else (800 if is_soul else 500)
    if token_count < min_tokens:
        return True

    # For GLM5.2, be stricter — must end with punctuation or code fence or section marker
    if "glm" in model.lower():
        if (stripped.endswith(".") or stripped.endswith("!") or 
            stripped.endswith("?") or stripped.endswith("```") or
            stripped.endswith("---")):
            return False  # Proper ending
        # Doesn't end properly for GLM
        return True
    
    # General check for other models
    proper_endings = (".", "!", "?", "```", "---", "##", "#")
    if any(stripped.endswith(ending) for ending in proper_endings):
        return False
    
    # Check if it ends mid-sentence (last word has no punctuation)
    words = stripped.split()
    if words:
        last_word = words[-1]
        # If last word doesn't end with punctuation and isn't a code element
        if not any(last_word.endswith(p) for p in (".", "!", "?", ")", "]", "`")):
            return True
    
    return False


def _patch_truncated_section(primary_text: str, fallback_text: str) -> str:
    """Merge truncated primary output with fallback tail.

    Finds the last complete section boundary in primary text, then appends
    everything after that point from the fallback output.
    """
    if not primary_text or not fallback_text:
        return fallback_text or primary_text or ""

    # Find section boundaries (markdown headers or --- separators)
    section_patterns = ["\n## ", "\n# ", "\n---", "\n### "]
    
    last_boundary_pos = 0
    for pattern in section_patterns:
        pos = primary_text.rfind(pattern)
        if pos > last_boundary_pos:
            last_boundary_pos = pos
    
    # If we found a boundary, extract the tail from fallback
    if last_boundary_pos > 0:
        # Get the section header from primary
        section_header = primary_text[last_boundary_pos:last_boundary_pos + 10].strip()
        
        # Find the same section in fallback
        fallback_section_pos = fallback_text.find(section_header)
        if fallback_section_pos != -1:
            # Check if fallback has more content after this section
            primary_tail = primary_text[last_boundary_pos:]
            fallback_tail = fallback_text[fallback_section_pos:]
            
            # If fallback is longer, append the difference
            if len(fallback_tail) > len(primary_tail):
                # Find where they diverge
                divergence = 0
                for i in range(min(len(primary_tail), len(fallback_tail))):
                    if primary_tail[i] != fallback_tail[i]:
                        divergence = i
                        break
                else:
                    divergence = len(primary_tail)
                
                # Append the missing part
                return primary_text[:last_boundary_pos + divergence] + fallback_tail[divergence:]
    
    # No clear section match, just return fallback
    return fallback_text


def _call_llm(prompt: str, retries: int = None, model: str = None, system_prompt: str = None) -> str:
    """Call the LLM for the distillation step. Returns raw text.

    Uses SSE streaming so reasoning models (e.g. GLM5.2) that spend minutes
    on internal reasoning don't hit read timeouts — each token delta keeps
    the connection alive.

    Implements fallback chain for GLM5.2 truncation:
    mistral-small-4-119b → gpt-oss-120b → glm5.2
    """
    retries = retries if retries is not None else config.MAX_RETRIES
    sys_prompt = system_prompt if system_prompt is not None else DISTILL_SYSTEM_PROMPT

    # Fallback model chain for truncation recovery
    fallback_models = ["mistral-small-4-119b", "gpt-oss-120b", "glm5.2"]
    primary_model = model or config.MODEL
    
    # Try primary model first, then fallbacks if truncation detected
    models_to_try = [primary_model]
    if primary_model not in fallback_models:
        models_to_try.extend(fallback_models)
    
    last_err = None
    primary_result = None
    sys = __import__("sys")
    
    for call_model in models_to_try:
        is_glm = "glm" in call_model.lower()
        
        payload = {
            "model": call_model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 16000 if is_glm else 64000,
            "stream": True,
        }
        
        timeout = 600 if is_glm else 120
        model_retries = retries
        
        for attempt in range(model_retries):
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
                if not result.strip():
                    last_err = RuntimeError("empty response")
                    break
                
                # Check for truncation
                if _detect_truncation(result, call_model):
                    print(f"warning: truncation detected with {call_model}, trying fallback...", file=sys.stderr)
                    if primary_result is None:
                        primary_result = result
                    last_err = RuntimeError("truncation detected")
                    break
                
                # Success - no truncation
                if call_model != primary_model:
                    print(f"info: fallback model {call_model} succeeded", file=sys.stderr)
                    # Try to patch if we have a primary result
                    if primary_result is not None:
                        return _patch_truncated_section(primary_result, result)
                return result
                
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                last_err = e
                time.sleep(config.RETRY_DELAY * (attempt + 1))
    
    # All models failed or truncated
    if primary_result is not None:
        print("warning: all models truncated, returning primary result", file=sys.stderr)
        return primary_result
    
    raise RuntimeError(f"LLM distill failed after {retries} retries: {last_err}")


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


def generalize_trigger(trigger: str) -> str:
    """Apply SANITIZE_REPLACEMENTS to generalize C-specific terms in triggers.
    
    This pre-generalizes triggers before they're formatted into the prompt,
    ensuring C-specific terms are removed at the source.
    """
    if not trigger:
        return trigger
    result = trigger
    for term, replacement in SANITIZE_REPLACEMENTS.items():
        result = result.replace(term, replacement)
    return result


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

    max_chars = 500000
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
    category_system_prompt = f"""\nYou are writing a section of a code review skill document, focusing on ONE category of review patterns.

═══════════════════════════════════════════════════════════════════════
CRITICAL RULE: TOTAL LANGUAGE AND PROJECT AGNOSTICISM
═══════════════════════════════════════════════════════════════════════

The skill must work for a reviewer reading Python, Go, Rust, TypeScript, Java, Haskell, 
or any other language. Torvalds reviews C kernel code, but his REVIEWING METHOD is 
universal. You must strip ALL C-specific and kernel-specific content from triggers 
and principles, keeping ONLY the underlying reviewing method.

TRIGGERS and PRINCIPLES must NEVER contain:
  - C types or keywords: int, char, void, struct, union, enum, typedef, const, volatile, static, inline
  - C macros or functions: BUG_ON, WARN_ON, READ_ONCE, WRITE_ONCE, copy_to_user, kmalloc, kfree
  - Kernel concepts: syscall, inode, dentry, superblock, sk_buff, task_struct
  - Linux-specific APIs: procfs, sysfs, debugfs, ioctl
  - Architecture-specific terms: x86, ARM, riscv, SMP, RCU

QUOTES (the "Response" field) are Torvalds' VERBATIM words and MUST be preserved 
exactly as written, including any C-specific terms they contain. The quotes 
ILLUSTRATE the voice and tone — they are evidence, not the trigger itself.

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

═══════════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════════

You will receive review moves from the category: {category}

Generate a skill fragment that:
1. Identifies the recurring themes within this category
2. For each theme, provides:
   - A clear trigger (language-agnostic)
   - The underlying principle
   - Severity level (reject / request-changes / nitpick)
   - A representative Torvalds quote (verbatim)
3. Labels each trigger with its type: invariant-true, invariant-false, precedence-rule, or general-guideline

Output format (markdown):

## Category: {category}

### Theme 1: [Theme Name]
- **Trigger**: [language-agnostic description]
  - **Type**: [invariant-true / invariant-false / precedence-rule / general-guideline]
  - **Why it's a problem**: [underlying design principle]
  - **Severity**: [reject / request-changes / nitpick]
  - **Example**: "[Torvalds quote]"

[Continue with 3-6 triggers for this category]

Remember: Every trigger must be language-agnostic. If it mentions C keywords or kernel
concepts, generalize it to the underlying design problem.
"""

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
    synthesis_system_prompt = """\nYou are synthesizing category-specific skill fragments into a unified SKILL.md document.

═══════════════════════════════════════════════════════════════════════
CRITICAL RULE: TOTAL LANGUAGE AND PROJECT AGNOSTICISM
═══════════════════════════════════════════════════════════════════════

The final skill must work for a reviewer reading Python, Go, Rust, TypeScript, Java, Haskell, 
or any other language. All C-specific and kernel-specific content must be generalized.

═══════════════════════════════════════════════════════════════════════
SKILL QUALITIES
═══════════════════════════════════════════════════════════════════════

1. Language-agnostic — triggers must work for any language
2. Four qualities of review rules — every trigger must be ONE of these:
   a) Invariant TRUE: A condition that MUST always be true
   b) Invariant FALSE: A condition that MUST NEVER be true
   c) Precedence rule: An explicit ordering when rules conflict
   d) General guideline: A concrete pattern with clear detection criteria
3. Explicit precedence chain: Correctness > Performance > Complexity > Style
4. Concrete definitions — define key terms explicitly
5. Actionable — tell the reviewer WHAT to do and WHEN
6. Grounded in real examples — use the provided quotes
7. Comprehensive — aim for 6000-9000 words

═══════════════════════════════════════════════════════════════════════
OUTPUT STRUCTURE
═══════════════════════════════════════════════════════════════════════

Output exactly this structure (replace bracketed parts with real content):

**CRITICAL FORMATTING RULE: DO NOT USE MARKDOWN TABLES**
- Use structured nested bullet lists, NOT `| column | column |` tables

---
name: linus-torvalds-skill
description: "[1-2 sentence description]"
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> [2-3 sentence intro: what this skill is, corpus size, language-agnostic method]

## Reviewer Mindset
[5-7 core attitudes with principles and quotes]

## Review Triggers
[Comprehensive catalog grouped by semantic theme, NOT by category labels.
Each trigger must have:
- Type: invariant-true / invariant-false / precedence-rule / general-guideline
- What to look for: language-agnostic description
- Why it's a problem: underlying design principle
- Severity: reject / request-changes / nitpick
- Example: verbatim Torvalds quote
Cover at least 12 distinct themes with 3-6 triggers each.]

## Precedence and Priorities
[Explicit hierarchy with explanations and quotes]

## Key Definitions
[Define: bug, hack, workaround, patch, non-negotiable, recoverable error, API contract]

## Voice and Tone
[How Torvalds phrases feedback with quotes]

## Decision Framework
[Text-based decision tree]

## Severity Calibration
[Use calibration stats to ground severity assignments. Format as nested bullets, NOT tables.]

## Severity Decision Tree
[Category-based decision procedure. Format as nested bullets, NOT tables.]

## Quick Reference Checklist
[15-20 concrete items grouped by theme]

Keep output between 6000-9000 words. Complete ALL sections.
"""

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
    lines.append("5. Use interview quotes for definitions and mindset sections")
    lines.append("6. Use calibration stats for Severity Calibration and Decision Tree sections")
    lines.append("7. Ensure EVERY trigger is language-agnostic (apply translation table)")
    lines.append("8. Label every trigger with its type (invariant-true, invariant-false, etc.)")
    lines.append("9. Include at least 12 distinct trigger themes with 3-6 triggers each")
    lines.append("10. Complete ALL required sections in the output structure")
    lines.append("")
    lines.append("OUTPUT FORMAT: Start with YAML frontmatter (--- fences), then markdown body.")
    lines.append("DO NOT use markdown tables — use nested bullet lists instead.")
    lines.append("Target: 6000-9000 words, comprehensive coverage of all sections.")
    
    user_prompt = "\n".join(lines)
    
    print("  synthesizing final skill from fragments...", flush=True)
    synthesized = _call_llm(user_prompt, model=model, system_prompt=synthesis_system_prompt)
    
    return synthesized


def distill_skill(patterns_path: Path, output_path: Path, top_n: int = 40, model: str = None,
                  calibration_path: Path = None):
    """Read patterns.json, call LLM (two-stage), sanitize, write skill markdown.

    Two-stage approach:
    Stage 1: For each of 14 categories, generate a category-specific fragment (~25 patterns each)
    Stage 2: Synthesize all fragments into final SKILL.md
    
    Total: 15 LLM calls max (14 categories + 1 synthesis)
    
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

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(skill_md, encoding="utf-8")

    word_count = len(skill_md.split())
    print(f"skill written: {output_path} ({word_count} words)")
    return skill_md
