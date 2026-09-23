"""Tests for scripts/render_cross.py."""

import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.render_cross import (
    collect_cross_only_discoveries,
    collect_unmatched_findings,
    compute_cell_metrics,
    compute_marginal_means,
    group_results_by_pairing,
    load_jsonl,
    rank_by_verdict,
    render_markdown,
)


class TestLoadJsonl:
    """Tests for load_jsonl function."""

    def test_missing_file_returns_empty_list(self):
        result = load_jsonl(Path("/nonexistent/file.jsonl"))
        assert result == []

    def test_empty_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            tmp_path = Path(f.name)
        try:
            result = load_jsonl(tmp_path)
            assert result == []
        finally:
            tmp_path.unlink()

    def test_valid_jsonl_loads_records(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"id": 1}\n')
            f.write('{"id": 2}\n')
            f.write('{"id": 3}\n')
            tmp_path = Path(f.name)
        try:
            result = load_jsonl(tmp_path)
            assert len(result) == 3
            assert result[0]["id"] == 1
            assert result[2]["id"] == 3
        finally:
            tmp_path.unlink()

    def test_skips_malformed_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"id": 1}\n')
            f.write("not valid json\n")
            f.write('{"id": 2}\n')
            tmp_path = Path(f.name)
        try:
            result = load_jsonl(tmp_path)
            assert len(result) == 2
            assert result[0]["id"] == 1
            assert result[1]["id"] == 2
        finally:
            tmp_path.unlink()


class TestGroupResultsByPairing:
    """Tests for group_results_by_pairing function."""

    def test_diagonal_records_default_skill_to_model(self):
        results = [
            {"model": "gpt-oss-120b", "diff_id": "DIFF-001"},
            {"model": "glm5.2", "diff_id": "DIFF-002"},
        ]
        grouped = group_results_by_pairing(results)
        assert ("gpt-oss-120b", "gpt-oss-120b") in grouped
        assert ("glm5.2", "glm5.2") in grouped
        assert len(grouped[("gpt-oss-120b", "gpt-oss-120b")]) == 1
        assert len(grouped[("glm5.2", "glm5.2")]) == 1

    def test_cross_records_use_explicit_skill(self):
        results = [
            {"model": "gpt-oss-120b", "skill": "glm5.2", "diff_id": "DIFF-001"},
            {"model": "mistral", "skill": "qwen3.8-27b", "diff_id": "DIFF-002"},
        ]
        grouped = group_results_by_pairing(results)
        assert ("gpt-oss-120b", "glm5.2") in grouped
        assert ("mistral", "qwen3.8-27b") in grouped
        assert ("gpt-oss-120b", "gpt-oss-120b") not in grouped

    def test_mixed_diagonal_and_cross(self):
        results = [
            {"model": "gpt-oss-120b", "diff_id": "D1"},
            {"model": "gpt-oss-120b", "skill": "glm5.2", "diff_id": "D2"},
            {"model": "gpt-oss-120b", "diff_id": "D3"},
        ]
        grouped = group_results_by_pairing(results)
        assert len(grouped[("gpt-oss-120b", "gpt-oss-120b")]) == 2
        assert len(grouped[("gpt-oss-120b", "glm5.2")]) == 1


