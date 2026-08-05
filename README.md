# Torvalds Skill

Distills Linus Torvalds' code-review methodology from his LKML emails into a reusable, language-agnostic skill (**No swear words included**).  
It is built from **38,293 real review moves** extracted from 19,802 of his emails (2003–2026) on the Linux kernel mailing list.  

This repository provides 3 different skill generated with different models using the same prompt and corpus:

* [linus-torvalds-skill/SKILL.md](linus-torvalds-skill/SKILL.md) - Generated with [regolo.ai](https://regolo.ai) and GPT-OSS-120b
* [linus-torvalds-skill/SKILL-GLM.md](linus-torvalds-skill/SKILL-GLM.md) - Generated with [regolo.ai](https://regolo.ai) and GLM 5.2
* [linus-torvalds-skill/SKILL-Mistral.md](linus-torvalds-skill/SKILL-Mistral.md) - Generated with [regolo.ai](https://regolo.ai) and Mistral-Small-4-119b

## Distillation Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Acquisition                     │────▶│          Classification            │      ────▶│      Extraction        │
│  (NNTP gmane)               │     │         (rule-based)      │                   │     (LLM per email)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                                                      │
┌─────────────────┐     ┌─────────────────┐                 │
│  Verification                    │◀────│  Distillation              │◀────────────┘
│  (quality stats)                 │     │  (LLM synthesis)  │
└─────────────────┘     └─────────────────┘
                                              │
                                              ▼
                        ┌──────────────────────┐
                        │  linus-torvalds-skill           │
                        │  /SKILL.md                     │
                        └──────────────────────┘
```

### Pipeline stages

1. **Acquisition** — `scripts/fetch_emails.py`
   - NNTP source: `news.gmane.io:119`, group `gmane.linux.kernel`
   - Filters for Torvalds' messages only
   - Output: `data/lkml.mbox` (31,397 emails, ~192 MB, mboxrd format)

2. **Normalization** — `scripts/mbox_to_jsonl.py`
   - Converts mbox → JSONL for fast streaming access
   - Output: `data/corpus.jsonl` (~61 MB)

3. **Classification** — `src/torvalds_skill/classify.py`
   - Rule-based, no LLM
   - Filters review emails from announcements/pull requests
   - Patterns filtered: `[GIT PULL]`, `[RFC]`, `[PATCH]`, sign-offs, short bodies
   - Output: `data/reviews.jsonl` (~30K review emails)

4. **Extraction** — `src/torvalds_skill/extract.py`
   - One LLM call per email (sequential — batching tested and rejected: 46% move loss)
   - LLM: **gpt-oss-120b** via **regolo.ai** API
   - Extracts structured review moves: `trigger`, `principle`, `response`, `severity`, `category`
   - Persistent skip-list for zero-move emails (saves API calls on future runs)
   - Checkpointing every 1,000 emails for crash recovery
   - Output: `data/moves.jsonl`

5. **Clustering** — `src/torvalds_skill/cluster.py`
   - Stratified sampling by category + severity + date
   - ~25 samples per category (325 total across 13 categories)
   - Semantic grouping is delegated to the distill LLM
   - Output: `data/patterns.json`

6. **Distillation** — `src/torvalds_skill/distill.py`
   - Single LLM call synthesizes the skill from sampled moves
   - Produces language-agnostic guidance with verbatim quotes
   - LLM: **gpt-oss-120b** via **regolo.ai** API (`api.regolo.ai`)
   - Output: `linus-torvalds-skill/SKILL.md` (SKILL.md format compliant)

7. **Verification** — `scripts/verify_skill.py`
   - Quality metrics: coverage, coherence, uniqueness, severity calibration
   - Validates skill completeness

## Model Variants

The distillation step can use different LLMs on **regolo.ai** to produce variant skills from the same extracted moves.  
All variants share identical input data (`data/patterns.json`); only the synthesizing model differs.

| File                                  | Model                  | Words  | Notes                                      |
| ------------------------------------- | ---------------------- | ------ | ------------------------------------------ |
| `linus-torvalds-skill/SKILL.md`           | gpt-oss-120b (default) | ~7170  | Default; fast (~30s)                        |
| `linus-torvalds-skill/skill-glm.md`       | glm5.2                 | ~10500 | Reasoning model; slow (~10–15 min, streaming) |
| `linus-torvalds-skill/skill-mistral.md`   | mistral-small-4-119b   | ~9400  | Fast (~30s)                                 |

Generate a variant:

```bash
python -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/skill-glm.md
python -m torvalds_skill distill --model mistral-small-4-119b --out linus-torvalds-skill/skill-mistral.md
```

## Setup

```bash
# Install dependencies (requires uv)
uv sync

# Configure API credentials
cp .env.example .env
# Edit .env:
#   LLM_HOST=api.regolo.ai
#   LLM_MODEL=gpt-oss-120b
#   LLM_API_KEY=sk-...
```

## Usage

### Run the full pipeline

```bash
python3 -m torvalds_skill run --sample 2000 --workers 16
```

### Run individual stages

```bash
# 1. Fetch emails from NNTP (one-time, ~30 min)
python3 scripts/fetch_emails.py

# 2. Convert mbox → JSONL
python3 scripts/mbox_to_jsonl.py

# 3. Classify reviews (rule-based, no LLM)
python3 -m torvalds_skill classify

# 4. Extract review moves (LLM, can take hours)
python3 -m torvalds_skill extract --resume --workers 16

# 5. Cluster moves into stratified samples
python3 -m torvalds_skill cluster

# 6. Distill into the final skill (default: gpt-oss-120b → SKILL.md)
python3 -m torvalds_skill distill

#    Generate a variant with a different model:
python3 -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/skill-glm.md
python3 -m torvalds_skill distill --model mistral-small-4-119b --out linus-torvalds-skill/skill-mistral.md

# 7. Verify quality
python3 scripts/verify_skill.py
```

### Resume after a crash

```bash
# Extraction checkpoints every 1,000 emails and reads data/skip_list.json
python3 -m torvalds_skill extract --resume --workers 16
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_HOST` | `api.regolo.ai` | LLM API endpoint |
| `LLM_MODEL` | `gpt-oss-120b` | Model used for extraction and distillation |
| `LLM_API_KEY` | — | API key (required) |

## Performance

| Metric | Value |
|--------|-------|
| Extraction rate | ~2.7 emails/s (16 workers) |
| Full corpus (19,802 emails) | ~127 min, 24,790 moves, 0 errors |
| Skip-list savings | ~4,670 emails skipped on reruns |

## Data files

All files under `data/` are regenerable and excluded from version control. The only tracked data file is `data/skip_list.json` — a curated list of message IDs that produce zero moves, which saves API calls on future runs.

| File | Size | Description |
|------|------|-------------|
| `data/lkml.mbox` | 192 MB | Raw emails (re-downloadable via NNTP) |
| `data/corpus.jsonl` | 61 MB | Parsed emails (regenerable from mbox) |
| `data/reviews.jsonl` | ~40 MB | Review-only emails (regenerable) |
| `data/moves.jsonl` | ~23 MB | Extracted review moves (regenerable via LLM) |
| `data/patterns.json` | ~116 KB | Stratified samples (regenerable) |
| `data/skip_list.json` | 412 KB | Zero-move email IDs (**tracked** — curated) |
| `data/manifest.json` | ~1 KB | Provenance metadata |
| `data/checkpoint.jsonl` | varies | Crash-recovery checkpoint |

## Project layout

```
torvalds-skill/
├── linus-torvalds-skill/        # Distributable artifact (tracked)
│   ├── SKILL.md                 # Default skill (gpt-oss-120b, SKILL.md format)
│   ├── SKILL-GLM.md             # Variant: glm5.2
│   └── SKILL-Mistral.md         # Variant: mistral-small-4-119b
├── src/torvalds_skill/          # Pipeline source
│   ├── classify.py              # Rule-based review filtering
│   ├── extract.py               # LLM move extraction
│   ├── cluster.py               # Stratified sampling
│   ├── distill.py               # LLM skill synthesis
│   ├── cli.py                   # Pipeline orchestration
│   ├── config.py                # API configuration
│   └── models.py                # Data models
├── scripts/                     # Standalone utilities
│   ├── fetch_emails.py          # NNTP scraper
│   ├── mbox_to_jsonl.py         # Format converter
│   ├── verify_mbox.py           # Corpus validator
│   ├── write_manifest.py        # Provenance writer
│   └── verify_skill.py          # Skill quality checker
├── tests/                       # Test suite (34 passing)
├── data/                        # Regenerable data (gitignored)
└── pyproject.toml
```

## Troubleshooting

### Zero moves extracted
- Some emails are genuinely not reviews (discussions, RFC debates)
- The `skip-list.json` persists these message IDs automatically
- Check pre-filter patterns in `classify.py`

### Resume fails
- Verify `data/moves.jsonl` is valid JSONL
- Run `python3 scripts/verify_mbox.py` to validate the corpus
- Check `data/checkpoint.jsonl` for the last saved position

## License

Everything in this repository — source code, pipeline scripts, the distilled skill, and documentation — is released to the **public domain** under [CC0 1.0](LICENSE). You may copy, modify, distribute, and use any part of it for any purpose, including commercial, without attribution.
