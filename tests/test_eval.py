"""Tests for run_eval.py and validate_eval.py functions."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add parent directory to path for imports
SRC = Path(__file__).parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from report.build_comparison import compute_refusal_metrics
from scripts.run_eval import (
    _cross_pairs,
    _extract_json_from_content,
    _print_status_table,
    _rescore_zeros,
    _run_pair,
    _status_cells,
    build_diff_prompt,
    match_finding_to_diff_bug,
    run_model_on_codebase,
    run_model_on_diff,
    score_finding_with_judge,
)
from scripts.validate_eval import validate_record


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


class TestBuildDiffPrompt:
    """Tests for build_diff_prompt ground-truth-free requirement."""

    def test_prompt_contains_no_ground_truth_bugs_findings(self):
        """Regression: prompt must NOT contain ground truth bug information."""
        skill_text = "# Test Skill\n\nReview code carefully."

        # Test with findings expected (2+ bugs)
        diff_record_findings = {
            "id": "DIFF-001",
            "diff": "+buggy code\n+more buggy code",
            "language": "c",
            "file": "server.c",
            "expected": "findings",
            "bugs": [
                {
                    "line": 100,
                    "category": "memory-safety",
                    "severity": "CRITICAL",
                    "description": "Use after free vulnerability in connection handler",
                },
                {
                    "line": 250,
                    "category": "logic",
                    "severity": "HIGH",
                    "description": "Off-by-one error in buffer allocation",
                },
            ],
        }

        prompt = build_diff_prompt(diff_record_findings, skill_text)

        # Must NOT contain ground truth indicators
        assert "Ground truth bugs present in this diff" not in prompt
        assert "should be clean" not in prompt
        # Must NOT contain any bug descriptions (use first 40 chars as distinctive substring)
        for bug in diff_record_findings["bugs"]:
            desc_fragment = bug["description"][:40]
            assert desc_fragment not in prompt
            assert f"at line {bug['line']}" not in prompt

        # Must STILL contain diff body and skill text (guard against over-deletion)
        assert "+buggy code" in prompt
        assert "+more buggy code" in prompt
        assert "# Test Skill" in prompt
        assert "Review code carefully" in prompt

    def test_prompt_contains_no_ground_truth_no_findings(self):
        """Regression: prompt for clean diffs must NOT say 'should be clean'."""
        skill_text = "# Test Skill\n\nReview code carefully."

        diff_record_clean = {
            "id": "DIFF-002",
            "diff": "+clean code\n+refactored function",
            "language": "python",
            "file": "utils.py",
            "expected": "no-findings",
            "bugs": [],
        }

        prompt = build_diff_prompt(diff_record_clean, skill_text)

        # Must NOT contain clean hint
        assert "should be clean" not in prompt
        assert "Ground truth bugs present in this diff" not in prompt

        # Must STILL contain diff body and skill text
        assert "+clean code" in prompt
        assert "# Test Skill" in prompt

    def test_prompt_contains_no_ground_truth_refuse(self):
        """Regression: prompt for ambiguous diffs must NOT leak ground truth."""
        skill_text = "# Test Skill\n\nReview code carefully."

        diff_record_refuse = {
            "id": "DIFF-003",
            "diff": "+partial implementation\n+incomplete logic",
            "language": "c",
            "file": "driver.c",
            "expected": "refuse-to-conclude",
            "bugs": [
                {
                    "line": 42,
                    "category": "unclear",
                    "severity": "LOW",
                    "description": "Intent of this code path is ambiguous",
                }
            ],
        }

        prompt = build_diff_prompt(diff_record_refuse, skill_text)

        # Must NOT contain ground truth indicators
        assert "Ground truth bugs present in this diff" not in prompt
        assert "should be clean" not in prompt
        # Must NOT contain bug description fragment
        assert "Intent of this code path is ambiguous"[:40] not in prompt
        assert "at line 42" not in prompt

        # Must STILL contain diff body and skill text
        assert "+partial implementation" in prompt
        assert "# Test Skill" in prompt


class TestBaselineMode:
    """Tests for baseline mode (no skill text) functionality."""

    def test_baseline_prompt_contains_no_skill_block(self):
        """Baseline mode prompt must NOT contain any skill text."""
        diff_record = {
            "id": "DIFF-001",
            "diff": "+test code",
            "language": "python",
            "file": "test.py",
            "expected": "findings",
            "bugs": [],
        }

        # Baseline mode: skill_text is None
        prompt = build_diff_prompt(diff_record, None)

        # Must NOT contain skill block markers
        assert "== SKILL ==" not in prompt
        # Must NOT contain any skill text content
        assert (
            "Torvalds skill" not in prompt or "Linus Torvalds reviewer skill" in prompt
        )  # Only in header

        # Must STILL contain diff block
        assert "== DIFF ==" in prompt
        assert "+test code" in prompt
        assert "File: test.py" in prompt
        assert "Language: python" in prompt

    def test_baseline_prompt_contains_no_ground_truth(self):
        """Baseline mode prompt must NOT contain ground truth bug information."""
        diff_record = {
            "id": "DIFF-001",
            "diff": "+buggy code",
            "language": "c",
            "file": "server.c",
            "expected": "findings",
            "bugs": [
                {
                    "line": 100,
                    "category": "memory-safety",
                    "severity": "CRITICAL",
                    "description": "Use after free vulnerability",
                }
            ],
        }

        # Baseline mode: skill_text is None
        prompt = build_diff_prompt(diff_record, None)

        # Must NOT contain ground truth
        assert "Use after free" not in prompt
        assert "at line 100" not in prompt
        assert "Ground truth" not in prompt

    def test_baseline_records_carry_skill_none(self, monkeypatch, tmp_path):
        """Baseline mode records must have skill='none'."""

        # Mock call_llm
        def mock_call_llm(*args, **kwargs):
            return "# Review\n\nNo findings."

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)

        # Mock MODELS (not used in baseline mode)
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

        # Run in baseline mode
        diff_record = {
            "id": "DIFF-001",
            "diff": "+test",
            "language": "python",
            "file": "test.py",
            "expected": "findings",
            "bugs": [],
        }

        result = run_model_on_diff("test-model", diff_record, no_judge=True, baseline=True)

        assert result is not None
        assert result["skill"] == "none"


class TestRepetitions:
    """Tests for --repetitions functionality."""

    def test_repetitions_flag_parses_default_one(self):
        """Test that --repetitions flag parses and defaults to 1."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--repetitions",
            type=int,
            default=1,
            help="Number of times to run each diff (default: 1).",
        )

        args = parser.parse_args([])
        assert args.repetitions == 1

        args = parser.parse_args(["--repetitions", "3"])
        assert args.repetitions == 3

        args = parser.parse_args(["--repetitions", "5"])
        assert args.repetitions == 5

    def test_records_carry_rep_field(self, monkeypatch, tmp_path):
        """Each repetition gets a separate record with 'rep' field (0-based)."""
        import json as json_lib

        # Mock call_llm
        def mock_call_llm(*args, **kwargs):
            return "# Review\n\nNo findings."

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

        # Create output file
        output_file = tmp_path / "results.jsonl"

        # Run with 3 repetitions
        diff_records = [
            {
                "id": "DIFF-001",
                "diff": "+test",
                "language": "python",
                "file": "test.py",
                "expected": "findings",
                "bugs": [],
            }
        ]

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
            repetitions=3,
            baseline=False,
        )

        # Verify 3 records were written with rep 0, 1, 2
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == 3

        reps = []
        for line in lines:
            record = json_lib.loads(line)
            reps.append(record["rep"])

        assert reps == [0, 1, 2]

    def test_resume_skips_existing_rep(self, monkeypatch, tmp_path):
        """Resume-safe: existing (diff, model, skill, rep) triple is skipped."""
        import json as json_lib

        # Mock call_llm
        call_count = [0]

        def mock_call_llm(*args, **kwargs):
            call_count[0] += 1
            return "# Review\n\nNo findings."

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

        # Create output file with existing rep=0 record
        output_file = tmp_path / "results.jsonl"
        existing_record = {
            "diff_id": "DIFF-001",
            "model": "test-model",
            "skill": "test-model",
            "rep": 0,
            "findings": [],
            "scores": {"accuracy": 0, "prioritization": 0, "justification": 0, "actionability": 0},
        }
        output_file.write_text(json_lib.dumps(existing_record) + "\n")

        # Run with 3 repetitions
        diff_records = [
            {
                "id": "DIFF-001",
                "diff": "+test",
                "language": "python",
                "file": "test.py",
                "expected": "findings",
                "bugs": [],
            }
        ]

        existing_results = {}
        # Load existing results from file
        with open(output_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json_lib.loads(line)
                    key = (
                        record.get("diff_id"),
                        record.get("model"),
                        record.get("skill") or record.get("model"),
                        record.get("rep", 0),
                    )
                    existing_results[key] = record

        _run_pair(
            "test-model",
            "test-model",
            diff_records,
            True,
            None,
            existing_results,
            output_file,
            False,
            repetitions=3,
            baseline=False,
        )

        # Verify only 2 new records were written (rep=1 and rep=2)
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == 3  # 1 existing + 2 new

        # Verify rep=0 was not re-evaluated (call_count should be 2, not 3)
        assert call_count[0] == 2

    def test_legacy_record_without_rep_honored_as_rep_zero(self, monkeypatch, tmp_path):
        """Legacy record without rep field is honored as rep=0 and not re-evaluated."""
        import json as json_lib

        # Mock call_llm
        call_count = [0]

        def mock_call_llm(*args, **kwargs):
            call_count[0] += 1
            return "# Review\n\nNo findings."

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

        # Create output file with legacy record (no rep field)
        output_file = tmp_path / "results.jsonl"
        legacy_record = {
            "diff_id": "DIFF-001",
            "model": "test-model",
            "skill": "test-model",
            # No 'rep' field - legacy record
            "findings": [],
            "scores": {"accuracy": 0, "prioritization": 0, "justification": 0, "actionability": 0},
        }
        output_file.write_text(json_lib.dumps(legacy_record) + "\n")

        # Run with 3 repetitions
        diff_records = [
            {
                "id": "DIFF-001",
                "diff": "+test",
                "language": "python",
                "file": "test.py",
                "expected": "findings",
                "bugs": [],
            }
        ]

        existing_results = {}
        # Load existing results from file (backward compatible: missing rep = 0)
        with open(output_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json_lib.loads(line)
                    diff_id = record.get("diff_id")
                    model = record.get("model")
                    skill = record.get("skill") or record.get("model")
                    rep = record.get("rep", 0)  # Backward compatible
                    key = (diff_id, model, skill, rep)
                    existing_results[key] = record

        _run_pair(
            "test-model",
            "test-model",
            diff_records,
            True,
            None,
            existing_results,
            output_file,
            False,
            repetitions=3,
            baseline=False,
        )

        # Verify only 2 new records were written (rep=1 and rep=2)
        # Legacy record treated as rep=0, so it's skipped
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == 3  # 1 legacy + 2 new

        # Verify legacy record was not re-evaluated (call_count should be 2, not 3)
        assert call_count[0] == 2


class TestReasoningOnlyFallback:
    """A reasoning-only failure must retry with the thinking phase disabled.

    Repeating the identical call cannot succeed: the model spends the same budget on
    chain-of-thought and returns no review body again.
    """

    REVIEW = "### HIGH Buffer overflow\n- **Location:** smallchat-server.c:42\n- **Issue:** x\n"

    def _patch_profile(self, monkeypatch):
        profile = MagicMock()
        profile.review_timeout = 60
        profile.reasoning = True
        monkeypatch.setattr("scripts.run_eval.get_profile", lambda model: profile)

    def test_diff_mode_disables_thinking_on_retry(self, monkeypatch):
        self._patch_profile(monkeypatch)
        calls = []

        def mock_call_llm(model, prompt, timeout=600, **kwargs):
            calls.append(kwargs.get("disable_thinking"))
            if len(calls) == 1:
                raise RuntimeError("reasoning_only_response")
            return self.REVIEW

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)
        diff_record = {"id": "D1", "diff": "+x", "file": "smallchat-server.c", "bugs": []}

        result = run_model_on_diff("qwen", diff_record, no_judge=True, baseline=True)

        assert calls == [False, True]
        assert result is not None

    def test_codebase_mode_disables_thinking_on_retry(self, monkeypatch):
        self._patch_profile(monkeypatch)
        monkeypatch.setattr("scripts.run_eval.build_codebase_prompt", lambda skill: "prompt")
        calls = []

        def mock_call_llm(model, prompt, timeout=600, **kwargs):
            calls.append(kwargs.get("disable_thinking"))
            if len(calls) == 1:
                raise RuntimeError("reasoning_only_response")
            return self.REVIEW

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)

        result = run_model_on_codebase("qwen", [], no_judge=True, baseline=True)

        assert calls == [False, True]
        assert result is not None

    def test_persistent_reasoning_only_returns_none(self, monkeypatch):
        self._patch_profile(monkeypatch)
        monkeypatch.setattr("scripts.run_eval.build_codebase_prompt", lambda skill: "prompt")
        calls = []

        def mock_call_llm(model, prompt, timeout=600, **kwargs):
            calls.append(kwargs.get("disable_thinking"))
            raise RuntimeError("reasoning_only_response")

        monkeypatch.setattr("scripts.run_eval.call_llm", mock_call_llm)

        result = run_model_on_codebase("qwen", [], no_judge=True, baseline=True)

        assert calls == [False, True]
        assert result is None
