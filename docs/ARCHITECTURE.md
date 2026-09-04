# Project Architecture

This document describes the technical architecture, data flow, and runtime constraints of the Torvalds Skill project.

## Pipeline Architecture

The distillation pipeline consists of five stages, run in order:

1. **Classify** (`classify.py`) — rule-based, no LLM. Filters reviews from announcements, pre-filters git-pull/patch/RFC emails.
2. **Extract** (`extract.py`) — LLM per email (gpt-oss-120b). Extracts structured review moves. One email at a time (batching causes 46% move loss).
3. **Cluster** (`cluster.py`) — semantic similarity clustering, stratified sampling by category+severity+date. 25 samples/category = 350 total (canonical count).
4. **Calibrate** (`scripts/calibrate_interviews.py`) — severity calibration from corpus stats.
5. **Distill** (`distill.py`) — two-stage (14 categories + synthesis) or single-call mode depending on model profile. Produces `SKILL.md`.

## Review Pipeline

The review pipeline (`report/run_review.py`) generates code reviews of SmallChat using each model with and without the skill to measure impact.

- **With-skill review**: model reviews SmallChat source files using the skill as a system prompt.
- **Baseline review**: model reviews without the skill (measures raw model capability).
- **Comparison** (`report/build_comparison.py`): parses all reviews, builds a consensus matrix, and computes skill-vs-baseline metrics.

### Auto-chunking

If a prompt exceeds the model's `profile.prompt_budget_chars`, the review automatically chunks by source file and merges results. This applies to ALL models, not just a configured list. See `src/torvalds_skill/profiles.py` for per-model budgets.

### Soul Persona in Reviews
The soul file (`soul/*.md`) is **NOT** part of the review pipeline. It was removed because it pushed GLM5.2 over its context limit. Reviews use the skill file only.

## Runtime Constraints

### Model Token Limits

| Model | Max tokens | Reasoning |
|-------|-----------|----------|
| glm5.2 | 16000 | Yes |
| gpt-oss-120b | 16000 | No |
| mistral-small-4-119b | 16000 | No |

Note: These values come from `src/torvalds_skill/profiles.py` (`ModelProfile.max_tokens`). The field is the effective budget used during generation (may be lower than the model's actual context limit to avoid timeouts); reasoning output and content share it.

### Reasoning Models

GLM5.2 is a reasoning model. It must keep its thinking phase (never disable it); its thinking and content share the profile `max_tokens` budget (see table above).

### API Configuration
- **Host**: configurable via `LLM_HOST` or `OPENAI_BASE_URL` (default: `api.regolo.ai`)
- **Default model**: `gpt-oss-120b` (override via `LLM_MODEL`)
- **API key**: set via `REGOLO_API_KEY`, `OPENAI_API_KEY`, or `LLM_API_KEY` in `.env` (see `.env.example`)

## Data Directory

The `data/` directory is gitignored (contains ~192MB mbox, 38K moves, patterns, and calibration). Pre-built data is available on the repository's Releases page.

### Key Files
- `data/lkml.mbox` — 31,397 Torvalds emails (192MB)
- `data/moves.jsonl` — 38,293 extracted review moves
- `data/patterns.json` — 350 sampled patterns (cluster output, canonical count)
- `data/calibration.json` — severity calibration stats
- `data/skip_list.json` — emails that returned 0 moves (skip on re-run)
- `data/checkpoint.jsonl` — extraction crash-recovery checkpoint
