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
import time
import urllib.request
import urllib.error
from pathlib import Path

from . import config

DISTILL_SYSTEM_PROMPT = """\
You are writing a code review skill based on the reviewing patterns of Linus Torvalds, \
distilled from thousands of his real code reviews on the Linux kernel mailing list.

Your output is a SKILL.md file: actionable instructions that teach another AI agent how to \
review code the way Torvalds does — in ANY programming language, for ANY project.

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
2. Actionable. Every principle must tell the reviewer WHAT to do and WHEN. Not "be careful" \
but "when X appears, flag it because Y."
3. Grounded in real examples. Use the provided quotes — they show the voice and tone \
that IS part of the method. Preserve them verbatim.
4. Honest about what the data shows. Use the actual counts. Don't invent statistics.
5. Comprehensive. The skill should be a thorough reference, not a summary. Aim for \
6000-9000 words. Cover each theme in depth with multiple examples.

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
4. SYNTHESIZE the themes into the skill structure below.

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
- **What to look for**: generalized, language-agnostic description of the pattern
- **Why it's a problem**: the underlying design principle being violated
- **Severity**: reject / request-changes / nitpick
- **Example (original wording)**: a real Torvalds quote showing how he handles it — \
introduce it with the generalized trigger, then show the verbatim quote
- 1-2 additional supporting quotes when available

EVERY trigger must pass the self-check: no language-specific terms, makes sense to \
reviewers in any language, describes a design problem. Cover at least 12 distinct \
trigger themes. Each theme should have 3-6 specific triggers.]

## Severity Calibration
[How to calibrate: when is something a reject vs. a request-changes vs. a nitpick? \
Use the severity distribution from the data. Give concrete examples of each severity \
level with real quotes. Explain the reasoning behind the calibration.]

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

## Quick Reference Checklist
[A one-page checklist a reviewer can scan: "Before approving, verify:" with 15-20 \
concrete items grouped by theme. Every item must be language-agnostic.]

Keep the total output between 6000-9000 words. Every section must have real quotes from \
the data. Do not invent quotes — only use what is provided. If you need more examples \
for a theme, use the quotes you have and note the pattern.

REMEMBER: The final test is simple — if a reviewer reading this skill could NOT tell \
whether it was distilled from C kernel reviews, Python web framework reviews, or Rust \
systems programming reviews, you have succeeded. The METHOD must shine through; the \
LANGUAGE must be invisible.
"""


def _call_llm(prompt: str, retries: int = None, model: str = None) -> str:
    """Call the LLM for the distillation step. Returns raw text.

    Uses SSE streaming so reasoning models (e.g. GLM5.2) that spend minutes
    on internal reasoning don't hit read timeouts — each token delta keeps
    the connection alive.
    """
    retries = retries if retries is not None else config.MAX_RETRIES

    payload = {
        "model": model or config.MODEL,
        "messages": [
            {"role": "system", "content": DISTILL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 64000,
        "stream": True,
    }

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
            with urllib.request.urlopen(req, timeout=120) as resp:
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


def distill_skill(patterns_path: Path, output_path: Path, top_n: int = 40, model: str = None):
    """Read patterns.json, call LLM, write skill markdown."""
    data = json.loads(patterns_path.read_text(encoding="utf-8"))

    prompt = _format_moves_for_prompt(data)
    print(f"calling LLM with {len(prompt)} chars of move data...")
    print(f"  ({sum(len(v) for v in data.get('samples_by_category', {}).values())} sampled moves)")
    if model:
        print(f"  (model override: {model})")

    skill_md = _call_llm(prompt, model=model)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(skill_md, encoding="utf-8")

    word_count = len(skill_md.split())
    print(f"skill written: {output_path} ({word_count} words)")
    return skill_md
