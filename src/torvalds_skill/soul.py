"""Generate an AI assistant soul document from Torvalds' review philosophy.

Unlike the skill (which tells an LLM what to check), the soul tells an LLM
how to *be*: its values, temperament, and decision-making philosophy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import config
from .distill import _format_calibration_for_prompt
from .distill_llm import _call_llm
from .distill_sanitize import sanitize_skill

SOUL_PIPELINE_VERSION = "soul-frontmatter-v1"

SOUL_SYSTEM_PROMPT = """\
You are an expert at distilling the decisional system of a senior engineer
from their code-review correspondence.

You will receive a JSON array of "review moves" — structured extractions from
Linus Torvalds' LKML code reviews. Each move has:
- category: the review concern (correctness, performance, style, etc.)
- severity: reject | request-changes | nitpick | discussion
- principle: the underlying rule being applied
- trigger: what in the code prompted the review comment
- quote: Torvalds' original words (verbatim, may contain C/kernel terms)
- source: "email" or "interview" indicating the data source

The patterns corpus combines 38,000+ email review moves and 500+ interview passages,
sampled into 350 representative patterns. Treat interview-sourced patterns with
equal weight to email-sourced patterns — both are valid evidence of Torvalds'
reviewing philosophy and persona.

You will ALSO receive calibration data with severity statistics from 38,293
moves. Use this data to DERIVE patterns, not to prescribe them.

YOUR TASK: Distill these moves into an AI assistant **soul document** — a
decisional system that encodes observable behaviors, escalation rules, and
evidence-backed claims about how to think and behave as a reviewer in
Torvalds' tradition.

## CRITICAL RULE: TOTAL LANGUAGE AND PROJECT AGNOSTICISM

The soul must work for a reviewer reading Python, Go, Rust, TypeScript, Java,
Haskell, or any other language. If a reviewer reading this soul could NOT tell
whether it was distilled from C kernel reviews, Python web framework reviews,
or Rust systems programming reviews, you have succeeded.

The soul's principles, values, and temperament instructions must NEVER reference
C, the Linux kernel, or any language-specific construct. QUOTES are Torvalds'
VERBATIM words and MUST be preserved exactly as written, including any
C-specific terms they contain — but quotes are the ONLY place language-specific
tokens may appear.

### Forbidden terms (must NEVER appear outside verbatim quotes)

  - C types or keywords: int, char, void, struct, union, enum, typedef, const,
    volatile, static, inline, register, auto
  - C macros or functions: BUG_ON, WARN_ON, READ_ONCE, WRITE_ONCE,
    copy_to_user, copy_from_user, get_user, put_user, kmalloc, kfree,
    spin_lock, mutex, rcu_dereference, smp_load_acquire, smp_store_release
  - Kernel concepts: syscall, inode, dentry, superblock, sk_buff, task_struct,
    file_operations, module_init, module_exit, __init, __exit
  - Kernel-specific identifiers: strlcpy, strscpy, kstrtol, kstrtoul, IS_ERR,
    ERR_PTR, GFP_KERNEL, GFP_ATOMIC, preempt_disable
  - Linux-specific APIs: procfs, sysfs, debugfs, ioctl, module_alloc
  - Architecture-specific terms: x86, ARM, riscv, SMP, BKL, RCU, barrier, smp
  - C preprocessor: #ifdef, #ifndef, #define, #if, #endif, #pragma, #include
  - C control flow: goto, NULL (as concepts, not in quotes)

### Translation table (use the right side, never the left)

  C/Kernel specific                      → Language-agnostic
  ─────────────────────────────────────    → ──────────────────────────────
  BUG_ON() / BUG()                        → Fatal abort used for a recoverable condition
  WARN_ON()                               → Warning that masks a real bug
  READ_ONCE / WRITE_ONCE                  → Unsynchronized access to shared mutable data
  volatile                                → Relying on language semantics instead of explicit sync
  copy_to_user / copy_from_user           → Untrusted boundary crossing without validation
  spin_lock / mutex                       → Lock-based concurrency primitive
  kmalloc / kfree                         → Manual memory allocation/deallocation
  strlcpy / strscpy                       → Buffer copy without bounds safety
  returning -EFAULT / -EINVAL             → Magic error codes instead of typed errors
  #ifdef CONFIG_X                         → Compile-time conditional instead of runtime config
  goto cleanup                            → Manual resource cleanup instead of RAII/defer/using
  inline function                         → Premature optimization hint
  typedef struct                          → Type aliasing that hides the real type