class TestComputeCellMetrics:
    """Tests for compute_cell_metrics function."""

    def test_empty_results_returns_zeros(self):
        diff_records = [{"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}]}]
        metrics = compute_cell_metrics([], diff_records)
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["ds"] == 0.0
        assert metrics["refusal_rate"] == 0.0
        assert metrics["judge_mean"] == 0.0
        assert metrics["total_results"] == 0

    def test_perfect_findings_precision_recall_ds_one(self):
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}]},
            {"id": "DIFF-002", "file": "server.c", "bugs": [{"line": 200}]},
        ]
        results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "findings",
                "findings": [{"file": "server.c", "line": 100}],
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 2.0,
                    "justification": 2.0,
                    "actionability": 2.0,
                },
            },
            {
                "diff_id": "DIFF-002",
                "model": "test",
                "expected": "findings",
                "findings": [{"file": "server.c", "line": 200}],
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 2.0,
                    "justification": 2.0,
                    "actionability": 2.0,
                },
            },
        ]
        metrics = compute_cell_metrics(results, diff_records)
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["ds"] == 1.0
        assert len(metrics["hits"]) == 2
        assert len(metrics["misses"]) == 0

    def test_partial_match_recall_0_5(self):
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}]},
            {"id": "DIFF-002", "file": "server.c", "bugs": [{"line": 200}]},
        ]
        results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "findings",
                "findings": [{"file": "server.c", "line": 100}],
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 2.0,
                    "justification": 2.0,
                    "actionability": 2.0,
                },
            },
            {
                "diff_id": "DIFF-002",
                "model": "test",
                "expected": "findings",
                "findings": [],
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                },
            },
        ]
        metrics = compute_cell_metrics(results, diff_records)
        assert metrics["recall"] == 0.5
        assert metrics["precision"] == 1.0
        assert len(metrics["hits"]) == 1
        assert len(metrics["misses"]) == 1

    def test_judge_scores_averaged_correctly(self):
        diff_records = [{"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}]}]
        results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "findings",
                "findings": [{"file": "server.c", "line": 100}],
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 1.0,
                    "justification": 2.0,
                    "actionability": 1.0,
                },
            },
        ]
        metrics = compute_cell_metrics(results, diff_records)
        assert metrics["judge_accuracy"] == 2.0
        assert metrics["judge_prioritization"] == 1.0
        assert metrics["judge_justification"] == 2.0
        assert metrics["judge_actionability"] == 1.0
        assert metrics["judge_mean"] == 1.5

    def test_refusal_rate_computed_from_empty_findings(self):
        diff_records = [{"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}]}]
        results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "findings",
                "findings": [{"file": "server.c", "line": 100}],
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 2.0,
                    "justification": 2.0,
                    "actionability": 2.0,
                },
            },
            {
                "diff_id": "DIFF-002",
                "model": "test",
                "expected": "no-findings",
                "findings": [],
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                },
            },
        ]
        metrics = compute_cell_metrics(results, diff_records)
        assert metrics["refusal_rate"] == 0.5


class TestComputeMarginalMeans:
    """Tests for compute_marginal_means function."""

    def test_row_and_column_means_computed_correctly(self):
        cell_data = {
            ("m1", "s1"): {"ds": 0.8, "judge_mean": 1.5, "refusal_rate": 0.1, "total_results": 10},
            ("m1", "s2"): {"ds": 0.6, "judge_mean": 1.2, "refusal_rate": 0.2, "total_results": 10},
            ("m2", "s1"): {"ds": 0.7, "judge_mean": 1.4, "refusal_rate": 0.15, "total_results": 10},
            ("m2", "s2"): {"ds": 0.9, "judge_mean": 1.6, "refusal_rate": 0.05, "total_results": 10},
        }
        all_models = ["m1", "m2"]

        model_means, skill_means = compute_marginal_means(cell_data, all_models)

        # Model m1: (0.8 + 0.6) / 2 = 0.7
        assert model_means["m1"]["ds"] == 0.7
        # Model m2: (0.7 + 0.9) / 2 = 0.8
        assert model_means["m2"]["ds"] == 0.8
        # Skill s1: (0.8 + 0.7) / 2 = 0.75
        assert skill_means["s1"]["ds"] == 0.75
        # Skill s2: (0.6 + 0.9) / 2 = 0.75
        assert skill_means["s2"]["ds"] == 0.75


class TestRankByVerdict:
    """Tests for rank_by_verdict function."""

    def test_rank_by_ds_desc_then_judge_desc_then_refusal_asc(self):
        means = {
            "m1": {"ds": 0.8, "judge_mean": 1.5, "refusal_rate": 0.1},
            "m2": {"ds": 0.9, "judge_mean": 1.4, "refusal_rate": 0.2},
            "m3": {"ds": 0.9, "judge_mean": 1.6, "refusal_rate": 0.15},
        }
        ranked = rank_by_verdict(means)
        # m3 should be first (F1=0.9, judge=1.6 is highest tiebreak)
        # m2 second (F1=0.9, judge=1.4)
        # m3 third (F1=0.8)
        assert ranked[0][0] == "m3"
        assert ranked[1][0] == "m2"
        assert ranked[2][0] == "m1"

    def test_tiebreak_by_refusal_when_ds_and_judge_equal(self):
        means = {
            "m1": {"ds": 0.8, "judge_mean": 1.5, "refusal_rate": 0.2},
            "m2": {"ds": 0.8, "judge_mean": 1.5, "refusal_rate": 0.1},
        }
        ranked = rank_by_verdict(means)
        # m2 should be first (lower refusal)
        assert ranked[0][0] == "m2"
        assert ranked[1][0] == "m1"


class TestCollectUnmatchedFindings:
    """Tests for collect_unmatched_findings function."""

    def test_unmatched_finding_classification(self):
        all_results = [
            {
                "diff_id": "DIFF-001",
                "model": "m1",
                "skill": "m1",
                "findings": [
                    {"file": "server.c", "line": 100, "issue": "Matches bug"},
                    {
                        "file": "server.c",
                        "line": 999,
                        "issue": "Far from any bug",
                    },
                ],
            },
        ]
        diff_records = [
            {
                "id": "DIFF-001",
                "file": "server.c",
                "line": 100,
                "bugs": [{"file": "server.c", "line": 100, "description": "Bug at 100"}],
            },
        ]

        unmatched, counts = collect_unmatched_findings(all_results, diff_records)

        assert len(unmatched) == 1
        assert unmatched[0]["file"] == "server.c"
        assert unmatched[0]["line"] == 999
        assert counts[("m1", "m1")] == 1


