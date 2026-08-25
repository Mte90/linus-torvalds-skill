"""Tests for streaming.py generator functions.

Verifies memory-efficient streaming iteration over JSONL and JSON files
for corpus processing without loading entire files into memory.
"""

import json

import pytest

from torvalds_skill.streaming import (
    count_jsonl,
    iter_jsonl,
    iter_moves,
    iter_patterns,
    write_jsonl,
)


class TestIterJsonl:
    """Test iter_jsonl JSONL line iteration."""

    def test_parses_valid_jsonl(self, tmp_path):
        """Should parse each line as JSON."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
        
        results = list(iter_jsonl(str(jsonl_path)))
        
        assert len(results) == 3
        assert results[0] == {"a": 1}
        assert results[1] == {"b": 2}
        assert results[2] == {"c": 3}

    def test_skips_blank_lines(self, tmp_path):
        """Should skip blank lines without error."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text('{"a": 1}\n\n{"b": 2}\n\n\n{"c": 3}\n')
        
        results = list(iter_jsonl(str(jsonl_path)))
        
        assert len(results) == 3

    def test_handles_malformed_json(self, tmp_path):
        """Should yield None for malformed JSON lines."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text('{"a": 1}\n{invalid json}\n{"c": 3}\n')
        
        results = list(iter_jsonl(str(jsonl_path)))
        
        assert len(results) == 3
        assert results[0] == {"a": 1}
        assert results[1] is None
        assert results[2] == {"c": 3}

    def test_empty_file(self, tmp_path):
        """Should handle empty files gracefully."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text("")
        
        results = list(iter_jsonl(str(jsonl_path)))
        
        assert len(results) == 0

    def test_nonexistent_file(self, tmp_path):
        """Should return empty generator for nonexistent file."""
        jsonl_path = tmp_path / "nonexistent.jsonl"
        
        results = list(iter_jsonl(str(jsonl_path)))
        
        assert len(results) == 0

    def test_single_line(self, tmp_path):
        """Should handle single-line files."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text('{"single": "line"}\n')
        
        results = list(iter_jsonl(str(jsonl_path)))
        
        assert len(results) == 1
        assert results[0] == {"single": "line"}


class TestIterMoves:
    """Test iter_moves move flattening."""

    def test_flattens_nested_moves(self, tmp_path):
        """Should flatten nested moves array into individual records."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "e1@example.com", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "quote": "q1"}, {"category": "correctness", "severity": "approve", "trigger": "t2", "principle": "p2", "quote": "q2"}]}\n'
        )
        
        results = list(iter_moves(str(moves_path)))
        
        assert len(results) == 2
        assert results[0]["email_message_id"] == "e1@example.com"
        assert results[0]["category"] == "testing"
        assert results[1]["category"] == "correctness"

    def test_preserves_email_message_id(self, tmp_path):
        """Should add email_message_id to each flattened move."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "msg123@example.com", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "quote": "q1"}]}\n'
        )
        
        results = list(iter_moves(str(moves_path)))
        
        assert len(results) == 1
        assert results[0]["email_message_id"] == "msg123@example.com"

    def test_handles_multiple_emails(self, tmp_path):
        """Should process multiple email records."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "e1@example.com", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "quote": "q1"}]}\n'
            '{"email_message_id": "e2@example.com", "moves": [{"category": "correctness", "severity": "approve", "trigger": "t2", "principle": "p2", "quote": "q2"}]}\n'
        )
        
        results = list(iter_moves(str(moves_path)))
        
        assert len(results) == 2
        assert results[0]["email_message_id"] == "e1@example.com"
        assert results[1]["email_message_id"] == "e2@example.com"

    def test_skips_malformed_lines(self, tmp_path):
        """Should skip malformed JSON lines without error."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "e1@example.com", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "quote": "q1"}]}\n'
            '{invalid json}\n'
            '{"email_message_id": "e2@example.com", "moves": [{"category": "correctness", "severity": "approve", "trigger": "t2", "principle": "p2", "quote": "q2"}]}\n'
        )
        
        results = list(iter_moves(str(moves_path)))
        
        assert len(results) == 2

    def test_empty_moves_array(self, tmp_path):
        """Should handle empty moves arrays."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "e1@example.com", "moves": []}\n'
        )
        
        results = list(iter_moves(str(moves_path)))
        
        assert len(results) == 0

    def test_missing_moves_key(self, tmp_path):
        """Should handle records without moves key."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "e1@example.com"}\n'
        )
        
        results = list(iter_moves(str(moves_path)))
        
        assert len(results) == 0


class TestIterPatterns:
    """Test iter_patterns JSON array iteration."""

    def test_parses_json_array(self, tmp_path):
        """Should parse patterns.json as JSON array."""
        patterns_path = tmp_path / "patterns.json"
        patterns_path.write_text(
            '[{"category": "testing", "trigger": "t1"}, {"category": "correctness", "trigger": "t2"}]'
        )
        
        results = list(iter_patterns(str(patterns_path)))
        
        assert len(results) == 2
        assert results[0]["category"] == "testing"
        assert results[1]["category"] == "correctness"

    def test_empty_array(self, tmp_path):
        """Should handle empty JSON array."""
        patterns_path = tmp_path / "patterns.json"
        patterns_path.write_text('[]')
        
        results = list(iter_patterns(str(patterns_path)))
        
        assert len(results) == 0

    def test_nonexistent_file(self, tmp_path):
        """Should return empty generator for nonexistent file."""
        patterns_path = tmp_path / "nonexistent.json"
        
        results = list(iter_patterns(str(patterns_path)))
        
        assert len(results) == 0

    def test_handles_malformed_json(self, tmp_path):
        """Should handle malformed JSON gracefully."""
        patterns_path = tmp_path / "patterns.json"
        patterns_path.write_text('{invalid json}')
        
        results = list(iter_patterns(str(patterns_path)))
        
        assert len(results) == 0

    def test_single_pattern(self, tmp_path):
        """Should handle single pattern in array."""
        patterns_path = tmp_path / "patterns.json"
        patterns_path.write_text('[{"category": "testing", "trigger": "t1"}]')
        
        results = list(iter_patterns(str(patterns_path)))
        
        assert len(results) == 1
        assert results[0]["category"] == "testing"


class TestCountJsonl:
    """Test count_jsonl line counting."""

    def test_counts_lines(self, tmp_path):
        """Should count non-blank lines."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
        
        count = count_jsonl(str(jsonl_path))
        
        assert count == 3

    def test_excludes_blank_lines(self, tmp_path):
        """Should not count blank lines."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text('{"a": 1}\n\n{"b": 2}\n\n\n{"c": 3}\n')
        
        count = count_jsonl(str(jsonl_path))
        
        assert count == 3

    def test_empty_file(self, tmp_path):
        """Should return 0 for empty file."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text("")
        
        count = count_jsonl(str(jsonl_path))
        
        assert count == 0

    def test_nonexistent_file(self, tmp_path):
        """Should return 0 for nonexistent file."""
        jsonl_path = tmp_path / "nonexistent.jsonl"
        
        count = count_jsonl(str(jsonl_path))
        
        assert count == 0

    def test_single_line(self, tmp_path):
        """Should count single line."""
        jsonl_path = tmp_path / "test.jsonl"
        jsonl_path.write_text('{"single": "line"}\n')
        
        count = count_jsonl(str(jsonl_path))
        
        assert count == 1


