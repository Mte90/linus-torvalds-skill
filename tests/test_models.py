"""Tests for models.py dataclasses and iterators.

Verifies the dataclass definitions for EmailRecord, ReviewMove, and Pattern,
including frozen behavior and JSON parsing.
"""

import json

import pytest

from torvalds_skill.models import (
    CATEGORIES,
    SEVERITIES,
    EmailRecord,
    Pattern,
    ReviewMove,
    iter_moves,
    iter_corpus,
)


class TestEmailRecord:
    """Test EmailRecord dataclass."""

    def test_construction(self):
        """Should construct EmailRecord with required fields."""
        record = EmailRecord(
            message_id="msg@example.com",
            from_name="Linus Torvalds",
            from_email="torvalds@linux.org",
            date="2024-01-01",
            subject="Re: Some patch",
            in_reply_to="parent@example.com",
            body="This is the email body.",
        )
        
        assert record.message_id == "msg@example.com"
        assert record.from_name == "Linus Torvalds"
        assert record.from_email == "torvalds@linux.org"
        assert record.date == "2024-01-01"
        assert record.subject == "Re: Some patch"
        assert record.in_reply_to == "parent@example.com"
        assert record.body == "This is the email body."

    def test_optional_fields_default_empty(self):
        """Optional fields should default to empty strings."""
        record = EmailRecord(
            message_id="msg@example.com",
            from_name="Test",
            from_email="test@example.com",
            date="2024-01-01",
            subject="Test",
            in_reply_to=None,
            body="Body",
        )
        
        assert record.to == ""
        assert record.cc == ""

    def test_from_jsonl_line(self):
        """Should parse EmailRecord from JSONL line."""
        line = json.dumps({
            "message_id": "msg@example.com",
            "from_name": "Linus Torvalds",
            "from_email": "torvalds@linux.org",
            "date": "2024-01-01",
            "subject": "Re: Some patch",
            "in_reply_to": "parent@example.com",
            "body": "This is the email body.",
            "to": "kernel@lists.org",
            "cc": "maintainer@example.com",
        })
        
        record = EmailRecord.from_jsonl_line(line)
        
        assert record.message_id == "msg@example.com"
        assert record.from_name == "Linus Torvalds"
        assert record.to == "kernel@lists.org"
        assert record.cc == "maintainer@example.com"

    def test_from_jsonl_line_minimal(self):
        """Should parse EmailRecord with minimal fields."""
        line = json.dumps({
            "message_id": "msg@example.com",
            "from_name": "Test",
            "from_email": "test@example.com",
            "date": "2024-01-01",
            "subject": "Test",
            "in_reply_to": None,
            "body": "Body",
        })
        
        record = EmailRecord.from_jsonl_line(line)
        
        assert record.to == ""
        assert record.cc == ""

    def test_frozen(self):
        """EmailRecord should be immutable."""
        record = EmailRecord(
            message_id="msg@example.com",
            from_name="Test",
            from_email="test@example.com",
            date="2024-01-01",
            subject="Test",
            in_reply_to=None,
            body="Body",
        )
        
        with pytest.raises(Exception):  # Frozen dataclass raises TypeError
            record.message_id = "new@example.com"

    def test_hashable(self):
        """Frozen EmailRecord should be hashable."""
        record1 = EmailRecord(
            message_id="msg@example.com",
            from_name="Test",
            from_email="test@example.com",
            date="2024-01-01",
            subject="Test",
            in_reply_to=None,
            body="Body",
        )
        record2 = EmailRecord(
            message_id="msg@example.com",
            from_name="Test",
            from_email="test@example.com",
            date="2024-01-01",
            subject="Test",
            in_reply_to=None,
            body="Body",
        )
        
        # Same content should hash to same value
        assert hash(record1) == hash(record2)
        assert record1 == record2

    def test_invalid_json_raises(self):
        """Should raise JSONDecodeError for invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            EmailRecord.from_jsonl_line("invalid json")

    def test_missing_fields_raises(self):
        """Should raise TypeError for missing required fields."""
        line = json.dumps({"message_id": "msg@example.com"})
        
        with pytest.raises(TypeError):
            EmailRecord.from_jsonl_line(line)


class TestReviewMove:
    """Test ReviewMove dataclass."""

    def test_construction(self):
        """Should construct ReviewMove with all fields."""
        move = ReviewMove(
            email_message_id="msg@example.com",
            email_date="2024-01-01",
            trigger="untested code",
            principle="require tests",
            response="add tests before merging",
            severity="reject",
            category="testing",
        )
        
        assert move.email_message_id == "msg@example.com"
        assert move.email_date == "2024-01-01"
        assert move.trigger == "untested code"
        assert move.principle == "require tests"
        assert move.response == "add tests before merging"
        assert move.severity == "reject"
        assert move.category == "testing"

    def test_frozen(self):
        """ReviewMove should be immutable."""
        move = ReviewMove(
            email_message_id="msg@example.com",
            email_date="2024-01-01",
            trigger="test",
            principle="test",
            response="test",
            severity="reject",
            category="testing",
        )
        
        with pytest.raises(Exception):  # Frozen dataclass raises TypeError
            move.category = "correctness"

    def test_hashable(self):
        """Frozen ReviewMove should be hashable."""
        move1 = ReviewMove(
            email_message_id="msg@example.com",
            email_date="2024-01-01",
            trigger="test",
            principle="test",
            response="test",
            severity="reject",
            category="testing",
        )
        move2 = ReviewMove(
            email_message_id="msg@example.com",
            email_date="2024-01-01",
            trigger="test",
            principle="test",
            response="test",
            severity="reject",
            category="testing",
        )
        
        assert hash(move1) == hash(move2)
        assert move1 == move2


class TestPattern:
    """Test Pattern dataclass."""

    def test_construction(self):
        """Should construct Pattern with required fields."""
        pattern = Pattern(
            category="testing",
            principle="require tests",
            count=5,
        )
        
        assert pattern.category == "testing"
        assert pattern.principle == "require tests"
        assert pattern.count == 5

    def test_default_factory_lists(self):
        """Optional list fields should default to empty lists."""
        pattern = Pattern(
            category="testing",
            principle="require tests",
            count=5,
        )
        
        assert pattern.example_triggers == []
        assert pattern.example_responses == []
        assert pattern.severities == {}

    def test_with_lists(self):
        """Should accept list values."""
        pattern = Pattern(
            category="testing",
            principle="require tests",
            count=5,
            example_triggers=["untested code", "no tests"],
            example_responses=["add tests", "tests required"],
            severities={"reject": 3, "nitpick": 2},
        )
        
        assert pattern.example_triggers == ["untested code", "no tests"]
        assert pattern.example_responses == ["add tests", "tests required"]
        assert pattern.severities == {"reject": 3, "nitpick": 2}

    def test_not_frozen(self):
        """Pattern should be mutable (not frozen)."""
        pattern = Pattern(
            category="testing",
            principle="require tests",
            count=5,
        )
        
        pattern.count = 10
        assert pattern.count == 10

    def test_mutable_default_factory_isolation(self):
        """Each Pattern instance should have independent list defaults."""
        pattern1 = Pattern(category="testing", principle="p1", count=1)
        pattern2 = Pattern(category="correctness", principle="p2", count=2)
        
        pattern1.example_triggers.append("trigger1")
        
        assert pattern1.example_triggers == ["trigger1"]
        assert pattern2.example_triggers == []  # Should not be affected


class TestIterCorpus:
    """Test iter_corpus generator."""

    def test_yields_email_records(self, tmp_path):
        """Should yield EmailRecord objects from JSONL."""
        corpus_path = tmp_path / "corpus.jsonl"
        corpus_path.write_text(
            '{"message_id": "m1@example.com", "from_name": "Test1", "from_email": "t1@example.com", "date": "2024-01-01", "subject": "S1", "in_reply_to": null, "body": "B1"}\n'
            '{"message_id": "m2@example.com", "from_name": "Test2", "from_email": "t2@example.com", "date": "2024-01-02", "subject": "S2", "in_reply_to": "m1@example.com", "body": "B2"}\n'
        )
        
        records = list(iter_corpus(corpus_path))
        
        assert len(records) == 2
        assert isinstance(records[0], EmailRecord)
        assert records[0].message_id == "m1@example.com"
        assert records[1].message_id == "m2@example.com"

    def test_skips_blank_lines(self, tmp_path):
        """Should skip blank lines in corpus."""
        corpus_path = tmp_path / "corpus.jsonl"
        corpus_path.write_text(
            '{"message_id": "m1@example.com", "from_name": "Test1", "from_email": "t1@example.com", "date": "2024-01-01", "subject": "S1", "in_reply_to": null, "body": "B1"}\n'
            '\n'
            '{"message_id": "m2@example.com", "from_name": "Test2", "from_email": "t2@example.com", "date": "2024-01-02", "subject": "S2", "in_reply_to": null, "body": "B2"}\n'
        )
        
        records = list(iter_corpus(corpus_path))
        
        assert len(records) == 2

    def test_empty_file(self, tmp_path):
        """Should handle empty corpus file."""
        corpus_path = tmp_path / "corpus.jsonl"
        corpus_path.write_text("")
        
        records = list(iter_corpus(corpus_path))
        
        assert len(records) == 0


class TestIterMoves:
    """Test iter_moves generator for ReviewMove objects."""

    def test_yields_review_moves(self, tmp_path):
        """Should yield ReviewMove objects from moves JSONL."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "m1@example.com", "email_date": "2024-01-01", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "response": "r1"}]}\n'
        )
        
        moves = list(iter_moves(moves_path))
        
        assert len(moves) == 1
        assert isinstance(moves[0], ReviewMove)
        assert moves[0].email_message_id == "m1@example.com"
        assert moves[0].category == "testing"

    def test_flattens_multiple_moves(self, tmp_path):
        """Should flatten multiple moves from single email."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "m1@example.com", "email_date": "2024-01-01", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "response": "r1"}, {"category": "correctness", "severity": "approve", "trigger": "t2", "principle": "p2", "response": "r2"}]}\n'
        )
        
        moves = list(iter_moves(moves_path))
        
        assert len(moves) == 2
        assert moves[0].category == "testing"
        assert moves[1].category == "correctness"

    def test_skips_blank_lines(self, tmp_path):
        """Should skip blank lines in moves file."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_message_id": "m1@example.com", "email_date": "2024-01-01", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "response": "r1"}]}\n'
            '\n'
            '{"email_message_id": "m2@example.com", "email_date": "2024-01-02", "moves": [{"category": "correctness", "severity": "approve", "trigger": "t2", "principle": "p2", "response": "r2"}]}\n'
        )
        
        moves = list(iter_moves(moves_path))
        
        assert len(moves) == 2


class TestConstants:
    """Test module constants."""

    def test_severities_defined(self):
        """SEVERITIES should contain expected values."""
        assert "reject" in SEVERITIES
        assert "request-changes" in SEVERITIES
        assert "nitpick" in SEVERITIES
        assert "approve" in SEVERITIES
        assert "discussion" in SEVERITIES

    def test_categories_defined(self):
        """CATEGORIES should contain expected values."""
        assert "api-stability" in CATEGORIES
        assert "performance" in CATEGORIES
        assert "correctness" in CATEGORIES
        assert "complexity" in CATEGORIES
        assert "testing" in CATEGORIES
        assert "documentation" in CATEGORIES
        assert "security" in CATEGORIES

    def test_categories_count(self):
        """Should have 14 categories."""
        assert len(CATEGORIES) == 14