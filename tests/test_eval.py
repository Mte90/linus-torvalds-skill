"""Tests for run_eval.py and validate_eval.py functions."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add parent directory to path for imports
SRC = Path(__file__).parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from report.build_comparison import compute_diff_eval_metrics, compute_refusal_metrics
from scripts.run_eval import (
    _cross_pairs,
    _extract_json_from_content,
    _print_status_table,
    _rescore_zeros,
    _run_pair,
    _status_cells,
    match_finding_to_diff_bug,
    run_model_on_diff,
    score_finding_with_judge,
)
from scripts.validate_eval import validate_record


class TestComputeDiffEvalMetrics:
    """Tests for compute_diff_eval_metrics function."""

    def test_empty_inputs_returns_zeros(self):
        """Test that empty eval_results and diff_records return all zeros."""
        result = compute_diff_eval_metrics([], [])

        assert result["precision"] == 0.0
        assert result["recall"] == 0.0
        assert result["f1"] == 0.0
        assert result["hits"] == []
        assert result["misses"] == []
        assert result["avg_accuracy"] == 0.0
        assert result["avg_prioritization"] == 0.0
        assert result["avg_justification"] == 0.0
        assert result["avg_actionability"] == 0.0
        assert result["overall_score"] == 0.0
        assert result["total_findings"] == 0
        assert result["total_benchmark"] == 0

    def test_empty_eval_results_returns_zeros(self):
        """Test that empty eval_results with non-empty diff_records returns zeros."""
        diff_records = [{"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}]}]

        result = compute_diff_eval_metrics([], diff_records)

        assert result["precision"] == 0.0
        assert result["recall"] == 0.0
        assert result["f1"] == 0.0
        assert result["hits"] == []
        assert result["misses"] == ["DIFF-001"]

    def test_empty_diff_records_returns_zeros(self):
        """Test that non-empty eval_results with empty diff_records returns zeros."""
        eval_results = [
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
            }
        ]

        result = compute_diff_eval_metrics(eval_results, [])

        assert result["precision"] == 0.0
        assert result["recall"] == 0.0
        assert result["f1"] == 0.0
        assert result["hits"] == []
        assert result["misses"] == []

    def test_perfect_match_precision_recall_f1_one(self):
        """Test perfect match: all bugs found → precision/recall/f1 == 1.0."""
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"},
            {"id": "DIFF-002", "file": "server.c", "bugs": [{"line": 200}], "expected": "findings"},
            {"id": "DIFF-003", "file": "client.c", "bugs": [{"line": 50}], "expected": "findings"},
        ]

        eval_results = [
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
            {
                "diff_id": "DIFF-003",
                "model": "test",
                "expected": "findings",
                "findings": [{"file": "client.c", "line": 50}],
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 2.0,
                    "justification": 2.0,
                    "actionability": 2.0,
                },
            },
        ]

        result = compute_diff_eval_metrics(eval_results, diff_records)

        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0
        assert len(result["hits"]) == 3
        assert len(result["misses"]) == 0

    def test_partial_match_recall_0_5(self):
        """Test partial match: half the bugs found → recall == 0.5."""
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"},
            {"id": "DIFF-002", "file": "server.c", "bugs": [{"line": 200}], "expected": "findings"},
        ]

        eval_results = [
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
                "findings": [],  # No findings for second bug
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                },
            },
        ]

        result = compute_diff_eval_metrics(eval_results, diff_records)

        # 1 hit / 2 benchmark = 0.5 recall
        assert result["recall"] == 0.5
        # 1 hit / 1 finding = 1.0 precision
        assert result["precision"] == 1.0
        assert len(result["hits"]) == 1
        assert len(result["misses"]) == 1
        assert "DIFF-002" in result["misses"]

    def test_line_tolerance_5_hits_6_misses(self):
        """Test line tolerance: ±5 hits, ±6 misses."""
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"},
            {"id": "DIFF-002", "file": "server.c", "bugs": [{"line": 200}], "expected": "findings"},
            {"id": "DIFF-003", "file": "server.c", "bugs": [{"line": 300}], "expected": "findings"},
        ]

        eval_results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "findings",
                "findings": [{"file": "server.c", "line": 105}],  # Within ±5 of 100
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
                "findings": [{"file": "server.c", "line": 206}],  # Outside ±5 of 200
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 2.0,
                    "justification": 2.0,
                    "actionability": 2.0,
                },
            },
            {
                "diff_id": "DIFF-003",
                "model": "test",
                "expected": "findings",
                "findings": [{"file": "server.c", "line": 295}],  # Within ±5 of 300
                "scores": {
                    "accuracy": 2.0,
                    "prioritization": 2.0,
                    "justification": 2.0,
                    "actionability": 2.0,
                },
            },
        ]

        result = compute_diff_eval_metrics(eval_results, diff_records)

        # 2 hits (DIFF-001, DIFF-003), 1 miss (DIFF-002)
        assert len(result["hits"]) == 2
        assert len(result["misses"]) == 1
        assert "DIFF-002" in result["misses"]

    def test_excludes_no_findings_records_from_metrics(self):
        """Test that expected='no-findings' records are excluded from P/R/F1."""
        diff_records = [
            {"id": "DIFF-001", "file": "server.c", "bugs": [{"line": 100}], "expected": "findings"},
            {
                "id": "DIFF-002",
                "file": "server.c",
                "bugs": [{"line": 200}],
                "expected": "no-findings",
            },
        ]

        eval_results = [
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

        result = compute_diff_eval_metrics(eval_results, diff_records)

        # Only DIFF-001 counts for precision (findings), but recall uses all benchmark records
        assert result["precision"] == 1.0  # 1 hit / 1 finding
        assert result["recall"] == 0.5  # 1 hit / 2 benchmark (includes no-findings)
        assert result["total_findings"] == 1  # Only from findings records


class TestMatchFindingToDiffBug:
    """Tests for match_finding_to_diff_bug function."""

    def test_exact_match(self):
        """Test exact file+line match."""
        finding = {"file": "server.c", "line": 100}
        bugs = [{"line": 100, "severity": "reject"}]

        result = match_finding_to_diff_bug(finding, bugs, "server.c")

        assert result is not None
        assert result["severity"] == "reject"

    def test_within_5_line_tolerance(self):
        """Test matching within ±5 line tolerance."""
        finding = {"file": "server.c", "line": 105}
        bugs = [{"line": 100, "severity": "reject"}]

        result = match_finding_to_diff_bug(finding, bugs, "server.c")

        assert result is not None

    def test_at_5_line_boundary(self):
        """Test matching at exactly ±5 boundary (should match)."""
        finding = {"file": "server.c", "line": 105}
        bugs = [{"line": 100, "severity": "reject"}]

        result = match_finding_to_diff_bug(finding, bugs, "server.c")

        assert result is not None

        finding_minus = {"file": "server.c", "line": 95}
        result_minus = match_finding_to_diff_bug(finding_minus, bugs, "server.c")

        assert result_minus is not None

    def test_at_6_line_boundary_miss(self):
        """Test matching at exactly ±6 boundary (should miss)."""
        finding = {"file": "server.c", "line": 106}
        bugs = [{"line": 100, "severity": "reject"}]

        result = match_finding_to_diff_bug(finding, bugs, "server.c")

        assert result is None

        finding_minus = {"file": "server.c", "line": 94}
        result_minus = match_finding_to_diff_bug(finding_minus, bugs, "server.c")

        assert result_minus is None

    def test_different_file_no_match(self):
        """Test that different files don't match."""
        finding = {"file": "client.c", "line": 100}
        bugs = [{"line": 100, "severity": "reject"}]

        result = match_finding_to_diff_bug(finding, bugs, "server.c")

        assert result is None

    def test_missing_line_no_match(self):
        """Test that findings without line don't match."""
        finding = {"file": "server.c", "line": None}
        bugs = [{"line": 100, "severity": "reject"}]

        result = match_finding_to_diff_bug(finding, bugs, "server.c")

        assert result is None

    def test_missing_file_no_match(self):
        """Test that findings without file don't match."""
        finding = {"file": "", "line": 100}
        bugs = [{"line": 100, "severity": "reject"}]

        result = match_finding_to_diff_bug(finding, bugs, "server.c")

        assert result is None


