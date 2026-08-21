# AGENTS.md — Project Conventions

## Generated files are not hand-edited

All `.md` artifacts in this repository are produced by scripts. Do not edit them directly. Edit the script that generates them, then re-run the generator. This keeps the project replicable: anyone can regenerate every artifact from source.

### Generated artifacts and their generators

| Artifact | Generator | Regeneration command |
|----------|-----------|---------------------|
| `linus-torvalds-skill/SKILL.md` | `src/torvalds_skill/distill.py` | `python -m torvalds_skill distill --model gpt-oss-120b --out linus-torvalds-skill/SKILL.md` |
| `linus-torvalds-skill/SKILL-GLM.md` | `src/torvalds_skill/distill.py` | `python -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/SKILL-GLM.md --single-call` |
| `linus-torvalds-skill/SKILL-Mistral.md` | `src/torvalds_skill/distill.py` | `python -m torvalds_skill distill --model mistral-small-4-119b --out linus-torvalds-skill/SKILL-Mistral.md` |
| `soul/soul.md` | `src/torvalds_skill/soul.py` | `python -m torvalds_skill soul --model gpt-oss-120b --out soul/soul.md` |
| `soul/soul-glm.md` | `src/torvalds_skill/soul.py` | `python -m torvalds_skill soul --model glm5.2 --out soul/soul-glm.md` |
| `soul/soul-mistral.md` | `src/torvalds_skill/soul.py` | `python -m torvalds_skill soul --model mistral-small-4-119b --out soul/soul-mistral.md` |
| `report/review-*.md` | `report/run_review.sh` | `bash report/run_review.sh` |
| `report/comparison.md` | `report/build_comparison.py` | `python3 report/build_comparison.py` |
| `data/patterns.json` | `src/torvalds_skill/cluster.py` | `python -m torvalds_skill cluster` |
| `data/calibration.json` | `scripts/calibrate_interviews.py` | `python -m torvalds_skill calibrate-interviews` |

### Rule

When a generated file needs to change:
1. Identify the script that generates it (see table above).
2. Edit the script.
3. Re-run the generator.
4. Verify the output.

Never edit a generated `.md` file directly. Manual edits are overwritten on the next run and break replicability.

### Source files (hand-editable)

These are not generated — edit them directly:
- `src/torvalds_skill/*.py` — pipeline source code
- `scripts/*.py` — standalone scripts
- `report/run_review.sh` — review orchestration
- `report/build_comparison.py` — comparison generator
- `data/interviews/*.md` — interview transcripts (source data, not generated)
- `README.md`, `docs/*.md` — documentation
- `todo.md` — task tracking
- `CHANGELOG.md` — changelog

---

## Language-agnostic enforcement

Skills and souls must be language-agnostic. Torvalds reviews C kernel code, but the skill captures his METHOD, not his C knowledge.

- `src/torvalds_skill/distill.py` contains a forbidden-terms list and a translation table in the system prompt
- `sanitize_skill()` post-processor replaces C/kernel identifiers in unquoted text
- `scripts/verify_skill.py` validates generated skill files — run it after any skill regeneration
- Quotes (Torvalds' verbatim words) are exempt — they preserve C terms as evidence of voice
- Over-sanitization is also a bug: the translation table applies to trigger descriptions only, not to quotes or examples

## Runtime constraints

### Model token limits

| Model | Max tokens |
|-------|-----------|
| glm5.2 | 200K |
| gpt-oss-120b | 120K |
| mistral-small-4-119b | 120K |

### GLM5.2

- `max_tokens` ≤ 16000 for skill/soul generation (model supports 200K but generating that much times out)
- `timeout` ≥ 600 seconds (reasoning model, slow)
- Use `--single-call` flag on `distill` (bypasses per-category distillation, 1 LLM call instead of 15)
- Typical generation time: 10-15 minutes for skill, 10-15 minutes for soul
- Review pipeline: use `CHUNKED_MODELS="glm5.2"` to chunk the review by source file (5 calls instead of 1)

### API

- Host: `api.regolo.ai`
- Default model: `gpt-oss-120b`
- API key: `sk-1ZXgFKoLcq8oZfKozQIpew`

## Pipeline architecture

Five stages, run in order:

1. **Classify** (`classify.py`) — rule-based, no LLM. Filters reviews from announcements, pre-filters git-pull/patch/RFC emails.
2. **Extract** (`extract.py`) — LLM per email (gpt-oss-120b). Extracts structured review moves. One email at a time (batching causes 46% move loss).
3. **Cluster** (`cluster.py`) — semantic similarity clustering, stratified sampling by category+severity+date. 25 samples/category = 325 total.
4. **Calibrate** (`scripts/calibrate_interviews.py`) — severity calibration from corpus stats.
5. **Distill** (`distill.py`) — single LLM call, produces `SKILL.md`.

Full pipeline: `python -m torvalds_skill run --sample 2000 --workers 10`

Resume after crash: `python -m torvalds_skill extract --resume` (checkpoint every 1000 emails)

## Review pipeline

`report/run_review.sh` generates code reviews of SmallChat using each model with and without the skill.

- **With-skill review**: model reviews SmallChat source files using the skill as a system prompt
- **Baseline review**: model reviews without the skill (measures raw model capability)
- **Comparison** (`report/build_comparison.py`): parses all reviews, builds a consensus matrix, computes skill-vs-baseline metrics

### Chunked mode

GLM5.2 times out on large prompts. Set `CHUNKED_MODELS="glm5.2"` to split the review into one call per source file (5 calls) plus a merge step, instead of a single call.

```bash
CHUNKED_MODELS="glm5.2" bash report/run_review.sh --force
```

### Soul is not used in reviews

The soul file (`soul/*.md`) is NOT part of the review pipeline. It was removed because it pushed GLM5.2 over its context limit. Reviews use the skill file only.

## Verification commands

| Check | Command |
|-------|---------|
| Skill language-agnostic | `python3 scripts/verify_skill.py` |
| Comparison regenerates | `python3 report/build_comparison.py` |
| Review pipeline syntax | `bash -n report/run_review.sh` |
| Full review run | `CHUNKED_MODELS="glm5.2" bash report/run_review.sh --force` |
| Pipeline data valid | `python -m torvalds_skill validate` |

## Data directory

`data/` is gitignored (contains 192MB mbox, 38K moves, patterns, calibration). Download pre-built data from the repository's Releases page if you need to run the pipeline.

Key files:
- `data/lkml.mbox` — 31,397 Torvalds emails (192MB)
- `data/moves.jsonl` — 38,293 extracted review moves
- `data/patterns.json` — 325 sampled patterns (cluster output)
- `data/calibration.json` — severity calibration stats
- `data/skip_list.json` — emails that returned 0 moves (skip on re-run)
- `data/checkpoint.jsonl` — extraction crash-recovery checkpoint

## Git discipline

Local only. No `git push`, `git pull`, `git rebase`, or `git merge`. Humans push manually.

Commit messages: terse and factual. No references to internal task numbers, plan phases, or scaffolding.
