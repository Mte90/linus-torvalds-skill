"""Tests for calibrate_interviews.py severity calibration logic.

Verifies the calibration statistics computation from merged email and interview moves.
"""

import json
import tempfile
from pathlib import Path

from torvalds_skill.calibrate_interviews import (
    clean_category,
    clean_severity,
    compute_corpus_stats,
    compute_severity_by_category,
    compute_temporal_trends,
    load_moves_from_jsonl,
    tokenize,
)


class TestCleanFunctions:
    """Test category and severity cleaning/remapping."""

    def test_canonical_category_returns_same(self):
        """Canonical categories should return unchanged."""
        assert clean_category("testing") == "testing"
        assert clean_category("correctness") == "correctness"
        assert clean_category("api-stability") == "api-stability"

    def test_remap_category(self):
        """Mapped categories should be remapped to canonical."""
        assert clean_category("security") == "correctness"
        assert clean_category("api") == "api-stability"
        assert clean_category("api-design") == "api-stability"
        assert clean_category("compatibility") == "api-stability"

    def test_unknown_category_returns_none(self):
        """Unknown categories should return None."""
        assert clean_category("unknown-category") is None

    def test_canonical_severity_returns_same(self):
        """Canonical severities should return unchanged."""
        assert clean_severity("reject") == "reject"
        assert clean_severity("approve") == "approve"
        assert clean_severity("nitpick") == "nitpick"

    def test_remap_severity(self):
        """Mapped severities should be remapped to canonical."""
        assert clean_severity("process") == "discussion"

    def test_unknown_severity_returns_none(self):
        """Unknown severities should return None."""
        assert clean_severity("unknown-severity") is None


class TestTokenize:
    """Test tokenization for language-agnostic processing."""

    def test_basic_tokenization(self):
        """Should extract words and filter stopwords."""
        tokens = tokenize("the test has a bug")
        assert "test" in tokens
        assert "bug" not in tokens  # "bug" is in STOPWORDS
        assert "the" not in tokens
        assert "has" not in tokens
        assert "a" not in tokens

    def test_underscores_preserved(self):
        """Underscored identifiers should be preserved as single tokens."""
        tokens = tokenize("set_fs function and buf pointer")
        # set_fs and buf are in STOPWORDS
        assert "set_fs" not in tokens
        assert "buf" not in tokens
        # function is in STOPWORDS
        assert "function" not in tokens
        assert "pointer" in tokens

    def test_empty_string(self):
        """Empty string should return empty list."""
        assert tokenize("") == []

    def test_stopwords_coverage(self):
        """Common kernel terms should be filtered as stopwords."""
        text = "kernel patch series merge pull request tree"
        tokens = tokenize(text)
        for word in ["kernel", "patch", "series", "merge", "pull", "request", "tree"]:
            assert word not in tokens