class TestScoreFindingWithJudge:
    """Tests for score_finding_with_judge function."""

    def test_offline_mode_returns_zeros(self):
        """Test that no_judge=True returns zeros without API call."""
        finding = {"file": "server.c", "line": 100, "severity": "CRITICAL"}
        bug = {"file": "server.c", "line": 100, "severity": "reject"}

        result = score_finding_with_judge(finding, bug, "test-model", no_judge=True)

        assert result["accuracy"] == 0
        assert result["prioritization"] == 0
        assert result["justification"] == 0
        assert result["actionability"] == 0

    def test_offline_mode_with_no_bug_returns_zeros(self):
        """Test that no_judge=True returns zeros even without matching bug."""
        finding = {"file": "server.c", "line": 100, "severity": "CRITICAL"}

        result = score_finding_with_judge(finding, None, "test-model", no_judge=True)

        assert result["accuracy"] == 0
        assert result["prioritization"] == 0
        assert result["justification"] == 0
        assert result["actionability"] == 0

    def test_null_content_returns_zeros(self, monkeypatch):
        """Regression: API returning content:null yields zeros instead of crashing."""
        import json as json_lib
        import urllib.request

        monkeypatch.setattr("torvalds_skill.config.API_KEY", "sk-test")

        raw = json_lib.dumps({"choices": [{"message": {"content": None}}]}).encode()

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return raw

        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp())

        finding = {"file": "server.c", "line": 100, "severity": "CRITICAL"}
        result = score_finding_with_judge(finding, None, "gpt-oss-120b", no_judge=False)

        assert result["accuracy"] == 0
        assert result["prioritization"] == 0
        assert result["justification"] == 0
        assert result["actionability"] == 0


