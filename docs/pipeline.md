# Pipeline Architecture

This document explains how the torvalds-skill pipeline transforms raw LKML
emails into a language-agnostic code-review skill.

## Overview

```
Emails (mbox)          →  Moves (JSONL)        →  Samples (JSON)      →  Skill (MD)
       classify              extract                 cluster               distill
  (rule-based)          (LLM per email)         (stratified)           (LLM once)
                                                                          ↑
                                              data/calibration.json ───┘
                                                (calibrate, rule-based)
```

Five stages, each with a single responsibility:

| Stage | Input | Output | LLM? | Time |
|---|---|---|---|---|
| 1. Classify | `corpus.jsonl` (30,033 emails) | review/non-review flag | No (regex) | seconds |
| 2. Extract | review emails | `moves.jsonl` (38,293 moves) | Yes (1 call/email) | ~2 hours |
| 3. Cluster | `moves.jsonl` | `patterns.json` (350 samples) | No (stratified) | seconds |
| 3b. Calibrate | `moves.jsonl` | `calibration.json` (severity stats) | No (rule-based) | seconds |
| 4. Distill | `patterns.json` + `calibration.json` | `SKILL.md` (5,000-9,000 words depending on model) | Yes (1 call) | ~2 min |

## Usage

```bash
# Run the full pipeline
python3 -m torvalds_skill run --sample 2000 --workers 16

# Run individual stages
python3 -m torvalds_skill classify       # rule-based filter
python3 -m torvalds_skill extract --resume --workers 16   # LLM extraction
python3 -m torvalds_skill cluster        # stratified sampling
python3 scripts/calibrate.py             # severity calibration stats
python3 -m torvalds_skill distill       # generate SKILL.md (loads calibration.json)
python3 -m torvalds_skill soul          # generate soul.md

# Generate a variant skill with a different model
python3 -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/SKILL-GLM.md
python3 -m torvalds_skill distill --model mistral-small-4-119b --out linus-torvalds-skill/SKILL-Mistral.md

# Generate a variant soul with a different model
python3 -m torvalds_skill soul --model glm5.2 --out soul/soul-glm.md
python3 -m torvalds_skill soul --model mistral-small-4-119b --out soul/soul-mistral.md

# Verify quality
python3 scripts/verify_skill.py
```

### Resume after a crash

```bash
python3 -m torvalds_skill extract --resume --workers 16
```

Extraction checkpoints every 1,000 emails and skips zero-move message IDs from `data/skip_list.json`.

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
retries (0.5-2s) and batched future submission prevent thundering-herd 429s. Uses `concurrent.futures.ThreadPoolExecutor` for parallel extraction.

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

**Purpose:** reduce 38,293 moves to 350 representative samples for the LLM.

**Why not cluster semantically?** Lexical Jaccard was tried first — it
fragmented badly (7,434 clusters at threshold 0.35, mostly singletons).
Embedding-based cosine similarity was considered but adds an API dependency
for marginal gain. The distill LLM is better at semantic grouping than any
pre-clustering step.

**Stratified sampling** by `category × severity × year`:

- 13 categories × ~25 samples = 350 total (297 email + 53 interview)
- Within each stratum, samples are drawn evenly across years (2002-2026) to
  avoid recency bias
- This guarantees the LLM sees the full range of Torvalds' review style

**Output:** `data/patterns.json` — a list of 350 entries (297 from emails, 53 from interviews):

```json
[
  {
    "category": "correctness",
    "severity": "reject",
    "trigger": "...",
    "principle": "...",
    "quote": "...",
    "source": "email"
  },
  ...
]
```

## Stage 3b: Calibrate (`scripts/calibrate.py`)

**Purpose:** compute data-driven severity statistics from the full moves corpus.

Rule-based, no LLM. Reads `data/moves.jsonl` and produces
`data/calibration.json` containing:

- **P(severity | category)** — probability of each severity level given a
  category. Key findings from 38,293 moves:
  - Security: 59% rejected (highest reject rate)
  - Style: 36% nitpicked, only 13% rejected
  - Error-handling: 58% request-changes
- **Category distribution** — move counts per category
- **Temporal trends** — severity distribution over time (2002-2026)

**Output:** `data/calibration.json`, loaded by `distill.py` and injected into
the LLM prompt as "Severity Calibration" and "Severity Decision Tree" sections.

```bash
python3 scripts/calibrate.py
```

## Interview pipeline

Interview transcripts (TED talks, conference Q&As, magazine interviews) are processed through the same stages as emails:

1. **Fetch** — `interviews` command downloads transcripts from configured URLs in `data/interview_sources.json` (67 sources)
2. **Classify** — `classify-interviews` filters transcripts by relevance
3. **Extract** — `extract-interviews` extracts review moves via LLM (one call per transcript)
4. **Cluster** — `cluster-interviews` merges interview moves with email moves in `patterns.json`
5. **Calibrate** — `calibrate-interviews` merges interview severity stats into `calibration.json`

```bash
python3 -m torvalds_skill interviews              # fetch transcripts
python3 -m torvalds_skill interviews-pipeline      # full pipeline
```

