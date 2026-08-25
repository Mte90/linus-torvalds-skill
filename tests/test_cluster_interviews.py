"""Tests for cluster_interviews.py stratified sampling with source diversity.

Verifies the merge of email and interview moves with stratified sampling
that ensures source diversity across categories and severities.
"""

import random

import pytest

from torvalds_skill.cluster_interviews import (
    _load_email_moves,
    _load_interview_moves,
    _stratified_sample_diverse,
    SAMPLES_PER_CATEGORY,
)


class TestStratifiedSampleDiverse:
    """Test _stratified_sample_diverse source diversity balancing."""

    def test_single_source_only(self):
        """When only one source exists, sample from it exclusively."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": "t1", "principle": "p1", "quote": "q1"},
                {"category": "testing", "severity": "reject", "source": "email", "trigger": "t2", "principle": "p2", "quote": "q2"},
                {"category": "testing", "severity": "reject", "source": "email", "trigger": "t3", "principle": "p3", "quote": "q3"},
            ]
        }
        rng = random.Random(42)
        result = _stratified_sample_diverse(moves_by_cat_sev, 5, rng)
        
        assert len(result) == 3  # Only 3 available
        assert all(m["source"] == "email" for m in result)

    def test_multi_source_split(self):
        """When both sources exist, split roughly evenly."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": f"email{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(10)
            ] + [
                {"category": "testing", "severity": "reject", "source": "interview", "trigger": f"int{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(10)
            ]
        }
        rng = random.Random(42)
        result = _stratified_sample_diverse(moves_by_cat_sev, 10, rng)
        
        assert len(result) == 10
        sources = [m["source"] for m in result]
        assert "email" in sources
        assert "interview" in sources

    def test_under_sample_fill(self):
        """When fewer than target available, return all without error."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": "t1", "principle": "p1", "quote": "q1"},
                {"category": "testing", "severity": "reject", "source": "interview", "trigger": "t2", "principle": "p2", "quote": "q2"},
            ]
        }
        rng = random.Random(42)
        result = _stratified_sample_diverse(moves_by_cat_sev, 10, rng)
        
        assert len(result) == 2  # Only 2 available, target was 10

    def test_over_sample_trim(self):
        """When more than target available, trim to target."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": f"t{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(20)
            ]
        }
        rng = random.Random(42)
        result = _stratified_sample_diverse(moves_by_cat_sev, 10, rng)
        
        assert len(result) == 10

    def test_empty_category(self):
        """Empty categories should be skipped silently."""
        moves_by_cat_sev = {}
        rng = random.Random(42)
        result = _stratified_sample_diverse(moves_by_cat_sev, 10, rng)
        
        assert len(result) == 0

    def test_deterministic_with_seed(self):
        """Same seed should produce identical results."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": f"t{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(15)
            ]
        }
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        
        result1 = _stratified_sample_diverse(moves_by_cat_sev, 10, rng1)
        result2 = _stratified_sample_diverse(moves_by_cat_sev, 10, rng2)
        
        triggers1 = [m["trigger"] for m in result1]
        triggers2 = [m["trigger"] for m in result2]
        assert triggers1 == triggers2

    def test_different_seeds_different_samples(self):
        """Different seeds should produce different samples."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": f"t{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(30)
            ]
        }
        rng1 = random.Random(42)
        rng2 = random.Random(99)
        
        result1 = _stratified_sample_diverse(moves_by_cat_sev, 10, rng1)
        result2 = _stratified_sample_diverse(moves_by_cat_sev, 10, rng2)
        
        triggers1 = [m["trigger"] for m in result1]
        triggers2 = [m["trigger"] for m in result2]
        assert triggers1 != triggers2

    def test_multiple_categories(self):
        """Should sample from multiple categories independently."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": f"t{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(10)
            ],
            ("correctness", "reject"): [
                {"category": "correctness", "severity": "reject", "source": "interview", "trigger": f"c{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(10)
            ]
        }
        rng = random.Random(42)
        result = _stratified_sample_diverse(moves_by_cat_sev, 5, rng)
        
        categories = set(m["category"] for m in result)
        assert "testing" in categories
        assert "correctness" in categories

    def test_multiple_severities_per_category(self):
        """Should sample from multiple severities within a category."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": f"r{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(10)
            ],
            ("testing", "approve"): [
                {"category": "testing", "severity": "approve", "source": "interview", "trigger": f"a{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(10)
            ]
        }
        rng = random.Random(42)
        result = _stratified_sample_diverse(moves_by_cat_sev, 10, rng)
        
        severities = set(m["severity"] for m in result)
        assert "reject" in severities
        assert "approve" in severities

    def test_interview_priority_when_both_sources(self):
        """Interview should be prioritized when both sources available."""
        moves_by_cat_sev = {
            ("testing", "reject"): [
                {"category": "testing", "severity": "reject", "source": "email", "trigger": f"e{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(20)
            ] + [
                {"category": "testing", "severity": "reject", "source": "interview", "trigger": f"i{i}", "principle": f"p{i}", "quote": f"q{i}"}
                for i in range(20)
            ]
        }
        rng = random.Random(42)
        result = _stratified_sample_diverse(moves_by_cat_sev, 10, rng)
        
        interview_count = sum(1 for m in result if m["source"] == "interview")
        email_count = sum(1 for m in result if m["source"] == "email")
        # Interview should get roughly half or more (target // 2 + target % 2 = 5 + 0 = 5, but capped by available)
        assert interview_count >= email_count or interview_count >= 5


class TestLoadEmailMoves:
    """Test _load_email_moves JSON parsing."""

    def test_parses_single_move(self, tmp_path):
        """Should parse a single move from email moves file."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_date": "2024-01-01", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "response": "r1"}]}\n'
        )
        
        result = _load_email_moves(moves_path)
        
        assert len(result) == 1
        assert result[0]["category"] == "testing"
        assert result[0]["severity"] == "reject"
        assert result[0]["source"] == "email"
        assert result[0]["email_date"] == "2024-01-01"

    def test_parses_multiple_moves_per_email(self, tmp_path):
        """Should flatten multiple moves from single email."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_date": "2024-01-01", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "response": "r1"}, {"category": "correctness", "severity": "approve", "trigger": "t2", "principle": "p2", "response": "r2"}]}\n'
        )
        
        result = _load_email_moves(moves_path)
        
        assert len(result) == 2
        assert result[0]["category"] == "testing"
        assert result[1]["category"] == "correctness"

    def test_skips_blank_lines(self, tmp_path):
        """Should skip blank lines in JSONL file."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"email_date": "2024-01-01", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "response": "r1"}]}\n'
            '\n'
            '{"email_date": "2024-01-02", "moves": [{"category": "correctness", "severity": "approve", "trigger": "t2", "principle": "p2", "response": "r2"}]}\n'
        )
        
        result = _load_email_moves(moves_path)
        
        assert len(result) == 2


class TestLoadInterviewMoves:
    """Test _load_interview_moves JSON parsing."""

    def test_parses_single_move(self, tmp_path):
        """Should parse a single move from interview moves file."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"passage_id": "p1", "source_file": "interview1.txt", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "response": "r1"}]}\n'
        )
        
        result = _load_interview_moves(moves_path)
        
        assert len(result) == 1
        assert result[0]["category"] == "testing"
        assert result[0]["severity"] == "reject"
        assert result[0]["source"] == "interview"

    def test_uses_quote_field_as_fallback(self, tmp_path):
        """Should use quote field if response not present."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"passage_id": "p1", "source_file": "interview1.txt", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "quote": "q1"}]}\n'
        )
        
        result = _load_interview_moves(moves_path)
        
        assert len(result) == 1
        assert result[0]["quote"] == "q1"

    def test_parses_multiple_moves_per_passage(self, tmp_path):
        """Should flatten multiple moves from single passage."""
        moves_path = tmp_path / "moves.jsonl"
        moves_path.write_text(
            '{"passage_id": "p1", "source_file": "interview1.txt", "moves": [{"category": "testing", "severity": "reject", "trigger": "t1", "principle": "p1", "response": "r1"}, {"category": "correctness", "severity": "approve", "trigger": "t2", "principle": "p2", "response": "r2"}]}\n'
        )
        
        result = _load_interview_moves(moves_path)
        
        assert len(result) == 2
