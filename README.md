# Torvalds Skill

Distills Linus Torvalds' code-review methodology from his LKML emails into a reusable, language-agnostic Skill (and Soul) from various LLMs.

Built from **38,293 real review moves** extracted from 31,397 of his emails (2002–2026) on the Linux kernel mailing list, plus 67 interview transcripts.

## Validation: SmallChat Comparison

The skill was validated on [antirez/smallchat](https://github.com/antirez/smallchat) (706 LOC, C). Each model reviewed the codebase twice — once with the skill, once without (baseline). Full results are in [`report/comparison.md`](report/comparison.md); methodology in [`docs/validation.md`](docs/validation.md).

## Quick Start

### Model Divergence Showcase

The four skill variants are **intentionally kept separate** — not unified. Same corpus (38,293 review moves), same pipeline, four different LLMs → four demonstrably different distillations. This is the clearest evidence of how much the generation model shapes a distillation pipeline.

| Variant | Model | Words | Style | Trade-off |
|---|---|---|---|---|
| `SKILL.md` | gpt-oss-120b | ~6,780 | Balanced, comprehensive | Recommended default |
| `SKILL-GLM.md` | glm5.2 | ~8,890 | Most detailed, reasoning-heavy | Best for complex architecture reviews |
| `SKILL-Mistral.md` | mistral-small-4-119b | ~5,410 | Concise, YAML-formatted | Fast, small-context models |
| `SKILL-Qwen.md` | qwen3.8-27b | ~6,200 | Balanced, practical | Recommended for general reviews |

See [docs/models.md](docs/models.md) for full variant details, token costs, and regeneration commands.

**Key differences**:
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

The `data/` directory (mbox, extracted moves, patterns, calibration data) is not committed — it's large and regenerable. **It is published as a release asset** on the repository's Releases page and updated (manually) when the pipeline produces new artifacts.

Download and extract it into the project root instead of running the full pipeline:

```bash
# From the Releases page, download data.tar.gz and extract:
tar xzf data.tar.gz
```

This gives you `data/moves.jsonl`, `data/patterns.json`, `data/calibration.json`, and all other artifacts needed to regenerate skill and soul files without fetching 31,000 emails or spending LLM API calls.

Run the full pipeline only if you want to re-extract from source.

## Configuration

The pipeline requires an API key from [regolo.ai](https://regolo.ai) or any OpenAI-compatible endpoint. Set `LLM_HOST`, `LLM_MODEL`, and `REGOLO_API_KEY` (or `OPENAI_API_KEY`) in `.env` (see `.env.example`).

Model profiles (timeout, max_tokens, distill_mode, etc.) are in `src/torvalds_skill/profiles.py` and can be overridden via `LLM_PROFILE_<NAME>__<FIELD>` env vars.

Caching is on by default (`CACHE_ENABLED=1`); bypass with `CACHE_ENABLED=0`.

See [`docs/pipeline.md`](docs/pipeline.md) for full configuration, caching, and profile override details.

## Regenerate

```bash
# Full pipeline (calibrate → distill → verify → soul → review → comparison → stats)
python3 scripts/run_pipeline.py

# Dry-run (shows commands without executing)
python3 scripts/run_pipeline.py --dry-run

# Individual stages
python3 scripts/run_pipeline.py --stage distill
python3 scripts/run_pipeline.py --stage soul
```

See [`docs/pipeline.md`](docs/pipeline.md) for full stage details and [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for the regeneration table.

## License

Everything in this repository — source code, pipeline scripts, the distilled skill, the soul document, and documentation — is released to the **public domain** under [CC0 1.0](LICENSE).