class TestCollectCrossOnlyDiscoveries:
    """Tests for collect_cross_only_discoveries function."""

    def test_cross_only_discovery_logic(self):
        all_results = [
            # Native pair (m1, m1) - does NOT find bug B
            {
                "diff_id": "DIFF-001",
                "model": "m1",
                "skill": "m1",
                "findings": [{"file": "server.c", "line": 100}],
            },
            # Cross pair (m1, s2) - finds bug B (cross-only for s2)
            {
                "diff_id": "DIFF-001",
                "model": "m1",
                "skill": "s2",
                "findings": [{"file": "server.c", "line": 200}],
            },
        ]
        diff_records = [
            {
                "id": "DIFF-001",
                "file": "server.c",
                "line": 100,
                "bugs": [
                    {"file": "server.c", "line": 100, "description": "Bug A"},
                    {"file": "server.c", "line": 200, "description": "Bug B"},
                ],
            },
        ]

        cross_only, counts = collect_cross_only_discoveries(all_results, diff_records)

        # Bug B should be cross-only for skill s2
        assert "DIFF-001" in cross_only
        assert len(cross_only["DIFF-001"]) == 1
        assert cross_only["DIFF-001"][0]["bug_desc"] == "Bug B"
        assert cross_only["DIFF-001"][0]["found_by_skill"] == "s2"
        assert counts["s2"] == 1

    def test_native_covered_not_cross_only(self):
        all_results = [
            # Native pair finds bug A
            {
                "diff_id": "DIFF-001",
                "model": "m1",
                "skill": "m1",
                "findings": [{"file": "server.c", "line": 100}],
            },
            # Cross pair also finds bug A (not cross-only since native found it)
            {
                "diff_id": "DIFF-001",
                "model": "m2",
                "skill": "m1",
                "findings": [{"file": "server.c", "line": 100}],
            },
        ]
        diff_records = [
            {
                "id": "DIFF-001",
                "file": "server.c",
                "line": 100,
                "bugs": [{"file": "server.c", "line": 100, "description": "Bug A"}],
            },
        ]

        cross_only, counts = collect_cross_only_discoveries(all_results, diff_records)

        # Bug A was found by native, so no cross-only discoveries
        assert "DIFF-001" not in cross_only or len(cross_only.get("DIFF-001", [])) == 0


class TestRenderMarkdown:
    """Tests for render_markdown function."""

    def test_empty_matrix_generates_valid_markdown(self, tmp_path):
        cell_data = {}
        all_models = ["gpt-oss-120b", "glm5.2", "mistral-small-3.2-24b", "qwen3.8-27b"]
        diff_records = []
        out_path = tmp_path / "test_matrix.md"
        render_markdown(cell_data, all_models, diff_records, out_path)
        content = out_path.read_text()
        assert "# Cross-Model Evaluation Matrix" in content
        assert "## Overview Matrix" in content
        assert "## Marginal Analysis" in content
        assert "## New Bug Candidates" in content
        assert "## Cross-Only Discoveries" in content

    def test_matrix_with_data_shows_metrics(self, tmp_path):
        cell_data = {
            ("gpt-oss-120b", "gpt-oss-120b"): {
                "precision": 0.8,
                "recall": 0.6,
                "ds": 0.69,
                "refusal_rate": 0.1,
                "judge_accuracy": 1.8,
                "judge_prioritization": 1.5,
                "judge_justification": 1.7,
                "judge_actionability": 1.6,
                "judge_mean": 1.65,
                "total_results": 10,
                "hits": ["DIFF-001"],
                "misses": ["DIFF-002"],
            },
        }
        all_models = ["gpt-oss-120b"]
        diff_records = []
        out_path = tmp_path / "test_matrix.md"
        render_markdown(cell_data, all_models, diff_records, out_path)
        content = out_path.read_text()
        assert "DS=0.69" in content
        assert "R=10%" not in content
        assert "J=1.6/2" in content
        assert "*(native)*" in content

    def test_marginal_analysis_verdict_shows_winners(self, tmp_path):
        cell_data = {
            ("m1", "s1"): {"ds": 0.9, "refusal_rate": 0.1, "judge_mean": 1.8, "total_results": 10},
            ("m1", "s2"): {"ds": 0.7, "refusal_rate": 0.2, "judge_mean": 1.5, "total_results": 10},
            ("m2", "s1"): {"ds": 0.8, "refusal_rate": 0.15, "judge_mean": 1.6, "total_results": 10},
            ("m2", "s2"): {"ds": 0.6, "refusal_rate": 0.25, "judge_mean": 1.4, "total_results": 10},
        }
        all_models = ["m1", "m2"]
        diff_records = []

        model_means, skill_means = compute_marginal_means(cell_data, all_models)
        model_ranked = rank_by_verdict(model_means)
        skill_ranked = rank_by_verdict(skill_means)

        out_path = tmp_path / "test_matrix.md"
        render_markdown(
            cell_data,
            all_models,
            diff_records,
            out_path,
            model_ranked=model_ranked,
            skill_ranked=skill_ranked,
        )
        content = out_path.read_text()
        assert "## Marginal Analysis" in content
        assert "Best Model" in content
        assert "Best Skill" in content
        assert "Model Rankings" in content
        assert "Skill Rankings" in content