class TestExtractJsonFromContent:
    """Tests for _extract_json_from_content helper."""

    def test_direct_json_parses(self):
        """Test that direct JSON parses correctly."""
        content = '{"accuracy": 2, "prioritization": 1, "justification": 2, "actionability": 1}'
        result = _extract_json_from_content(content)

        assert result == {
            "accuracy": 2,
            "prioritization": 1,
            "justification": 2,
            "actionability": 1,
        }

    def test_fenced_json_extracts(self):
        """Test that markdown-fenced JSON extracts correctly."""
        content = """```json
{"accuracy": 2, "prioritization": 1, "justification": 2, "actionability": 1}
```"""
        result = _extract_json_from_content(content)

        assert result == {
            "accuracy": 2,
            "prioritization": 1,
            "justification": 2,
            "actionability": 1,
        }

    def test_fenced_json_no_language_extracts(self):
        """Test that markdown-fenced JSON (no language tag) extracts correctly."""
        content = """```
{"accuracy": 2, "prioritization": 1, "justification": 2, "actionability": 1}
```"""
        result = _extract_json_from_content(content)

        assert result == {
            "accuracy": 2,
            "prioritization": 1,
            "justification": 2,
            "actionability": 1,
        }

    def test_balanced_braces_extract_from_text(self):
        """Test that balanced {...} extracts from surrounding text."""
        content = """Here's the result:
{"accuracy": 2, "prioritization": 1, "justification": 2, "actionability": 1}
End of report."""
        result = _extract_json_from_content(content)

        assert result == {
            "accuracy": 2,
            "prioritization": 1,
            "justification": 2,
            "actionability": 1,
        }

    def test_invalid_json_returns_none(self):
        """Test that invalid JSON returns None."""
        content = "not json at all"
        result = _extract_json_from_content(content)

        assert result is None

    def test_empty_content_returns_none(self):
        """Test that empty content returns None."""
        result = _extract_json_from_content("")

        assert result is None


class TestJudgeErrorHandling:
    """Tests for judge error handling and retry logic."""

    def test_double_failure_sets_judge_error(self, monkeypatch):
        """Test that double failure (after retry) sets judge_error:true."""
        import json as json_lib
        import urllib.request

        monkeypatch.setattr("torvalds_skill.config.API_KEY", "sk-test")

        # Both attempts return invalid JSON
        raw = json_lib.dumps({"choices": [{"message": {"content": "not json"}}]}).encode()

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return raw

        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp())

        finding = {"file": "server.c", "line": 100, "severity": "CRITICAL", "diff_text": "+test"}
        result = score_finding_with_judge(finding, None, "gpt-oss-120b", no_judge=False)

        assert result["accuracy"] == 0
        assert result["judge_error"] is True

    def test_retry_then_success(self, monkeypatch):
        """Test that retry on first failure succeeds on second attempt."""
        import json as json_lib
        import urllib.request

        monkeypatch.setattr("torvalds_skill.config.API_KEY", "sk-test")

        call_count = [0]

        def fake_urlopen(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call returns invalid
                raw = json_lib.dumps({"choices": [{"message": {"content": "bad"}}]}).encode()
            else:
                # Second call (retry) returns valid JSON
                raw = json_lib.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"accuracy": 2, "prioritization": 1, "justification": 2, "actionability": 1}'
                                }
                            }
                        ]
                    }
                ).encode()

            class FakeResp:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def read(self):
                    return raw

            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        finding = {"file": "server.c", "line": 100, "severity": "CRITICAL", "diff_text": "+test"}
        result = score_finding_with_judge(finding, None, "gpt-oss-120b", no_judge=False)

        assert result["accuracy"] == 2
        assert result["prioritization"] == 1
        assert "judge_error" not in result


