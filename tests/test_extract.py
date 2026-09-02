"""Tests for extract.py LLM extraction logic.

Verifies JSON parsing of LLM responses, move extraction with mocked LLM calls,
and batch extraction with file I/O. No real API calls are made.
"""

import json
from unittest.mock import patch

import pytest

from torvalds_skill.extract import (
    HARD_LANGUAGE_INDICATORS,
    SOFT_LANGUAGE_INDICATORS,
    _parse_batch_response,
    _parse_json_response,
    _validate_severity_consistency,
    extract_batch,
    extract_moves,
)
from torvalds_skill.models import EmailRecord


def _make_email(
    message_id: str = "test@example.com",
    subject: str = "Re: Some patch",
    body: str = "This code is broken. You cannot free the buffer before the last use. That is a use-after-free bug.",
) -> EmailRecord:
    return EmailRecord(
        message_id=message_id,
        from_name="Linus Torvalds",
        from_email="torvalds@linux.org",
        date="2024-01-01",
        subject=subject,
        in_reply_to="parent@example.com",
        body=body,
    )


class TestParseJsonResponse:
    """Test _parse_json_response handles various LLM output formats."""

    def test_plain_json(self):
        content = '{"moves": [{"trigger": "x", "principle": "y"}]}'
        result = _parse_json_response(content)
        assert result == {"moves": [{"trigger": "x", "principle": "y"}]}

    def test_json_with_leading_whitespace(self):
        content = '  \n  {"moves": []}  '
        result = _parse_json_response(content)
        assert result == {"moves": []}

    def test_json_wrapped_in_markdown_fence(self):
        content = '```json\n{"moves": []}\n```'
        result = _parse_json_response(content)
        assert result == {"moves": []}

    def test_json_wrapped_in_bare_fence(self):
        content = '```\n{"moves": []}\n```'
        result = _parse_json_response(content)
        assert result == {"moves": []}

    def test_empty_moves(self):
        content = '{"moves": []}'
        result = _parse_json_response(content)
        assert result["moves"] == []

    def test_multiple_moves(self):
        content = json.dumps(
            {
                "moves": [
                    {"trigger": "a", "principle": "b", "severity": "reject"},
                    {"trigger": "c", "principle": "d", "severity": "nitpick"},
                ]
            }
        )
        result = _parse_json_response(content)
        assert len(result["moves"]) == 2

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("not json at all")

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("")

    def test_json_with_extra_text_after(self):
        content = '{"moves": []}\nSome trailing text'
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(content)


class TestExtractMoves:
    """Test extract_moves with mocked LLM calls."""

    @patch("torvalds_skill.extract._call_llm")
    def test_successful_extraction(self, mock_call):
        mock_call.return_value = {
            "moves": [
                {
                    "trigger": "use-after-free",
                    "principle": "Don't free before last use",
                    "response": "This is broken.",
                    "severity": "reject",
                    "category": "memory-safety",
                }
            ]
        }
        email = _make_email()
        result = extract_moves(email)

        assert result["email_message_id"] == "test@example.com"
        assert result["email_subject"] == "Re: Some patch"
        assert len(result["moves"]) == 1
        assert result["moves"][0]["trigger"] == "use-after-free"
        assert "error" not in result

    @patch("torvalds_skill.extract._call_llm")
    def test_empty_moves(self, mock_call):
        mock_call.return_value = {"moves": []}
        email = _make_email()
        result = extract_moves(email)

        assert result["moves"] == []
        assert "error" not in result

    @patch("torvalds_skill.extract._call_llm")
    def test_missing_moves_key(self, mock_call):
        mock_call.return_value = {}
        email = _make_email()
        result = extract_moves(email)

        assert result["moves"] == []

    @patch("torvalds_skill.extract._call_llm")
    def test_llm_error_returns_error_field(self, mock_call):
        mock_call.side_effect = RuntimeError("LLM call failed after 3 retries: timeout")
        email = _make_email()
        result = extract_moves(email)

        assert result["moves"] == []
        assert "error" in result
        assert "timeout" in result["error"]

    @patch("torvalds_skill.extract._call_llm")
    def test_email_metadata_preserved(self, mock_call):
        mock_call.return_value = {"moves": []}
        email = _make_email(
            message_id="unique@id",
            subject="Re: [PATCH] fix bug",
        )
        result = extract_moves(email)

        assert result["email_message_id"] == "unique@id"
        assert result["email_subject"] == "Re: [PATCH] fix bug"
        assert result["email_date"] == "2024-01-01"

    @patch("torvalds_skill.extract._call_llm")
    def test_multiple_moves_extracted(self, mock_call):
        mock_call.return_value = {
            "moves": [{"trigger": f"t{i}", "principle": f"p{i}"} for i in range(5)]
        }
        email = _make_email()
        result = extract_moves(email)

        assert len(result["moves"]) == 5