class TestLoadMovesFromJsonl:
    """Test loading moves from JSONL files."""

    def test_load_single_move(self):
        """Should load a single move correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "email_message_id": "test@example.com",
                        "email_date": "2024-01-01",
                        "moves": [
                            {
                                "trigger": "test trigger",
                                "principle": "test principle",
                                "response": "test response",
                                "severity": "reject",
                                "category": "testing",
                            }
                        ],
                    }
                )
                + "\n"
            )
            f.flush()
            moves = load_moves_from_jsonl(Path(f.name), "email")
            assert len(moves) == 1
            assert moves[0]["trigger"] == "test trigger"
            assert moves[0]["severity"] == "reject"
            assert moves[0]["source"] == "email"

    def test_load_multiple_moves_per_email(self):
        """Should load multiple moves from a single email."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "email_message_id": "test@example.com",
                        "email_date": "2024-01-01",
                        "moves": [
                            {
                                "trigger": "t1",
                                "principle": "p1",
                                "response": "r1",
                                "severity": "reject",
                                "category": "testing",
                            },
                            {
                                "trigger": "t2",
                                "principle": "p2",
                                "response": "r2",
                                "severity": "approve",
                                "category": "correctness",
                            },
                        ],
                    }
                )
                + "\n"
            )
            f.flush()
            moves = load_moves_from_jsonl(Path(f.name), "email")
            assert len(moves) == 2

    def test_filters_invalid_category(self):
        """Moves with invalid categories should be filtered out."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "email_message_id": "test@example.com",
                        "email_date": "2024-01-01",
                        "moves": [
                            {
                                "trigger": "test",
                                "principle": "test",
                                "response": "test",
                                "severity": "reject",
                                "category": "invalid-category",
                            }
                        ],
                    }
                )
                + "\n"
            )
            f.flush()
            moves = load_moves_from_jsonl(Path(f.name), "email")
            assert len(moves) == 0

    def test_filters_invalid_severity(self):
        """Moves with invalid severities should be filtered out."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "email_message_id": "test@example.com",
                        "email_date": "2024-01-01",
                        "moves": [
                            {
                                "trigger": "test",
                                "principle": "test",
                                "response": "test",
                                "severity": "invalid-severity",
                                "category": "testing",
                            }
                        ],
                    }
                )
                + "\n"
            )
            f.flush()
            moves = load_moves_from_jsonl(Path(f.name), "email")
            assert len(moves) == 0

    def test_handles_empty_lines(self):
        """Empty lines should be skipped."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "email_message_id": "test@example.com",
                        "email_date": "2024-01-01",
                        "moves": [
                            {
                                "trigger": "t",
                                "principle": "p",
                                "response": "r",
                                "severity": "reject",
                                "category": "testing",
                            }
                        ],
                    }
                )
                + "\n\n"
            )
            f.flush()
            moves = load_moves_from_jsonl(Path(f.name), "email")
            assert len(moves) == 1

    def test_extract_year_from_date(self):
        """Year should be extracted from email_date."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "email_message_id": "test@example.com",
                        "email_date": "2023-06-15",
                        "moves": [
                            {
                                "trigger": "t",
                                "principle": "p",
                                "response": "r",
                                "severity": "reject",
                                "category": "testing",
                            }
                        ],
                    }
                )
                + "\n"
            )
            f.flush()
            moves = load_moves_from_jsonl(Path(f.name), "email")
            assert moves[0]["year"] == 2023

    def test_invalid_date_year(self):
        """Invalid date should result in None year."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "email_message_id": "test@example.com",
                        "email_date": "invalid",
                        "moves": [
                            {
                                "trigger": "t",
                                "principle": "p",
                                "response": "r",
                                "severity": "reject",
                                "category": "testing",
                            }
                        ],
                    }
                )
                + "\n"
            )
            f.flush()
            moves = load_moves_from_jsonl(Path(f.name), "email")
            assert moves[0]["year"] is None


class TestComputeSeverityByCategory:
    """Test severity distribution computation."""

    def test_single_category_single_severity(self):
        """Single category with single severity should show 100%."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_severity_by_category(moves)
        assert "testing" in result
        assert result["testing"]["total"] == 3
        assert result["testing"]["percentages"]["reject"] == 100.0

    def test_multiple_severities(self):
        """Multiple severities should show correct distribution."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "approve",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_severity_by_category(moves)
        assert result["testing"]["percentages"]["reject"] == 66.7
        assert result["testing"]["percentages"]["approve"] == 33.3

    def test_dominant_severity(self):
        """Dominant severity should be the most common one."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "approve",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "approve",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_severity_by_category(moves)
        assert result["testing"]["dominant_severity"] == "approve"

    def test_empty_moves(self):
        """Empty moves list should return empty result."""
        result = compute_severity_by_category([])
        assert result == {}

    def test_multiple_categories(self):
        """Multiple categories should each have their own distribution."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "correctness",
                "severity": "approve",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_severity_by_category(moves)
        assert "testing" in result
        assert "correctness" in result
        assert result["testing"]["dominant_severity"] == "reject"
        assert result["correctness"]["dominant_severity"] == "approve"


class TestComputeTemporalTrends:
    """Test temporal trend computation."""

    def test_year_range(self):
        """Year range should be computed correctly."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2020,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2023,
                "source": "email",
            },
        ]
        result = compute_temporal_trends(moves)
        assert result["year_range"] == [2020, 2023]

    def test_total_per_year(self):
        """Total moves per year should be counted correctly."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2020,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2020,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2021,
                "source": "email",
            },
        ]
        result = compute_temporal_trends(moves)
        assert result["total_per_year"]["2020"] == 2
        assert result["total_per_year"]["2021"] == 1

    def test_reject_rate_per_year(self):
        """Reject rate per year should be computed correctly."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2020,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "approve",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2020,
                "source": "email",
            },
        ]
        result = compute_temporal_trends(moves)
        assert result["reject_rate_per_year"]["2020"] == 50.0

    def test_empty_moves(self):
        """Empty moves list should return empty year range."""
        result = compute_temporal_trends([])
        assert result["year_range"] == []

    def test_null_year_ignored(self):
        """Moves with null year should be ignored in temporal trends."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": None,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2020,
                "source": "email",
            },
        ]
        result = compute_temporal_trends(moves)
        # Bug: year_range is [2020, 2020] instead of [2020]
        # This is because the code uses [years[0], years[-1]] which duplicates when only one year exists
        assert result["year_range"] == [2020]


class TestComputeCorpusStats:
    """Test corpus statistics computation."""

    def test_total_moves_count(self):
        """Total moves should be counted correctly."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_corpus_stats(moves, email_count=1, interview_count=0)
        assert result["total_moves"] == 2

    def test_source_breakdown(self):
        """Source breakdown should match input counts."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_corpus_stats(moves, email_count=1, interview_count=2)
        assert result["total_emails"] == 1
        assert result["total_interviews"] == 2

    def test_severity_distribution(self):
        """Severity distribution should be computed correctly."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "testing",
                "severity": "approve",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_corpus_stats(moves, email_count=1, interview_count=0)
        assert result["severity_distribution"]["reject"]["count"] == 1
        assert result["severity_distribution"]["approve"]["count"] == 1

    def test_category_distribution(self):
        """Category distribution should be computed correctly."""
        moves = [
            {
                "category": "testing",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "correctness",
                "severity": "reject",
                "trigger": "",
                "principle": "",
                "response": "",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_corpus_stats(moves, email_count=1, interview_count=0)
        assert result["category_distribution"]["testing"]["count"] == 1
        assert result["category_distribution"]["correctness"]["count"] == 1

    def test_empty_corpus(self):
        """Empty corpus should return zero counts."""
        # Bug: compute_corpus_stats raises ZeroDivisionError when total=0
        result = compute_corpus_stats([], email_count=0, interview_count=0)
        assert result["total_moves"] == 0
        assert result["severity_distribution"]["reject"]["count"] == 0


class TestLanguageAgnosticism:
    """Test that calibration output is language-agnostic."""

    def test_no_c_keywords_in_tokenization(self):
        """Tokenization should filter out C-specific keywords."""
        text = "set_fs(buf, size_t len) returns void"
        tokens = tokenize(text)
        # These C-specific terms should be filtered but set_fs is not in STOPWORDS
        assert "set_fs" not in tokens
        assert "buf" not in tokens  # "buf" is in STOPWORDS
        # Generic terms may remain
        assert "returns" in tokens or "len" in tokens

    def test_category_based_only(self):
        """Calibration should be based on categories, not specific code terms."""
        moves = [
            {
                "category": "memory-safety",
                "severity": "reject",
                "trigger": "buffer overflow",
                "principle": "check bounds",
                "response": "add bounds check",
                "year": 2024,
                "source": "email",
            },
            {
                "category": "memory-safety",
                "severity": "reject",
                "trigger": "null pointer",
                "principle": "check null",
                "response": "add null check",
                "year": 2024,
                "source": "email",
            },
        ]
        result = compute_severity_by_category(moves)
        # Result should only contain category/severity data, not trigger text
        assert "memory-safety" in result
        assert "trigger" not in result["memory-safety"]