class TestValidateRecord:
    """Tests for validate_record function."""

    def test_valid_record_returns_no_errors(self):
        """Test that a valid record returns empty error list."""
        # Create a diff with 15 lines (within 10-40 range)
        diff_lines = ["+line" + str(i) for i in range(15)]
        diff_text = "\n".join(diff_lines)

        record = {
            "id": "DIFF-001",
            "diff": diff_text,
            "language": "c",
            "file": "server.c",
            "expected": "findings",
            "bugs": [
                {
                    "line": 100,
                    "category": "memory-safety",
                    "severity": "reject",
                    "description": "Test bug",
                }
            ],
        }

        errors = validate_record(record, 1)

        assert errors == []

    def test_missing_bugs_field_returns_error(self):
        """Test that a record missing 'bugs' field returns error."""
        record = {
            "id": "DIFF-001",
            "diff": "+" * 150,
            "language": "c",
            "file": "server.c",
            "expected": "findings",
        }

        errors = validate_record(record, 1)

        assert any("Missing required field 'bugs'" in err for err in errors)

    def test_missing_id_field_returns_error(self):
        """Test that a record missing 'id' field returns error."""
        record = {
            "diff": "+" * 150,
            "language": "c",
            "file": "server.c",
            "expected": "findings",
            "bugs": [],
        }

        errors = validate_record(record, 1)

        assert any("Missing required field 'id'" in err for err in errors)

    def test_missing_diff_field_returns_error(self):
        """Test that a record missing 'diff' field returns error."""
        record = {
            "id": "DIFF-001",
            "language": "c",
            "file": "server.c",
            "expected": "findings",
            "bugs": [],
        }

        errors = validate_record(record, 1)

        assert any("Missing required field 'diff'" in err for err in errors)

    def test_invalid_id_format_returns_error(self):
        """Test that invalid id format returns error."""
        record = {
            "id": "INVALID",
            "diff": "+" * 150,
            "language": "c",
            "file": "server.c",
            "expected": "findings",
            "bugs": [],
        }

        errors = validate_record(record, 1)

        assert any("Invalid id format" in err for err in errors)

    def test_invalid_language_returns_error(self):
        """Test that invalid language returns error."""
        record = {
            "id": "DIFF-001",
            "diff": "+" * 150,
            "language": "java",
            "file": "server.c",
            "expected": "findings",
            "bugs": [],
        }

        errors = validate_record(record, 1)

        assert any("Invalid language" in err for err in errors)


