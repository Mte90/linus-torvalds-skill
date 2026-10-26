"""Tests for scripts/render_cross.py."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

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
from scripts.run_eval import _stamp_judge_model


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
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"}
        ]
        metrics = compute_cell_metrics([], diff_records)
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["ds"] == 0.0
        assert metrics["refusal_rate"] == 0.0
        assert metrics["judge_mean"] == 0.0
        assert metrics["total_results"] == 0

    def test_perfect_findings_precision_recall_ds_one(self):
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"},
            {"id": "DIFF-002", "file": "server.c", "bugs": [{"line": 200}], "expected": "findings"},
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
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"},
            {"id": "DIFF-002", "file": "server.c", "bugs": [{"line": 200}], "expected": "findings"},
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
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"}
        ]
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
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"}
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


class TestStampJudgeModel:
    """--stamp-judge-model tags records without re-judging them."""

    def _write(self, tmp_path, records):
        path = tmp_path / "results.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return path

    def _load(self, path):
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def test_stamps_records_without_the_field(self, tmp_path):
        path = self._write(
            tmp_path,
            [
                {"model": "a", "skill": "none", "scores": {"accuracy": 2.0}},
                {"model": "b", "skill": "a", "scores": {"accuracy": 1.0}},
            ],
        )
        _stamp_judge_model(path, "glm5.2")

        records = self._load(path)
        assert all(r["judge_model"] == "glm5.2" for r in records)
        # Scores must be untouched: stamping records provenance, it does not re-judge.
        assert [r["scores"]["accuracy"] for r in records] == [2.0, 1.0]

    def test_preserves_baseline_and_rep_fields(self, tmp_path):
        path = self._write(
            tmp_path,
            [{"model": "a", "skill": "none", "rep": 2, "refused": True, "findings": []}],
        )
        _stamp_judge_model(path, "glm5.2")

        record = self._load(path)[0]
        assert record["skill"] == "none"
        assert record["rep"] == 2
        assert record["refused"] is True
        assert record["judge_model"] == "glm5.2"

    def test_never_overwrites_a_different_judge(self, tmp_path):
        path = self._write(
            tmp_path,
            [
                {"model": "a", "skill": "a", "judge_model": "qwen3.8-27b"},
                {"model": "b", "skill": "b"},
            ],
        )
        _stamp_judge_model(path, "glm5.2")

        records = self._load(path)
        assert records[0]["judge_model"] == "qwen3.8-27b"
        assert records[1]["judge_model"] == "glm5.2"

    def test_is_idempotent(self, tmp_path):
        path = self._write(tmp_path, [{"model": "a", "skill": "a"}])
        _stamp_judge_model(path, "glm5.2")
        _stamp_judge_model(path, "glm5.2")
        assert self._load(path)[0]["judge_model"] == "glm5.2"

    def test_requires_a_judge_name(self, tmp_path, capsys):
        path = self._write(tmp_path, [{"model": "a", "skill": "a"}])
        with pytest.raises(SystemExit) as excinfo:
            _stamp_judge_model(path, None)
        assert excinfo.value.code == 2
        assert "requires the judge name" in capsys.readouterr().err

    def test_empty_file_is_reported_not_crashed(self, tmp_path, capsys):
        path = tmp_path / "results.jsonl"
        path.write_text("")
        _stamp_judge_model(path, "glm5.2")
        assert "No records found" in capsys.readouterr().out


class TestRepetitionInvariance:
    """--repetitions re-runs a diff, so metrics must not move when it does.

    Regression: summing findings across repetitions inflated the precision
    denominator, dropping Detection Score by ~3x on a 3-repetition run without
    a single extra true positive.
    """

    DIFFS = [
        {
            "id": "DIFF-001",
            "file": "server.c",
            "expected": "findings",
            "bugs": [{"line": 100, "severity": "HIGH", "category": "memory-safety"}],
        },
    ]

    def _run(self, rep, findings):
        return {
            "diff_id": "DIFF-001",
            "model": "test",
            "expected": "findings",
            "rep": rep,
            "findings": findings,
            "scores": {"accuracy": 2.0},
        }

    def _matched(self):
        return [{"file": "server.c", "line": 100, "issue": "use after free"}]

    def test_identical_repetitions_do_not_change_metrics(self):
        single = compute_cell_metrics([self._run(0, self._matched())], self.DIFFS)
        tripled = compute_cell_metrics(
            [self._run(rep, self._matched()) for rep in range(3)], self.DIFFS
        )
        assert tripled["precision"] == single["precision"]
        assert tripled["recall"] == single["recall"]
        assert tripled["ds"] == single["ds"]
        assert tripled["total_findings"] == single["total_findings"]
        assert len(tripled["hits"]) == len(single["hits"])

    def test_identical_repetitions_do_not_inflate_severity_counts(self):
        tripled = compute_cell_metrics(
            [self._run(rep, self._matched()) for rep in range(3)], self.DIFFS
        )
        assert tripled["severity_counts"] == {"HIGH": 1}
        assert tripled["category_counts"] == {"memory-safety": 1}
        assert len(tripled["matched_bugs"]) == 1

    def test_reps_are_counted_for_the_report(self):
        tripled = compute_cell_metrics(
            [self._run(rep, self._matched()) for rep in range(3)], self.DIFFS
        )
        assert tripled["reps"] == 3

    def _matrix(self, tmp_path, reps):
        cell_data = {("gpt-oss-120b", "gpt-oss-120b"): {"total_results": 3, "reps": reps}}
        out_path = tmp_path / "matrix.md"
        render_markdown(cell_data, ["gpt-oss-120b"], [], out_path)
        return out_path.read_text()

    def test_significance_note_reports_a_single_run(self, tmp_path):
        assert "1 run per cell" in self._matrix(tmp_path, 1)

    def test_significance_note_reports_repeated_runs(self, tmp_path):
        content = self._matrix(tmp_path, 3)
        assert "3 runs per cell" in content
        assert "1 run per cell" not in content

    def test_differing_findings_across_reps_stay_distinct(self):
        results = [
            self._run(0, [{"file": "server.c", "line": 100, "issue": "use after free"}]),
            self._run(1, [{"file": "server.c", "line": 100, "issue": "double free"}]),
            self._run(2, [{"file": "server.c", "line": 100, "issue": "buffer overflow"}]),
        ]
        metrics = compute_cell_metrics(results, self.DIFFS)
        assert metrics["total_findings"] == 3
        assert len(metrics["hits"]) == 1
        assert metrics["precision"] == pytest.approx(1 / 3)

    def test_unmatched_findings_are_deduplicated_across_reps(self):
        noise = [{"file": "server.c", "line": 900, "issue": "style nit"}]
        tripled = compute_cell_metrics(
            [self._run(rep, self._matched() + noise) for rep in range(3)], self.DIFFS
        )
        assert tripled["total_findings"] == 2
        assert tripled["precision"] == pytest.approx(0.5)


class TestFindingClassification:
    """Non-TP findings split into duplicates / on-non-buggy / unmatched (audit P2-2)."""

    BUGGY = [
        {
            "id": "DIFF-001",
            "file": "server.c",
            "expected": "findings",
            "bugs": [{"line": 100, "severity": "HIGH", "category": "memory-safety"}],
        },
        {
            "id": "DIFF-002",
            "file": "server.c",
            "expected": "no-findings",
            "bugs": [{"line": 200, "severity": "HIGH", "category": "memory-safety"}],
        },
    ]

    def _rec(self, diff_id, expected, findings):
        return {
            "diff_id": diff_id,
            "model": "test",
            "expected": expected,
            "findings": findings,
            "scores": {"accuracy": 2.0},
        }

    def test_a_finding_matching_nothing_is_unmatched(self):
        metrics = compute_cell_metrics(
            [self._rec("DIFF-001", "findings", [{"file": "other.c", "line": 5}])], self.BUGGY
        )
        assert metrics["unmatched"] == 1
        assert metrics["duplicate_findings"] == 0

    def test_two_findings_on_one_bug_yield_one_tp_and_one_duplicate(self):
        metrics = compute_cell_metrics(
            [
                self._rec("DIFF-001", "findings", [{"file": "server.c", "line": 100}]),
                self._rec("DIFF-001", "findings", [{"file": "server.c", "line": 102}]),
            ],
            self.BUGGY,
        )
        assert metrics["duplicate_findings"] == 1
        assert len(metrics["hits"]) == 1
        assert metrics["total_findings"] == 2

    def test_a_finding_on_a_clean_scenario_lands_in_unmatched(self):
        metrics = compute_cell_metrics(
            [self._rec("DIFF-002", "no-findings", [{"file": "server.c", "line": 999}])], self.BUGGY
        )
        assert metrics["unmatched"] == 1
        assert len(metrics["hits"]) == 0

    def test_categories_partition_the_total_findings(self):
        """Every distinct finding lands in exactly one bucket.

        Note the partition is over findings, not over bugs: two findings can match
        one bug, so `hits` (unique bugs) is a subset of matches_a_bug, not a
        separate term to add.
        """
        metrics = compute_cell_metrics(
            [
                self._rec("DIFF-001", "findings", [{"file": "server.c", "line": 100}]),
                self._rec("DIFF-001", "findings", [{"file": "server.c", "line": 102}]),
                self._rec("DIFF-001", "findings", [{"file": "other.c", "line": 9}]),
            ],
            self.BUGGY,
        )
        parts = metrics["matches_a_bug"] + metrics["unmatched"] + metrics["duplicate_findings"]
        assert metrics["total_findings"] == parts == 3
        # Unique bugs found cannot exceed findings that matched a bug.
        assert len(metrics["hits"]) <= metrics["matches_a_bug"]


class TestRenderMarkdown:
    """Tests for render_markdown function."""

    def test_empty_matrix_generates_valid_markdown(self, tmp_path):
        """Test that empty matrix generates valid markdown with skeleton structure."""
        cell_data = {}
        all_models = ["gpt-oss-120b", "glm5.2", "mistral-small-3.2-24b", "qwen3.8-27b"]
        diff_records = []
        out_path = tmp_path / "test_matrix.md"
        render_markdown(cell_data, all_models, diff_records, out_path)
        content = out_path.read_text()
        assert "# Cross-Model Evaluation Matrix" in content
        # Phase 4: About this report section (replaced Q&A)
        assert "## About this report" in content
        assert "Three roles" in content or "reviewer model" in content
        # No more Anti-contradiction blockquote (removed in P3)
        # Metrics Glossary now appears before Verdict
        assert "## Metrics Glossary" in content
        # Note: Verdict and other sections only appear when there's data
        # Limitations section always appears
        assert "## Limitations" in content
        assert "n=45" in content

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
                "buggy_count": 1,
            },
        }
        all_models = ["gpt-oss-120b"]
        diff_records = [{"id": "DIFF-001", "expected": "findings"}]
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
                "expected": "findings",
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


class TestBaselineSupport:
    """Tests for baseline (no skill) support."""

    def test_baseline_row_appears_when_baseline_records_exist(self, tmp_path):
        """Test that baseline row appears in matrices when baseline data exists."""
        # Create synthetic data with baseline records
        cell_data = {
            ("m1", "s1"): {
                "ds": 0.8,
                "refusal_rate": 0.1,
                "judge_mean": 1.5,
                "total_results": 10,
                "precision": 0.85,
                "recall": 0.75,
            },
            ("m1", "s2"): {
                "ds": 0.7,
                "refusal_rate": 0.2,
                "judge_mean": 1.4,
                "total_results": 10,
                "precision": 0.80,
                "recall": 0.70,
            },
            ("m2", "s1"): {
                "ds": 0.6,
                "refusal_rate": 0.15,
                "judge_mean": 1.3,
                "total_results": 10,
                "precision": 0.75,
                "recall": 0.65,
            },
            ("m2", "s2"): {
                "ds": 0.5,
                "refusal_rate": 0.25,
                "judge_mean": 1.2,
                "total_results": 10,
                "precision": 0.70,
                "recall": 0.60,
            },
        }
        all_models = ["m1", "m2"]
        diff_records = [{"id": "DIFF-001", "expected": "findings"}]

        # Baseline cell data (skill="none")
        baseline_cell_data = {
            "m1": {
                "ds": 0.4,
                "refusal_rate": 0.3,
                "judge_mean": 1.1,
                "total_results": 10,
                "precision": 0.65,
                "recall": 0.55,
            },
            "m2": {
                "ds": 0.3,
                "refusal_rate": 0.35,
                "judge_mean": 1.0,
                "total_results": 10,
                "precision": 0.60,
                "recall": 0.50,
            },
        }

        model_means, skill_means = compute_marginal_means(cell_data, all_models)
        model_ranked = rank_by_verdict(model_means)
        skill_ranked = rank_by_verdict(skill_means)

        out_path = tmp_path / "test_baseline.md"
        render_markdown(
            cell_data,
            all_models,
            diff_records,
            out_path,
            model_ranked=model_ranked,
            skill_ranked=skill_ranked,
            baseline_cell_data=baseline_cell_data,
            has_baseline=True,
        )
        content = out_path.read_text()

        # Baseline row should appear in Overview Matrix
        assert "No skill (baseline)" in content
        assert "## Overview Matrix" in content

        # Baseline row should appear in Precision Matrix
        assert "## Precision Matrix" in content

        # Baseline row should appear in Recall Matrix
        assert "## Recall Matrix" in content

        # Baseline comparison paragraph was removed in P3 (now lives in comparison.md)
        # assert "Baseline comparison" in content

    def test_no_baseline_row_when_baseline_records_absent(self, tmp_path):
        """Test that baseline row does NOT appear when no baseline data exists."""
        cell_data = {
            ("m1", "s1"): {
                "ds": 0.8,
                "refusal_rate": 0.1,
                "judge_mean": 1.5,
                "total_results": 10,
                "precision": 0.85,
                "recall": 0.75,
            },
            ("m1", "s2"): {
                "ds": 0.7,
                "refusal_rate": 0.2,
                "judge_mean": 1.4,
                "total_results": 10,
                "precision": 0.80,
                "recall": 0.70,
            },
        }
        all_models = ["m1"]
        diff_records = []

        out_path = tmp_path / "test_no_baseline.md"
        render_markdown(cell_data, all_models, diff_records, out_path, has_baseline=False)
        content = out_path.read_text()

        # Baseline row should NOT appear
        assert "No skill (baseline)" not in content
        # Baseline verdict should NOT appear
        assert "Baseline comparison" not in content

    def test_baseline_excluded_from_skill_rankings(self, tmp_path):
        """Test that baseline is excluded from skill rankings and Best Skill per Model."""
        cell_data = {
            ("m1", "s1"): {"ds": 0.8, "refusal_rate": 0.1, "judge_mean": 1.5, "total_results": 10},
            ("m1", "s2"): {"ds": 0.7, "refusal_rate": 0.2, "judge_mean": 1.4, "total_results": 10},
        }
        all_models = ["m1"]
        diff_records = []

        baseline_cell_data = {
            "m1": {"ds": 0.9, "refusal_rate": 0.05, "judge_mean": 1.6, "total_results": 10},
        }

        model_means, skill_means = compute_marginal_means(cell_data, all_models)
        model_ranked = rank_by_verdict(model_means)
        skill_ranked = rank_by_verdict(skill_means)

        out_path = tmp_path / "test_baseline_excluded.md"
        render_markdown(
            cell_data,
            all_models,
            diff_records,
            out_path,
            model_ranked=model_ranked,
            skill_ranked=skill_ranked,
            baseline_cell_data=baseline_cell_data,
            has_baseline=True,
        )
        content = out_path.read_text()

        # Skill rankings should NOT include "none" or baseline
        assert "Skill Rankings" in content
        # The baseline should not appear in skill rankings section
        lines = content.split("\n")
        in_skill_rankings = False
        for line in lines:
            if "Skill Rankings" in line:
                in_skill_rankings = True
            elif in_skill_rankings and line.startswith("|") and "none" in line.lower():
                # Found baseline in skill rankings - this is a failure
                raise AssertionError("Baseline found in skill rankings")
            elif in_skill_rankings and line.startswith("##"):
                in_skill_rankings = False

    def test_baseline_gap_renders_as_missing_marker(self, tmp_path):
        """Test that a baseline cell with zero records renders as missing cell marker."""
        cell_data = {
            ("m1", "s1"): {
                "ds": 0.8,
                "refusal_rate": 0.1,
                "judge_mean": 1.5,
                "total_results": 10,
                "precision": 0.85,
                "recall": 0.75,
            },
        }
        all_models = ["m1"]
        diff_records = []

        # Baseline cell has zero records (gap)
        baseline_cell_data = {
            "m1": {"total_results": 0},  # Empty cell
        }

        model_means, skill_means = compute_marginal_means(cell_data, all_models)
        model_ranked = rank_by_verdict(model_means)
        skill_ranked = rank_by_verdict(skill_means)

        out_path = tmp_path / "test_baseline_gap.md"
        render_markdown(
            cell_data,
            all_models,
            diff_records,
            out_path,
            model_ranked=model_ranked,
            skill_ranked=skill_ranked,
            baseline_cell_data=baseline_cell_data,
            has_baseline=True,
        )
        content = out_path.read_text()

        # Baseline row should appear but with missing marker (—)
        assert "No skill (baseline)" in content
        # Should show missing cell marker
        assert "— |" in content
