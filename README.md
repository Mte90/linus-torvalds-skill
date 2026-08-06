# Torvalds Skill

Distills Linus Torvalds' code-review methodology from his LKML emails into a reusable, language-agnostic skill.

Built from **38,293 real review moves** extracted from 19,802 of his emails (2003–2026) on the Linux kernel mailing list.

## What you get

**Skill files** (`linus-torvalds-skill/`) — the *rules*: triggers, precedence, definitions. Clean, no profanity.

| File | Model | Words | Notes |
|---|---|---|---|
| [`SKILL.md`](linus-torvalds-skill/SKILL.md) | gpt-oss-120b | ~7,100 | Default. Best balance. |
| [`SKILL-GLM.md`](linus-torvalds-skill/SKILL-GLM.md) | glm5.2 | ~11,700 | Reasoning model. Most thorough. |
| [`SKILL-Mistral.md`](linus-torvalds-skill/SKILL-Mistral.md) | mistral-small-4-119b | ~5,400 | Fastest. May skip sections. |

**Soul files** (`soul/`) — the *persona*: identity, values, voice. **Includes profanity** — replicates Torvalds' actual tone, swearing only when a defect is dangerous or feedback is ignored.

| File | Model | Words |
|---|---|---|
| [`soul.md`](soul/soul.md) | gpt-oss-120b | ~990 |
| [`soul-glm.md`](soul/soul-glm.md) | glm5.2 | ~1,650 |
| [`soul-mistral.md`](soul/soul-mistral.md) | mistral-small-4-119b | ~1,940 |

All skills and souls were generated with [regolo.ai](https://regolo.ai) using gpt-oss-120b (default), glm5.2, and mistral-small-4-119b.

## How it works

```
Emails → Classify → Extract → Cluster → Distill → Skill
(mbox)  (regex)    (LLM)     (sample)  (LLM)     (SKILL.md)
                                        └→ Soul   (soul.md)
```

Four stages, each with a single responsibility. Full architecture in [`docs/pipeline.md`](docs/pipeline.md).

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
| Extraction rate | ~2.7 emails/s (16 workers) |
| Full corpus (19,802 emails) | ~127 min, 24,790 moves, 0 errors |
| Skip-list savings | ~4,670 emails skipped on reruns |

## Validation report

The skill was tested on [antirez/smallchat](https://github.com/antirez/smallchat) (706 LOC, C) — a minimal TCP chat server. Three independent reviews were generated, one per skill variant, on the same codebase.

| Review | Model | Words | Findings |
|---|---|---|---|
| [`review-gpt-oss-120b.md`](report/review-gpt-oss-120b.md) | gpt-oss-120b | ~4,100 | 21 (2 CRIT) |
| [`review-glm5.2.md`](report/review-glm5.2.md) | glm5.2 | ~3,400 | 15 (2 CRIT) |
| [`review-mistral.md`](report/review-mistral.md) | mistral-small-4-119b | ~2,400 | 12 (3 CRIT) |
| [`comparison.md`](report/comparison.md) | — | ~2,100 | synthesis |

All three models reached the same verdict (does not pass) and converged on the same core defects. Only mistral caught the un-NUL-terminated nickname — a heap over-read on every connection. Replicate with `bash report/run_review.sh`.

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
│   └── pipeline.md         # Pipeline architecture
├── report/                  # Validation reviews + comparison
├── src/torvalds_skill/      # Pipeline source
├── scripts/                 # Standalone utilities
├── tests/                   # Test suite (34 passing)
├── data/                    # Regenerable data (gitignored, except skip_list.json)
└── pyproject.toml
```

## Data files

All files under `data/` are regenerable and excluded from version control, except `data/skip_list.json` — a curated list of 6,379 message IDs that produce zero moves, saving API calls on future runs.

## License

Everything in this repository — source code, pipeline scripts, the distilled skill, the soul document, and documentation — is released to the **public domain** under [CC0 1.0](LICENSE).