class TestExtractBatch:
    """Test extract_batch with file I/O and mocked extraction."""

    @patch("torvalds_skill.extract.extract_moves")
    def test_writes_jsonl_file(self, mock_extract, tmp_path):
        mock_extract.return_value = {
            "email_message_id": "a@b",
            "moves": [{"trigger": "x"}],
        }
        out = tmp_path / "out.jsonl"
        emails = [_make_email(message_id="a@b")]

        result = extract_batch(emails, str(out))

        assert out.exists()
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["email_message_id"] == "a@b"
        assert result["processed"] == 1
        assert result["moves"] == 1
        assert result["errors"] == 0

    @patch("torvalds_skill.extract.extract_moves")
    def test_append_mode(self, mock_extract, tmp_path):
        mock_extract.return_value = {
            "email_message_id": "c@d",
            "moves": [],
        }
        out = tmp_path / "out.jsonl"
        out.write_text('{"existing": true}\n', encoding="utf-8")

        extract_batch([_make_email(message_id="c@d")], str(out), append=True)

        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    @patch("torvalds_skill.extract.extract_moves")
    def test_overwrite_mode(self, mock_extract, tmp_path):
        mock_extract.return_value = {
            "email_message_id": "e@f",
            "moves": [],
        }
        out = tmp_path / "out.jsonl"
        out.write_text('{"existing": true}\n', encoding="utf-8")

        extract_batch([_make_email(message_id="e@f")], str(out), append=False)

        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert "existing" not in lines[0]

    @patch("torvalds_skill.extract.extract_moves")
    def test_counts_errors(self, mock_extract, tmp_path):
        mock_extract.return_value = {
            "email_message_id": "x",
            "moves": [],
            "error": "timeout",
        }
        out = tmp_path / "out.jsonl"

        result = extract_batch([_make_email()], str(out))

        assert result["errors"] == 1
        assert result["moves"] == 0

    @patch("torvalds_skill.extract.extract_moves")
    def test_multiple_emails(self, mock_extract, tmp_path):
        mock_extract.side_effect = [
            {"email_message_id": "1", "moves": [{"trigger": "a"}, {"trigger": "b"}]},
            {"email_message_id": "2", "moves": [{"trigger": "c"}]},
            {"email_message_id": "3", "moves": []},
        ]
        out = tmp_path / "out.jsonl"
        emails = [_make_email(message_id=str(i)) for i in range(3)]

        result = extract_batch(emails, str(out))

        assert result["processed"] == 3
        assert result["moves"] == 3
        assert result["errors"] == 0
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3

    @patch("torvalds_skill.extract.extract_moves")
    def test_empty_batch(self, mock_extract, tmp_path):
        out = tmp_path / "out.jsonl"
        result = extract_batch([], str(out))

        assert result["processed"] == 0
        assert result["moves"] == 0
        assert result["errors"] == 0