class TestComputeRefusalMetrics:
    """Tests for compute_refusal_metrics function."""

    def test_empty_inputs_returns_zeros(self):
        """Test that empty eval_results returns all zeros."""
        result = compute_refusal_metrics([], [])

        assert result["clean_fp_rate"] == 0.0
        assert result["ambiguous_confidence_error"] == 0.0
        assert result["refusal_accuracy"] == 0.0  # Returns 0.0 when no ambiguous results
        assert result["clean_total"] == 0
        assert result["ambiguous_total"] == 0

    def test_all_correct_refusal_precision_one(self):
        """Test all-correct refusal: no findings on clean, refused on ambiguous → fp 0.0, accuracy 1.0."""
        eval_results = [
            {
                "diff_id": "DIFF-001",
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
            {
                "diff_id": "DIFF-003",
                "model": "test",
                "expected": "refuse-to-conclude",
                "findings": [],
                "refused": True,
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                },
            },
            {
                "diff_id": "DIFF-004",
                "model": "test",
                "expected": "refuse-to-conclude",
                "findings": [],
                "refused": True,
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                },
            },
        ]

        result = compute_refusal_metrics(eval_results, [])

        assert result["clean_fp_rate"] == 0.0
        assert result["refusal_accuracy"] == 1.0
        assert result["clean_total"] == 2
        assert result["ambiguous_total"] == 2

    def test_false_positive_on_clean(self):
        """Test false positive on clean record → clean_fp_rate > 0."""
        eval_results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "no-findings",
                "findings": [{"file": "server.c", "line": 100}],  # False positive
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
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

        result = compute_refusal_metrics(eval_results, [])

        # 1 FP / 2 clean = 0.5
        assert result["clean_fp_rate"] == 0.5
        assert result["clean_total"] == 2

    def test_false_positive_on_all_clean_records(self):
        """Test false positive on all clean records → clean_fp_rate == 1.0."""
        eval_results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "no-findings",
                "findings": [{"file": "server.c", "line": 100}],
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                },
            },
            {
                "diff_id": "DIFF-002",
                "model": "test",
                "expected": "no-findings",
                "findings": [{"file": "server.c", "line": 200}],
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                },
            },
        ]

        result = compute_refusal_metrics(eval_results, [])

        assert result["clean_fp_rate"] == 1.0

    def test_ambiguous_with_high_confidence_error(self):
        """Test ambiguous case with high confidence and no refusal → error."""
        eval_results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "refuse-to-conclude",
                "findings": [{"file": "server.c", "line": 100}],  # Should have refused
                "refused": False,
                "scores": {
                    "accuracy": 1.0,
                    "prioritization": 1.0,
                    "justification": 1.0,
                    "actionability": 1.0,
                    "confidence": 1.0,
                },
            },
        ]

        result = compute_refusal_metrics(eval_results, [])

        # 1 error / 1 ambiguous = 1.0 error rate
        assert result["ambiguous_confidence_error"] == 1.0
        assert result["refusal_accuracy"] == 0.0

    def test_ambiguous_with_low_confidence_correct(self):
        """Test ambiguous case with low confidence → correct (no error)."""
        eval_results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "refuse-to-conclude",
                "findings": [],
                "refused": True,
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                    "confidence": 0.3,
                },
            },
        ]

        result = compute_refusal_metrics(eval_results, [])

        assert result["ambiguous_confidence_error"] == 0.0
        assert result["refusal_accuracy"] == 1.0

    def test_mixed_correct_and_incorrect_refusals(self):
        """Test mixed correct and incorrect refusals."""
        eval_results = [
            {
                "diff_id": "DIFF-001",
                "model": "test",
                "expected": "refuse-to-conclude",
                "findings": [],
                "refused": True,
                "scores": {
                    "accuracy": 0.0,
                    "prioritization": 0.0,
                    "justification": 0.0,
                    "actionability": 0.0,
                    "confidence": 0.2,
                },
            },
            {
                "diff_id": "DIFF-002",
                "model": "test",
                "expected": "refuse-to-conclude",
                "findings": [{"file": "server.c", "line": 100}],
                "refused": False,
                "scores": {
                    "accuracy": 1.0,
                    "prioritization": 1.0,
                    "justification": 1.0,
                    "actionability": 1.0,
                    "confidence": 0.9,
                },
            },
        ]

        result = compute_refusal_metrics(eval_results, [])

        # 1 error / 2 ambiguous = 0.5 error rate
        assert result["ambiguous_confidence_error"] == 0.5
        assert result["refusal_accuracy"] == 0.5


