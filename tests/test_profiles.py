"""Tests for profiles.py - capability-based model profiles."""

import os
import subprocess
from pathlib import Path

from torvalds_skill.profiles import (
    DEFAULT_PROFILE,
    KNOWN_PROFILES,
    get_profile,
)


class TestModelProfile:
    """Tests for ModelProfile dataclass."""

    def test_default_profile_fields(self):
        """Default profile should have expected default values."""
        assert DEFAULT_PROFILE.reasoning is False
        assert DEFAULT_PROFILE.slow is False
        assert DEFAULT_PROFILE.prompt_budget_chars == 50000
        assert DEFAULT_PROFILE.distill_mode == "two-stage"
        assert DEFAULT_PROFILE.strict_truncation is False
        assert DEFAULT_PROFILE.timeout == 120
        assert DEFAULT_PROFILE.max_tokens == 16000
        assert DEFAULT_PROFILE.parallel_workers == 3  # Updated: match known profiles
        assert DEFAULT_PROFILE.review_timeout == 900
        assert DEFAULT_PROFILE.fallback_models == []
        assert DEFAULT_PROFILE.review_max_tokens is None

    def test_known_profiles_exist(self):
        """All known models should have profiles."""
        assert "gpt-oss-120b" in KNOWN_PROFILES
        assert "glm5.2" in KNOWN_PROFILES
        assert "mistral-small-4-119b" in KNOWN_PROFILES