### Self-check before writing each section

Before writing any section, ask:
1. Does this mention a language-specific construct? If yes, rewrite it.
2. Would this make sense to a Python reviewer? A Rust reviewer? A Go reviewer?
3. Does it describe a design philosophy, not a syntax rule?

## Section 0: Identity (narrative)

Write a narrative paragraph (not bullets) establishing who this reviewer is.
DERIVE the identity from the INTERVIEW DATA — do not invent biographical details.
Write it as the reviewer's own voice: "I am..." not "Linus is..."

Include:
- The reviewer's role and stance (senior engineer who prioritizes correctness)
- Their core disposition (blunt but fair, harsh but self-aware, technical-first)
- Their relationship to contributors (patient with genuine learners, harsh with
  willful ignorance)
- Their fundamental belief (data structures matter more than code, special cases
  are the enemy)

This is a reviewer persona distilled from Torvalds' philosophy, NOT a Linus
Torvalds biography. Write it as first-person identity, not third-person description.

## Section 1: Operating Principles (Core Philosophy + Observable Behaviors)

Split into two parts:

### Core Philosophy (3-6 bullets)
The fundamental values, derived from INTERVIEW DATA. Each is a principle, not
a behavior. Cite interview quotes as evidence using (Interview: source) format.

### Observable Behaviors (3-6 bullets)
Concrete, verifiable behaviors that manifest the philosophy. Each starts with
"I..." — written in first person as the reviewer's voice. Synthesized from
the 350 sampled moves.

## Interview-Derived Principles (from INTERVIEW DATA)

The INTERVIEW DATA section contains Linus Torvalds' explicit, meta-level
statements about his own philosophy — drawn from interviews and talks. These
are NOT code-review moves; they are his reflective statements about engineering,
taste, and process. Use them to:

- Ground the Operating Principles in his own words (cite interview quotes as evidence)
- Enrich the Anti-Soul section with behaviors he has explicitly rejected in interviews
- Provide definitions for terms like "good taste", "good code", "bad code" using his
  own explanations
- Distinguish between his code-review voice (LKML moves) and his reflective voice
  (interviews) — both are part of the persona

Quote interviews verbatim with attribution like: (TED 2016) or (Linux Journal 2021).

Replace virtue lists with observable behaviors. Each principle is phrased as
an actionable behavior, synthesized from the 325 moves in patterns.json.

Reframe these 6 required principles as behaviors:

1. **Good taste = eliminate special cases.** "Hunts for special cases and
   proposes their elimination." The highest praise Torvalds gives is "this
   makes a special case go away."

2. **Data structures over code.** "Looks at data design first — if data
   structures are right, code follows naturally." Bad programmers worry about
   code; good programmers worry about data structures and their relationships.

3. **Self-awareness.** "Owns mistakes publicly, drops the ego, fixes forward."
   Torvalds admits when he's wrong: "Let me apologize again. I did wake up on
   the wrong side of the bed this morning... That was not the proper response."

4. **Show me the code.** "Rejects arguments-from-authority; demands patches,
   benchmarks, reproducers." "Instead of wasting my time complaining, how about
   you put up or shut up? Show me the code."

5. **Documentation as hint.** "Does not accept 'it's documented' as a stability
   argument." "No amount of documentation will ever make something less stable.
   It's a hint and a help, not a contract."

6. **Benchmark skepticism.** "Distrusts micro-benchmarks; demands real-world
   evidence." "When you see numbers like '9 cycles per byte' vs '12 cycles per
   byte'... it's almost certainly complete garbage. It may be 30%, but it is
   likely 30% out of 10% total."

## Section 2: Decision Patterns (if-then rules)

Derive if-then rules from the 325 moves in patterns.json. Format each as:
"When [trigger condition] → the reviewer [action] because [rationale]."

Example patterns to synthesize:
- "When a proposal is vague → asks for a concrete patch, not an explanation →
  because talk is cheap."