class TestRunModelOnDiff:
    """Tests for run_model_on_diff function."""

    def test_call_llm_uses_wall_clock_timeout_from_profile(self, monkeypatch):
        """Test that call_llm is called with timeout derived from profile.review_timeout."""
        # Create a mock diff record
        diff_record = {
            "id": "DIFF-001",
            "diff": "+test\n+code",
            "language": "python",
            "file": "test.py",
            "expected": "findings",
            "bugs": [],
        }

        # Mock the skill file
        skill_path = Path(__file__).parent.parent / "linus-torvalds-skill" / "SKILL.md"

        # Mock call_llm to capture arguments
        call_args = []

        def mock_call_llm(model, prompt, timeout=600, **kwargs):
            call_args.append({"model": model, "timeout": timeout, "prompt": prompt})
            return "# Review\n\nNo findings."

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)
        monkeypatch.setattr("scripts.run_eval.MODELS", {"test-model": skill_path})

        # Mock get_profile to return a profile with review_timeout
        mock_profile = MagicMock()
        mock_profile.max_tokens = 1000
        mock_profile.review_timeout = 420
        mock_profile.reasoning = False

        def mock_get_profile(model):
            return mock_profile

        monkeypatch.setattr("scripts.run_eval.get_profile", mock_get_profile)

        # Run the function
        run_model_on_diff("test-model", diff_record, no_judge=True)

        # Verify call_llm was called with the correct timeout
        assert len(call_args) == 1
        assert call_args[0]["timeout"] == 420

    def test_retry_then_none_on_persistent_failure(self, monkeypatch):
        """Test that one retry then None on persistent failure - no record written."""
        diff_record = {
            "id": "DIFF-001",
            "diff": "+test\n+code",
            "language": "python",
            "file": "test.py",
            "expected": "findings",
            "bugs": [],
        }

        # Mock call_llm to always fail
        def mock_call_llm(*args, **kwargs):
            raise Exception("API error")

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)

        skill_path = Path(__file__).parent.parent / "linus-torvalds-skill" / "SKILL.md"
        monkeypatch.setattr("scripts.run_eval.MODELS", {"test-model": skill_path})

        mock_profile = MagicMock()
        mock_profile.max_tokens = 1000
        mock_profile.review_timeout = 600
        mock_profile.reasoning = False

        def mock_get_profile(model):
            return mock_profile

        monkeypatch.setattr("scripts.run_eval.get_profile", mock_get_profile)

        # Run the function
        result = run_model_on_diff("test-model", diff_record, no_judge=True)

        # Verify result is None (no record written)
        assert result is None

    def test_first_attempt_fails_second_succeeds(self, monkeypatch):
        """Test that first attempt fails, second succeeds → one record written."""
        diff_record = {
            "id": "DIFF-001",
            "diff": "+test\n+code",
            "language": "python",
            "file": "test.py",
            "expected": "findings",
            "bugs": [],
        }

        call_count = [0]

        def mock_call_llm(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("API error on first attempt")
            return "# Review\n\nNo findings."

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)

        skill_path = Path(__file__).parent.parent / "linus-torvalds-skill" / "SKILL.md"
        monkeypatch.setattr("scripts.run_eval.MODELS", {"test-model": skill_path})

        mock_profile = MagicMock()
        mock_profile.max_tokens = 1000
        mock_profile.review_timeout = 600
        mock_profile.reasoning = False

        def mock_get_profile(model):
            return mock_profile

        monkeypatch.setattr("scripts.run_eval.get_profile", mock_get_profile)

        # Run the function
        result = run_model_on_diff("test-model", diff_record, no_judge=True)

        # Verify result is not None (record written)
        assert result is not None
        assert result["diff_id"] == "DIFF-001"
        # Verify retry happened
        assert call_count[0] == 2


class TestCrossPairsAndStatusCells:
    """Tests for _cross_pairs and _status_cells helpers."""

    def test_cross_pairs_single_model_yields_three_off_diagonal(self):
        """Test that cross mode with single model filter yields exactly 3 off-diagonal pairs."""
        # Mock MODELS to have 4 models
        models_filter = ["mistral-small-4-119b"]

        pairs = _cross_pairs(models_filter)

        # Should have exactly 3 pairs (mistral × all other models)
        assert len(pairs) == 3
        # All pairs should have mistral as reviewer (first element)
        assert all(m == "mistral-small-4-119b" for m, _ in pairs)
        # No diagonal pairs (mistral × mistral should be excluded)
        assert all(m != s for m, s in pairs)
        # Should span all other 3 models as skills
        skills = [s for _, s in pairs]
        assert set(skills) == {"gpt-oss-120b", "glm5.2", "qwen3.8-27b"}

    def test_status_cells_single_model_cross_spans_all_skills(self):
        """Test that status table cells for single model filter span all 4 skills in cross mode."""
        models_filter = ["glm5.2"]

        cells = _status_cells(models_filter, cross_mode=True)

        # Should have exactly 3 cells (glm5.2 × all other models)
        assert len(cells) == 3
        # All cells should have glm5.2 as model (first element)
        assert all(m == "glm5.2" for m, _ in cells)
        # No diagonal cells
        assert all(m != s for m, s in cells)
        # Should span all other 3 skills
        skills = [s for _, s in cells]
        assert set(skills) == {"gpt-oss-120b", "mistral-small-4-119b", "qwen3.8-27b"}

    def test_cross_pairs_with_skills_filter_spans_only_selected_skills(self):
        """Test that skills_filter restricts skill sources in cross pairs."""
        pairs = _cross_pairs(["qwen3.8-27b"], skills_filter=["glm5.2", "mistral-small-4-119b"])

        assert pairs == [
            ("qwen3.8-27b", "glm5.2"),
            ("qwen3.8-27b", "mistral-small-4-119b"),
        ]

    def test_cross_pairs_with_skills_filter_excludes_diagonal(self):
        """Test that a skills_filter containing the reviewer itself yields no self-pair."""
        pairs = _cross_pairs(["qwen3.8-27b"], skills_filter=["qwen3.8-27b"])

        assert pairs == []

    def test_status_cells_single_model_diagonal_only(self):
        """Test that status table cells for single model filter shows diagonal only."""
        models_filter = ["qwen3.8-27b"]

        cells = _status_cells(models_filter, cross_mode=False)

        # Should have exactly 1 cell (diagonal)
        assert len(cells) == 1
        # Should be the diagonal cell
        assert cells[0] == ("qwen3.8-27b", "qwen3.8-27b")


