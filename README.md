# Torvalds Skill

Distills Linus Torvalds' code-review methodology from his LKML emails into a reusable, language-agnostic skill.

Built from **38,303 real review moves** extracted from 31,397 of his emails (2002–2026) on the Linux kernel mailing list, plus 67 interview transcripts.
## Quick Start

### Use the skill in your AI coding assistant

1. **Pick a skill variant** from `linus-torvalds-skill/`:
   - `SKILL.md` — gpt-oss-120b (balanced, recommended)
   - `SKILL-GLM.md` — glm5.2 (most detailed, reasoning model)
   - `SKILL-Mistral.md` — mistral (concise)

2. **Add it to your system prompt** or skill registry:
   - Copy the contents of `SKILL.md` into your AI assistant's system prompt, OR
   - Register the skill file path in your tool's skill configuration

3. **What you get**: The skill instructs the AI to review code with Linus' principles:
   - Correctness > Performance > Complexity > Style (precedence hierarchy)
   - Language-agnostic triggers (works for any language, not just C/kernel)
   - Severity calibration from 38,000+ real review moves
   - Concrete definitions for "bug", "hack", "patch", "API contract"

### Use the soul persona

1. **Pick a soul variant** from `soul/`:
   - `soul.md` — gpt-oss-120b
   - `soul-glm.md` — glm5.2 (most detailed)
   - `soul-mistral.md` — mistral

2. **Use it as a system prompt** for Linus-style code review persona.

## Model Comparison

Three model variants generate the skill and soul files. Each has different characteristics based on its training and reasoning style.

| Model | Skill words | Soul words | Strictness | Verbosity | Tonal aggression | Best for |
|---|---|---|---|---|---|---|
| gpt-oss-120b | 5,661 | 1,215 | Medium | Medium | Medium | Production code review (recommended default) |
| glm5.2 | 8,561 | 3,494 | High | High | High | Detailed reasoning, complex architecture reviews |
| mistral-small-4-119b | 5,505 | 1,705 | Medium | Medium | Medium | Quick checks, fast iteration cycles |

**Tradeoffs:**

- **gpt-oss-120b** (balanced, recommended default): Provides the best balance between thoroughness and speed. The skill captures all 13 review categories with clear triggers and the soul replicates Torvalds' tone without excessive aggression. Use this for most production code reviews.

- **glm5.2** (most detailed, reasoning model): Generates the most comprehensive skill with deeper explanations for each trigger and more nuanced escalation rules. The soul file includes detailed interlocutor modeling and confidence backing. Best for complex architecture reviews where reasoning matters more than speed. Longer generation time due to the larger output.

- **mistral-small-4-119b** (concise, fast): Produces compact skill files with YAML formatting for easier parsing. The soul is direct and efficient. Ideal for quick checks, CI integration, or when you need fast feedback without sacrificing accuracy.

All three models reach the same verdicts on critical issues (correctness bugs, API breaks, memory safety). The differences are in depth of explanation and generation speed, not fundamental review quality.

## What you get

**Skill files** (`linus-torvalds-skill/`) — the *rules*: triggers, precedence, definitions. Clean, no profanity.

| File | Model | Words | Notes |
|---|---|---|---|
| `SKILL.md` | gpt-oss-120b | ~5,660 | Default. Best balance. |
| `SKILL-GLM.md` | glm5.2 | ~8,560 | Reasoning model. Most thorough. |
| `SKILL-Mistral.md` | mistral-small-4-119b | ~5,510 | Fastest. |

**Soul files** (`soul/`) — the *persona*: identity, values, voice. **Includes profanity** — replicates Torvalds' actual tone, swearing only when a defect is dangerous or feedback is ignored.

| File | Model | Words |
|---|---|---|
| `soul.md` | gpt-oss-120b | ~1,215 |
| `soul-glm.md` | glm5.2 | ~3,495 |
| `soul-mistral.md` | mistral-small-4-119b | ~1,705 |

