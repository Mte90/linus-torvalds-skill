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

**Soul file** (`soul/soul.md`) — the *persona*: identity, values, voice. **Includes profanity** — replicates Torvalds' actual tone, swearing only when a defect is dangerous or feedback is ignored.

All skills and the soul were generated with [regolo.ai](https://regolo.ai) using gpt-oss-120b (default), glm5.2, and mistral-small-4-119b.

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

## Usage

```bash
# Run the full pipeline
python3 -m torvalds_skill run --sample 2000 --workers 16

# Run individual stages
python3 -m torvalds_skill classify       # rule-based filter
python3 -m torvalds_skill extract --resume --workers 16   # LLM extraction
python3 -m torvalds_skill cluster        # stratified sampling
python3 -m torvalds_skill distill       # generate SKILL.md
python3 -m torvalds_skill soul          # generate soul.md

# Generate a variant skill with a different model
python3 -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/SKILL-GLM.md

# Verify quality
python3 scripts/verify_skill.py
```

### Resume after a crash

```bash
python3 -m torvalds_skill extract --resume --workers 16
```

Extraction checkpoints every 1,000 emails and skips zero-move message IDs from `data/skip_list.json`.

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

## Documentation

| Document | Purpose |
|---|---|
| [`docs/pipeline.md`](docs/pipeline.md) | Full pipeline architecture, data flow, stage details |
| [`soul/README.md`](soul/README.md) | What a soul document is and how it differs from a skill |

## Project layout

```
torvalds-skill/
├── linus-torvalds-skill/    # Skill files (tracked)
│   ├── SKILL.md             # gpt-oss-120b (default)
│   ├── SKILL-GLM.md         # glm5.2
│   └── SKILL-Mistral.md     # mistral-small-4-119b
├── soul/                    # Soul document (tracked)
│   ├── soul.md              # AI persona with Torvalds' tone
│   └── README.md
├── docs/                    # Documentation
│   └── pipeline.md         # Pipeline architecture
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
