# Torvalds Skill

Distills Linus Torvalds' code-review methodology from his LKML emails into a reusable, language-agnostic skill.

Built from **38,293 real review moves** extracted from 31,397 of his emails (2002–2026) on the Linux kernel mailing list, plus 67 interview transcripts.

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

## Setup

```bash
uv sync
cp .env.example .env
# Edit .env: LLM_HOST, LLM_MODEL, LLM_API_KEY
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

| Variable | Default | Description |
|---|---|---|
| `LLM_HOST` | `https://api.regolo.ai/v1` | LLM API endpoint |
| `LLM_MODEL` | `gpt-oss-120b` | Model for extraction and distillation |
| `LLM_API_KEY` | — | API key (required) |

CLI flags override env vars: `--model`, `--out`.

## Documentation

| Document | Purpose |
|---|---|
| `docs/pipeline.md` | Full pipeline architecture, data flow, stage details |
| `docs/models.md` | Model variants, word counts, tradeoffs |
| `docs/validation.md` | SmallChat validation (with-skill vs baseline methodology) |
| `soul/README.md` | What a soul document is and how to generate it |
| `report/comparison.md` | Three-model comparison with delta analysis |

## License

Everything in this repository — source code, pipeline scripts, the distilled skill, the soul document, and documentation — is released to the **public domain** under [CC0 1.0](LICENSE).
