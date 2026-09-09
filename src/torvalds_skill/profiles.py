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
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModelProfile:
    """Capability-based profile for an LLM model.

    Fields replace hard-coded model-name branching across:
    - config.py (_MODEL_TIMEOUTS)
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
        reasoning=True,
        slow=True,
        prompt_budget_chars=30000,
        distill_mode="single",
        strict_truncation=True,
        timeout=600,
        max_tokens=16000,
        parallel_workers=3,
        review_timeout=2400,
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
        max_tokens=16000,  # from profiles, replaces GLM_MAX_TOKENS
        parallel_workers=3,  # GLM keeps parallelism (provider rate-limit decision, explicit per task 3.2)
        review_timeout=2400,  # 40 min for GLM5.2 reviews
        fallback_models=["mistral-small-4-119b", "gpt-oss-120b"],
        review_max_tokens=32000,
    ),
    "mistral-small-4-119b": ModelProfile(
        reasoning=True,
        slow=True,
        prompt_budget_chars=30000,
        distill_mode="single",
        strict_truncation=True,
        timeout=600,
        max_tokens=16000,
        parallel_workers=3,
        review_timeout=2400,
        fallback_models=["gpt-oss-120b", "glm5.2"],
        review_max_tokens=32000,
    ),
    "qwen3.8-27b": ModelProfile(
        # Reasoning model (verified: spends budget on thinking traces before
        # content, like glm5.2) — single-call distill, long timeouts.
        # Context: 240K tokens. review_max_tokens=131072 leaves room for both
        # the reasoning phase and the final review output.
        reasoning=True,
        slow=True,
        prompt_budget_chars=30000,
        distill_mode="single",
        strict_truncation=True,
        timeout=600,
        max_tokens=16000,
        parallel_workers=3,
        review_timeout=2400,
        fallback_models=["gpt-oss-120b", "mistral-small-4-119b"],
        review_max_tokens=131072,
    ),
}

# Default profile for unknown models
# Rationale for defaults:
# - parallel_workers=3: Match known profiles (gpt-oss-120b, glm5.2, mistral) for consistent throughput
# - distill_mode="two-stage": Safer default for unknown models; single-call is GLM-specific
# - no fallback_models: Unknown models shouldn't chain to known profiles automatically
# - timeout=120: Standard timeout; slow/reasoning models set this explicitly in their profiles
DEFAULT_PROFILE = ModelProfile(
    reasoning=False,
    slow=False,
    prompt_budget_chars=50000,
    distill_mode="two-stage",
    strict_truncation=False,
    timeout=120,
    max_tokens=16000,
    parallel_workers=3,  # Match known profiles for consistent throughput
    review_timeout=900,
    fallback_models=[],  # Unknown models don't auto-fallback to known profiles
    review_max_tokens=None,
)


def _load_toml_profile(model_name: str) -> ModelProfile | None:
    """Load profile from profiles.toml if present using stdlib tomllib.

    TOML structure:
    [profiles.glm5.2]
    reasoning = true
    timeout = 900
    max_tokens = 32000
    fallback_models = ["model-a", "model-b"]
    """
    import tomllib

    toml_path = Path(__file__).resolve().parent.parent.parent / "profiles.toml"
    if not toml_path.exists():
        return None

    try:
        content = toml_path.read_text(encoding="utf-8")
        data = tomllib.loads(content)

        # Find [profiles.MODEL_NAME] section
        profiles_section = data.get("profiles", {})
        if model_name in profiles_section:
            profile_data = profiles_section[model_name]
        else:
            # Dotted model names (e.g. "glm5.2") may be parsed as nested
            # TOML: [profiles.glm5.2] → profiles["glm5"]["2"]
            parts = model_name.split(".")
            if len(parts) == 2:
                nested = profiles_section.get(parts[0], {})
                if isinstance(nested, dict) and parts[1] in nested:
                    profile_data = nested[parts[1]]
                else:
                    return None
            else:
                return None

        # Warn about unrecognized sections
        known_models = sorted(KNOWN_PROFILES.keys())
        for section_name in profiles_section.keys():
            if section_name not in known_models:
                print(
                    f"Warning: profiles.toml contains unrecognized profile '{section_name}' — known models: {', '.join(known_models)}",
                    file=sys.stderr,
                )

        # Use dataclasses.replace for present-wins merge semantics
        from dataclasses import replace

        base = KNOWN_PROFILES.get(model_name, DEFAULT_PROFILE)
        return replace(base, **profile_data)  # type: ignore[arg-type]
    except Exception:
        return None


def _load_env_override(model_name: str) -> dict[str, Any]:
    """Load environment overrides for a model profile.

    Env var format: LLM_PROFILE_<NAME>__<FIELD>
    Example: LLM_PROFILE_GLM52__TIMEOUT=900
    """
    overrides: dict[str, Any] = {}
    model_upper = model_name.upper().replace("-", "_").replace(".", "_")

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