class TestInputValidation:
    """Test input validation in extract_moves."""

    def test_valid_email_passes_validation(self):
        """Valid email passes validation (no error in output)."""
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.return_value = {"moves": []}
            email = _make_email()
            result = extract_moves(email)

            assert "error" not in result
            assert result["moves"] == []

    def test_missing_body_returns_validation_error(self):
        """Missing body returns validation_failed error with empty moves."""
        email = _make_email(body="")
        result = extract_moves(email)

        assert result["moves"] == []
        assert "error" in result
        assert "validation_failed" in result["error"]
        assert "body" in result["error"]

    def test_missing_message_id_returns_validation_error(self):
        """Missing message_id returns validation_failed error with empty moves."""
        email = _make_email(message_id="")
        result = extract_moves(email)

        assert result["moves"] == []
        assert "error" in result
        assert "validation_failed" in result["error"]
        assert "message_id" in result["error"]

    def test_missing_subject_returns_validation_error(self):
        """Missing subject returns validation_failed error with empty moves."""
        email = _make_email(subject="")
        result = extract_moves(email)

        assert result["moves"] == []
        assert "error" in result
        assert "validation_failed" in result["error"]
        assert "subject" in result["error"]

    def test_missing_from_name_returns_validation_error(self):
        """Missing from_name returns validation_failed error with empty moves."""
        email = EmailRecord(
            message_id="test@example.com",
            from_name="",
            from_email="torvalds@linux.org",
            date="2024-01-01",
            subject="Re: Some patch",
            in_reply_to="parent@example.com",
            body="Valid body content here.",
        )
        result = extract_moves(email)

        assert result["moves"] == []
        assert "error" in result
        assert "validation_failed" in result["error"]
        assert "from_name" in result["error"]

    def test_very_short_body_logs_warning(self):
        """Very short body (<10 chars) logs warning but still attempts extraction."""
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.return_value = {"moves": []}
            email = _make_email(body="short")
            result = extract_moves(email)

            # Should not have validation error, extraction attempted
            assert "error" not in result or "validation_failed" not in result.get("error", "")
            # _call_llm was called, meaning validation passed
            mock_call.assert_called_once()

    def test_very_long_body_logs_warning(self):
        """Very long body (>100K chars) logs warning but still attempts extraction."""
        with patch("torvalds_skill.extract._call_llm") as mock_call:
            mock_call.return_value = {"moves": []}
            long_body = "x" * 100001
            email = _make_email(body=long_body)
            result = extract_moves(email)

            # Should not have validation error, extraction attempted
            assert "error" not in result or "validation_failed" not in result.get("error", "")
            # _call_llm was called, meaning validation passed
            mock_call.assert_called_once()


