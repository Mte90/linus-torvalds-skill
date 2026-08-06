# Pipeline Architecture

This document explains how the torvalds-skill pipeline transforms raw LKML
emails into a language-agnostic code-review skill.

## Overview

```
Emails (mbox)          →  Moves (JSONL)        →  Samples (JSON)      →  Skill (MD)
       classify              extract                 cluster               distill
  (rule-based)          (LLM per email)         (stratified)           (LLM once)
```

Four stages, each with a single responsibility:

| Stage | Input | Output | LLM? | Time |
|---|---|---|---|---|
| 1. Classify | `corpus.jsonl` (19,802 emails) | review/non-review flag | No (regex) | seconds |
| 2. Extract | review emails | `moves.jsonl` (24,790 moves) | Yes (1 call/email) | ~2 hours |
| 3. Cluster | `moves.jsonl` | `patterns.json` (325 samples) | No (stratified) | seconds |
| 4. Distill | `patterns.json` | `SKILL.md` (7,000+ words) | Yes (1 call) | ~2 min |

## Stage 1: Classify (`classify.py`)

**Purpose:** filter announcements from actual reviews.

Rule-based, no LLM. Three filters:

1. **Author filter** — only Linus Torvalds' messages (applied at fetch time).
2. **Git-pull filter** — regex `\[\s*GIT\s+PULL\s*\]` catches all variants.
3. **Zero-move filter** — subjects matching `PATCH`, `RFC`, or generic `Re:`
   are pre-filtered because they overwhelmingly produce zero review moves.

**Output:** each email in `corpus.jsonl` gets a `is_review` boolean.

**Skip list:** `data/skip_list.json` persists message IDs that produced zero
moves in previous runs. On `--resume`, these are skipped entirely, saving
thousands of API calls.

## Stage 2: Extract (`extract.py`)

**Purpose:** extract structured review moves from each email.

**One email = one LLM call.** Batching was tested and rejected:

| Batch size | Move loss | Verdict |
|---|---|---|
| 1 (sequential) | 0% | ✅ baseline |
| 2 | 18% | ❌ rejected |
| 3 | 38.5% | ❌ rejected |
| 5 | 46% | ❌ rejected |

The gpt-oss-120b model suffers attention drift after the second email in a
batch, silently dropping moves. Sequential extraction is mandatory.

**Concurrency:** 16 parallel workers, each making one sequential call. Jittered
retries (0.5-2s) and batched future submission prevent thundering-herd 429s.

**Checkpointing:** every 1,000 emails, progress is written to
`data/checkpoint.jsonl`. On crash:

```bash
python -m torvalds_skill extract --resume
```

resumes from the last checkpoint, skipping both done IDs and the skip list.

**Output:** `data/moves.jsonl` — one JSON object per email, containing:

```json
{
  "email_message_id": "<abc@example.com>",
  "moves": [
    {
      "category": "correctness",
      "severity": "reject",
      "trigger": "the patch silently corrupts state on 32-bit systems",
      "principle": "never introduce silent data corruption",
      "quote": "this is broken on 32-bit, period"
    }
  ]
}
```

## Stage 3: Cluster (`cluster.py`)

**Purpose:** reduce 24,790 moves to 325 representative samples for the LLM.

**Why not cluster semantically?** Lexical Jaccard was tried first — it
fragmented badly (7,434 clusters at threshold 0.35, mostly singletons).
Embedding-based cosine similarity was considered but adds an API dependency
for marginal gain. The distill LLM is better at semantic grouping than any
pre-clustering step.

**Stratified sampling** by `category × severity × year`:

- 13 categories × 25 samples = 325 total
- Within each stratum, samples are drawn evenly across years (2002-2026) to
  avoid recency bias
- This guarantees the LLM sees the full range of Torvalds' review style

**Output:** `data/patterns.json`:

```json
{
  "total_moves": 24790,
  "samples_by_category": {
    "correctness": [25 moves...],
    "performance": [25 moves...],
    ...
  }
}
```

## Stage 4: Distill (`distill.py`)

**Purpose:** one LLM call turns 325 samples into a SKILL.md.

**Prompt structure:**