Interview-derived moves (53) are merged with email moves (38,293) in `patterns.json` (350 samples: 297 email + 53 interview). Both skill and soul generation consume the merged patterns.

## Stage 4: Distill (`distill.py`)

**Purpose:** one LLM call turns 350 samples + calibration data into a SKILL.md.

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

6. **Severity calibration** — `calibration.json` is loaded and formatted into
   "Severity Calibration" and "Severity Decision Tree" sections appended to the
   prompt. This gives the LLM corpus-derived statistics so generated reviews
   match Linus' actual severity distribution.

**SSE streaming:** GLM5.2 is a reasoning model that spends minutes on internal
thought. Streaming keeps the connection alive (one token delta = one heartbeat).
Request timeout is 600s for GLM5.2, 120s for others. GLM5.2 also requires
`max_tokens` ≤ 16000.

**Output:** `linus-torvalds-skill/SKILL.md` with:
- YAML frontmatter (name, description, metadata)
- Reviewer Mindset
- Review Triggers (13 themes, each with typed rules)
- Precedence and Priorities (with example)
- Key Definitions
- Voice and Tone
- Severity Calibration
- Severity Decision Tree
- Quick Reference Checklist

## Skill variants

Three variants generated from the same `patterns.json` + `calibration.json`:

| File | Model | Words | Notes |
|---|---|---|---|
| `SKILL.md` | gpt-oss-120b | ~7,474 | Default. Best balance. |
| `SKILL-GLM.md` | glm5.2 | ~10,103 | Reasoning model. Most thorough. Needs streaming + 600s timeout + max_tokens ≤ 16000. |
| `SKILL-Mistral.md` | mistral-small-4-119b | ~7,853 | Fastest. |

```bash
# Generate a variant
python -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/SKILL-GLM.md
```

## Soul generation (`soul.py`)

A **soul document** defines the AI's persona, values, and voice — not its rules.
The soul generator uses the same `patterns.json` but a different system prompt
focused on identity, decision hierarchy, and communication style.

Three variants generated from the same `patterns.json`:

| File | Model | Words | Notes |
|---|---|---|---|
| `soul.md` | gpt-oss-120b | ~1,440 | Default. |
| `soul-glm.md` | glm5.2 | ~4,128 | Reasoning model. Needs streaming + 600s timeout. |
| `soul-mistral.md` | mistral-small-4-119b | ~1,970 | Most verbose. |

```bash
python -m torvalds_skill soul
python -m torvalds_skill soul --model glm5.2 --out soul/soul-glm.md
python -m torvalds_skill soul --model mistral-small-4-119b --out soul/soul-mistral.md
```

Output: `soul/soul.md` — includes Identity, Operating Principles, Decision Patterns, Review Workflow, Communication Style, Emergent Hierarchy, Interlocutor Model, Escalation Rules, Error Gravity, Anti-Soul, Voices, and Insult Vocabulary sections.

## Verification (`verify_skill.py`)

Checks:
- File non-empty
- Word count in range (1,500-10,000)
- Required sections present (Reviewer Mindset, Review Triggers, Precedence and
  Priorities, Key Definitions, Voice and Tone, Severity Calibration,
  Severity Decision Tree, Quick Reference Checklist)
- Real quotes (20+ char quoted strings)
- No placeholder/TODO/stub text
- No forbidden C/kernel terms outside quotes
- Category coverage (10/13)
- Severity levels (4/4)

```bash
python scripts/verify_skill.py linus-torvalds-skill/SKILL.md
```

## Validation (`validate.py`)

Validates data integrity at each pipeline stage:

```bash
python3 -m torvalds_skill validate
```

Checks:
- `moves.jsonl` — schema conformance (required fields, valid categories, valid severities)
- `patterns.json` — sample count, category coverage
- `calibration.json` — category statistics present
- `skip_list.json` — format validity

## Data flow

```
data/lkml.mbox          192 MB, 31,397 emails (NNTP fetch)
    ↓ convert
data/corpus.jsonl        30,033 review emails (after classify)
    ↓ extract
data/moves.jsonl          ~12 MB, 30,033 emails, 38,293 review moves
    ↓ cluster                        ↓ calibrate
data/patterns.json       350 samples (297 email + 53 interview)    data/calibration.json
    ↓ distill ←──────────────────────┘
linus-torvalds-skill/SKILL.md         ~37 KB, 7,474 words
linus-torvalds-skill/SKILL-GLM.md    ~57 KB, 10,103 words
linus-torvalds-skill/SKILL-Mistral.md ~36 KB, 7,853 words
    ↓ soul
soul/soul.md             ~8 KB, 1,440 words
soul/soul-glm.md         ~23 KB, 4,128 words
soul/soul-mistral.md     ~11 KB, 1,970 words
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
| Interview extract | Yes | `python -m torvalds_skill extract-interviews --resume` |
| Cluster | No (idempotent) | re-run `python -m torvalds_skill cluster` |
| Calibrate | No (idempotent) | re-run `python3 scripts/calibrate.py` |
| Distill | No (one call) | re-run `python -m torvalds_skill distill` |

Extract resume skips:
1. Message IDs in `data/checkpoint.jsonl` (already processed)
2. Message IDs in `data/skip_list.json` (produced zero moves)