class TestSeverityConsistency:
    """Test severity consistency validation logic."""

    def test_consistent_reject_with_hard_language(self):
        """Reject severity with hard language is consistent."""
        move = {
            "severity": "reject",
            "description": "This code is broken and will crash.",
            "trigger": "use-after-free bug",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True
        assert reason == ""

    def test_consistent_request_changes_with_hard_language(self):
        """Request-changes severity with hard language is consistent."""
        move = {
            "severity": "request-changes",
            "description": "This is wrong and cannot work.",
            "trigger": "memory leak",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True
        assert reason == ""

    def test_consistent_nitpick_with_soft_language(self):
        """Nitpick severity with soft language is consistent."""
        move = {
            "severity": "nitpick",
            "description": "Consider improving the style here.",
            "trigger": "cosmetic issue",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True
        assert reason == ""

    def test_consistent_nitpick_with_mixed_language(self):
        """Nitpick with both hard and soft language is consistent."""
        move = {
            "severity": "nitpick",
            "description": "This might be broken, but consider fixing it.",
            "trigger": "minor issue",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True
        assert reason == ""

    def test_inconsistent_reject_with_soft_language(self):
        """Reject severity with only soft language is inconsistent."""
        move = {
            "severity": "reject",
            "description": "Consider improving this code.",
            "trigger": "could be better",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is False
        assert "uses only soft language" in reason

    def test_inconsistent_request_changes_with_soft_language(self):
        """Request-changes severity with only soft language is inconsistent."""
        move = {
            "severity": "request-changes",
            "description": "It might be nice to fix this.",
            "trigger": "optional improvement",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is False
        assert "uses only soft language" in reason

    def test_inconsistent_nitpick_with_hard_language(self):
        """Nitpick severity with hard language (no soft) is inconsistent."""
        move = {
            "severity": "nitpick",
            "description": "This is broken and will fail.",
            "trigger": "critical error",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is False
        assert "uses hard language" in reason

    def test_case_insensitive_matching(self):
        """Matching is case-insensitive."""
        move = {
            "severity": "REJECT",
            "description": "This is BROKEN and CRASHES.",
            "trigger": "BUG",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True

    def test_empty_description_is_consistent(self):
        """Empty description is consistent (no language detected)."""
        move = {"severity": "reject", "description": "", "trigger": ""}
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True
        assert reason == ""

    def test_missing_severity_is_consistent(self):
        """Missing severity is treated as consistent (no validation)."""
        move = {"description": "This is broken.", "trigger": "test"}
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True
        assert reason == ""

    def test_missing_description_is_consistent(self):
        """Missing description is treated as consistent (no language detected)."""
        move = {"severity": "reject"}
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True
        assert reason == ""

    def test_word_boundary_matching(self):
        """Word boundaries prevent false positives."""
        # "broken" should match but "unbroken" should not
        move = {"severity": "nitpick", "description": "This is unbroken code.", "trigger": "test"}
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True  # "unbroken" doesn't match "broken"

    def test_phrase_matching(self):
        """Multi-word phrases are matched correctly."""
        move = {"severity": "reject", "description": "This should not be done.", "trigger": "test"}
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is True  # "should not" is hard language

    def test_nice_to_is_soft(self):
        """'nice to' is detected as soft language."""
        move = {
            "severity": "reject",
            "description": "It would be nice to fix this.",
            "trigger": "test",
        }
        is_consistent, reason = _validate_severity_consistency(move)
        assert is_consistent is False
        assert "uses only soft language" in reason

    def test_all_hard_indicators_detected(self):
        """All hard language indicators are detected."""
        for indicator in HARD_LANGUAGE_INDICATORS:
            move = {
                "severity": "nitpick",
                "description": f"This {indicator} here.",
                "trigger": "test",
            }
            is_consistent, reason = _validate_severity_consistency(move)
            # Should be inconsistent (hard language in nitpick)
            # Unless it's also a soft indicator (none overlap)
            assert is_consistent is False, f"Failed for indicator: {indicator}"

    def test_all_soft_indicators_detected(self):
        """All soft language indicators are detected."""
        for indicator in SOFT_LANGUAGE_INDICATORS:
            move = {
                "severity": "reject",
                "description": f"You {indicator} this.",
                "trigger": "test",
            }
            is_consistent, reason = _validate_severity_consistency(move)
            # Should be inconsistent (only soft language in reject)
            assert is_consistent is False, f"Failed for indicator: {indicator}"


class TestParseBatchResponse:
    """Test _parse_batch_response for batched LLM calls."""

    def test_valid_batch_response(self):
        """Valid batch response with correct length parses successfully."""
        content = json.dumps(
            [
                {"moves": [{"trigger": "a", "principle": "b"}]},
                {"moves": [{"trigger": "c", "principle": "d"}]},
                {"moves": []},
            ]
        )
        result = _parse_batch_response(content, 3)
        assert len(result) == 3
        assert result[0]["moves"][0]["trigger"] == "a"
        assert result[2]["moves"] == []

    def test_valid_batch_with_markdown_fences(self):
        """Batch response with markdown fences parses successfully."""
        content = '```json\n[{"moves": []}, {"moves": []}]\n```'
        result = _parse_batch_response(content, 2)
        assert len(result) == 2

    def test_invalid_json_raises(self):
        """Invalid JSON raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            _parse_batch_response("not json at all", 2)

    def test_wrong_length_raises(self):
        """Response with wrong array length raises ValueError."""
        content = json.dumps([{"moves": []}])  # Only 1, expected 3
        with pytest.raises(ValueError) as exc_info:
            _parse_batch_response(content, 3)
        assert "Expected 3 results, got 1" in str(exc_info.value)

    def test_non_array_raises(self):
        """Non-array response raises ValueError."""
        content = json.dumps({"moves": []})  # Object, not array
        with pytest.raises(ValueError) as exc_info:
            _parse_batch_response(content, 1)
        assert "Expected JSON array" in str(exc_info.value)

    def test_empty_array_for_zero_batch(self):
        """Empty array for batch_size=0 parses successfully."""
        content = "[]"
        result = _parse_batch_response(content, 0)
        assert result == []

    def test_single_email_batch(self):
        """Single email batch (batch_size=1) works correctly."""
        content = json.dumps([{"moves": [{"trigger": "x"}]}])
        result = _parse_batch_response(content, 1)
        assert len(result) == 1
        assert result[0]["moves"][0]["trigger"] == "x"

    def test_large_batch(self):
        """Large batch response parses correctly."""
        moves_list = [{"moves": [{"trigger": f"t{i}"}]} for i in range(10)]
        content = json.dumps(moves_list)
        result = _parse_batch_response(content, 10)
        assert len(result) == 10
        assert result[5]["moves"][0]["trigger"] == "t5"


class TestBatchExtraction:
    """Test batch extraction with batch_size > 1."""

    @patch("torvalds_skill.extract.extract_moves_batch")
    def test_batch_mode_uses_batch_extraction(self, mock_batch, tmp_path):
        """When batch_size > 1, extract_moves_batch is called."""
        mock_batch.return_value = [
            {"email_message_id": "1", "moves": [{"trigger": "a"}]},
            {"email_message_id": "2", "moves": []},
        ]
        out = tmp_path / "out.jsonl"
        emails = [_make_email(message_id=str(i)) for i in range(2)]

        result = extract_batch(emails, str(out), batch_size=2, batch_retry=True)

        mock_batch.assert_called_once()
        assert result["processed"] == 2

    @patch("torvalds_skill.extract.extract_moves")
    def test_sequential_mode_uses_extract_moves(self, mock_extract, tmp_path):
        """When batch_size=1, extract_moves is called for each email."""
        mock_extract.return_value = {"email_message_id": "1", "moves": []}
        out = tmp_path / "out.jsonl"
        emails = [_make_email(message_id="1")]

        extract_batch(emails, str(out), batch_size=1)

        # extract_moves should be called once per email
        assert mock_extract.call_count == 1

    @patch("torvalds_skill.extract._call_llm_batch")
    @patch("torvalds_skill.extract.extract_moves")
    def test_batch_retry_enabled(self, mock_extract, mock_batch, tmp_path):
        """When batch_retry=True, failed batches are retried sequentially."""
        # Simulate batch failure, then sequential success
        mock_batch.side_effect = RuntimeError("Batch failed")
        mock_extract.return_value = {"email_message_id": "0", "moves": []}

        out = tmp_path / "out.jsonl"
        emails = [_make_email(message_id=str(i)) for i in range(2)]

        # Should not raise, should fall back to sequential
        result = extract_batch(emails, str(out), batch_size=2, batch_retry=True)

        # Should have processed all emails via fallback
        assert result["processed"] == 2
        # extract_moves should be called for each email in the failed batch
        assert mock_extract.call_count == 2

    @patch("torvalds_skill.extract._call_llm_batch")
    @patch("torvalds_skill.extract.extract_moves")
    def test_batch_retry_disabled(self, mock_extract, mock_batch, tmp_path):
        """When batch_retry=False, failed batches return errors."""
        mock_batch.side_effect = RuntimeError("Batch failed")

        out = tmp_path / "out.jsonl"
        emails = [_make_email(message_id=str(i)) for i in range(2)]

        result = extract_batch(emails, str(out), batch_size=2, batch_retry=False)

        # Should have errors for all emails in failed batch
        assert result["errors"] == 2
        # extract_moves should NOT be called when retry is disabled
        assert mock_extract.call_count == 0
