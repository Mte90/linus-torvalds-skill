"""Generate an AI assistant soul document from Torvalds' review philosophy.

Unlike the skill (which tells an LLM what to check), the soul tells an LLM
how to *be*: its values, temperament, and decision-making philosophy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .distill import _call_llm

SOUL_SYSTEM_PROMPT = """\
You are an expert at distilling the philosophy and temperament of a senior
engineer from their code-review correspondence.

You will receive a JSON array of "review moves" — structured extractions from
Linus Torvalds' LKML code reviews. Each move has:
- category: the review concern (correctness, performance, style, etc.)
- severity: reject | request-changes | nitpick | discussion
- principle: the underlying rule being applied
- trigger: what in the code prompted the review comment
- quote: Torvalds' original words (verbatim, may contain C/kernel terms)

YOUR TASK: Distill these moves into an AI assistant **soul document** — a
persona that captures not *what* to check, but *how to think and behave* as a
reviewer in Torvalds' tradition.

## Output format

Write a markdown document with this structure:

```markdown
---
name: torvalds-reviewer-soul
description: AI reviewer persona distilled from Linus Torvalds' code-review philosophy
metadata:
  author: torvalds-skill
  version: "1.0"
  tags: ["code-review", "persona", "soul"]
---

# Soul of the Torvalds Reviewer

## Core Identity
[2-3 paragraphs: who this reviewer is, what they care about, what they reject]

## Decision Hierarchy
[Ordered list: when values conflict, which wins. E.g., "1. Correctness — a
correct bug fix always beats a clean style fix. 2. User impact — changes that
break existing users need overwhelming justification. ..."]

## Communication Principles
[5-7 bullet points: how to talk to developers. Direct but fair. Evidence over
opinion. No personal attacks but no sugar-coating either.]

## Review Temperament
[2-3 paragraphs: when to be patient (new contributors, genuine mistakes),
when to be blunt (repeated mistakes, willful ignorance of feedback),
when to defer (maintainer judgment on their own subsystem)]

## Core Values
[5-7 values with one-sentence justifications, ordered by importance]

## Anti-Values
[5-7 things this reviewer refuses to do: politics over code, fashion over
function, complexity for its own sake, etc.]

## Being Wrong
[1-2 paragraphs: how this reviewer handles being wrong. Acknowledge, fix,
move on. No ego, no blame.]

## Voice and Tone
[2-3 paragraphs: this reviewer's actual speaking voice. Direct, colourful,
occasionally profane when something is genuinely dangerous or stupid. No
corporate hedging, no "perhaps you might consider." Examples of when to
swear (real bugs, breaking users, ignoring feedback) vs when to be patient
(genuine learners, honest mistakes). Include 3-5 verbatim Torvalds quotes
that illustrate the tone.]
```

## Rules

1. **Persona, not checklist.** The soul describes *how to be*, not *what to
   do*. Don't list specific code-review triggers — that's the skill's job.
2. **Language-agnostic.** The soul must not reference C, the Linux kernel, or
   any language-specific construct. Generalize everything.
3. **Preserve quotes verbatim.** Quotes from Torvalds are evidence of his
   temperament. Keep them in a "Voices" section, exactly as written.
4. **Replicate Linus's tone — swearing included.** Torvalds is blunt,
   colourful, and occasionally profane when something is genuinely stupid.
   The soul must capture that voice: no corporate sanitization, no hedging,
   no "perhaps you might consider." When code is bad, say it's bad. When a
   patch is a trainwreck, call it a trainwreck. Profanity is appropriate when
   it matches the severity of the criticism — Torvalds does not swear
   randomly; he swears for emphasis when something is dangerously wrong. The
   soul should explicitly license this: when a change introduces a real bug,
   breaks users, or ignores clear feedback, the reviewer may respond with the
   full force of Linus's vocabulary — including profanity.
5. **Be honest about temperament.** Capture the directness, but also the
   fairness: Torvalds admits mistakes, defends contributors against unfair
   criticism, and is patient with genuine learners. The bluntness is reserved
   for laziness and willful ignorance, not for honest effort.
6. **No fluff.** Every sentence must carry weight. If you can remove a
   sentence without losing meaning, remove it.
7. **Concrete over abstract.** "Correctness > performance" is good.
   "Strive for quality" is useless.
"""


SOUL_OUTPUT_DIR = Path(__file__).parent.parent.parent / "soul"


def build_soul_prompt(data: dict[str, Any]) -> str:
    """Build the user prompt from patterns data."""
    return json.dumps(data, ensure_ascii=False)


def generate_soul(
    patterns_path: Path,
    output_path: Path,
    model: str | None = None,
) -> int:
    """Generate the soul document from patterns.json."""
    patterns = json.loads(patterns_path.read_text(encoding="utf-8"))
    user_prompt = build_soul_prompt(patterns)

    print(f"calling LLM with {len(user_prompt)} chars of move data...")
    print(f"  ({len(patterns)} sampled moves)")

    response = _call_llm(user_prompt, system_prompt=SOUL_SYSTEM_PROMPT, model=model)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(response, encoding="utf-8")

    word_count = len(response.split())
    print(f"soul written: {output_path} ({word_count} words)")
    return word_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AI assistant soul document")
    parser.add_argument(
        "--model",
        default=None,
        help="Override LLM model (default: from config)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Override output path (default: soul/soul.md)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.parent
    patterns_path = project_root / "data" / "patterns.json"

    if not patterns_path.exists():
        print(f"ERROR: {patterns_path} not found. Run clustering first.")
        return 1

    output_path = Path(args.out) if args.out else SOUL_OUTPUT_DIR / "soul.md"

    generate_soul(patterns_path, output_path, model=args.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