class TestWriteJsonl:
    """Test write_jsonl streaming write."""

    def test_writes_records(self, tmp_path):
        """Should write records as JSONL."""
        output_path = tmp_path / "output.jsonl"
        records = [{"a": 1}, {"b": 2}, {"c": 3}]
        
        write_jsonl(str(output_path), records)
        
        content = output_path.read_text()
        lines = content.strip().split('\n')
        assert len(lines) == 3
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}
        assert json.loads(lines[2]) == {"c": 3}

    def test_round_trip(self, tmp_path):
        """Written records should be readable back."""
        output_path = tmp_path / "output.jsonl"
        original = [{"a": 1, "b": "x"}, {"c": 2, "d": "y"}, {"e": 3, "f": "z"}]
        
        write_jsonl(str(output_path), original)
        results = list(iter_jsonl(str(output_path)))
        
        assert results == original

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        output_path = tmp_path / "nested" / "dir" / "output.jsonl"
        records = [{"a": 1}]
        
        write_jsonl(str(output_path), records)
        
        assert output_path.exists()
        assert json.loads(output_path.read_text().strip()) == {"a": 1}

    def test_empty_iterable(self, tmp_path):
        """Should handle empty iterable."""
        output_path = tmp_path / "output.jsonl"
        
        write_jsonl(str(output_path), [])
        
        assert output_path.exists()
        assert output_path.read_text() == ""

    def test_single_record(self, tmp_path):
        """Should write single record."""
        output_path = tmp_path / "output.jsonl"
        records = [{"single": "record"}]
        
        write_jsonl(str(output_path), records)
        
        content = output_path.read_text().strip()
        assert json.loads(content) == {"single": "record"}

    @pytest.mark.parametrize("records", [
        [{"a": 1}, {"b": 2}],
        [{"x": "y", "z": 123}, {"p": "q", "r": 456}],
        [{"nested": {"key": "value"}}],
    ])
    def test_various_record_types(self, tmp_path, records):
        """Should handle various record structures."""
        output_path = tmp_path / "output.jsonl"
        
        write_jsonl(str(output_path), records)
        results = list(iter_jsonl(str(output_path)))
        
        assert results == records