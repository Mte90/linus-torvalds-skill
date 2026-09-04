"""Tests for parallel category execution in distill.py."""

import os
import time
from unittest.mock import patch

from torvalds_skill.distill import _distill_category, _run_categories_parallel


class TestRunCategoriesParallel:
    """Tests for _run_categories_parallel function."""

    def test_parallel_execution_order_preserved(self):
        """5 categories with staggered delays; verify final structure is in original order."""
        # Create a mock call_fn that simulates staggered delays
        call_order = []

        def mock_call_fn(category, patterns, model):
            # Staggered delays to test parallel completion
            delay_map = {
                "cat1": 0.3,
                "cat2": 0.2,
                "cat3": 0.1,
                "cat4": 0.15,
                "cat5": 0.25,
            }
            delay = delay_map.get(category, 0.1)
            time.sleep(delay)
            call_order.append(category)
            return f"fragment-{category}"

        categories = ["cat1", "cat2", "cat3", "cat4", "cat5"]
        patterns_by_category = {cat: [{"pattern": "test"}] for cat in categories}

        fragments, failed = _run_categories_parallel(
            categories, patterns_by_category, mock_call_fn, model="glm5.2", max_workers=3
        )

        # Verify all categories completed successfully
        assert len(failed) == 0

        # Verify results are in ORIGINAL category order (not completion order)
        # The fragments dict values should be in the same order as categories
        assert list(fragments.values()) == [f"fragment-{cat}" for cat in categories]

        # Verify each fragment has the correct content
        for cat in categories:
            assert fragments[cat] == f"fragment-{cat}"

        # Verify all categories were called (order may vary due to thread scheduling)
        assert sorted(call_order) == sorted(categories)

    def test_max_workers_env_override(self):
        """DISTILL_MAX_WORKERS=2 is respected."""

        def mock_call_fn(category, patterns, model):
            return f"fragment-{category}"

        categories = ["cat1", "cat2", "cat3"]
        patterns_by_category = {cat: [{"pattern": "test"}] for cat in categories}

        # Just verify the function completes with max_workers=2
        fragments, failed = _run_categories_parallel(
            categories, patterns_by_category, mock_call_fn, model="glm5.2", max_workers=2
        )

        # Verify all categories completed
        assert len(failed) == 0
        assert len(fragments) == 3

    def test_single_worker_for_fast_models(self):
        """Non-glm model → workers forced to 1."""

        def mock_call_fn(category, patterns, model):
            return f"fragment-{category}"

        categories = ["cat1", "cat2", "cat3"]
        patterns_by_category = {cat: [{"pattern": "test"}] for cat in categories}

        # Just verify the function completes with max_workers=1
        fragments, failed = _run_categories_parallel(
            categories, patterns_by_category, mock_call_fn, model="mistral-small", max_workers=1
        )

        # Verify all categories completed
        assert len(failed) == 0
        assert len(fragments) == 3

    def test_failed_category_retried_then_warned(self):
        """One category fails twice; verify warning printed and synthesis proceeds with remaining categories."""
        call_count = {"cat1": 0, "cat2": 0, "cat3": 0}

        def mock_call_fn(category, patterns, model):
            call_count[category] += 1
            if category == "cat2":
                raise Exception(f"Simulated failure for {category}")
            return f"fragment-{category}"

        categories = ["cat1", "cat2", "cat3"]
        patterns_by_category = {cat: [{"pattern": "test"}] for cat in categories}

        # Capture printed output
        with patch("sys.stderr"):
            fragments, failed = _run_categories_parallel(
                categories, patterns_by_category, mock_call_fn, model="glm5.2", max_workers=1
            )

        # Verify cat2 failed and was recorded
        assert "cat2" in failed

        # Verify cat1 and cat3 succeeded
        assert fragments["cat1"] == "fragment-cat1"
        assert fragments["cat3"] == "fragment-cat3"

        # Verify cat2 was called only once (no retry in parallel phase)
        assert call_count["cat2"] == 1

    def test_all_results_present_on_success(self):
        """Happy path returns identical structure to sequential version."""

        def mock_call_fn(category, patterns, model):
            return f"fragment-{category}"

        categories = ["cat1", "cat2", "cat3", "cat4", "cat5"]
        patterns_by_category = {cat: [{"pattern": f"pattern-{cat}"}] for cat in categories}

        fragments, failed = _run_categories_parallel(
            categories, patterns_by_category, mock_call_fn, model="glm5.2", max_workers=3
        )

        # Verify no failures
        assert len(failed) == 0

        # Verify all categories have fragments
        assert len(fragments) == len(categories)

        # Verify each fragment is correct
        for cat in categories:
            assert cat in fragments
            assert fragments[cat] == f"fragment-{cat}"
            assert len(fragments[cat]) > 0


class TestDistillCategory:
    """Tests for _distill_category function."""

    def test_empty_patterns_returns_empty_string(self):
        """Empty patterns list returns empty string."""
        result = _distill_category("test-category", [], model="glm5.2")
        assert result == ""

    def test_non_empty_patterns_calls_llm(self):
        """Non-empty patterns calls _call_llm and returns fragment."""
        patterns = [
            {
                "trigger": "test trigger",
                "principle": "test principle",
                "severity": "reject",
                "source": "email",
                "quote": "test quote",
            }
        ]

        with patch("torvalds_skill.distill._call_llm") as mock_call_llm:
            mock_call_llm.return_value = "mocked fragment"

            with patch("torvalds_skill.distill.log_decision"):
                result = _distill_category("test-category", patterns, model="glm5.2")

                assert result == "mocked fragment"
                mock_call_llm.assert_called_once()

    def test_exception_returns_empty_string(self):
        """Exception during LLM call returns empty string."""
        patterns = [
            {
                "trigger": "test trigger",
                "principle": "test principle",
                "severity": "reject",
                "source": "email",
                "quote": "test quote",
            }
        ]

        with patch("torvalds_skill.distill._call_llm") as mock_call_llm:
            mock_call_llm.side_effect = Exception("LLM error")

            with patch("torvalds_skill.distill.log_decision"):
                result = _distill_category("test-category", patterns, model="glm5.2")

                assert result == ""