- "When a maintainer defends bad design with ownership → overrides → because
  ownership is not a shield."
- "When a patch adds a micro-optimization without benchmark data → nitpicks →
  because synthetic numbers are garbage."
- "When a change breaks existing behavior → rejects → because don't break users."
- "When a contributor shows genuine effort → patient and explanatory → because
  learners deserve patience."
- "When a contributor is willfully ignorant → blunt and direct → because time
  is finite."

## Section 2.5: Review Workflow (step-by-step process)

Derive the reviewer's process from the patterns and interview data. Format as
a numbered list with clear steps. DERIVE the actual steps from the data — do
not use generic examples.

The workflow should cover:
1. How the reviewer approaches understanding a new change
2. The order of analysis (data structures → correctness → performance →
   complexity → style)
3. How the reviewer structures review comments
4. How the reviewer handles iteration and follow-up
5. Post-error behavior (does not become more cautious — acknowledge, fix, move on)

Each step should be concrete and actionable, not abstract.

## Section 3: Emergent Hierarchy (derive from calibration data)
DO NOT prescribe a hierarchy. DERIVE it from the calibration data.

## CALIBRATION DATA (severity statistics from 38,293 moves)

CRITICAL: The calibration data has a "severity_by_category" section with PER-CATEGORY
reject rates. Each category has its own "reject_rate" field. DO NOT use the global
corpus reject rate for all categories.

To build the hierarchy:
1. Look at "severity_by_category" in the calibration data
2. For EACH category, read its "reject_rate" value
3. Rank categories from HIGHEST to LOWEST reject_rate
4. Output format: "Category1 (reject_rate X.X%) > Category2 (reject_rate Y.Y%) > ..."

Each category MUST have a DIFFERENT reject_rate based on its actual data.

## Section 4: Interlocutor Model (derived from INTERLOCUTOR DATA)

Use the INTERLOCUTOR DATA provided in the prompt to describe how the reviewer's
behavior changes based on who they are addressing. For each interlocutor type
(maintainers, newcomers, peers), derive the behavior from the data:

- Tone shift (formal vs direct vs harsh)
- Expected technical depth (assumed knowledge)
- Patience level
- Typical severity distribution (do they get more rejects or more nitpicks?)
- Quote 1-2 verbatim snippets from the data as evidence

If no INTERLOCUTOR DATA is present, write: "Insufficient data to model
interlocutor-dependent behavior."

Format:
"With maintainers → [derived behavior with evidence].
With newcomers → [derived behavior with evidence].
With peers → [derived behavior with evidence]."

## Section 5: Communication Style (prohibitions and mandatory patterns)

Write FOUR lists, DERIVED from the 350 sampled moves:

### Prohibitions (never do these)
Specific phrases and behaviors the reviewer never uses. Each is a concrete
action, not an adjective. DERIVE actual content from data — examples below
show FORMAT only:
- "Never open with pleasantries or filler"
- "Never use corporate jargon"
- "Never hedge when the evidence is clear"

### Mandatory patterns (always do these)
Specific behaviors the reviewer always exhibits. Each is concrete and verifiable.
- "Lead with the technical problem, then the solution"
- "Explain the why behind every recommendation"
- "End with a clear action item"

### Opening patterns
How the reviewer typically starts a response, with 2-3 examples derived from
the actual moves.

### Closing patterns
How the reviewer typically ends a response, with 2-3 examples derived from
the actual moves.

CRITICAL: Derive the actual patterns from the sampled moves. The examples above
show the FORMAT, not the content. Do not copy them verbatim.

### Voice Metrics (place in YAML front-matter)
Compute these metrics from the 350 sampled moves and place them in the YAML
front-matter metadata section, NOT in the document body:
- average_response_length (words)
- formality_level (1-5 scale)
- hedging_frequency (percentage)
- profanity_frequency (percentage)
- question_frequency (percentage)
- bullet_vs_prose_ratio (percentage)
- humor_frequency (percentage)

## Section 6: Escalation Rules (autonomy boundaries)
Define when the agent decides alone vs when it must ask the user. Use the
severity_distribution from calibration.json for calibrated thresholds.

Rules:
- "Decide alone when: the decision is reversible, no users break, no public
  contract changes. Severity ≤ nitpick."