All skills and souls were generated with [regolo.ai](https://regolo.ai) using gpt-oss-120b (default), glm5.2, and mistral-small-4-119b.

## How it works

```
Emails → Classify → Extract → Cluster ↘
(mbox)  (regex)    (LLM)     (sample)  Distill → Skill
                    ↓         ↗    ↑       (SKILL.md)
              moves.jsonl   patterns.json
                             ↓
Interviews → Classify → Extract → Cluster ↗
(sources)  (regex)    (LLM)     (merge)
                              ↓
                    Calibrate → calibration.json
```
Interviews feed both skill and soul generation. Full architecture in docs/pipeline.md.

Five stages, each with a single responsibility. Full architecture in [`docs/pipeline.md`](docs/pipeline.md).

Validate data integrity at any stage:
```bash
python3 -m torvalds_skill validate
```

## Setup

```bash
uv sync
cp .env.example .env
# Edit .env: LLM_HOST, LLM_MODEL, LLM_API_KEY
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_HOST` | `https://api.regolo.ai/v1` | LLM API endpoint |
| `LLM_MODEL` | `gpt-oss-120b` | Model for extraction and distillation |
| `LLM_API_KEY` | — | API key (required) |

CLI flags override env vars: `--model`, `--out`.

## Performance

| Metric | Value |
|---|---|
| Total emails fetched | 31,397 (2002–2026) |
| Emails processed | 30,033 (after classification) |
| Review moves extracted | 38,293 from emails + 10 from interviews |
| Interview sources | 67 configured, 80 transcripts on disk |
| Skip-list savings | zero-move emails skipped on reruns |

## Validation report

The skill was tested on [antirez/smallchat](https://github.com/antirez/smallchat) (706 LOC, C) — a minimal TCP chat server. Three independent reviews were generated, one per skill variant, on the same codebase.

| Review | Model | Words | Findings |
|---|---|---|---|
| [`review-gpt-oss-120b.md`](report/review-gpt-oss-120b.md) | gpt-oss-120b | ~940 | 18 (4 CRIT) |
| [`review-glm5.2.md`](report/review-glm5.2.md) | glm5.2 | ~2,350 | 12 (1 CRIT) |
| [`review-mistral.md`](report/review-mistral.md) | mistral-small-4-119b | ~1,990 | 15 (1 CRIT) |
| [`comparison.md`](report/comparison.md) | — | ~2,000 | synthesis |

All three models reached the same verdict (FAIL). glm5.2 found the most consequential bug (`acceptClient(-1)` memory corruption) that no other model caught. Mistral recovered from a previous false-APPROVE after the calibration data was made language-agnostic. Replicate with `bash report/run_review.sh`.

## Interview corpus

67 interview transcripts (TED talks, conference Q&As, magazine interviews) are fetched and processed through the same pipeline as emails: classify → extract → cluster → calibrate. Interview-derived moves are merged with email moves in `patterns.json` (325 samples: 315 email + 10 interview). Both skill and soul generation consume the merged patterns.

Fetch interviews:
```bash
python3 -m torvalds_skill interviews              # fetch transcripts
python3 -m torvalds_skill interviews-pipeline      # full interview pipeline
```

## Documentation

| Document | Purpose |
|---|---|
| [`docs/pipeline.md`](docs/pipeline.md) | Full pipeline architecture, data flow, stage details |
| [`soul/README.md`](soul/README.md) | What a soul document is and how to generate it |
| [`report/comparison.md`](report/comparison.md) | Three-model validation on antirez/smallchat |

## Project layout

```
torvalds-skill/
├── linus-torvalds-skill/    # Skill files (tracked)
│   ├── SKILL.md             # gpt-oss-120b (default)
│   ├── SKILL-GLM.md         # glm5.2
│   └── SKILL-Mistral.md     # mistral-small-4-119b
├── soul/                    # Soul files (tracked)
│   ├── soul.md              # gpt-oss-120b (default)
│   ├── soul-glm.md          # glm5.2
│   ├── soul-mistral.md      # mistral-small-4-119b
│   └── README.md
├── docs/                    # Documentation
│   └── pipeline.md          # Pipeline architecture
├── report/                  # Validation reviews + comparison
├── src/torvalds_skill/      # Pipeline source
│   ├── classify.py          # Stage 1: rule-based filter
│   ├── extract.py           # Stage 2: LLM extraction
│   ├── cluster.py            # Stage 3: stratified sampling
│   ├── distill.py           # Stage 4: LLM distillation
│   ├── soul.py              # Soul generation
│   ├── validate.py          # Data validation
│   └── cli.py               # CLI entry point
├── scripts/                 # Standalone utilities
│   ├── calibrate.py         # Severity calibration
│   └── verify_skill.py      # Skill file verifier
├── tests/                   # Test suite (34 passing)
├── data/                    # Regenerable data (gitignored)
│   ├── interview_sources.json  # 67 interview URLs
│   └── interviews/             # Fetched transcripts
└── pyproject.toml
```

## Data files

All files under `data/` are regenerable and excluded from version control, except `data/skip_list.json` — a curated list of message IDs that produce zero moves, saving API calls on future runs.

## License

Everything in this repository — source code, pipeline scripts, the distilled skill, the soul document, and documentation — is released to the **public domain** under [CC0 1.0](LICENSE).
