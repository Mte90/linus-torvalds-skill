"""Tests for extract.py LLM extraction logic.

Verifies JSON parsing of LLM responses, move extraction with mocked LLM calls,
and batch extraction with file I/O. No real API calls are made.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from torvalds_skill.extract import (
    _parse_json_response,
    extract_moves,
    extract_batch,
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
        content = json.dumps({
            "moves": [
                {"trigger": "a", "principle": "b", "severity": "reject"},
                {"trigger": "c", "principle": "d", "severity": "nitpick"},
            ]
        })
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
            "moves": [
                {"trigger": f"t{i}", "principle": f"p{i}"}
                for i in range(5)
            ]
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
