# Torvalds Skill

Distills Linus Torvalds' code-review methodology from his LKML emails into a reusable, language-agnostic skill.

The final artifact is a single Markdown document — [`linus-torvalds-skill/SKILL.md`](linus-torvalds-skill/SKILL.md) — that captures *how* Torvalds reviews code: what he flags, why it matters, and how he reacts. It is built from **38,293 real review moves** extracted from 19,802 of his emails (2003–2026) on the Linux kernel mailing list.

## What you get

The skill is a decision engine, not a style guide. For each review trigger it gives you:

- **What to look for** — the concrete code smell
- **Principle** — why it matters
- **Severity** — reject / request-changes / nitpick / discussion / approve (calibrated to Torvalds' real distribution)
- **Real quote** — verbatim from LKML, so the voice is part of the method

It covers 13 categories: API-stability, correctness, performance, complexity, abstraction, style, process, concurrency, memory-safety, documentation, testing, error-handling, and other.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Acquisition    │────▶│  Classification │────▶│  Extraction     │
│  (NNTP gmane)   │     │  (rule-based)   │     │  (LLM per email)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
┌─────────────────┐     ┌─────────────────┐             │
│  Verification   │◀────│  Distillation   │◀────────────┘
│  (quality stats)│     │  (LLM synthesis)│
└─────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌──────────────────────┐
                        │  linus-torvalds-skill│
                        │  /SKILL.md           │
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
   - Output: `linus-torvalds-skill/SKILL.md` (SKILL.md format compliant)

7. **Verification** — `scripts/verify_skill.py`
   - Quality metrics: coverage, coherence, uniqueness, severity calibration
   - Validates skill completeness

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

# 6. Distill into the final skill
python3 -m torvalds_skill distill

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
│   └── SKILL.md                 # The final skill document (SKILL.md format)
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

### Extraction hangs
- Check API rate limits (429 errors in logs)
- Reduce workers: `python3 -m torvalds_skill extract --workers 8 --resume`
- Jitter and batched futures are enabled by default to prevent thundering-herd

### Zero moves extracted
- Some emails are genuinely not reviews (discussions, RFC debates)
- The skip-list persists these message IDs automatically
- Check pre-filter patterns in `classify.py`

### Resume fails
- Verify `data/moves.jsonl` is valid JSONL
- Run `python3 scripts/verify_mbox.py` to validate the corpus
- Check `data/checkpoint.jsonl` for the last saved position

## License

Everything in this repository — source code, pipeline scripts, the distilled skill, and documentation — is released to the **public domain** under [CC0 1.0](LICENSE). You may copy, modify, distribute, and use any part of it for any purpose, including commercial, without attribution.
