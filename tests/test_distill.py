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


def _make_data(
    total_moves: int = 100,
    categories: dict | None = None,
    severity_distribution: dict | None = None,
    samples_by_category: dict | None = None,
) -> dict:
    return {
        "total_moves": total_moves,
        "categories": categories or {"testing": 50, "correctness": 50},
        "severity_distribution": severity_distribution or {"reject": 50, "approve": 50},
        "samples_by_category": samples_by_category or {},
    }


def _make_sample(
    trigger: str = "untested code",
    principle: str = "require tests",
    response: str = "add tests before merging",
    severity: str = "reject",
    date: str = "2020-01-01",
) -> dict:
    return {
        "trigger": trigger,
        "principle": principle,
        "response": response,
        "severity": severity,
        "date": date,
    }


class TestFormatMovesForPrompt:
    def test_includes_corpus_statistics(self):
        data = _make_data(
            total_moves=5000,
            categories={"testing": 3000, "correctness": 2000},
            severity_distribution={"reject": 2500, "approve": 2500},
        )
        result = _format_moves_for_prompt(data)
        assert "5000" in result
        assert "3000" in result
        assert "2500" in result

    def test_includes_total_sample_count(self):
        data = _make_data(
            samples_by_category={
                "testing": [_make_sample() for _ in range(15)],
                "correctness": [_make_sample() for _ in range(10)],
            }
        )
        result = _format_moves_for_prompt(data)
        assert "25 representative review moves" in result

    def test_formats_each_category_header(self):
        data = _make_data(
            samples_by_category={
                "testing": [_make_sample()],
                "correctness": [_make_sample()],
            }
        )
        result = _format_moves_for_prompt(data)
        assert "## Category: testing (1 samples)" in result
        assert "## Category: correctness (1 samples)" in result

    def test_formats_each_move_with_all_fields(self):
        sample = _make_sample(
            trigger="broken userspace",
            principle="never break userspace",
            response="this breaks existing setups",
            severity="reject",
            date="2015-06-01",
        )
        data = _make_data(samples_by_category={"testing": [sample]})
        result = _format_moves_for_prompt(data)
        assert "Trigger: broken userspace" in result
        assert "Principle: never break userspace" in result
        assert "Severity: reject" in result
        assert "Date: 2015-06-01" in result
        assert 'Response (Torvalds\' words): "this breaks existing setups"' in result

    def test_handles_empty_samples(self):
        data = _make_data(samples_by_category={})
        result = _format_moves_for_prompt(data)
        assert "0 representative review moves" in result

    def test_includes_instructions_for_llm(self):
        data = _make_data()
        result = _format_moves_for_prompt(data)
        assert "THEMES" in result or "themes" in result
        assert "synthesize" in result

    def test_quotes_response_text(self):
        sample = _make_sample(response='say "no" firmly')
        data = _make_data(samples_by_category={"testing": [sample]})
        result = _format_moves_for_prompt(data)
        assert '"say "no" firmly"' in result

    def test_numbers_moves_within_category(self):
        samples = [_make_sample(trigger=f"t{i}") for i in range(5)]
        data = _make_data(samples_by_category={"testing": samples})
        result = _format_moves_for_prompt(data)
        for i in range(1, 6):
            assert f"### Move {i}" in result

    def test_preserves_category_order(self):
        data = _make_data(
            samples_by_category={
                "testing": [_make_sample(trigger="test-trigger")],
                "correctness": [_make_sample(trigger="correct-trigger")],
                "performance": [_make_sample(trigger="perf-trigger")],
            }
        )
        result = _format_moves_for_prompt(data)
        test_pos = result.index("test-trigger")
        correct_pos = result.index("correct-trigger")
        perf_pos = result.index("perf-trigger")
        # categories should appear in dict insertion order
        assert test_pos < correct_pos < perf_pos

    def test_large_corpus_formats_without_error(self):
        """Stress test: 200 samples (full run scale)."""
        samples = [
            _make_sample(
                trigger=f"trigger {i}",
                principle=f"principle {i}",
                response=f"response {i}" * 20,
                severity="reject",
                date=f"202{i % 10}-01-01",
            )
            for i in range(200)
        ]
        data = _make_data(
            total_moves=60000,
            categories={"testing": 30000, "correctness": 30000},
            samples_by_category={"testing": samples},
        )
        result = _format_moves_for_prompt(data)
        assert "200 representative review moves" in result
        assert len(result) > 10000  # substantial prompt