class TestParallelMode:
    """Tests for parallel execution mode."""

    def test_parallel_produces_same_records_as_sequential(self, monkeypatch, tmp_path):
        """Test that parallel mode produces the same record set as sequential with stubbed LLM."""
        import json as json_lib

        # Mock call_llm to return a simple review
        def mock_call_llm(*args, **kwargs):
            return """### [MEDIUM] Test finding
- **Type:** bug
- **Trigger:** unmatched
- **Location:** test.py:10
- **Issue:** test issue
- **Fix:** apply fix
"""

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)

        # Mock MODELS
        skill_path = Path(__file__).parent.parent / "linus-torvalds-skill" / "SKILL.md"
        monkeypatch.setattr("scripts.run_eval.MODELS", {"test-model": skill_path})

        # Mock get_profile
        mock_profile = MagicMock()
        mock_profile.max_tokens = 1000
        mock_profile.review_timeout = 600
        mock_profile.reasoning = False

        def mock_get_profile(model):
            return mock_profile

        monkeypatch.setattr("scripts.run_eval.get_profile", mock_get_profile)

        # Create test diff records
        diff_records = [
            {
                "id": "DIFF-001",
                "diff": "+test\n+code",
                "language": "python",
                "file": "test.py",
                "expected": "findings",
                "bugs": [],
            },
            {
                "id": "DIFF-002",
                "diff": "+test2\n+code2",
                "language": "python",
                "file": "test.py",
                "expected": "findings",
                "bugs": [],
            },
        ]

        output_file = tmp_path / "results.jsonl"

        # Run sequential
        existing_results = {}
        _run_pair(
            "test-model",
            "test-model",
            diff_records,
            True,
            None,
            existing_results,
            output_file,
            False,
        )

        sequential_lines = output_file.read_text().strip().split("\n")
        sequential_ids = set(json_lib.loads(line)["diff_id"] for line in sequential_lines)

        # Clear and run parallel
        output_file.unlink()

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    _run_pair,
                    "test-model",
                    "test-model",
                    diff_records,
                    True,
                    None,
                    existing_results,
                    output_file,
                    False,
                )
            ]
            for future in as_completed(futures):
                future.result()

        parallel_lines = output_file.read_text().strip().split("\n")
        parallel_ids = set(json_lib.loads(line)["diff_id"] for line in parallel_lines)

        # Both should produce the same set of diff IDs
        assert sequential_ids == parallel_ids
        assert len(sequential_lines) == len(parallel_lines) == 2

    def test_thread_safe_append_never_interleaves(self, monkeypatch, tmp_path):
        """Test that two threads appending via the locked helper never interleave lines."""
        import json as json_lib

        # Mock call_llm to return a simple review
        def mock_call_llm(*args, **kwargs):
            return """### [MEDIUM] Test finding
- **Type:** bug
- **Trigger:** unmatched
- **Location:** test.py:10
- **Issue:** test issue
- **Fix:** apply fix
"""

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)

        # Mock MODELS
        skill_path = Path(__file__).parent.parent / "linus-torvalds-skill" / "SKILL.md"
        monkeypatch.setattr("scripts.run_eval.MODELS", {"test-model": skill_path})

        # Mock get_profile
        mock_profile = MagicMock()
        mock_profile.max_tokens = 1000
        mock_profile.review_timeout = 600
        mock_profile.reasoning = False

        def mock_get_profile(model):
            return mock_profile

        monkeypatch.setattr("scripts.run_eval.get_profile", mock_get_profile)

        # Create many small diff records to increase contention
        diff_records = [
            {
                "id": f"DIFF-{i:03d}",
                "diff": "+x",
                "language": "python",
                "file": "test.py",
                "expected": "findings",
                "bugs": [],
            }
            for i in range(20)
        ]

        output_file = tmp_path / "results.jsonl"

        # Run multiple pairs in parallel to test lock contention
        from concurrent.futures import ThreadPoolExecutor, as_completed

        existing_results = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(4):  # 4 concurrent workers
                model = f"model-{i}"
                monkeypatch.setattr("scripts.run_eval.MODELS", {model: skill_path})
                futures.append(
                    executor.submit(
                        _run_pair,
                        model,
                        model,
                        diff_records[:5],
                        True,
                        None,
                        existing_results,
                        output_file,
                        False,
                    )
                )

            for future in as_completed(futures):
                future.result()

        # Verify every line parses as valid JSON
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) > 0

        for i, line in enumerate(lines, 1):
            try:
                record = json_lib.loads(line)
                assert "diff_id" in record
                assert "model" in record
            except json_lib.JSONDecodeError as e:
                raise AssertionError(f"Line {i} is not valid JSON: {line[:100]}") from e


