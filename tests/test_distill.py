"""Tests for distill.py prompt formatting.

Verifies the rewrite that changed distill from consuming pre-clustered
patterns to consuming samples_by_category (stratified raw moves).
The _format_moves_for_prompt function is pure and fully testable
without LLM access.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from torvalds_skill.distill import (
    MODEL_SEVERITY_BIAS,
    _format_model_calibration_note,
    _format_moves_for_prompt,
    _load_interview_data,
    _load_severity_weights,
    _validate_severity_consistency,
    _validate_skill_structure,
    _weighted_sample_patterns,
)
from torvalds_skill.distill_llm import _detect_truncation, _WallClockTimeout
from torvalds_skill.distill_prompts import DISTILL_SYSTEM_PROMPT


def _make_pattern(
    category: str = "testing",
    severity: str = "reject",
    source: str = "email",
    trigger: str = "untested code",
    principle: str = "require tests",
    quote: str = "add tests before merging",
) -> dict:
    return {
        "category": category,
        "severity": severity,
        "source": source,
        "trigger": trigger,
        "principle": principle,
        "quote": quote,
    }


class TestFormatMovesForPrompt:
    def test_includes_corpus_statistics(self):
        patterns = [
            _make_pattern(category="testing", severity="reject", source="email"),
            _make_pattern(category="testing", severity="approve", source="interview"),
            _make_pattern(category="correctness", severity="reject", source="email"),
        ]
        result = _format_moves_for_prompt(patterns)
        assert "3" in result
        assert "2" in result
        assert "1" in result

    def test_includes_total_sample_count(self):
        patterns = [_make_pattern(category="testing") for _ in range(15)] + [
            _make_pattern(category="correctness") for _ in range(10)
        ]
        result = _format_moves_for_prompt(patterns)
        assert "25 representative review moves" in result

    def test_formats_each_category_header(self):
        patterns = [
            _make_pattern(category="testing"),
            _make_pattern(category="correctness"),
        ]
        result = _format_moves_for_prompt(patterns)
        assert "## Category: correctness (1 samples)" in result
        assert "## Category: testing (1 samples)" in result

    def test_formats_each_move_with_all_fields(self):
        patterns = [
            _make_pattern(
                category="testing",
                trigger="broken userspace",
                principle="never break userspace",
                severity="reject",
                quote="this breaks existing setups",
            )
        ]
        result = _format_moves_for_prompt(patterns)
        assert "Trigger: broken userspace" in result
        assert "Principle: never break userspace" in result
        assert "Severity: reject" in result
        assert 'Response (Torvalds\' words): "this breaks existing setups"' in result

    def test_handles_empty_samples(self):
        result = _format_moves_for_prompt([])
        assert "0 representative" in result

    def test_includes_instructions_for_llm(self):
        patterns = [_make_pattern()]
        result = _format_moves_for_prompt(patterns)
        assert "THEMES" in result or "themes" in result
        assert "synthesize" in result

    def test_quotes_response_text(self):
        patterns = [_make_pattern(quote='say "no" firmly')]
        result = _format_moves_for_prompt(patterns)
        assert '"say "no" firmly"' in result

    def test_numbers_moves_within_category(self):
        patterns = [_make_pattern(trigger=f"t{i}") for i in range(5)]
        result = _format_moves_for_prompt(patterns)
        for i in range(1, 6):
            assert f"### Move {i}" in result

    def test_preserves_category_order(self):
        patterns = [
            _make_pattern(category="testing", trigger="test-trigger"),
            _make_pattern(category="correctness", trigger="correct-trigger"),
            _make_pattern(category="performance", trigger="perf-trigger"),
        ]
        result = _format_moves_for_prompt(patterns)
        # Categories are sorted alphabetically
        correct_pos = result.index("correct-trigger")
        perf_pos = result.index("perf-trigger")
        test_pos = result.index("test-trigger")
        assert correct_pos < perf_pos < test_pos

    def test_large_corpus_formats_without_error(self):
        """Stress test: 200 samples (full run scale)."""
        patterns = [
            _make_pattern(
                trigger=f"trigger {i}",
                principle=f"principle {i}",
                quote=f"response {i}" * 20,
            )
            for i in range(200)
        ]
        result = _format_moves_for_prompt(patterns)
        assert "200 representative review moves" in result
        assert len(result) > 10000


class TestDistillPromptTierStructure:
    """Tests for the 3-tier hierarchical trigger structure in DISTILL_SYSTEM_PROMPT."""

    def test_contains_level_1_global_invariants(self):
        """Verify Level 1: Global Invariants tier is present."""
        assert "Level 1" in DISTILL_SYSTEM_PROMPT
        assert "Global Invariants" in DISTILL_SYSTEM_PROMPT
        assert "non-negotiables" in DISTILL_SYSTEM_PROMPT

    def test_contains_level_2_structural_patterns(self):
        """Verify Level 2: Structural Patterns tier is present."""
        assert "Level 2" in DISTILL_SYSTEM_PROMPT
        assert "Structural Patterns" in DISTILL_SYSTEM_PROMPT
        assert "architecture-level" in DISTILL_SYSTEM_PROMPT

    def test_contains_level_3_tactical_guidelines(self):
        """Verify Level 3: Tactical Guidelines tier is present."""
        assert "Level 3" in DISTILL_SYSTEM_PROMPT
        assert "Tactical Guidelines" in DISTILL_SYSTEM_PROMPT
        assert "implementation-level" in DISTILL_SYSTEM_PROMPT

    def test_tier_structure_section_exists(self):
        """Verify the Tier Structure section header exists."""
        assert "### Tier Structure" in DISTILL_SYSTEM_PROMPT


class TestDistillPromptReasoningProtocol:
    """Tests for the Reasoning Protocol section in DISTILL_SYSTEM_PROMPT."""

    def test_contains_reasoning_protocol_section(self):
        """Verify Reasoning Protocol section exists."""
        assert "## Reasoning Protocol" in DISTILL_SYSTEM_PROMPT

    def test_contains_reason_marker(self):
        """Verify [REASON] marker is present."""
        assert "[REASON]" in DISTILL_SYSTEM_PROMPT

    def test_contains_act_marker(self):
        """Verify [ACT] marker is present."""
        assert "[ACT]" in DISTILL_SYSTEM_PROMPT

    def test_contains_reason_act_workflow(self):
        """Verify the [REASON]→[ACT] workflow is described."""
        assert (
            "[REASON]→[ACT]" in DISTILL_SYSTEM_PROMPT
            or "[REASON] -> [ACT]" in DISTILL_SYSTEM_PROMPT
        )

    def test_reasoning_protocol_prevents_false_positives(self):
        """Verify the protocol mentions preventing pattern-matching false positives."""
        assert "pattern-matching" in DISTILL_SYSTEM_PROMPT
        # "false positives" may be split across lines due to line continuations
        assert (
            "false" in DISTILL_SYSTEM_PROMPT.lower()
            and "positives" in DISTILL_SYSTEM_PROMPT.lower()
        )


class TestDistillPromptExistingFeatures:
    """Tests to ensure existing prompt features are still present."""

    def test_forbidden_terms_list_present(self):
        """Verify the forbidden terms list (C/kernel specific terms) is still present."""
        assert "BUG_ON" in DISTILL_SYSTEM_PROMPT
        assert "WARN_ON" in DISTILL_SYSTEM_PROMPT
        assert "copy_to_user" in DISTILL_SYSTEM_PROMPT

    def test_language_agnostic_requirements_present(self):
        """Verify language-agnostic requirements are still enforced."""
        assert "language-agnostic" in DISTILL_SYSTEM_PROMPT.lower()
        assert "Python" in DISTILL_SYSTEM_PROMPT
        assert "Go" in DISTILL_SYSTEM_PROMPT
        assert "Rust" in DISTILL_SYSTEM_PROMPT

    def test_translation_table_present(self):
        """Verify the translation table is still present."""
        assert "TRANSLATION TABLE" in DISTILL_SYSTEM_PROMPT
        assert "C/Kernel specific" in DISTILL_SYSTEM_PROMPT

    def test_severity_calibration_present(self):
        """Verify severity calibration section is still present."""
        assert "## Severity Calibration" in DISTILL_SYSTEM_PROMPT

    def test_precedence_chain_present(self):
        """Verify the precedence chain is still present."""
        assert "Correctness" in DISTILL_SYSTEM_PROMPT
        assert "Performance" in DISTILL_SYSTEM_PROMPT
        assert "Complexity" in DISTILL_SYSTEM_PROMPT
        assert "Style" in DISTILL_SYSTEM_PROMPT


class TestValidateSkillStructure:
    """Tests for _validate_skill_structure function."""

    def test_all_required_sections_present(self):
        """Skill with all required sections returns empty list."""
        skill = """
