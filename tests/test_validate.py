"""Tests for validate.py JSON schema validation.

Tests the validation functions for moves.jsonl, patterns.json, and
calibration.json files, covering all error conditions and valid cases.
"""

import json

import pytest

from torvalds_skill.validate import (
    _validate_move,
    validate_moves,
    validate_patterns,
    validate_calibration,
)
from torvalds_skill.models import CATEGORIES, SEVERITIES


class TestValidateMove:
    """Test _validate_move pure function for individual move validation."""

    def test_valid_move_returns_empty_list(self):
        """A valid move with all required fields and correct types returns no errors."""
        move = {
            "category": "correctness",
            "severity": "reject",
            "trigger": "memory leak",
            "principle": "Always free allocated memory",
        }
        errors = _validate_move(move)
        assert errors == []

    def test_valid_move_with_optional_quote(self):
        """A valid move with optional quote field returns no errors."""
        move = {
            "category": "style",
            "severity": "nitpick",
            "trigger": "naming",
            "principle": "Use clear names",
            "quote": "Naming is hard",
        }
        errors = _validate_move(move)
        assert errors == []

    def test_missing_category(self):
        """Missing category field produces an error."""
        move = {
            "severity": "reject",
            "trigger": "test",
            "principle": "test",
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert "Missing required field: category" in errors[0]

    def test_missing_severity(self):
        """Missing severity field produces an error."""
        move = {
            "category": "correctness",
            "trigger": "test",
            "principle": "test",
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert "Missing required field: severity" in errors[0]

    def test_missing_trigger(self):
        """Missing trigger field produces an error."""
        move = {
            "category": "correctness",
            "severity": "reject",
            "principle": "test",
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert "Missing required field: trigger" in errors[0]

    def test_missing_principle(self):
        """Missing principle field produces an error."""
        move = {
            "category": "correctness",
            "severity": "reject",
            "trigger": "test",
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert "Missing required field: principle" in errors[0]

    def test_multiple_missing_fields(self):
        """Multiple missing fields produce multiple errors."""
        move = {"category": "correctness"}
        errors = _validate_move(move)
        assert len(errors) == 3
        assert any("Missing required field: severity" in e for e in errors)
        assert any("Missing required field: trigger" in e for e in errors)
        assert any("Missing required field: principle" in e for e in errors)

    @pytest.mark.parametrize("category", [
        "invalid-category",
        "Correctness",
        "CORRECTNESS",
        "unknown",
    ])
    def test_invalid_category(self, category):
        """Invalid category values produce an error."""
        move = {
            "category": category,
            "severity": "reject",
            "trigger": "test",
            "principle": "test",
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert f"Invalid category '{category}'" in errors[0]

    @pytest.mark.parametrize("severity", [
        "invalid-severity",
        "Reject",
        "REJECT",
        "unknown",
    ])
    def test_invalid_severity(self, severity):
        """Invalid severity values produce an error."""
        move = {
            "category": "correctness",
            "severity": severity,
            "trigger": "test",
            "principle": "test",
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert f"Invalid severity '{severity}'" in errors[0]

    def test_trigger_not_string(self):
        """Non-string trigger field produces an error."""
        move = {
            "category": "correctness",
            "severity": "reject",
            "trigger": 123,
            "principle": "test",
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert "Field 'trigger' must be a string" in errors[0]

    def test_principle_not_string(self):
        """Non-string principle field produces an error."""
        move = {
            "category": "correctness",
            "severity": "reject",
            "trigger": "test",
            "principle": ["array"],
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert "Field 'principle' must be a string" in errors[0]

    def test_quote_not_string(self):
        """Non-string quote field produces an error."""
        move = {
            "category": "correctness",
            "severity": "reject",
            "trigger": "test",
            "principle": "test",
            "quote": {"key": "value"},
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert "Field 'quote' must be a string" in errors[0]

    def test_trigger_null(self):
        """Null trigger field produces an error."""
        move = {
            "category": "correctness",
            "severity": "reject",
            "trigger": None,
            "principle": "test",
        }
        errors = _validate_move(move)
        assert len(errors) == 1
        assert "Field 'trigger' must be a string" in errors[0]

    def test_multiple_type_errors(self):
        """Multiple type errors are all reported."""
        move = {
            "category": "correctness",
            "severity": "reject",
            "trigger": 123,
            "principle": None,
            "quote": [],
        }
        errors = _validate_move(move)
        assert len(errors) == 3
        assert any("Field 'trigger' must be a string" in e for e in errors)
        assert any("Field 'principle' must be a string" in e for e in errors)
        assert any("Field 'quote' must be a string" in e for e in errors)

    def test_line_num_prefix_in_errors(self):
        """Errors include line number prefix when provided."""
        move = {"category": "invalid", "severity": "reject", "trigger": "test", "principle": "test"}
        errors = _validate_move(move, line_num=42)
        assert len(errors) == 1
        assert "Line 42:" in errors[0]
        assert "Invalid category" in errors[0]

    @pytest.mark.parametrize("valid_category", CATEGORIES)
    def test_all_valid_categories(self, valid_category):
        """All valid categories pass validation."""
        move = {
            "category": valid_category,
            "severity": "reject",
            "trigger": "test",
            "principle": "test",
        }
        errors = _validate_move(move)
        assert errors == []

    @pytest.mark.parametrize("valid_severity", SEVERITIES)
    def test_all_valid_severities(self, valid_severity):
        """All valid severities pass validation."""
        move = {
            "category": "correctness",
            "severity": valid_severity,
            "trigger": "test",
            "principle": "test",
        }
        errors = _validate_move(move)
        assert errors == []


class TestValidateMoves:
    """Test validate_moves function for moves.jsonl files."""

    def test_valid_moves_file(self, tmp_path):
        """A valid moves.jsonl file returns no errors."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text(
            '{"email_message_id": "test@example.com", "moves": [{"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test"}]}\n'
        )
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is True
        assert errors == []

    def test_missing_file(self, tmp_path):
        """Missing file returns False with file not found error."""
        is_valid, errors = validate_moves(str(tmp_path / "nonexistent.jsonl"))
        assert is_valid is False
        assert len(errors) == 1
        assert "File not found" in errors[0]

    def test_invalid_json_line(self, tmp_path):
        """Invalid JSON on a line produces an error."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text('{"email_message_id": "test@example.com", "moves": [\n')
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]

    def test_empty_file(self, tmp_path):
        """Empty file is considered valid (no moves to validate)."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text("")
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is True
        assert errors == []

    def test_missing_email_message_id(self, tmp_path):
        """Record missing email_message_id produces an error."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text(
            '{"moves": [{"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test"}]}\n'
        )
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Missing required field 'email_message_id'" in errors[0]

    def test_missing_moves_field(self, tmp_path):
        """Record missing moves field produces an error."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text('{"email_message_id": "test@example.com"}\n')
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Missing required field 'moves'" in errors[0]

    def test_moves_not_array(self, tmp_path):
        """Moves field that is not an array produces an error."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text(
            '{"email_message_id": "test@example.com", "moves": "not an array"}\n'
        )
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Field 'moves' must be an array" in errors[0]

    def test_invalid_move_in_moves(self, tmp_path):
        """Invalid move within moves array produces errors."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text(
            '{"email_message_id": "test@example.com", "moves": [{"category": "invalid-category", "severity": "reject", "trigger": "test", "principle": "test"}]}\n'
        )
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is False
        assert len(errors) >= 1
        assert any("Invalid category" in e for e in errors)

    def test_multiple_records_all_valid(self, tmp_path):
        """Multiple valid records all pass validation."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text(
            '{"email_message_id": "test1@example.com", "moves": [{"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test"}]}\n'
            '{"email_message_id": "test2@example.com", "moves": [{"category": "style", "severity": "nitpick", "trigger": "test", "principle": "test"}]}\n'
        )
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is True
        assert errors == []

    def test_empty_lines_ignored(self, tmp_path):
        """Empty lines in the file are ignored."""
        moves_file = tmp_path / "moves.jsonl"
        moves_file.write_text(
            '{"email_message_id": "test@example.com", "moves": [{"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test"}]}\n'
            '\n'
            '\n'
        )
        is_valid, errors = validate_moves(str(moves_file))
        assert is_valid is True
        assert errors == []


class TestValidatePatterns:
    """Test validate_patterns function for patterns.json files."""

    def test_valid_patterns_file(self, tmp_path):
        """A valid patterns.json file returns no errors."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text(
            '[{"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test"}]'
        )
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is True
        assert errors == []

    def test_missing_file(self, tmp_path):
        """Missing file returns False with file not found error."""
        is_valid, errors = validate_patterns(str(tmp_path / "nonexistent.json"))
        assert is_valid is False
        assert len(errors) == 1
        assert "File not found" in errors[0]

    def test_invalid_json(self, tmp_path):
        """Invalid JSON produces an error."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text('not valid json')
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]

    def test_empty_file(self, tmp_path):
        """Empty file produces invalid JSON error."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text("")
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]

    def test_not_array(self, tmp_path):
        """JSON that is not an array produces an error."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text('{"not": "an array"}')
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "File must contain a JSON array" in errors[0]

    def test_pattern_not_object(self, tmp_path):
        """Array element that is not an object produces an error."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text('["not an object"]')
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Pattern 0: Must be an object" in errors[0]

    def test_missing_required_fields(self, tmp_path):
        """Pattern missing required fields produces errors."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text('[{}]')
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 4
        assert any("Missing required field: category" in e for e in errors)
        assert any("Missing required field: severity" in e for e in errors)
        assert any("Missing required field: trigger" in e for e in errors)
        assert any("Missing required field: principle" in e for e in errors)

    def test_invalid_category(self, tmp_path):
        """Pattern with invalid category produces an error."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text(
            '[{"category": "invalid", "severity": "reject", "trigger": "test", "principle": "test"}]'
        )
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid category" in errors[0]

    def test_invalid_severity(self, tmp_path):
        """Pattern with invalid severity produces an error."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text(
            '[{"category": "correctness", "severity": "invalid", "trigger": "test", "principle": "test"}]'
        )
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid severity" in errors[0]

    def test_invalid_source(self, tmp_path):
        """Pattern with invalid source produces an error."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text(
            '[{"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test", "source": "invalid"}]'
        )
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid source" in errors[0]

    def test_valid_source_email(self, tmp_path):
        """Pattern with source 'email' passes validation."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text(
            '[{"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test", "source": "email"}]'
        )
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is True
        assert errors == []

    def test_valid_source_interview(self, tmp_path):
        """Pattern with source 'interview' passes validation."""
        patterns_file = tmp_path / "patterns.json"
        patterns_file.write_text(
            '[{"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test", "source": "interview"}]'
        )
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is True
        assert errors == []

    def test_multiple_patterns_all_valid(self, tmp_path):
        """Multiple valid patterns all pass validation."""
        patterns_file = tmp_path / "patterns.json"
        patterns = [
            {"category": "correctness", "severity": "reject", "trigger": "test1", "principle": "test1"},
            {"category": "style", "severity": "nitpick", "trigger": "test2", "principle": "test2"},
        ]
        patterns_file.write_text(json.dumps(patterns))
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is True
        assert errors == []

    def test_multiple_patterns_with_errors(self, tmp_path):
        """Multiple patterns with some errors reports all errors."""
        patterns_file = tmp_path / "patterns.json"
        patterns = [
            {"category": "correctness", "severity": "reject", "trigger": "test", "principle": "test"},
            {"category": "invalid"},
        ]
        patterns_file.write_text(json.dumps(patterns))
        is_valid, errors = validate_patterns(str(patterns_file))
        assert is_valid is False
        assert len(errors) == 4  # 4 missing fields in second pattern


class TestValidateCalibration:
    """Test validate_calibration function for calibration.json files."""

    def test_valid_calibration_file(self, tmp_path):
        """A valid calibration.json file returns no errors."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text(
            json.dumps({
                "severity_by_category": {},
                "temporal_trends": {},
                "corpus_stats": {"total_moves": 100},
            })
        )
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is True
        assert errors == []

    def test_missing_file(self, tmp_path):
        """Missing file returns False with file not found error."""
        is_valid, errors = validate_calibration(str(tmp_path / "nonexistent.json"))
        assert is_valid is False
        assert len(errors) == 1
        assert "File not found" in errors[0]

    def test_invalid_json(self, tmp_path):
        """Invalid JSON produces an error."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text('not valid json')
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]

    def test_empty_file(self, tmp_path):
        """Empty file produces invalid JSON error."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text("")
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]

    def test_not_object(self, tmp_path):
        """JSON that is not an object produces an error."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text('["not", "an", "object"]')
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "File must contain a JSON object" in errors[0]

    def test_missing_required_fields(self, tmp_path):
        """Calibration missing required fields produces errors."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text('{}')
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is False
        assert len(errors) == 3
        assert any("Missing required field: severity_by_category" in e for e in errors)
        assert any("Missing required field: temporal_trends" in e for e in errors)
        assert any("Missing required field: corpus_stats" in e for e in errors)

    def test_required_field_not_object(self, tmp_path):
        """Required field that is not an object produces an error."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text(
            json.dumps({
                "severity_by_category": [],
                "temporal_trends": {},
                "corpus_stats": {"total_moves": 100},
            })
        )
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Field 'severity_by_category' must be an object" in errors[0]

    def test_corpus_stats_missing_total_moves(self, tmp_path):
        """corpus_stats without total_moves produces an error."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text(
            json.dumps({
                "severity_by_category": {},
                "temporal_trends": {},
                "corpus_stats": {"other_field": 1},
            })
        )
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Field 'corpus_stats' must have 'total_moves' key" in errors[0]

    def test_corpus_stats_total_moves_not_int(self, tmp_path):
        """corpus_stats.total_moves that is not an integer produces an error."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text(
            json.dumps({
                "severity_by_category": {},
                "temporal_trends": {},
                "corpus_stats": {"total_moves": "not an int"},
            })
        )
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Field 'corpus_stats.total_moves' must be an integer" in errors[0]

    def test_corpus_stats_total_moves_is_float(self, tmp_path):
        """corpus_stats.total_moves that is a float produces an error."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text(
            json.dumps({
                "severity_by_category": {},
                "temporal_trends": {},
                "corpus_stats": {"total_moves": 100.5},
            })
        )
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is False
        assert len(errors) == 1
        assert "Field 'corpus_stats.total_moves' must be an integer" in errors[0]

    def test_corpus_stats_total_moves_is_zero(self, tmp_path):
        """corpus_stats.total_moves of zero (valid int) passes validation."""
        calibration_file = tmp_path / "calibration.json"
        calibration_file.write_text(
            json.dumps({
                "severity_by_category": {},
                "temporal_trends": {},
                "corpus_stats": {"total_moves": 0},
            })
        )
        is_valid, errors = validate_calibration(str(calibration_file))
        assert is_valid is True
        assert errors == []