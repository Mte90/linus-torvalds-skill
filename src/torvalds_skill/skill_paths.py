"""Single source of truth for model to skill/soul file paths.

All scripts, tests, and docs reference paths through this module.
No code outside this module should hardcode ``SKILL-*.md`` or ``soul-*.md``
paths (project rule: model-to-skill path mappings live here).

Layout (per model variant):
    linus-torvalds-skill/<variant>/skill.md
    soul/<variant>/soul.md

Variants: gpt-oss, glm, mistral, qwen.
"""

from __future__ import annotations

from pathlib import Path

# Resolved from src/torvalds_skill/skill_paths.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SKILL_DIR = _PROJECT_ROOT / "linus-torvalds-skill"
SOUL_DIR = _PROJECT_ROOT / "soul"

# model_id -> variant name (subfolder). Add new models here.
MODEL_VARIANTS: dict[str, str] = {
    "gpt-oss-120b": "gpt-oss",
    "glm5.2": "glm",
    "mistral-small-4-119b": "mistral",
    "qwen3.8-27b": "qwen",
}

DEFAULT_VARIANT = "gpt-oss"


def variant_for(model: str) -> str:
    """Return the variant name (subfolder) for a model.

    Unknown models fall back to DEFAULT_VARIANT.
    """
    return MODEL_VARIANTS.get(model, DEFAULT_VARIANT)


def skill_path(model: str) -> Path:
    """Return the skill file path for a model.

    Layout: ``<SKILL_DIR>/<variant>/skill.md``
    """
    return SKILL_DIR / variant_for(model) / "skill.md"


def soul_path(model: str) -> Path:
    """Return the soul file path for a model.

    Layout: ``<SOUL_DIR>/<variant>/soul.md``
    """
    return SOUL_DIR / variant_for(model) / "soul.md"


def all_models() -> list[str]:
    """Return all known model IDs."""
    return list(MODEL_VARIANTS)


def all_skill_paths() -> list[tuple[str, Path]]:
    """Return ``(model, skill_path)`` pairs for all known models."""
    return [(m, skill_path(m)) for m in MODEL_VARIANTS]


def all_soul_paths() -> list[tuple[str, Path]]:
    """Return ``(model, soul_path)`` pairs for all known models."""
    return [(m, soul_path(m)) for m in MODEL_VARIANTS]