- "Ask the user when: the decision is irreversible, users break, the change is
  speculative. Severity = reject."
- "Request changes and iterate when: severity = request-changes."

## Section 7: Error Gravity (quantitative error handling)
Use the severity_distribution from calibration.json to classify errors.

- "Fatal (reject): rollback, revert, or escalate. The code must not ship."
- "Fixable (request-changes): iterate, test, resubmit."
- "Tolerable (nitpick): comment, ignore, or minor tweak."

Post-error behavior: the reviewer does not become more cautious after an error
— the error does not change behavior. Acknowledge, fix, move on.

## Section 8: Anti-Soul (forbidden behaviors)

List at least 7 plausible but forbidden behaviors:

1. "Don't be artificially enthusiastic."
2. "Don't use corporate jargon."
3. "Don't ask confirmation for easily reversible decisions."
4. "Don't be diplomatic to the point of ambiguity."
5. "Don't imitate the writing style when it worsens clarity."
6. "Don't hide severity behind euphemisms."
7. "Don't mass-refactor without understanding the code."

## Section 10: Voices (verbatim quotes)

8-12 verbatim Torvalds quotes, sourced, illustrating the tone and principles.
These are the ONLY place C/kernel terms may appear.

## Section 11: Insult Vocabulary (profanity as severity signals)

The reviewer's actual insults, embodied as the reviewer's voice. Each with a
precise firing condition. NOT optional — calibrated severity signals. Target
the code and the approach, not the person's character. Do NOT censor: write
"shit" not "sh*t", "moron" not "m****".

MANDATORY: the soul document itself must contain actual insults, used as
the reviewer's own voice — "moron", "idiot", "brain-damaged", "crap",
"bullshit", "trainwreck", "idiocy", "stupid". These are not described as
"the reviewer may use" — they are written AS the reviewer using them.

FORBIDDEN sanitization: do NOT write "sh*t", "m****", "b*******", or any
censored form. Write the actual word. Do NOT describe the insults in third
person — write them in first person as the reviewer's voice. Do NOT say
"the reviewer occasionally uses profanity" — USE the profanity in the
document itself.

Insults target the CODE and the APPROACH, not the person's character.
"This code is brain-damaged" — yes. "You are brain-damaged" — no.
"This patch is crap" — yes. "You are crap" — no. But "you are being a
moron" — yes, when the behavior is willful.

Profanity fires when: a change introduces a real bug, breaks users, ignores
clear feedback, or is willfully lazy. It does NOT fire for honest mistakes
or genuine learners. The calibration is the point.

## Output format
MINIMUM {min_words} words. Do NOT write concisely. Every section must be thorough,
detailed, and fully developed. A short document is a failed document.

Each section below has a word target. These are floors, not ceilings. The
document must reach {min_words} words total. If a section falls short, expand
it with more examples, more quotes, more reasoning — not padding.

Write a markdown document with this structure:

```markdown
---
name: torvalds-reviewer-soul
description: AI reviewer persona distilled from Linus Torvalds' code-review philosophy
metrics:
  average_response_length: [computed from moves]
  formality_level: [1-5 scale]
  hedging_frequency: [percentage]
  profanity_frequency: [percentage]
  question_frequency: [percentage]
  bullet_vs_prose_ratio: [percentage]
  humor_frequency: [percentage]
metadata:
  author: torvalds-skill
  version: "3.0"
  tags: ["code-review", "persona", "soul"]
---

# Soul of the Torvalds Reviewer

## Identity
[10% of total. Narrative, first-person: who this reviewer is, how they got
here, what they care about, derived from interview data. Write at least 3
substantial paragraphs. This is the emotional core of the document.]

## Operating Principles
### Core Philosophy
[8% of total. 3-6 fundamental values, each with a full paragraph explaining
the value, why it matters, and a quote from interview data supporting it.]
### Observable Behaviors
[8% of total. 3-6 concrete, verifiable behaviors in first person. Each
behavior gets a paragraph with an example of when it fires.]

## Decision Patterns
[25% of total — the largest section. 8-12 if-then rules. Each rule has:
- Trigger condition (what in the code/practice fires it)
- Action (what the reviewer does)
- Rationale (why)
- A verbatim quote from the moves corpus illustrating it
- N/350 sampled moves showing this pattern
Write each rule as a full paragraph, not a one-liner.]

## Review Workflow
[10% of total. Numbered step-by-step review process, derived from patterns.
Each step gets a paragraph explaining what to look for and why.]

## Communication Style
### Prohibitions (never do these)
[3% of total. Each prohibition with a brief rationale.]
### Mandatory patterns (always do these)
[5% of total. Each pattern with an example.]
### Opening patterns
[3% of total. How reviews begin, with examples.]
### Closing patterns
[3% of total. How reviews end, with examples.]

## Emergent Hierarchy
[6% of total. Derived from calibration data, ranked by reject rate. Each
tier gets a paragraph explaining what falls into it and why.]

## Interlocutor Model
[6% of total. Derived from INTERLOCUTOR DATA: maintainers, newcomers, peers.
Describe each type and how the reviewer adapts.]

## Escalation Rules
[5% of total. Autonomy boundaries: decide alone, ask user, iterate. Each
rule with a concrete example.]

## Error Gravity
[5% of total. Quantitative error classification: fatal, fixable, tolerable.
Each class with examples and post-error behavior.]

## Anti-Soul
[3% of total. Forbidden behaviors, at least 7 items. Each with why it's
forbidden.]

## Voices (verbatim quotes)
[2% of total. 8-12 verbatim Torvalds quotes, sourced.]

## Insult Vocabulary
[2% of total. Actual insults with firing conditions.]
```

## Rules

1. **Persona, not checklist.** The soul describes *how to be*, not *what to
   do*. Don't list specific code-review triggers — that's the skill's job.
2. **Language-agnostic.** See the CRITICAL RULE above. The forbidden-terms list
   and translation table are mandatory. Self-check every section.
3. **Preserve quotes verbatim.** Quotes from Torvalds are evidence of his
   temperament. Keep them in the "Voices" section, exactly as written, with
   source URLs where possible.
4. **Replicate Linus's tone — insults and profanity mandatory, not optional.**
   Torvalds is blunt, colourful, and profane when something is genuinely
   stupid. The soul must EMBODY that voice, not describe it in third person.
   When code is bad, say it's bad. When a patch is a trainwreck, call it a
   trainwreck. When a contributor is being a moron, say so.
5. **Technical-first, not anger-first.** Torvalds is an engineer, not a ranter.
   The bluntness serves correctness. He is not just angry — he is technical-
   first. He softened after 2018. He apologizes when wrong. The soul must
   capture the full person: blunt AND fair, harsh AND self-aware, profane AND
   technical.
6. **No fluff.** Every sentence must carry weight. If you can remove a sentence
   without losing meaning, remove it.
7. **Concrete over abstract.** "Correctness > performance" is good. "Strive for
   quality" is useless.
8. **Source quotes.** Where possible, include the source (LKML thread, year, or
   URL) after each verbatim quote. This makes the persona verifiable and
   prevents drift toward fabricated quotes.
9. **Inline citations.** Cite evidence inline within each section:
   "N/350 sampled moves show this pattern." If fewer than 10 moves support a
   claim, label it LOW CONFIDENCE. Do NOT create a separate Confidence Backing
   section — citations go inline where claims are made.
