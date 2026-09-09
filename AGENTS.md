# AGENTS.md — Project Conventions

## Core Rules

- **Generated Files**: All `.md` artifacts are produced by scripts. Never edit them directly. See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full regeneration table.
- **Git Discipline**: Local-only git. No push/pull/rebase/merge. See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).
- **Language Agnosticism**: Skills and souls must be language-agnostic. They capture Torvalds' METHOD, not his C knowledge.
- **File Size Limit**: Source files in `src/torvalds_skill/*` must not exceed 900 lines. Split large modules into focused submodules. **Grandfathered**: `report/build_comparison.py` (1388), `report/run_review.py` (1308), `report/classify_interviews.py` (1161), `report/comparison_render.py` (932) — split ticket created, do not touch until that work is assigned.
- **No Committed Secrets**: API keys, tokens, and credentials must never be hardcoded in source. All credentials come from environment variables (`OPENAI_API_KEY` / `REGOLO_API_KEY` / `LLM_API_KEY` for the key; `OPENAI_BASE_URL` / `LLM_HOST` for the endpoint). The `.env` file is gitignored; `.env.example` is the template. If a key is ever committed, purge it from git history with `git filter-repo` before pushing.
- **Model Matching**: No model-specific branching outside `src/torvalds_skill/profiles.py` — `get_profile()` is the single source of truth.
- **Prompt Centralization**: Prompt blocks live once in `src/torvalds_skill/distill_prompts.py`; never duplicate across skills.
- **Trigger Contract**: Pattern extraction regexes live in `report/trigger_patterns.py`; consumed by `build_comparison.py` and `verify_skill.py`. Change all three together.
- **Validation Symmetry**: Both comparison arms must validate identically — either both run full checks or neither skips.
- **Stats Generated**: Pattern/word counts and timeouts come from `data/patterns.json`; docs link to source, never type values.
- **Soul Generation**: Soul files must be generated via the `soul` CLI stage and validated with `scripts/verify_soul.py`, not hand-edited. Match skill variant (gpt-oss → soul.md, glm → soul-glm.md, mistral → soul-mistral.md, qwen → soul-qwen.md).
- **Caching**: Unified cache is on by default (`CACHE_ENABLED=1`). Bypass with `CACHE_ENABLED=0`. Cache entries expire after `CACHE_TTL_HOURS` (default 168h / 7d). Cache path: `CACHE_PATH` (default `data/unified_cache.jsonl`). Invalid cache = truncated responses never cached.
- **Profile Overrides**: Priority: env vars > profiles.toml > built-in. Env format: `LLM_PROFILE_<NAME>__<FIELD>` where dots and dashes in `<NAME>` become underscores (e.g., `LLM_PROFILE_GLM5_2__TIMEOUT=900` for `glm5.2`, `LLM_PROFILE_QWEN3_8_27B__TIMEOUT=900` for `qwen3.8-27b`). TOML: copy `profiles.example.toml` to `profiles.toml`.

## Local Checks

Run these before committing (CI removed — project is local-only):

```bash
python -m pytest tests/ -q
ruff check src/ scripts/ tests/
ruff format --check .
mypy src/
gitleaks detect --source .  # install gitleaks first if needed
python scripts/verify_skill.py linus-torvalds-skill/SKILL.md  # skill quality gate
```

Install pre-commit hooks once: `pre-commit install`. The `.pre-commit-config.yaml` includes gitleaks scanning.

## Directory Map

| Stage/Script | Location |
|---|---|
| CLI stages (classify, extract, cluster, distill, soul) | `src/torvalds_skill/` |
| Utility scripts (calibrate, verify_skill, generate_variant_table) | `scripts/` |
| Review pipeline, comparison generation | `report/` |
| Pipeline outputs (skill/soul files) | `linus-torvalds-skill/`, `soul/` |
| Pipeline artifacts (mbox, moves, patterns, calibration) | `data/` |
| Tests | `tests/` |

## Documentation Pointers

- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — Contributor guide, git rules, and regeneration commands.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Pipeline architecture, runtime constraints, and data layout.
- [README.md](README.md) — Project overview and quick start.
