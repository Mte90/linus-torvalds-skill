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
review code the way Torvalds does. The skill must be:

1. Language-agnostic. Torvalds reviews C kernel code, but the skill must work for any \
language. Abstract away from C/kernel specifics — keep the reviewing METHOD. When a trigger \
references a C idiom (BUG_ON, READ_ONCE, volatile), generalize to the underlying concept \
(fatal assertion for recoverable conditions, explicit memory ordering, etc.).
2. Actionable. Every principle must tell the reviewer WHAT to do and WHEN. Not "be careful" \
but "when X appears, flag it because Y."
3. Grounded in real examples. Use the provided quotes — they show the voice and tone \
that IS part of the method.
4. Honest about what the data shows. Use the actual counts. Don't invent statistics.
5. Comprehensive. The skill should be a thorough reference, not a summary. Aim for \
6000-9000 words. Cover each theme in depth with multiple examples.

You will receive raw review moves sampled from the corpus, grouped by category. \
Each move has: trigger (what prompted the review), principle (the underlying rule), \
response (Torvalds' actual words), severity, and date.

Your job:
1. READ all the moves across all categories.
2. FIND recurring themes — principles that appear in multiple moves, even if phrased \
differently. Group them semantically, not lexically. "Don't break userspace" and \
"we don't break existing setups" are the same principle.
3. For each theme, pick the most representative quotes and triggers. Use multiple quotes \
per theme when they show different facets.
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
and the corpus size (use the provided stats). 2-3 sentences.]

## Reviewer Mindset
[The 5-7 core attitudes that define the approach. Each with a one-line principle \
and a real Torvalds quote. Explain WHY each attitude matters.]

## Review Triggers
[Comprehensive catalog of "when you see X, flag it" patterns, grouped by semantic \
theme (not by the raw category labels — use themes you discover across categories). \
For EACH trigger provide:
- What to look for (generalized, language-agnostic)
- Why it's a problem (the underlying principle)
- Severity: reject / request-changes / nitpick
- A real Torvalds quote showing how he handles it
- 1-2 additional supporting quotes when available

Cover at least 12 distinct trigger themes. Each theme should have 3-6 specific triggers.]

## Severity Calibration
[How to calibrate: when is something a reject vs. a request-changes vs. a nitpick? \
Use the severity distribution from the data. Give concrete examples of each severity \
level with real quotes. Explain the reasoning behind the calibration.]

## Anti-Patterns
[What Torvalds consistently rejects: over-engineering, abstraction for its own sake, \
breaking existing users, cleverness without measurement, etc. For each anti-pattern:
- What it looks like
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
[Walk through 5-8 concrete review scenarios showing the method in action:
- The situation
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
concrete items grouped by theme.]

Keep the total output between 6000-9000 words. Every section must have real quotes from \
the data. Do not invent quotes — only use what is provided. If you need more examples \
for a theme, use the quotes you have and note the pattern.
"""


def _call_llm(prompt: str, retries: int = None) -> str:
    """Call the LLM for the distillation step. Returns raw text."""
    retries = retries if retries is not None else config.MAX_RETRIES

    payload = {
        "model": config.MODEL,
        "messages": [
            {"role": "system", "content": DISTILL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.CHAT_URL,
        data=body,
        headers=config.headers(),
        method="POST",
    )

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(config.RETRY_DELAY * (attempt + 1))
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            last_err = e
            time.sleep(config.RETRY_DELAY)

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


def distill_skill(patterns_path: Path, output_path: Path, top_n: int = 40):
    """Read patterns.json, call LLM, write skill markdown."""
    data = json.loads(patterns_path.read_text(encoding="utf-8"))

    prompt = _format_moves_for_prompt(data)
    print(f"calling LLM with {len(prompt)} chars of move data...")
    print(f"  ({sum(len(v) for v in data.get('samples_by_category', {}).values())} sampled moves)")

    skill_md = _call_llm(prompt)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(skill_md, encoding="utf-8")

    word_count = len(skill_md.split())
    print(f"skill written: {output_path} ({word_count} words)")
    return skill_md