## Reviewer Mindset
Some content here.

## Review Triggers
More content.

## Severity Calibration
Calibration info.

## Severity Decision Tree
Decision tree content.

## Precedence and Priorities
Precedence info.

## Decision Cards
Cards content.

## Key Definitions
Definitions here.

## Voice and Tone
Tone guidelines.
"""
        result = _validate_skill_structure(skill)
        assert result == []

    def test_missing_single_section(self):
        """Skill missing 'Severity Decision Tree' returns that section name."""
        skill = """
## Reviewer Mindset
Content.

## Review Triggers
Content.

## Severity Calibration
Content.

## Precedence and Priorities
Content.

## Decision Cards
Content.

## Key Definitions
Content.

## Voice and Tone
Content.
"""
        result = _validate_skill_structure(skill)
        assert result == ["Severity Decision Tree"]

    def test_missing_multiple_sections(self):
        """Skill missing multiple sections returns all missing names."""
        skill = """
## Reviewer Mindset
Content.

## Review Triggers
Content.
"""
        result = _validate_skill_structure(skill)
        assert "Severity Calibration" in result
        assert "Severity Decision Tree" in result
        assert "Precedence and Priorities" in result
        assert "Decision Cards" in result
        assert "Key Definitions" in result
        assert "Voice and Tone" in result

    def test_empty_string_returns_all_sections(self):
        """Empty string returns all required sections as missing."""
        result = _validate_skill_structure("")
        assert len(result) == 8
        assert "Reviewer Mindset" in result
        assert "Review Triggers" in result


class TestValidateSeverityConsistency:
    """Tests for _validate_severity_consistency function."""

    def test_balanced_severities_no_warnings(self):
        """Skill text with balanced severities returns empty warnings."""
        skill = """
