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