"""
profiles.py — capability-based model profiles replacing hard-coded model-name branching.

This module defines ModelProfile dataclass and provides get_profile(model) as the ONLY
place where model names are matched. All timeout, token, parallelism, and capability
settings come from profiles, not scattered hard-coded branches.

Profile sources (in order of precedence):
1. Environment override: LLM_PROFILE_<NAME>__<FIELD> (e.g., LLM_PROFILE_GLM52__TIMEOUT=900)
2. profiles.toml (if present in project root)
3. Built-in known profiles table

Usage:
    from torvalds_skill.profiles import get_profile
    profile = get_profile("glm5.2")
    print(profile.timeout, profile.max_tokens)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModelProfile:
    """Capability-based profile for an LLM model.

    Fields replace hard-coded model-name branching across:
    - config.py (_MODEL_TIMEOUTS, WALL_CLOCK_GLM, GLM_MAX_TOKENS)
    - distill.py (max_workers rule, --single-call flag)
    - distill_llm.py (is_glm, fallback chain)
    - run_review.py (TIMEOUTS, auto-chunking)
    - llm_review.py (GLM special timeout/max_tokens)

    Attributes:
        reasoning: True if model has a reasoning/thinking phase (e.g., GLM5.2)
        slow: True if model is notably slow (requires longer timeouts)
        prompt_budget_chars: Max prompt length before auto-chunking triggers
        distill_mode: "single" or "two-stage" for skill generation
        strict_truncation: Stricter truncation detection for this model
        timeout: Default timeout in seconds for API calls
        max_tokens: Max tokens for generation
        parallel_workers: Max parallel workers for distill (GLM keeps parallelism due to provider rate limits)
        review_timeout: Timeout for review pipeline (run_review.py)
        fallback_models: Ordered list of fallback models on truncation/failure
        review_max_tokens: Token budget for review path (None = fall back to max_tokens)
    """

    reasoning: bool = False
    slow: bool = False
    prompt_budget_chars: int = 50000
    distill_mode: str = "two-stage"
    strict_truncation: bool = False
    timeout: int = 120
    max_tokens: int = 16000
    parallel_workers: int = 1
    review_timeout: int = 900
    fallback_models: list[str] = field(default_factory=list)
    review_max_tokens: int | None = None


# Built-in known profiles table
# These are the ONLY model names matched anywhere in src/ (except tests)
KNOWN_PROFILES: dict[str, ModelProfile] = {
    "gpt-oss-120b": ModelProfile(
        reasoning=False,
        slow=False,
        prompt_budget_chars=50000,
        distill_mode="two-stage",
        strict_truncation=False,
        timeout=120,
        max_tokens=16000,
        parallel_workers=3,  # Non-GLM models can parallelize
        review_timeout=900,
        fallback_models=["mistral-small-4-119b", "glm5.2"],
        review_max_tokens=None,
    ),
    "glm5.2": ModelProfile(
        reasoning=True,
        slow=True,
        prompt_budget_chars=30000,  # Smaller budget due to reasoning overhead
        distill_mode="single",  # GLM requires single-call mode
        strict_truncation=True,
        timeout=600,
        max_tokens=16000,  # GLM_MAX_TOKENS from config.py
        parallel_workers=3,  # GLM keeps parallelism (provider rate-limit decision, explicit per task 3.2)
        review_timeout=2400,  # 40 min for GLM5.2 reviews
        fallback_models=["mistral-small-4-119b", "gpt-oss-120b"],
        review_max_tokens=None,
    ),
    "mistral-small-4-119b": ModelProfile(
        reasoning=False,
        slow=False,
        prompt_budget_chars=50000,
        distill_mode="two-stage",
        strict_truncation=False,
        timeout=120,
        max_tokens=16000,
        parallel_workers=3,
        review_timeout=900,
        fallback_models=["gpt-oss-120b", "glm5.2"],
        review_max_tokens=None,
    ),
}

# Default profile for unknown models
DEFAULT_PROFILE = ModelProfile(
    reasoning=False,
    slow=False,
    prompt_budget_chars=50000,
    distill_mode="two-stage",
    strict_truncation=False,
    timeout=120,
    max_tokens=16000,
    parallel_workers=1,
    review_timeout=900,
    fallback_models=[],
    review_max_tokens=None,
)


def _load_toml_profile(model_name: str) -> ModelProfile | None:
    """Load profile from profiles.toml if present.

    TOML structure:
    [profiles.glm5.2]
    reasoning = true
    timeout = 900
    max_tokens = 32000
    """
    toml_path = Path(__file__).resolve().parent.parent.parent / "profiles.toml"
    if not toml_path.exists():
        return None

    try:
        # Simple TOML parser (stdlib only, no external deps)
        content = toml_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Find [profiles.MODEL_NAME] section
        in_section = False
        profile_data: dict[str, Any] = {}

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Section header
            if line.startswith("["):
                in_section = line == f"[profiles.{model_name}]"
                continue

            if in_section and "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                # Parse value
                if val.lower() == "true":
                    profile_data[key] = True
                elif val.lower() == "false":
                    profile_data[key] = False
                elif val.startswith('"') and val.endswith('"'):
                    profile_data[key] = val[1:-1]
                elif val.startswith("[") and val.endswith("]"):
                    # Parse list
                    items = val[1:-1].split(",")
                    profile_data[key] = [item.strip().strip('"') for item in items if item.strip()]
                else:
                    try:
                        profile_data[key] = int(val)
                    except ValueError:
                        try:
                            profile_data[key] = float(val)
                        except ValueError:
                            profile_data[key] = val

        if profile_data:
            # Use dataclasses.replace for present-wins merge semantics
            from dataclasses import replace

            base = KNOWN_PROFILES.get(model_name, DEFAULT_PROFILE)
            return replace(base, **profile_data)  # type: ignore[arg-type]
    except Exception:
        pass

    return None


def _load_env_override(model_name: str) -> dict[str, Any]:
    """Load environment overrides for a model profile.

    Env var format: LLM_PROFILE_<NAME>__<FIELD>
    Example: LLM_PROFILE_GLM52__TIMEOUT=900
    """
    overrides: dict[str, Any] = {}
    model_upper = model_name.upper().replace("-", "_")

    # Field mappings (env var name -> dataclass field)
    fields = [
        "reasoning",
        "slow",
        "prompt_budget_chars",
        "distill_mode",
        "strict_truncation",
        "timeout",
        "max_tokens",
        "parallel_workers",
        "review_timeout",
        "fallback_models",
        "review_max_tokens",
    ]

    for field_name in fields:
        env_key = f"LLM_PROFILE_{model_upper}__{field_name.upper()}"
        if env_val := os.environ.get(env_key):
            # Parse value based on field type
            if field_name in ("reasoning", "slow", "strict_truncation"):
                overrides[field_name] = env_val.lower() == "true"
            elif field_name in (
                "prompt_budget_chars",
                "timeout",
                "max_tokens",
                "parallel_workers",
                "review_timeout",
            ):
                try:
                    overrides[field_name] = int(env_val)
                except ValueError:
                    pass
            elif field_name == "distill_mode":
                overrides[field_name] = (
                    env_val if env_val in ("single", "two-stage") else "two-stage"
                )
            elif field_name == "fallback_models":
                # Parse CSV: "a,b,c" -> ["a", "b", "c"]
                overrides[field_name] = [m.strip() for m in env_val.split(",") if m.strip()]
            elif field_name == "review_max_tokens":
                try:
                    overrides[field_name] = int(env_val)
                except ValueError:
                    pass
            else:
                overrides[field_name] = env_val

    return overrides


def get_profile(model: str | None = None, default: ModelProfile | None = None) -> ModelProfile:
    """Get the profile for a model name.

    This is the ONLY place in src/ where model names are matched.

    Args:
        model: Model name (e.g., "glm5.2", "gpt-oss-120b"). Case-insensitive.
        default: Default profile to use if model not found (defaults to DEFAULT_PROFILE)

    Returns:
        ModelProfile for the model, with env overrides applied

    Example:
        >>> profile = get_profile("glm5.2")
        >>> profile.timeout
        600
        >>> profile.reasoning
        True
    """
    model = (model or "gpt-oss-120b").lower()
    default = default or DEFAULT_PROFILE

    # 1. Start with known profile or default
    profile = KNOWN_PROFILES.get(model, default)

    # 2. Try TOML override
    toml_profile = _load_toml_profile(model)
    if toml_profile:
        # Merge TOML profile with known profile using dataclasses.replace
        # Present-wins semantics: false/0/"" in TOML override defaults
        from dataclasses import replace

        profile = replace(
            profile, **{k: v for k, v in toml_profile.__dict__.items() if v is not None}
        )

    # 3. Apply environment overrides (highest precedence)
    env_overrides = _load_env_override(model)
    if env_overrides:
        from dataclasses import replace

        profile = replace(profile, **env_overrides)

    return profile


def get_profile_table() -> list[tuple[str, ModelProfile]]:
    """Return sorted list of (model_name, profile) tuples for documentation."""
    return sorted(KNOWN_PROFILES.items())


def resolve_distill_mode(explicit_mode: str | None, single_call: bool, model: str | None) -> str:
    """Resolve distill mode from explicit parameter, legacy flag, or model profile.

    Args:
        explicit_mode: Explicit --distill-mode value ("single" or "two-stage")
        single_call: Legacy --single-call flag (deprecated)
        model: Model name for profile lookup

    Returns:
        Resolved distill mode: "single" or "two-stage"
    """
    if explicit_mode is not None:
        return explicit_mode
    # Legacy --single-call flag (deprecated) wins over the profile default.
    if single_call:
        return "single"
    if model:
        return get_profile(model).distill_mode
    return "two-stage"