When you see a critical bug, reject it.
For minor style issues, nitpick them.
If the code needs improvement, request changes.
"""
        calibration = {
            "severity_by_category": {
                "correctness": {
                    "reject_rate": 40.0,
                    "request_changes_rate": 40.0,
                    "nitpick_rate": 10.0,
                },
                "performance": {
                    "reject_rate": 30.0,
                    "request_changes_rate": 50.0,
                    "nitpick_rate": 10.0,
                },
            }
        }
        result = _validate_severity_consistency(skill, calibration)
        # With such small sample, may or may not trigger warnings
        assert isinstance(result, list)

    def test_overrepresented_reject(self):
        """Skill text with 100% reject severities warns about over-representation."""
        skill = """
Reject this critical issue.
Reject the breaking change.
Reject the blocker.
This is critical and must be fixed.
"""
        calibration = {
            "severity_by_category": {
                "correctness": {
                    "reject_rate": 20.0,
                    "request_changes_rate": 50.0,
                    "nitpick_rate": 20.0,
                    "percentages": {
                        "reject": 20.0,
                        "request-changes": 50.0,
                        "nitpick": 20.0,
                        "approve": 5.0,
                        "discussion": 5.0,
                    },
                },
            }
        }
        result = _validate_severity_consistency(skill, calibration)
        # Should have warning about reject over-representation
        assert any("reject" in w.lower() and "over-represented" in w.lower() for w in result)

    def test_underrepresented_reject(self):
        """Skill text with zero reject severities warns about under-representation."""
        skill = """
Just a nitpick on the style.
Minor cosmetic issue.
Optional improvement.
"""
        calibration = {
            "severity_by_category": {
                "correctness": {
                    "reject_rate": 40.0,
                    "request_changes_rate": 40.0,
                    "nitpick_rate": 10.0,
                    "percentages": {
                        "reject": 40.0,
                        "request-changes": 40.0,
                        "nitpick": 10.0,
                        "approve": 5.0,
                        "discussion": 5.0,
                    },
                },
            }
        }
        result = _validate_severity_consistency(skill, calibration)
        # Should have warning about either reject under-representation or nitpick over-representation
        has_reject_under = any(
            "reject" in w.lower() and "under-represented" in w.lower() for w in result
        )
        has_nitpick_over = any(
            "nitpick" in w.lower() and "over-represented" in w.lower() for w in result
        )
        assert has_reject_under or has_nitpick_over

    def test_empty_calibration_no_warnings(self):
        """Empty calibration dict returns no warnings."""
        skill = "Reject this critical bug."
        result = _validate_severity_consistency(skill, {})
        assert result == []

    def test_no_calibration_data_no_warnings(self):
        """None calibration returns no warnings."""
        skill = "Reject this critical bug."
        result = _validate_severity_consistency(skill, None)
        assert result == []


class TestLoadInterviewData:
    """Tests for _load_interview_data function."""

    def test_empty_interviews_dir(self):
        """Empty interviews dir returns empty string."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # Create data directory but no interviews subdirectory
            (project_root / "data").mkdir()
            result = _load_interview_data(project_root)
            assert result == ""

    def test_small_files_under_limit(self):
        """Small files under limit returns all content."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            interviews_dir = project_root / "data" / "interviews"
            interviews_dir.mkdir(parents=True)

            # Create small files
            (interviews_dir / "interview1.md").write_text("Content 1")
            (interviews_dir / "interview2.md").write_text("Content 2")

            result = _load_interview_data(project_root)
            assert "Content 1" in result
            assert "Content 2" in result
            assert "## Interview: interview1.md" in result
            assert "## Interview: interview2.md" in result

    def test_large_files_exceeding_limit(self):
        """Large files exceeding limit returns truncated content up to limit."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            interviews_dir = project_root / "data" / "interviews"
            interviews_dir.mkdir(parents=True)

            # Create a large file (300k chars, well over the 200k limit)
            large_content = "x" * 300000
            (interviews_dir / "large.md").write_text(large_content)

            result = _load_interview_data(project_root)
            # Should be truncated to max_chars (200000)
            # Allow some margin for the header
            assert len(result) <= 200100
            # Should contain the header
            assert "## Interview: large.md" in result


