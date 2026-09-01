# Project Architecture

This document describes the technical architecture, data flow, and runtime constraints of the Torvalds Skill project.

## Pipeline Architecture

The distillation pipeline consists of five stages, run in order:

1. **Classify** (`classify.py`) — rule-based, no LLM. Filters reviews from announcements, pre-filters git-pull/patch/RFC emails.
2. **Extract** (`extract.py`) — LLM per email (gpt-oss-120b). Extracts structured review moves. One email at a time (batching causes 46% move loss).
3. **Cluster** (`cluster.py`) — semantic similarity clustering, stratified sampling by category+severity+date. 25 samples/category = 325 total.
4. **Calibrate** (`scripts/calibrate_interviews.py`) — severity calibration from corpus stats.
5. **Distill** (`distill.py`) — single LLM call, produces `SKILL.md`.

## Review Pipeline

The review pipeline (`report/run_review.py`) generates code reviews of SmallChat using each model with and without the skill to measure impact.

- **With-skill review**: model reviews SmallChat source files using the skill as a system prompt.
- **Baseline review**: model reviews without the skill (measures raw model capability).
- **Comparison** (`report/build_comparison.py`): parses all reviews, builds a consensus matrix, and computes skill-vs-baseline metrics.

### Chunked Mode
GLM5.2 times out on large prompts. Set `CHUNKED_MODELS="glm5.2"` to split the review into one call per source file (5 calls) plus a merge step, instead of a single call.

```bash
CHUNKED_MODELS="glm5.2" python3 report/run_review.py --force
```

### Soul Persona in Reviews
The soul file (`soul/*.md`) is **NOT** part of the review pipeline. It was removed because it pushed GLM5.2 over its context limit. Reviews use the skill file only.

## Runtime Constraints

### Model Token Limits

| Model | Max tokens |
|-------|-----------|
| glm5.2 | 200K |
| gpt-oss-120b | 120K |
| mistral-small-4-119b | 120K |

### GLM5.2 Specifics
- `max_tokens` ≤ 16000 for skill/soul generation (model supports 200K but generating that much times out).
- `timeout` ≥ 600 seconds (reasoning model, slow).
- Use `--single-call` flag on `distill` (bypasses per-category distillation, 1 LLM call instead of 15).
- Typical generation time: 10-15 minutes for skill, 10-15 minutes for soul.
- Review pipeline: use `CHUNKED_MODELS="glm5.2"` to chunk the review by source file.

### API Configuration
- **Host**: configurable via `LLM_HOST` or `OPENAI_BASE_URL` (default: `api.regolo.ai`)
- **Default model**: `gpt-oss-120b` (override via `LLM_MODEL`)
- **API key**: set via `REGOLO_API_KEY`, `OPENAI_API_KEY`, or `LLM_API_KEY` in `.env` (see `.env.example`)

## Data Directory

The `data/` directory is gitignored (contains ~192MB mbox, 38K moves, patterns, and calibration). Pre-built data is available on the repository's Releases page.

### Key Files
- `data/lkml.mbox` — 31,397 Torvalds emails (192MB)
- `data/moves.jsonl` — 38,293 extracted review moves
- `data/patterns.json` — 325 sampled patterns (cluster output)
- `data/calibration.json` — severity calibration stats
- `data/skip_list.json` — emails that returned 0 moves (skip on re-run)
- `data/checkpoint.jsonl` — extraction crash-recovery checkpoint