1. **Four qualities of review rules** — every trigger must be one of:
   - `invariant-true`: condition that MUST always be true
   - `invariant-false`: condition that MUST NEVER be true
   - `precedence-rule`: explicit ordering when rules conflict
   - `general-guideline`: concrete, detectable pattern

2. **Precedence chain** — Correctness > Performance > Complexity > Style > API stability

3. **Concrete definitions** — bug, hack/workaround, patch, non-negotiable,
   recoverable error, API contract

4. **Language agnosticism** — forbidden-terms list removes C/kernel APIs
   (BUG_ON, READ_ONCE, copy_to_user, etc.); translation table maps remaining
   kernel-specific phrasing to neutral equivalents. Verbatim quotes are exempt.

5. **Forbidden-terms list** — enforced via post-generation grep. Only verbatim
   quotes may contain language-specific tokens.

**SSE streaming:** GLM5.2 is a reasoning model that spends minutes on internal
thought. Streaming keeps the connection alive (one token delta = one heartbeat).
Request timeout is 600s for GLM5.2, 120s for others.

**Output:** `linus-torvalds-skill/SKILL.md` with:
- YAML frontmatter (name, description, metadata)
- Reviewer Mindset
- Review Triggers (13 themes, each with typed rules)
- Precedence and Priorities (with example)
- Key Definitions
- Anti-Patterns
- Voice and Tone
- Common Review Scenarios

## Skill variants

Three variants generated from the same `patterns.json`:

| File | Model | Words | Notes |
|---|---|---|---|
| `SKILL.md` | gpt-oss-120b | ~7,100 | Default. Best balance. |
| `SKILL-GLM.md` | glm5.2 | ~11,700 | Reasoning model. Most thorough. Needs streaming + 600s timeout. |
| `SKILL-Mistral.md` | mistral-small-4-119b | ~5,400 | Fastest. May skip sections. |

```bash
# Generate a variant
python -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/SKILL-GLM.md
```

## Soul generation (`soul.py`)

A **soul document** defines the AI's persona, values, and voice — not its rules.
The soul generator uses the same `patterns.json` but a different system prompt
focused on identity, decision hierarchy, and communication style.

```bash
python -m torvalds_skill soul
```

Output: `soul/soul.md` — includes a Voice and Tone section that replicates
Torvalds' actual tone, including profanity when warranted.

## Verification (`verify_skill.py`)

Checks:
- File non-empty
- Word count in range (1,500-15,000)
- Required sections present
- Real quotes (20+ char quoted strings)
- No placeholder/TODO/stub text
- Category coverage (13/13)
- Severity levels (4/4)

```bash
python scripts/verify_skill.py linus-torvalds-skill/SKILL.md
```

## Data flow

```
data/lkml.mbox          192 MB, 31,397 emails (NNTP fetch)
    ↓ convert
data/corpus.jsonl        61 MB, 19,802 review emails (after classify)
    ↓ extract
data/moves.jsonl          ~8 MB, 24,790 review moves
    ↓ cluster
data/patterns.json       ~1 MB, 325 stratified samples
    ↓ distill
linus-torvalds-skill/SKILL.md    ~50 KB, 7,000+ words
linus-torvalds-skill/SKILL-GLM.md    ~67 KB
linus-torvalds-skill/SKILL-Mistral.md    ~35 KB
    ↓ soul
soul/soul.md             ~5 KB, 1,000 words
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `LLM_HOST` | `https://api.regolo.ai/v1` | LLM API endpoint |
| `LLM_MODEL` | `gpt-oss-120b` | Default model |
| `LLM_API_KEY` | (required) | API key |
| `LLM_MAX_RETRIES` | `5` | Retry count on 429/5xx |

CLI flags override env vars:

```bash
python -m torvalds_skill distill --model glm5.2 --out custom.md
python -m torvalds_skill soul --model mistral-small-4-119b --out soul/soul-mistral.md
```

## Resume and recovery

| Stage | Resume | Command |
|---|---|---|
| Extract | Yes | `python -m torvalds_skill extract --resume` |
| Cluster | No (idempotent) | re-run `python -m torvalds_skill cluster` |
| Distill | No (one call) | re-run `python -m torvalds_skill distill` |

Extract resume skips:
1. Message IDs in `data/checkpoint.jsonl` (already processed)
2. Message IDs in `data/skip_list.json` (produced zero moves)