class TestIntegration:
    """Integration tests with synthetic data."""

    def test_marginal_verdict_math_on_2x2_grid(self, tmp_path):
        """Test exact expected winners on a tiny 2×2 grid."""
        # Create synthetic data where m1 wins on F1, s2 wins on F1
        cell_data = {
            ("m1", "s1"): {"ds": 0.8, "refusal_rate": 0.1, "judge_mean": 1.5, "total_results": 10},
            ("m1", "s2"): {"ds": 0.9, "refusal_rate": 0.1, "judge_mean": 1.6, "total_results": 10},
            ("m2", "s1"): {"ds": 0.5, "refusal_rate": 0.3, "judge_mean": 1.2, "total_results": 10},
            ("m2", "s2"): {"ds": 0.7, "refusal_rate": 0.2, "judge_mean": 1.4, "total_results": 10},
        }
        all_models = ["m1", "m2"]

        model_means, skill_means = compute_marginal_means(cell_data, all_models)
        model_ranked = rank_by_verdict(model_means)
        skill_ranked = rank_by_verdict(skill_means)

        # m1 row mean: (0.8 + 0.9) / 2 = 0.85
        # m2 row mean: (0.5 + 0.7) / 2 = 0.6
        assert model_ranked[0][0] == "m1"
        assert abs(model_ranked[0][1] - 0.85) < 0.0001

        # s1 column mean: (0.8 + 0.5) / 2 = 0.65
        # s2 column mean: (0.9 + 0.7) / 2 = 0.8
        assert skill_ranked[0][0] == "s2"
        assert skill_ranked[0][1] == 0.8

    def test_partial_data_grace_missing_cross_file(self, tmp_path):
        """Test graceful handling when cross file is missing."""
        diagonal_data = [
            {
                "diff_id": "DIFF-001",
                "model": "gpt-oss-120b",
                "skill": "gpt-oss-120b",
                "expected": "findings",
                "findings": [{"file": "server.c", "line": 100}],
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 2.0,
                    "justification": 2.0,
                    "actionability": 2.0,
                },
            },
        ]
        diff_records = [
            {
                "id": "DIFF-001",
                "file": "server.c",
                "line": 100,
                "bugs": [{"file": "server.c", "line": 100, "description": "Bug"}],
            }
        ]

        # Simulate missing cross file (empty list)
        all_results = diagonal_data
        grouped = group_results_by_pairing(all_results)

        cell_data = {}
        for (model, skill), results in grouped.items():
            metrics = compute_cell_metrics(results, diff_records)
            cell_data[(model, skill)] = metrics

        derived_models = sorted(
            set(m for (m, s) in grouped.keys()) | set(s for (m, s) in grouped.keys())
        )

        out_path = tmp_path / "output.md"
        model_means, skill_means = compute_marginal_means(cell_data, derived_models)
        model_ranked = rank_by_verdict(model_means)
        skill_ranked = rank_by_verdict(skill_means)
        unmatched, unmatched_counts = collect_unmatched_findings(all_results, diff_records)
        cross_only, cross_only_counts = collect_cross_only_discoveries(all_results, diff_records)

        render_markdown(
            cell_data,
            derived_models,
            diff_records,
            out_path,
            model_ranked=model_ranked,
            skill_ranked=skill_ranked,
            unmatched=unmatched,
            unmatched_counts=unmatched_counts,
            cross_only=cross_only,
            cross_only_counts=cross_only_counts,
        )

        assert out_path.exists()
        content = out_path.read_text()
        assert "# Cross-Model Evaluation Matrix" in content
        assert "## Marginal Analysis" in content
        assert "No cross-only discoveries" in content or "Cross-Only Discoveries" in content