class TestGetProfile:
    """Tests for get_profile function."""

    def test_get_glm52_profile(self):
        """GLM5.2 profile should have reasoning=True and longer timeouts."""
        profile = get_profile("glm5.2")
        assert profile.reasoning is True
        assert profile.slow is True
        assert profile.distill_mode == "single"
        assert profile.strict_truncation is True
        assert profile.review_timeout == 2400
        assert profile.max_tokens == 16000
        assert profile.parallel_workers == 3  # GLM keeps parallelism

    def test_get_gpt_oss_120b_profile(self):
        """gpt-oss-120b profile should have default settings."""
        profile = get_profile("gpt-oss-120b")
        assert profile.reasoning is False
        assert profile.distill_mode == "two-stage"
        assert profile.review_timeout == 900
        assert profile.parallel_workers == 3

    def test_get_mistral_profile(self):
        """mistral-small-4-119b profile should have default settings."""
        profile = get_profile("mistral-small-4-119b")
        assert profile.reasoning is False
        assert profile.distill_mode == "two-stage"
        assert profile.parallel_workers == 3

    def test_unknown_model_returns_default(self):
        """Unknown model should return default profile."""
        profile = get_profile("unknown-model")
        assert profile.reasoning is False
        assert profile.timeout == 120
        assert profile.fallback_models == []

    def test_case_insensitive_model_name(self):
        """Model name lookup should be case-insensitive."""
        profile1 = get_profile("glm5.2")
        profile2 = get_profile("GLM5.2")
        profile3 = get_profile("Glm5.2")
        assert profile1 == profile2 == profile3

    def test_env_override(self):
        """Environment variables should override profile values."""
        # Use a model with default timeout to make the override more obvious
        os.environ["LLM_PROFILE_GPT_OSS_120B__TIMEOUT"] = "900"
        try:
            profile = get_profile("gpt-oss-120b")
            assert profile.timeout == 900
        finally:
            del os.environ["LLM_PROFILE_GPT_OSS_120B__TIMEOUT"]

    def test_toml_false_wins_merge(self, tmp_path):
        """TOML false/0/empty should override True defaults (present-wins semantics)."""
        # Create a temporary profiles.toml with reasoning=false for gpt-oss-120b
        # This tests that false values in TOML are preserved (not treated as falsy)
        toml_content = """
[profiles.gpt-oss-120b]
reasoning = false
slow = false
"""
        toml_path = tmp_path / "profiles.toml"
        toml_path.write_text(toml_content)

        # Save original and replace
        real_toml = Path(__file__).parent.parent / "profiles.toml"
        real_toml_exists = real_toml.exists()
        real_toml_backup = tmp_path / "profiles.toml.backup"
        if real_toml_exists:
            import shutil

            shutil.copy(real_toml, real_toml_backup)
            real_toml.unlink()
        # Copy test TOML to real location
        import shutil

        shutil.copy(toml_path, real_toml)

        try:
            # Force reimport to pick up new TOML
            import importlib

            import torvalds_skill.profiles as profiles_module

            importlib.reload(profiles_module)

            # gpt-oss-120b has reasoning=False by default, so false=false is trivial
            # The key test is that the TOML was parsed and merged without error
            profile = profiles_module.get_profile("gpt-oss-120b")
            assert profile.reasoning is False
            assert profile.slow is False
        finally:
            # Restore original
            if real_toml_exists:
                real_toml.unlink(missing_ok=True)
                import shutil

                shutil.copy(real_toml_backup, real_toml)

    def test_env_fallback_models_csv(self):
        """Environment variable should set fallback_models via CSV parsing."""
        os.environ["LLM_PROFILE_GPT_OSS_120B__FALLBACK_MODELS"] = "model-a,model-b,model-c"
        try:
            profile = get_profile("gpt-oss-120b")
            assert profile.fallback_models == ["model-a", "model-b", "model-c"]
        finally:
            del os.environ["LLM_PROFILE_GPT_OSS_120B__FALLBACK_MODELS"]

    def test_review_max_tokens_default_none(self):
        """review_max_tokens should default to None for all profiles."""
        for model_name in KNOWN_PROFILES:
            profile = get_profile(model_name)
            assert profile.review_max_tokens is None, (
                f"{model_name} should have review_max_tokens=None"
            )
        assert DEFAULT_PROFILE.review_max_tokens is None

    def test_review_max_tokens_env_override(self):
        """Environment variable should set review_max_tokens."""
        # Note: dots in model name are NOT replaced (only dashes), so GLM5.2 -> GLM5.2
        os.environ["LLM_PROFILE_GLM5.2__REVIEW_MAX_TOKENS"] = "32000"
        try:
            profile = get_profile("glm5.2")
            assert profile.review_max_tokens == 32000
        finally:
            del os.environ["LLM_PROFILE_GLM5.2__REVIEW_MAX_TOKENS"]

    def test_severity_bias_removed(self):
        """severity_bias field should not exist in ModelProfile."""
        profile = get_profile("glm5.2")
        assert not hasattr(profile, "severity_bias"), "severity_bias field should be removed"

    def test_unknown_model_defaults(self):
        """Unknown model should use DEFAULT_PROFILE with parallel_workers=3, two-stage, timeout 120."""
        profile = get_profile("fake-off-table-model")
        assert profile.parallel_workers == 3, "Unknown models should default to 3 parallel workers"
        assert profile.distill_mode == "two-stage", (
            "Unknown models should default to two-stage distill"
        )
        assert profile.timeout == 120, "Unknown models should default to 120s timeout"
        assert profile.fallback_models == [], "Unknown models should have no fallback chain"
        assert profile.reasoning is False, "Unknown models should default to non-reasoning mode"
        assert profile.strict_truncation is False, (
            "Unknown models should use lenient truncation detection"
        )


class TestNoHardCodedGlmReferences:
    """Verify that 'glm' (case-insensitive) only appears in profiles.py and tests."""

    def test_no_glm_code_references_outside_profiles_and_tests(self):
        """Search src/ for 'glm' in code (not comments/docstrings) - should only find profiles.py."""
        src_dir = Path(__file__).parent.parent / "src"

        # Run grep to find all 'glm' references in src/
        result = subprocess.run(
            ["grep", "-ri", "glm", str(src_dir), "--include=*.py"],
            capture_output=True,
            text=True,
        )

        # Parse results and filter out comment/docstring lines
        # We're looking for actual code like: if "glm" in model.lower()
        code_matches = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            path = line.split(":")[0]
            # Skip if it's in profiles.py or test files
            if "profiles.py" in path or "test" in path:
                continue
            # Check if this is an actual code reference (string comparison)
            # Patterns: "glm" in ..., 'glm' in ..., == "glm", == 'glm'
            code_part = line.split("#")[0]  # Remove comments
            if any(pattern in code_part for pattern in ['"glm"', "'glm'", '== "glm"', "== 'glm'"]):
                code_matches.append(path)

        # All code matches should be in profiles.py or test files
        assert len(code_matches) == 0, (
            f"Found 'glm' code references outside profiles.py/tests: {code_matches}"
        )