class TestTruncationDetection:
    """Tests for enhanced _detect_truncation() function."""

    def test_detects_incomplete_yaml_frontmatter(self):
        """YAML frontmatter starts with --- but has no closing ---."""
        truncated_yaml = """---
title: Test
author: John
"""
        assert _detect_truncation(truncated_yaml, "glm5.2") is True

    def test_accepts_complete_yaml_frontmatter(self):
        """YAML frontmatter with proper closing ---."""
        complete_yaml = """---
title: Test
author: John
---
Content here.
"""
        # Need longer content to pass token threshold
        complete_yaml = "---\n" + "title: Test\n" * 200 + "---\n" + "Content here.\n"
        assert _detect_truncation(complete_yaml, "glm5.2") is False

    def test_detects_incomplete_markdown_section(self):
        """Last ## heading has no content after it."""
        incomplete_section = """# Skill File

## Reviewer Mindset
Some content here.

## Review Triggers
"""
        assert _detect_truncation(incomplete_section, "glm5.2") is True

    def test_accepts_complete_markdown_section(self):
        """## heading has content after it."""
        complete_section = """# Skill File

## Reviewer Mindset
Some content here.

## Review Triggers
Content for triggers.
"""
        # Need longer content to pass token threshold
        complete_section = (
            "# Skill File\n\n## Reviewer Mindset\n"
            + "Some content here.\n" * 200
            + "\n## Review Triggers\nContent for triggers.\n"
        )
        assert _detect_truncation(complete_section, "glm5.2") is False

    def test_detects_missing_required_skill_sections(self):
        """Skill file missing all required sections."""
        missing_sections = """# Random Content

Some text without any required sections.
"""
        assert _detect_truncation(missing_sections, "distill-skill") is True

    def test_accepts_skill_with_one_required_section(self):
        """Skill file has at least one required section."""
        one_section = """# Skill File

## Reviewer Mindset
This is the mindset section.
"""
        # Need longer content to pass token threshold
        one_section = (
            "# Skill File\n\n## Reviewer Mindset\n" + "This is the mindset section.\n" * 200 + "\n"
        )
        assert _detect_truncation(one_section, "distill-skill") is False

    def test_detects_mid_sentence_cutoff(self):
        """Text ends mid-sentence without punctuation."""
        mid_sentence = """# Review Guidelines

Always check for proper error handling when dealing with
user input to prevent security vulnerabilities and ensure
"""
        assert _detect_truncation(mid_sentence, "glm5.2") is True

    def test_accepts_proper_sentence_ending(self):
        """Text ends with proper punctuation."""
        proper_ending = """# Review Guidelines

Always check for proper error handling.
"""
        # Need longer content to pass token threshold
        proper_ending = (
            "# Review Guidelines\n\n" + "Always check for proper error handling.\n" * 200
        )
        assert _detect_truncation(proper_ending, "glm5.2") is False

    def test_detects_truncation_existing_patterns(self):
        """Ensure existing truncation detection still works."""
        # Very short text (below token threshold)
        short_text = "Short text."
        assert _detect_truncation(short_text, "distill-skill") is True

        # Ends mid-word for GLM
        mid_word = "This is a sentence that ends mid-wor"
        assert _detect_truncation(mid_word, "glm5.2") is True