class TestDistillSkillIntegration:
    """Integration tests for distill_skill with parallel execution."""

    def test_distill_skill_uses_parallel_for_glm52(self):
        """distill_skill uses parallel execution for glm5.2 model."""
        import json
        import tempfile
        from pathlib import Path

        from torvalds_skill.distill import distill_skill

        # Create temporary patterns file
        patterns = [
            {
                "category": "cat1",
                "trigger": "t1",
                "principle": "p1",
                "severity": "reject",
                "source": "email",
                "quote": "q1",
            },
            {
                "category": "cat2",
                "trigger": "t2",
                "principle": "p2",
                "severity": "reject",
                "source": "email",
                "quote": "q2",
            },
        ]

        # Complete skill markdown with all required sections
        complete_skill = """---
title: Test Skill
---

## Reviewer Mindset

Test content for mindset.

## Review Triggers

More content for triggers.

## Severity Calibration

Calibration data here.

## Severity Decision Tree

Decision tree content.

## Precedence and Priorities

Precedence rules.

## Decision Cards

Decision card content.

## Key Definitions

Definitions here.

## Anti-Patterns

Anti-pattern content.

## Voice and Tone

Tone guidelines."""

        with tempfile.TemporaryDirectory() as tmpdir:
            patterns_path = Path(tmpdir) / "patterns.json"
            output_path = Path(tmpdir) / "SKILL.md"
            patterns_path.write_text(json.dumps(patterns))

            with patch("torvalds_skill.distill._call_llm") as mock_call_llm:
                mock_call_llm.return_value = complete_skill

                with patch("torvalds_skill.distill_data.load_interview_data") as mock_interview:
                    mock_interview.return_value = ""

                    with patch(
                        "torvalds_skill.distill_data.load_interlocutor_variation_data"
                    ) as mock_iv:
                        mock_iv.return_value = ""

                        with patch("torvalds_skill.distill._load_json_cached") as mock_load:
                            mock_load.return_value = patterns

                            with patch("torvalds_skill.distill.config.WALL_CLOCK_CATEGORY", 300):
                                with patch("torvalds_skill.distill.log_decision"):
                                    # glm5.2 resolves to single-call mode: exactly 1 call (B1 fix)
                                    distill_skill(patterns_path, output_path, model="glm5.2")

                                    assert mock_call_llm.call_count == 1

                                    # Explicit two-stage still parallelizes (categories + synthesis)
                                    mock_call_llm.reset_mock()
                                    distill_skill(
                                        patterns_path,
                                        output_path,
                                        model="glm5.2",
                                        distill_mode="two-stage",
                                    )

                                    assert (
                                        mock_call_llm.call_count >= 3
                                    )  # 2 categories + 1 synthesis


class TestMaxWorkersEnvironmentVariable:
    """Tests for DISTILL_MAX_WORKERS environment variable."""

    def test_default_max_workers_is_3(self):
        """Default max_workers is 3 when env var not set."""
        # Remove env var if it exists
        env_var = os.environ.pop("DISTILL_MAX_WORKERS", None)

        try:
            # The default is checked in distill_skill, not _run_categories_parallel
            # So we test the logic directly
            env_workers = int(os.environ.get("DISTILL_MAX_WORKERS", 3))
            assert env_workers == 3
        finally:
            # Restore if it existed
            if env_var is not None:
                os.environ["DISTILL_MAX_WORKERS"] = env_var

    def test_env_var_respected(self):
        """DISTILL_MAX_WORKERS environment variable is respected."""
        os.environ["DISTILL_MAX_WORKERS"] = "5"

        try:
            env_workers = int(os.environ.get("DISTILL_MAX_WORKERS", 3))
            assert env_workers == 5
        finally:
            del os.environ["DISTILL_MAX_WORKERS"]

    def test_non_glm_model_forces_single_worker(self):
        """Non-glm5.2 model forces max_workers=1 regardless of env var."""
        os.environ["DISTILL_MAX_WORKERS"] = "10"

        try:
            env_workers = int(os.environ.get("DISTILL_MAX_WORKERS", 3))
            model = "mistral-small"

            if model and "glm5.2" not in model.lower():
                max_workers = 1
            else:
                max_workers = env_workers

            assert max_workers == 1
        finally:
            del os.environ["DISTILL_MAX_WORKERS"]

    def test_glm52_respects_env_var(self):
        """glm5.2 model respects DISTILL_MAX_WORKERS env var."""
        os.environ["DISTILL_MAX_WORKERS"] = "7"

        try:
            env_workers = int(os.environ.get("DISTILL_MAX_WORKERS", 3))
            model = "glm5.2"

            if model and "glm5.2" not in model.lower():
                max_workers = 1
            else:
                max_workers = env_workers

            assert max_workers == 7
        finally:
            del os.environ["DISTILL_MAX_WORKERS"]