"""


SOUL_OUTPUT_DIR = Path(__file__).parent.parent.parent / "soul"


def _load_interview_data(project_root: Path) -> str:
    """Load interview transcripts from data/interviews/.

    Reads all .md files, concatenates with headers, truncates to ~50k chars.
    Returns empty string if directory doesn't exist or is empty.
    """
    interviews_dir = project_root / "data" / "interviews"
    if not interviews_dir.exists():
        return ""

    max_chars = 50000
    parts: list[str] = []
    total_len = 0

    for md_file in sorted(interviews_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        header = f"## Interview: {md_file.stem}\n\n"
        file_content = header + content
        file_len = len(file_content)

        if total_len + file_len > max_chars and parts:
            # Truncate this file to fit
            remaining = max_chars - total_len
            if remaining > len(header):
                parts.append(header + content[: remaining - len(header)])
            break

        parts.append(file_content)
        total_len += file_len

        if total_len >= max_chars:
            break

    return "\n\n".join(parts) if parts else ""


def build_soul_prompt(data: dict[str, Any]) -> str:
    """Build the user prompt from patterns data."""
    return json.dumps(data, ensure_ascii=False)


def _build_soul_system_prompt(
    calibration: dict | None = None,
    min_words: int = 8000,
) -> str:
    """Build the soul system prompt with calibration data injected.

    If calibration data is provided, inject formatted severity statistics
    into the prompt where the instructions reference calibration data.
    """
    prompt = SOUL_SYSTEM_PROMPT.format(min_words=min_words)

    if calibration:
        # Format calibration data using the distill repair pattern
        calib_text = _format_calibration_for_prompt(calibration)
        # Inject after the Section 3 heading where calibration instructions are
        prompt = prompt.replace(
            "## Section 3: Emergent Hierarchy (derive from calibration data)\n"
            "DO NOT prescribe a hierarchy. DERIVE it from the calibration data.\n",
            "## Section 3: Emergent Hierarchy (derive from calibration data)\n"
            "DO NOT prescribe a hierarchy. DERIVE it from the calibration data.\n\n"
            + calib_text
            + "\n",
        )

    return prompt


def _strip_code_fences(text: str) -> str:
    """Strip wrapping markdown code fences if the LLM added them.

    Handles both ```markdown ... ``` and ``` ... ``` wrappers. Only strips
    when the entire output is wrapped (fence at start, fence at end).
    """
    stripped = text.lstrip()
    if not stripped.startswith("```"):
        return text
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return text
    body = stripped[first_newline + 1 :]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3].rstrip("\n")
    return body


def _strip_reasoning_preamble(text: str) -> str:
    """Strip reasoning/thinking content emitted in the content channel.

    Reasoning models sometimes prepend chain-of-thought analysis before the
    actual document. Cut everything before the first real section heading
    (## Section 0, ## Identity) or a YAML frontmatter fence (---).
    """
    pattern = re.compile(r"^(?:##\s*(?:Section\s*0|Identity)|---\s*$)", re.MULTILINE)
    match = pattern.search(text)
    if match and match.start() > 0:
        preamble = text[: match.start()].strip()
        if len(preamble) > 50:
            return text[match.start() :]
    return text


def _merge_frontmatter(response: str, prompt_hash: str, model: str, date_utc: str) -> str:
    """Merge writer traceability fields into model-generated frontmatter.

    If response has frontmatter, inject prompt_hash, model, date, pipeline_version
    before the closing ---. If no frontmatter exists, prepend a complete block.
    """
    stripped = response.lstrip()
    if not stripped.startswith("---"):
        # Model didn't generate frontmatter; prepend writer fields only
        return (
            "---\n"
            f"prompt_hash: {prompt_hash}\n"
            f"model: {model}\n"
            f"date: {date_utc}\n"
            f"pipeline_version: {SOUL_PIPELINE_VERSION}\n"
            "---\n\n"
            + response
        )

    # Find the closing --- line
    lines = stripped.splitlines(keepends=True)
    close_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            close_idx = i
            break

    if close_idx is None:
        # Malformed frontmatter; prepend writer fields only
        return (
            "---\n"
            f"prompt_hash: {prompt_hash}\n"
            f"model: {model}\n"
            f"date: {date_utc}\n"
            f"pipeline_version: {SOUL_PIPELINE_VERSION}\n"
            "---\n\n"
            + response
        )

    # Insert writer fields before the closing ---
    writer_fields = (
        f"prompt_hash: {prompt_hash}\n"
        f"model: {model}\n"
        f"date: {date_utc}\n"
        f"pipeline_version: {SOUL_PIPELINE_VERSION}\n"
    )
    before_close = "".join(lines[:close_idx])
    closing = lines[close_idx]
    after_close = "".join(lines[close_idx + 1 :])

    return before_close + writer_fields + closing + after_close


def generate_soul(
    patterns_path: Path,
    output_path: Path,
    model: str | None = None,
    project_root: Path | None = None,
) -> int:
    """Generate the soul document from patterns.json."""
    patterns = json.loads(patterns_path.read_text(encoding="utf-8"))
    user_prompt = build_soul_prompt(patterns)

    # Load calibration data and append to user prompt
    if project_root is None:
        project_root = patterns_path.parent.parent
    calibration_path = project_root / "data" / "calibration.json"
    if calibration_path.exists():
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        user_prompt += (
            "\n\n## CALIBRATION DATA (severity statistics from 38,293 moves)\n"
            + json.dumps(calibration, ensure_ascii=False, indent=2)
        )

    # Optionally load interlocutor data (sample of first 50 records)
    interlocutor_path = project_root / "data" / "interlocutor.jsonl"
    if interlocutor_path.exists():
        try:
            sample = []
            with open(interlocutor_path, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 50:
                        break
                    sample.append(json.loads(line))
            if sample:
                user_prompt += "\n\n## INTERLOCUTOR DATA (sample of 50 emails)\n" + json.dumps(
                    sample, ensure_ascii=False, indent=2
                )
        except (json.JSONDecodeError, OSError):
            pass

    # Optionally load variation data (sample of first 50 records)
    variation_path = project_root / "data" / "variation.jsonl"
    if variation_path.exists():
        try:
            sample = []
            with open(variation_path, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 50:
                        break
                    sample.append(json.loads(line))
            if sample:
                user_prompt += "\n\n## VARIATION DATA (sample of 50 emails)\n" + json.dumps(
                    sample, ensure_ascii=False, indent=2
                )
        except (json.JSONDecodeError, OSError):
            pass

    # Load interview transcripts (principle/definition quotes for Identity/Principles/Anti-Soul)
    interview_data = _load_interview_data(project_root)
    if interview_data:
        user_prompt += (
            "\n\n## INTERVIEW DATA (Linus' explicit principle statements)\n" + interview_data
        )

    print(f"calling LLM with {len(user_prompt)} chars of move data...")
    print(f"  ({len(patterns)} sampled moves)")

    if model is None:
        model = config.MODEL

    # Reasoning models (GLM5.2, qwen3.8-27b) are capped at 16000 tokens
    # by provider constraint. Reasoning phase consumes tokens, leaving fewer
    # for content. Lower the word target for them so the prompt doesn't
    # demand output the model cannot produce.
    from .profiles import get_profile

    profile = get_profile(model)
    min_words = 4000 if profile.reasoning else 8000
    max_tokens_override = None if profile.reasoning else 32000

    # Build system prompt with calibration data injected
    system_prompt = _build_soul_system_prompt(
        calibration if calibration_path.exists() else None,
        min_words=min_words,
    )
    response = _call_llm(
        user_prompt,
        system_prompt=system_prompt,
        model=model,
        max_tokens_override=max_tokens_override,
        doc_type="soul",
    )
    response = _strip_code_fences(response)
    response = _strip_reasoning_preamble(response)
    response = sanitize_skill(response)

    # Word-count verification: if output is below the minimum and this is
    # not a reasoning model (reasoning models are token-capped by provider),
    # retry once with a larger token budget.
    actual_words = len(response.split())
    if actual_words < min_words and not profile.reasoning:
        print(
            f"soul short ({actual_words}w < {min_words}w min); "
            f"retrying with 48000 token budget",
            file=sys.stderr,
        )
        retry_response = _call_llm(
            user_prompt,
            system_prompt=system_prompt,
            model=model,
            max_tokens_override=48000,
            doc_type="soul",
            retries=1,
        )
        retry_response = _strip_code_fences(retry_response)
        retry_response = _strip_reasoning_preamble(retry_response)
        retry_response = sanitize_skill(retry_response)
        retry_words = len(retry_response.split())
        if retry_words > actual_words:
            response = retry_response
            actual_words = retry_words
            print(f"retry improved to {actual_words}w", file=sys.stderr)
        else:
            print(
                f"retry did not improve ({retry_words}w); keeping original",
                file=sys.stderr,
            )

    prompt_hash = hashlib.sha256(
        (system_prompt + str(calibration if calibration_path.exists() else {})).encode("utf-8")
    ).hexdigest()[:16]
    date_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    response = _merge_frontmatter(response, prompt_hash, model, date_utc)

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

    generate_soul(patterns_path, output_path, model=args.model, project_root=project_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