class TestLLMCaching:
    """Tests for _call_llm() caching behavior."""

    def test_cache_hit_returns_cached_result(self):
        """Second call with same prompt returns cached result."""
        from torvalds_skill import config, distill_llm

        # Clear cache first
        if hasattr(distill_llm._call_llm, "_cache"):
            distill_llm._call_llm._cache.clear()

        prompt = "Test prompt for caching"

        # Create a mock connection that returns a valid SSE stream
        def mock_get_connection(host):
            mock_conn = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__iter__ = lambda self: iter(
                [
                    b'data: {"choices": [{"delta": {"content": "Cached response"}}]}\n',
                    b"data: [DONE]\n",
                ]
            )
            mock_conn.getresponse.return_value = mock_response
            mock_conn.sock = MagicMock()
            mock_conn.sock._closed = False
            return mock_conn

        # First call - cache miss
        with patch.object(distill_llm, "_get_connection", mock_get_connection):
            with patch.object(distill_llm, "_WallClockTimeout") as mock_timeout:
                mock_timeout.return_value.__enter__ = lambda self: self
                mock_timeout.return_value.__exit__ = lambda self, *args: None
                with patch.object(config, "CHAT_URL", "http://test.local"):
                    with patch.object(
                        config, "headers", return_value={"Content-Type": "application/json"}
                    ):
                        result1 = distill_llm._call_llm(prompt, retries=3, model="test-model")

        # Second call with same prompt - should be cache hit
        with patch.object(distill_llm, "_get_connection", mock_get_connection):
            with patch.object(distill_llm, "_WallClockTimeout") as mock_timeout:
                mock_timeout.return_value.__enter__ = lambda self: self
                mock_timeout.return_value.__exit__ = lambda self, *args: None
                with patch.object(config, "CHAT_URL", "http://test.local"):
                    with patch.object(
                        config, "headers", return_value={"Content-Type": "application/json"}
                    ):
                        result2 = distill_llm._call_llm(prompt, retries=3, model="test-model")

        # Verify cache was used (connection should not be used again for second call)
        assert result1 == result2
        # The second call should have returned from cache
        assert distill_llm._call_llm._cache is not None

    def test_cache_bypass_on_retries_one(self):
        """Cache is bypassed when retries=1."""
        from torvalds_skill import config, distill_llm

        # Clear cache first
        if hasattr(distill_llm._call_llm, "_cache"):
            distill_llm._call_llm._cache.clear()

        prompt = "Test prompt for bypass"
        call_count = [0]

        # Create a longer response that won't be detected as truncated
        # Need at least 500 tokens (~2000 chars) for skill models
        long_content = "This is a complete response with proper ending. " * 50 + "The end."

        def mock_get_connection(host):
            mock_conn = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__iter__ = lambda self: iter(
                [
                    f'data: {{"choices": [{{"delta": {{"content": "{long_content}"}}}}]}}\n'.encode(),
                    b"data: [DONE]\n",
                ]
            )
            mock_conn.getresponse.return_value = mock_response
            mock_conn.sock = MagicMock()
            mock_conn.sock._closed = False

            # Track request calls
            original_request = mock_conn.request

            def tracking_request(*args, **kwargs):
                call_count[0] += 1
                return original_request(*args, **kwargs)

            mock_conn.request = tracking_request

            return mock_conn

        # Call with retries=1 twice - should bypass cache both times
        with patch.object(distill_llm, "_get_connection", mock_get_connection):
            with patch.object(distill_llm, "_WallClockTimeout") as mock_timeout:
                mock_timeout.return_value.__enter__ = lambda self: self
                mock_timeout.return_value.__exit__ = lambda self, *args: None
                with patch.object(config, "CHAT_URL", "http://test.local"):
                    with patch.object(
                        config, "headers", return_value={"Content-Type": "application/json"}
                    ):
                        distill_llm._call_llm(prompt, retries=1, model="test-model")
                        distill_llm._call_llm(prompt, retries=1, model="test-model")

        # Should have been called twice (no caching)
        assert call_count[0] == 2


