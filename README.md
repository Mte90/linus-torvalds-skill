# Torvalds Skill

Distills Linus Torvalds' code-review methodology from his LKML emails into a reusable, language-agnostic skill.

Built from **38,293 real review moves** extracted from 31,397 of his emails (2002–2026) on the Linux kernel mailing list, plus 67 interview transcripts.

## What the skill does

Without the skill, a model gives generic, often verbose feedback:
> ### CRITICAL Out‑of‑bounds client array indexing
> - **Type:** bug
> - **Location:** smallchat-server.c:31‑38
> - **Issue:** `MAX_CLIENTS` is set to 1000 but the code indexes the `clients` array with the raw socket descriptor (`fd`). Socket descriptors can be arbitrarily large, causing out‑of‑bounds writes/read and memory corruption.
> - **Fix:** Use a dynamic data structure (e.g., hash table or linked list) to map fds to client structs...

With the skill, the same model reviews like Linus—focusing on invariants, correctness, and blunt technical truth:
> ### CRITICAL Missing null‑termination for client nickname
> - **Type:** invariant‑true
> - **Trigger:** Invariant‑true – Fatal aborts for recoverable conditions
> - **Location:** `createClient` (lines 45‑55)
> - **Issue:** `nicklen = snprintf(...); c->nick = chatMalloc(nicklen+1); memcpy(c->nick,nick,nicklen);` copies `nicklen` bytes **without** the terminating `'\0'`. Subsequent uses of `c->nick` read past the buffer, causing undefined behaviour and possible crashes.
> - **Fix:** Copy `nicklen+1` bytes or explicitly set `c->nick[nicklen] = '\0'` after `memcpy`.

