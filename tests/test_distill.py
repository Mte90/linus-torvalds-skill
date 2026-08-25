"""Tests for distill.py prompt formatting.

Verifies the rewrite that changed distill from consuming pre-clustered
patterns to consuming samples_by_category (stratified raw moves).
The _format_moves_for_prompt function is pure and fully testable
without LLM access.
"""

import json
from pathlib import Path

import pytest

from torvalds_skill.distill import _format_moves_for_prompt
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
        patterns = [
            _make_pattern(category="testing") for _ in range(15)
        ] + [
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
        assert "[REASON]→[ACT]" in DISTILL_SYSTEM_PROMPT or "[REASON] -> [ACT]" in DISTILL_SYSTEM_PROMPT
    
    def test_reasoning_protocol_prevents_false_positives(self):
        """Verify the protocol mentions preventing pattern-matching false positives."""
        assert "pattern-matching" in DISTILL_SYSTEM_PROMPT
        # "false positives" may be split across lines due to line continuations
        assert "false" in DISTILL_SYSTEM_PROMPT.lower() and "positives" in DISTILL_SYSTEM_PROMPT.lower()


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