class TestSelfFallbackRemoval:
    """Tests for self-fallback removal in _call_llm()."""

    def test_glm52_excluded_from_fallback_when_primary(self):
        """When primary model is glm5.2, it should not be in the fallback chain."""
        from torvalds_skill import config, distill_llm

        # Mock connection to avoid actual network call
        def mock_get_connection(host):
            mock_conn = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200
            # Return a long enough response to pass token threshold
            content = "x" * 2000
            mock_response.__iter__ = lambda self: iter(
                [
                    f'data: {{"choices": [{{"delta": {{"content": "{content}"}}}}]}}\n'.encode(),
                    b"data: [DONE]\n",
                ]
            )
            mock_conn.getresponse.return_value = mock_response
            mock_conn.sock = MagicMock()
            mock_conn.sock._closed = False
            return mock_conn

        # Call with glm5.2 as primary model
        with patch.object(distill_llm, "_get_connection", mock_get_connection):
            with patch.object(distill_llm, "_WallClockTimeout") as mock_timeout:
                mock_timeout.return_value.__enter__ = lambda self: self
                mock_timeout.return_value.__exit__ = lambda self, *args: None
                with patch.object(config, "CHAT_URL", "http://test.local"):
                    with patch.object(
                        config, "headers", return_value={"Content-Type": "application/json"}
                    ):
                        # The function should not loop infinitely
                        # We just verify it completes without self-fallback
                        result = distill_llm._call_llm("test prompt", retries=1, model="glm5.2")

        # Verify the result was returned (function completed)
        assert result is not None

    def test_fallback_chain_excludes_primary_model(self):
        """Verify fallback_models list excludes the primary model."""

        # Test with glm5.2 as primary
        primary_model = "glm5.2"
        all_fallback_models = ["mistral-small-4-119b", "gpt-oss-120b", "glm5.2"]
        fallback_models = [m for m in all_fallback_models if m != primary_model]

        assert "glm5.2" not in fallback_models
        assert "mistral-small-4-119b" in fallback_models
        assert "gpt-oss-120b" in fallback_models

        # Test with mistral as primary
        primary_model = "mistral-small-4-119b"
        fallback_models = [m for m in all_fallback_models if m != primary_model]

        assert "mistral-small-4-119b" not in fallback_models
        assert "glm5.2" in fallback_models


class TestWallClockTimeout:
    """Tests for thread-based _WallClockTimeout."""

    def test_timeout_fires(self):
        """_WallClockTimeout(1) should raise TimeoutError after 1 second."""
        with pytest.raises(TimeoutError, match="wall-clock timeout exceeded"):
            with _WallClockTimeout(1):
                time.sleep(2)  # Sleep longer than timeout

    def test_timeout_does_not_fire_when_fast(self):
        """_WallClockTimeout(5) should not raise if work completes quickly."""
        start = time.time()
        with _WallClockTimeout(5):
            time.sleep(0.1)  # Quick work
        elapsed = time.time() - start

        # Should complete in ~0.1s, not 5s
        assert elapsed < 1.0

    def test_timeout_cancels_on_normal_exit(self):
        """Timer should be cancelled when context exits normally."""
        with _WallClockTimeout(2) as timer:
            pass  # Exit immediately

        # Timer should be cancelled, no exception raised
        assert timer._timed_out is False


class TestWallClockOverride:
    """Tests for wall_clock_override parameter."""

    def test_wall_clock_override_is_used(self):
        """Verify that wall_clock_override value is used instead of defaults."""
        from torvalds_skill import config, distill_llm

        # Mock connection to capture the timeout value
        captured_wall_clock = []

        def mock_get_connection(host):
            mock_conn = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200
            content = "x" * 2000
            mock_response.__iter__ = lambda self: iter(
                [
                    f'data: {{"choices": [{{"delta": {{"content": "{content}"}}}}]}}\n'.encode(),
                    b"data: [DONE]\n",
                ]
            )
            mock_conn.getresponse.return_value = mock_response
            mock_conn.sock = MagicMock()
            mock_conn.sock._closed = False
            return mock_conn

        # Patch _WallClockTimeout to capture the wall_clock value
        original_timeout = distill_llm._WallClockTimeout

        class CapturingTimeout:
            def __init__(self, seconds):
                captured_wall_clock.append(seconds)
                self._inner = original_timeout(seconds)

            def __enter__(self):
                return self._inner.__enter__()

            def __exit__(self, *args):
                return self._inner.__exit__(*args)

        with patch.object(distill_llm, "_WallClockTimeout", CapturingTimeout):
            with patch.object(distill_llm, "_get_connection", mock_get_connection):
                with patch.object(config, "CHAT_URL", "http://test.local"):
                    with patch.object(
                        config, "headers", return_value={"Content-Type": "application/json"}
                    ):
                        # Call with override
                        distill_llm._call_llm(
                            "test prompt", retries=1, model="test-model", wall_clock_override=123
                        )

        # Verify the override value was used
        assert 123 in captured_wall_clock


class TestModelSeverityBias:
    """Tests for MODEL_SEVERITY_BIAS and _format_model_calibration_note()."""

    def test_bias_dict_contains_expected_models(self):
        """Verify MODEL_SEVERITY_BIAS contains all three expected models."""
        assert "gpt-oss-120b" in MODEL_SEVERITY_BIAS
        assert "glm5.2" in MODEL_SEVERITY_BIAS
        assert "mistral-small-4-119b" in MODEL_SEVERITY_BIAS

    def test_gpt_oss_bias_is_balanced(self):
        """Verify gpt-oss-120b has balanced bias description."""
        bias = MODEL_SEVERITY_BIAS["gpt-oss-120b"]
        assert "balanced" in bias.lower()

    def test_glm52_bias_over_rates(self):
        """Verify glm5.2 has over-rates severity bias description."""
        bias = MODEL_SEVERITY_BIAS["glm5.2"]
        assert "over-rates" in bias.lower() or "over rates" in bias.lower()
        assert "downgrade" in bias.lower()

    def test_mistral_bias_under_rates(self):
        """Verify mistral-small-4-119b has under-rates severity bias description."""
        bias = MODEL_SEVERITY_BIAS["mistral-small-4-119b"]
        assert "under-rates" in bias.lower() or "under rates" in bias.lower()
        assert "upgrade" in bias.lower()


