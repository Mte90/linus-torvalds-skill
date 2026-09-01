# AGENTS.md — Project Conventions

## Core Rules

- **Generated Files**: All `.md` artifacts are produced by scripts. Never edit them directly. See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full regeneration table.
- **Git Discipline**: Local-only git. No push/pull/rebase/merge. See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).
- **Language Agnosticism**: Skills and souls must be language-agnostic. They capture Torvalds' METHOD, not his C knowledge.
- **File Size Limit**: Source files must not exceed 900 lines. Split large modules into focused submodules with clear single responsibilities.
- **No Committed Secrets**: API keys, tokens, and credentials must never be hardcoded in source. All credentials come from environment variables (`OPENAI_API_KEY` / `REGOLO_API_KEY` / `LLM_API_KEY` for the key; `OPENAI_BASE_URL` / `LLM_HOST` for the endpoint). The `.env` file is gitignored; `.env.example` is the template. If a key is ever committed, purge it from git history with `git filter-repo` before pushing.

## Documentation Pointers

- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — Contributor guide, git rules, and regeneration commands.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Pipeline architecture, runtime constraints, and data layout.
- [README.md](README.md) — Project overview and quick start.