class TestRescoreZeros:
    """Tests for _rescore_zeros write-back, judge default, and record average."""

    def _write_files(self, tmp_path):
        import json as json_lib

        diffs = tmp_path / "diffs.jsonl"
        diffs.write_text(json_lib.dumps({"id": "DIFF-T1", "bugs": [], "diff": "dummy diff"}) + "\n")
        results = tmp_path / "results.jsonl"
        results.write_text(
            json_lib.dumps(
                {
                    "diff_id": "DIFF-T1",
                    "model": "glm5.2",
                    "skill": "qwen3.8-27b",
                    "expected": "findings",
                    "refused": False,
                    "scores": {
                        "accuracy": 0,
                        "prioritization": 0,
                        "justification": 0,
                        "actionability": 0,
                    },
                    "findings": [
                        {
                            "file": "a.c",
                            "line": 1,
                            "scores": {
                                "accuracy": 0,
                                "prioritization": 0,
                                "justification": 0,
                                "actionability": 0,
                            },
                        }
                    ],
                }
            )
            + "\n"
        )
        return diffs, results

    def test_rescore_persists_and_recomputes_record_average(self, tmp_path, monkeypatch):
        """Rescored findings must be written back with recomputed record average."""
        import json as json_lib

        import scripts.run_eval as run_eval_mod

        diffs, results = self._write_files(tmp_path)
        monkeypatch.setattr(
            run_eval_mod,
            "score_finding_with_judge",
            lambda finding, bug, judge, no_judge: {
                "accuracy": 2,
                "prioritization": 1,
                "justification": 2,
                "actionability": 1,
            },
        )
        _rescore_zeros(results, diffs, False, "gpt-oss-120b")
        persisted = json_lib.loads(results.read_text().strip())
        assert persisted["findings"][0]["scores"]["accuracy"] == 2
        assert persisted["scores"] == {
            "accuracy": 2.0,
            "prioritization": 1.0,
            "justification": 2.0,
            "actionability": 1.0,
        }

    def test_rescore_defaults_judge_to_record_model(self, tmp_path, monkeypatch):
        """With judge_model=None the record's own model must judge (self-judge)."""
        import scripts.run_eval as run_eval_mod

        diffs, results = self._write_files(tmp_path)
        seen = []

        def fake(finding, bug, judge, no_judge):
            seen.append(judge)
            return {
                "accuracy": 1,
                "prioritization": 1,
                "justification": 1,
                "actionability": 1,
            }

        monkeypatch.setattr(run_eval_mod, "score_finding_with_judge", fake)
        _rescore_zeros(results, diffs, False, None)
        assert seen == ["glm5.2"]

    def test_status_counts_skill_less_diagonal_records(self, tmp_path, capsys):
        """Diagonal records without a skill field must count toward (model, model)."""
        import json as json_lib

        diffs = tmp_path / "diffs.jsonl"
        diffs.write_text(json_lib.dumps({"id": "DIFF-T1"}) + "\n")
        results = tmp_path / "results.jsonl"
        results.write_text(
            json_lib.dumps({"diff_id": "DIFF-T1", "model": "glm5.2", "findings": []}) + "\n"
        )
        _print_status_table(str(results), diffs, "glm5.2", False)
        out = capsys.readouterr().out
        assert "1/1" in out and "COMPLETE" in out