## Validation: SmallChat Comparison
The skill was validated on [antirez/smallchat](https://github.com/antirez/smallchat) (706 LOC, C). Three models (gpt-oss-120b, glm5.2, mistral) each reviewed the codebase twice — once with the skill, once without (baseline). The full results are in [`report/comparison.md`](report/comparison.md).
The skill was validated on [antirez/smallchat](https://github.com/antirez/smallchat) (706 LOC, C). Four models (gpt-oss-120b, glm5.2, mistral, qwen3.8-27b) each reviewed the codebase twice — once with the skill, once without (baseline). The full results are in [`report/comparison.md`](report/comparison.md).

The comparison is not a count of findings. It cross-references bugs at the issue level so you can see which defects each model caught, which it missed, and whether the skill was responsible. Six sections matter:

1. **Stakeholder Scorecard** — one-row-per-model summary: total findings, criticals, skill-only criticals, verdict.
2. **Finding Consensus Matrix** — every finding from all three reviews mapped to the underlying issue, with per-model ✓/✗ and severity. Shows where models agree and where one model sees a bug the others miss.
3. **Severity Disagreement Table** — cases where 2+ models found the same issue but assigned different severities. Exposes calibration drift.
4. **With-Skill vs Baseline Comparison** — per model: baseline total, with-skill total, critical overlap, skill-only criticals, baseline-only criticals, and net skill impact.
5. **Per-Model Bug Comparison** — bug-by-bug tables: same bugs (with severity change), baseline-only (skill missed), skill-only (skill added). The baseline-only table includes a **Skill trigger covers?** column showing whether the skill has a trigger that should have caught the missed bug — distinguishing a skill gap (trigger exists, model didn't fire it) from out-of-scope (no trigger covers that bug type).
6. **Verdict** — per-model score from consensus-confirmed criticals, net critical impact, and severity disagreements.

**Latest result:** glm5.2 gained +2 net critical findings with the skill (4 new, 2 lost). gpt-oss-120b and mistral showed net negative critical coverage — the skill narrowed focus too aggressively and suppressed criticals the baseline caught. The trigger-coverage column shows which missed bugs were in-scope (skill gap) vs out-of-scope.

Replicate with `python3 report/run_review.py && python3 report/build_comparison.py`.

## Quick Start


### Model Divergence Showcase

The three skill variants are **intentionally kept separate** — not unified. Same corpus (38,293 review moves), same pipeline, three different LLMs → three demonstrably different distillations. This is the clearest evidence of how much the generation model shapes a distillation pipeline.

| Variant | Model | Words | Style | Trade-off |
|---|---|---|---|---|
| `SKILL.md` | gpt-oss-120b | ~6,780 | Balanced, comprehensive | Recommended default |
| `SKILL-GLM.md` | glm5.2 | ~8,890 | Most detailed, reasoning-heavy | Best for complex architecture reviews |
| `SKILL-Mistral.md` | mistral-small-4-119b | ~5,410 | Concise, YAML-formatted | Fast, small-context models |
| `SKILL-Qwen.md` | qwen3.8-27b | ~6,200 | Balanced, practical | Recommended for general reviews |

See [docs/models.md](docs/models.md) for full variant details, token costs, and regeneration commands.

**Key differences**:
- **Shared core**: All three agree on the 7 reviewer mindsets, Level 1 invariants, and the precedence chain (Correctness > Performance > Complexity > Style)
- **Shared core**: All four agree on the 7 reviewer mindsets, Level 1 invariants, and the precedence chain (Correctness > Performance > Complexity > Style)
- **Model-specific emphases**: GLM adds 15 detailed themes with 3-6 triggers each; Mistral compresses to 3 tiers; gpt-oss balances depth with readability
- **Severity calibration drift**: Same triggers, different severity assignments (e.g., "fatal assertion" = reject in gpt-oss, request-changes in Mistral)
- **Structural divergence**: GLM uses numbered themes (1-15), Mistral uses YAML headers, gpt-oss uses thematic groupings (A-J)

### Use the skill in your AI coding assistant

1. **Pick a skill variant** based on your needs (see Model Divergence Showcase above):
   - `SKILL.md` — gpt-oss-120b (balanced, recommended default)
   - `SKILL-GLM.md` — glm5.2 (most detailed, for reasoning models)
   - `SKILL-Mistral.md` — mistral (concise, for small-context models)
   - `SKILL-Qwen.md` — qwen3.8-27b (balanced, practical)

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
   - `soul-qwen.md` — qwen3.8-27b

2. **Use it as a system prompt** for Linus-style code review persona.

## Setup

```bash
uv sync
cp .env.example .env
# Edit .env: LLM_HOST, LLM_MODEL, REGOLO_API_KEY
```

## Pre-built Data

The `data/` directory (mbox, extracted moves, patterns, calibration data) is not committed — it's large and regenerable. **It is published as a release asset** on the repository's Releases page and updated when the pipeline produces new artifacts.

Download and extract it into the project root instead of running the full pipeline:

```bash
# From the Releases page, download data.tar.gz and extract:
tar xzf data.tar.gz
```

This gives you `data/moves.jsonl`, `data/patterns.json`, `data/calibration.json`, and all other artifacts needed to regenerate skill and soul files without fetching 31,000 emails or spending LLM API calls.

Run the full pipeline only if you want to re-extract from source (costs ~$5–8 in API calls, several hours).

## Configuration

The pipeline and review stages require an API key from [regolo.ai](https://regolo.ai) or any OpenAI-compatible endpoint.

### Connection settings

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` / `REGOLO_API_KEY` / `LLM_API_KEY` | (required) | API key (first set wins) |
| `OPENAI_BASE_URL` / `LLM_HOST` | `https://api.regolo.ai/v1` | LLM API endpoint (first set wins) |
| `LLM_MODEL` | `gpt-oss-120b` | Model for extraction and distillation |
| `LLM_MAX_RETRIES` | `3` | Retry count on 429/5xx |

### Caching

| Variable | Default | Description |
|---|---|---|
| `CACHE_ENABLED` | `1` | Set to `0` to bypass all caching |
| `CACHE_PATH` | `data/unified_cache.jsonl` | Unified cache file location |
| `CACHE_TTL_HOURS` | `168` (7d) | Cache TTL in hours (content-hash keys make this a cleanup window, not correctness requirement) |

**Cache behavior:** All LLM stages (extract, distill, review) use a unified cache with deterministic keys based on `SHA(stage + model + prompt + params)`. Different parameters (e.g., `max_tokens`, `temperature`) produce different keys, preventing stale outputs.

**CLI cache commands:**
```bash
# View cache statistics
python -m torvalds_skill cache stats

# Clear all cache entries
python -m torvalds_skill cache clear

# Compact cache (remove expired + dedupe)
python -m torvalds_skill cache compact
```

**Cache bypass:** Use `--no-cache` flag on extract stage or set `CACHE_ENABLED=0`:
```bash
python -m torvalds_skill extract --no-cache --workers 16
CACHE_ENABLED=0 python -m torvalds_skill extract --workers 16
```

**Cache invalidation:** Content-hash keys ensure different inputs never return stale outputs. To force re-extraction, either clear the cache or change input parameters.

### Profile overrides

Model profiles can be overridden via environment variables: `LLM_PROFILE_<NAME>__<FIELD>`

Example: `LLM_PROFILE_GLM52__TIMEOUT=900`

Available fields: `reasoning`, `slow`, `timeout`, `max_tokens`, `parallel_workers`, `review_timeout`, `distill_mode`, `prompt_budget_chars`, `strict_truncation`, `fallback_models`, `review_max_tokens`.

See `src/torvalds_skill/profiles.py` for profile defaults.

CLI flags override env vars: `--model`, `--out`.

## Documentation

| Document | Purpose |
|---|---|
| `docs/ARCHITECTURE.md` | Pipeline architecture, data flow, and runtime constraints |
| `docs/CONTRIBUTING.md` | Contributor guide, git rules, and regeneration commands |
| `docs/pipeline.md` | Full pipeline architecture, data flow, stage details |
| `docs/models.md` | Model variants, word counts, tradeoffs |
| `docs/validation.md` | SmallChat validation (with-skill vs baseline methodology) |
| `soul/README.md` | What a soul document is and how to generate it |
| `report/comparison.md` | Three-model comparison with delta analysis |
| `CHANGELOG.md` | Release notes and changes |

## Repository layout

```
.
├── src/torvalds_skill/     # Pipeline stages (classify, extract, cluster, distill, soul)
├── scripts/                 # Utility scripts (calibrate, verify_skill, etc.)
├── report/                  # Review pipeline and comparison generation
├── data/                    # Pipeline artifacts (mbox, moves, patterns, calibration)
├── linus-torvalds-skill/   # Generated skill files (SKILL.md, SKILL-GLM.md, etc.)
├── soul/                    # Generated soul files (soul.md, soul-glm.md, etc.)
└── tests/                   # Test suite
```

## Regenerate everything

### Option A: Use Python orchestrator (recommended)

Single orchestrator for the full pipeline:

```bash
# Dry-run (shows commands without executing)
python3 scripts/run_pipeline.py --dry-run

# Full regeneration chain
python3 scripts/run_pipeline.py

# Individual stages
python3 scripts/run_pipeline.py --stage calibrate    # Compute severity calibration
python3 scripts/run_pipeline.py --stage distill      # Distill patterns → skill
python3 scripts/run_pipeline.py --stage verify       # Verify skill quality
python3 scripts/run_pipeline.py --stage soul         # Generate soul document
python3 scripts/run_pipeline.py --stage review       # Run multi-model review pipeline
python3 scripts/run_pipeline.py --stage comparison   # Build comparison report
python3 scripts/run_pipeline.py --stage stats        # Generate variant table stats
```

Ordered chain: `calibrate → distill → verify → soul → review → comparison → stats`

### Option B: Manual commands

Ordered commands to regenerate all artifacts from scratch:

To regenerate with a different model:

```bash
python3 -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/SKILL-GLM.md
python3 -m torvalds_skill soul --model glm5.2 --out soul/soul-glm.md
```

## License

Everything in this repository — source code, pipeline scripts, the distilled skill, the soul document, and documentation — is released to the **public domain** under [CC0 1.0](LICENSE).