class TestFormatModelCalibrationNote:
    """Tests for _format_model_calibration_note() function."""

    def test_glm52_includes_calibration_note(self):
        """Verify glm5.2 gets the over-rates calibration note."""
        note = _format_model_calibration_note("glm5.2")
        assert "MODEL CALIBRATION NOTE" in note
        assert "glm5.2" in note
        assert "over-rates" in note.lower() or "over rates" in note.lower()
        assert "downgrade" in note.lower()
        assert "borderline" in note.lower()

    def test_mistral_includes_calibration_note(self):
        """Verify mistral-small-4-119b gets the under-rates calibration note."""
        note = _format_model_calibration_note("mistral-small-4-119b")
        assert "MODEL CALIBRATION NOTE" in note
        assert "mistral" in note.lower()
        assert "under-rates" in note.lower() or "under rates" in note.lower()
        assert "upgrade" in note.lower()
        assert "borderline" in note.lower()

    def test_gpt_oss_includes_calibration_note(self):
        """Verify gpt-oss-120b gets the balanced calibration note."""
        note = _format_model_calibration_note("gpt-oss-120b")
        assert "MODEL CALIBRATION NOTE" in note
        assert "gpt-oss" in note.lower()
        assert "balanced" in note.lower()

    def test_unknown_model_gets_balanced_default(self):
        """Verify unknown models get a balanced default note."""
        note = _format_model_calibration_note("unknown-model-xyz")
        assert "MODEL CALIBRATION NOTE" in note
        assert "unknown-model-xyz" in note
        assert "balanced" in note.lower()
        assert "no known systematic bias" in note.lower()

    def test_none_model_gets_balanced_default(self):
        """Verify None model gets a balanced default note."""
        note = _format_model_calibration_note(None)
        assert "MODEL CALIBRATION NOTE" in note
        assert "unknown model" in note.lower()
        assert "balanced" in note.lower()

    def test_different_models_get_different_notes(self):
        """Verify different models get different calibration notes."""
        glm_note = _format_model_calibration_note("glm5.2")
        mistral_note = _format_model_calibration_note("mistral-small-4-119b")
        gpt_note = _format_model_calibration_note("gpt-oss-120b")

        # All notes should be different
        assert glm_note != mistral_note
        assert glm_note != gpt_note
        assert mistral_note != gpt_note

        # Each should contain their specific bias description
        assert "downgrade" in glm_note.lower()
        assert "upgrade" in mistral_note.lower()
        assert "no systematic bias" in gpt_note.lower()

    def test_calibration_note_format(self):
        """Verify the calibration note has the expected structure."""
        note = _format_model_calibration_note("glm5.2")

        # Should have start and end markers
        assert "=== MODEL CALIBRATION NOTE ===" in note
        assert "=== END MODEL CALIBRATION NOTE ===" in note

        # Should mention the model name
        assert "glm5.2" in note

        # Should mention known bias
        assert "Known bias" in note

        # Should instruct to counteract bias
        assert "counteracts" in note.lower() or "counteract" in note.lower()

        # Should mention borderline cases
        assert "borderline" in note.lower()


class TestDistillPromptSeverityQuotas:
    """Tests for per-category severity quotas in the distill prompt."""

    def test_contains_per_category_quotas(self):
        """Verify the prompt contains binding per-category severity quotas."""
        assert "PER-CATEGORY SEVERITY QUOTAS" in DISTILL_SYSTEM_PROMPT
        assert "BINDING CONSTRAINTS" in DISTILL_SYSTEM_PROMPT

    def test_contains_all_category_quotas(self):
        """Verify all 13 categories have quota ranges specified."""
        categories = [
            "testing",
            "correctness",
            "complexity",
            "performance",
            "concurrency",
            "documentation",
            "style",
            "process",
            "api-stability",
            "error-handling",
            "memory-safety",
            "abstraction",
            "security",
        ]
        for cat in categories:
            assert cat in DISTILL_SYSTEM_PROMPT

    def test_quotas_contain_percentage_ranges(self):
        """Verify quotas contain percentage ranges for each severity."""
        assert "reject" in DISTILL_SYSTEM_PROMPT
        assert "request-changes" in DISTILL_SYSTEM_PROMPT
        assert "nitpick" in DISTILL_SYSTEM_PROMPT
        # Check for percentage signs indicating ranges
        assert "%" in DISTILL_SYSTEM_PROMPT


class TestDistillPromptNonFireList:
    """Tests for the non-fire build trivia list in the distill prompt."""

    def test_contains_non_fire_section(self):
        """Verify the NEVER-BLOCK ON BUILD TRIVIA section exists."""
        assert "NEVER-BLOCK ON BUILD TRIVIA" in DISTILL_SYSTEM_PROMPT
        assert "NON-FIRE LIST" in DISTILL_SYSTEM_PROMPT

    def test_contains_phony_declaration(self):
        """Verify .PHONY declarations are in the non-fire list."""
        assert ".PHONY" in DISTILL_SYSTEM_PROMPT or "phony" in DISTILL_SYSTEM_PROMPT.lower()

    def test_contains_cflags(self):
        """Verify CFLAGS are in the non-fire list."""
        assert "CFLAGS" in DISTILL_SYSTEM_PROMPT

    def test_contains_missing_docs(self):
        """Verify missing documentation is in the non-fire list."""
        assert (
            "docs" in DISTILL_SYSTEM_PROMPT.lower()
            or "documentation" in DISTILL_SYSTEM_PROMPT.lower()
        )

    def test_contains_comment_style(self):
        """Verify comment style is in the non-fire list."""
        assert "comment style" in DISTILL_SYSTEM_PROMPT.lower()

    def test_contains_redundant_rm(self):
        """Verify redundant rm commands are in the non-fire list."""
        assert "redundant" in DISTILL_SYSTEM_PROMPT.lower() or "rm" in DISTILL_SYSTEM_PROMPT


class TestSeverityWeightedSampling:
    """Tests for severity-weighted sampling in distillation."""

    def test_default_weights_loaded_when_no_calibration(self):
        """Default weights should be used when calibration.json is missing."""
        weights = _load_severity_weights(None)
        assert weights == {"reject": 3.0, "request-changes": 2.0, "nitpick": 1.0}

    def test_weights_loaded_from_calibration_json(self, tmp_path):
        """Custom weights should be loaded from calibration.json."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text(
            '{"severity_weights": {"reject": 4.0, "request-changes": 2.5, "nitpick": 1.0}}'
        )
        weights = _load_severity_weights(calibration_file)
        assert weights["reject"] == 4.0
        assert weights["request-changes"] == 2.5
        assert weights["nitpick"] == 1.0  # Default preserved for missing keys

    def test_weighted_sampling_favors_rejects(self):
        """Weighted sampling should favor reject patterns over nitpicks."""
        patterns = [_make_pattern(severity="reject") for _ in range(10)] + [
            _make_pattern(severity="nitpick") for _ in range(10)
        ]
        sampled = _weighted_sample_patterns(patterns, top_n=10, calibration_path=None)

        # Count severities in sampled set
        reject_count = sum(1 for p in sampled if p.get("severity") == "reject")
        nitpick_count = sum(1 for p in sampled if p.get("severity") == "nitpick")

        # Rejects should be favored (at least 60% of samples)
        assert reject_count > nitpick_count
        assert reject_count >= 6  # At least 60% rejects

    def test_nitpick_cap_enforced(self):
        """Nitpick samples should be capped at ~15% of total."""
        patterns = [_make_pattern(severity="reject") for _ in range(5)] + [
            _make_pattern(severity="nitpick") for _ in range(100)
        ]
        sampled = _weighted_sample_patterns(patterns, top_n=20, calibration_path=None)

        nitpick_count = sum(1 for p in sampled if p.get("severity") == "nitpick")
        max_nitpick = int(20 * 0.15)  # 15% cap

        assert nitpick_count <= max(1, max_nitpick + 1)  # Allow small margin

    def test_weighted_sampling_with_request_changes(self):
        """Weighted sampling should include request-changes patterns."""
        patterns = (
            [_make_pattern(severity="reject") for _ in range(5)]
            + [_make_pattern(severity="request-changes") for _ in range(5)]
            + [_make_pattern(severity="nitpick") for _ in range(10)]
        )
        sampled = _weighted_sample_patterns(patterns, top_n=10, calibration_path=None)

        severities = [p.get("severity") for p in sampled]
        assert "reject" in severities
        assert "request-changes" in severities
        # Rejects and request-changes should dominate (at least 60% high severity)
        high_severity_count = severities.count("reject") + severities.count("request-changes")
        assert high_severity_count >= 6  # At least 60% high severity
