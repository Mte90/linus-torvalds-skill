"""Integration tests for the torvalds-skill pipeline.

These tests verify that pipeline stages chain correctly and that data
formats are compatible between stages. No real LLM API calls are made.
"""

import json
from pathlib import Path
from unittest.mock import patch

from torvalds_skill.classify import classify_corpus
from torvalds_skill.cluster import cluster_moves
from torvalds_skill.extract import extract_batch, extract_moves
from torvalds_skill.models import EmailRecord, ReviewMove, iter_moves


def _make_email(
    message_id: str = "test@example.com",
    subject: str = "Re: Some patch",
    in_reply_to: str | None = "parent@example.com",
    body: str = "This is a substantive review comment that has enough length to pass the minimum body length requirement of one hundred characters.",
    from_name: str = "Linus Torvalds",
    from_email: str = "torvalds@linux.org",
    date: str = "2024-01-01",
) -> EmailRecord:
    """Helper to create EmailRecord fixtures."""
    return EmailRecord(
        message_id=message_id,
        from_name=from_name,
        from_email=from_email,
        date=date,
        subject=subject,
        in_reply_to=in_reply_to,
        body=body,
    )


def _make_review_move(
    email_message_id: str = "test@example.com",
    email_date: str = "2024-01-01",
    trigger: str = "untested code",
    principle: str = "require tests",
    response: str = "add tests before merging",
    severity: str = "reject",
    category: str = "testing",
) -> ReviewMove:
    """Helper to create ReviewMove fixtures."""
    return ReviewMove(
        email_message_id=email_message_id,
        email_date=email_date,
        trigger=trigger,
        principle=principle,
        response=response,
        severity=severity,
        category=category,
    )


def _write_moves_jsonl(path: Path, moves: list[ReviewMove]) -> None:
    """Write moves in the nested JSONL format iter_moves expects."""
    by_email: dict[str, dict] = {}
    for m in moves:
        if m.email_message_id not in by_email:
            by_email[m.email_message_id] = {
                "email_message_id": m.email_message_id,
                "email_date": m.email_date,
                "moves": [],
            }
        by_email[m.email_message_id]["moves"].append(
            {
                "trigger": m.trigger,
                "principle": m.principle,
                "response": m.response,
                "severity": m.severity,
                "category": m.category,
            }
        )
    with open(path, "w", encoding="utf-8") as f:
        for entry in by_email.values():
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class TestClassifyToExtractDataFlow:
    """Test that classify output matches what extract expects as input."""

    def test_classify_yields_email_records(self):
        """classify_corpus should yield EmailRecord objects."""
        emails = [
            _make_email(message_id=f"m{i}@example.com", subject=f"Re: Patch {i}") for i in range(5)
        ]
        results = list(classify_corpus(emails))

        assert len(results) == 5
        for email, label in results:
            assert isinstance(email, EmailRecord)
            assert label in ("review", "other")

    def test_review_emails_passed_to_extract(self):
        """Emails labeled 'review' should have the right structure for extract."""
        review_email = _make_email(
            message_id="review@exampl.com",
            subject="Re: Fix memory leak",
            body="The buffer is freed twice. This is a use-after-free bug. "
            "You need to remove the second kfree() call. "
            "This is critical and must be fixed before merging.",
        )
        emails = [review_email]
        results = list(classify_corpus(emails))

        # Filter for reviews
        reviews = [e for e, label in results if label == "review"]

        # These should be extractable
        for email in reviews:
            assert hasattr(email, "message_id")
            assert hasattr(email, "subject")
            assert hasattr(email, "body")
            assert hasattr(email, "date")

    def test_non_reviews_filtered_out(self):
        """Non-review emails should be labeled 'other'."""
        emails = [
            _make_email(message_id="ann1", subject="Linux 6.7 release", in_reply_to=None),
            _make_email(message_id="ann2", subject="[GIT PULL] updates", in_reply_to=None),
            _make_email(message_id="ann3", subject="[PATCH] fix", in_reply_to=None),
        ]
        results = list(classify_corpus(emails))

        for _email, label in results:
            assert label == "other"

    def test_extract_accepts_classified_email(self):
        """extract_moves should accept an EmailRecord from classify."""
        email = _make_email(
            message_id="extract-test@example.com",
            subject="Re: Code review",
            body="This code has issues. The error handling is incomplete. "
            "You need to add cleanup in all error paths. "
            "This is a correctness issue that must be addressed.",
        )

        # Classify first
        _, label = next(classify_corpus([email]))
        assert label == "review"

        # Then extract (with mocked LLM)
        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.return_value = {
                "moves": [
                    {
                        "trigger": "incomplete error handling",
                        "principle": "add cleanup in all error paths",
                        "response": "this is a correctness issue",
                        "severity": "request-changes",
                        "category": "correctness",
                    }
                ]
            }
            result = extract_moves(email)

        assert result["email_message_id"] == "extract-test@example.com"
        assert "moves" in result
        assert len(result["moves"]) == 1


class TestExtractToClusterDataFlow:
    """Test that extract output matches what cluster expects as input."""

    def test_extract_output_format(self):
        """extract_moves should return dict with email_message_id and moves."""
        email = _make_email(message_id="format-test@example.com")

        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.return_value = {
                "moves": [
                    {
                        "trigger": "t1",
                        "principle": "p1",
                        "response": "r1",
                        "severity": "reject",
                        "category": "testing",
                    }
                ]
            }
            result = extract_moves(email)

        assert "email_message_id" in result
        assert "email_date" in result
        assert "email_subject" in result
        assert "moves" in result
        assert isinstance(result["moves"], list)

    def test_moves_have_required_fields_for_cluster(self):
        """Extracted moves must have all fields cluster.py needs."""
        email = _make_email(message_id="fields-test@example.com")

        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.return_value = {
                "moves": [
                    {
                        "trigger": "untested buffer",
                        "principle": "require tests for all code paths",
                        "response": "add tests before merging",
                        "severity": "reject",
                        "category": "testing",
                    }
                ]
            }
            result = extract_moves(email)

        move = result["moves"][0]
        required_fields = ["trigger", "principle", "response", "severity", "category"]
        for field in required_fields:
            assert field in move, f"Move missing required field: {field}"

    def test_extract_batch_writes_clusterable_format(self, tmp_path):
        """extract_batch should write JSONL that cluster can read."""
        out_path = tmp_path / "moves.jsonl"
        email = _make_email(message_id="batch-test@example.com")

        with patch("torvalds_skill.extract.extract_moves") as mock_extract:
            mock_extract.return_value = {
                "email_message_id": "batch-test@example.com",
                "email_date": "2024-01-01",
                "email_subject": "Re: Test",
                "moves": [
                    {
                        "trigger": "t1",
                        "principle": "p1",
                        "response": "r1",
                        "severity": "reject",
                        "category": "testing",
                    }
                ],
            }
            result = extract_batch([email], str(out_path))

        assert result["processed"] == 1
        assert out_path.exists()

        # Verify the file can be read by iter_moves
        moves = list(iter_moves(out_path))
        assert len(moves) == 1
        assert isinstance(moves[0], ReviewMove)

    def test_cluster_accepts_extract_output(self, tmp_path):
        """cluster_moves should accept moves from extract_batch."""
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"

        # Create moves in the format extract produces
        moves = [
            _make_review_move(
                email_message_id="cluster-test@example.com",
                email_date="2024-01-01",
                trigger="untested code",
                principle="require tests",
                response="add tests",
                severity="reject",
                category="testing",
            )
        ]
        _write_moves_jsonl(moves_path, moves)

        # Cluster should work - returns a list of patterns
        result = cluster_moves(moves_path, out_path)

        assert isinstance(result, list)
        assert len(result) == 1
        # Each pattern should have required fields
        assert "category" in result[0]
        assert "severity" in result[0]
        assert "trigger" in result[0]
        assert "principle" in result[0]
        assert "response" in result[0]
        assert "quote" in result[0]
        assert "source" in result[0]
        assert "email_message_id" in result[0]
        assert "email_date" in result[0]


class TestClusterToDistillDataFlow:
    """Test that cluster output matches what distill expects as input."""

    def test_cluster_output_structure(self, tmp_path):
        """cluster_moves output should have the structure distill expects."""
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"

        moves = [_make_review_move(email_message_id=f"m{i}@test.com") for i in range(10)]
        _write_moves_jsonl(moves_path, moves)

        result = cluster_moves(moves_path, out_path)

        # Result should be a flat list of pattern dicts
        assert isinstance(result, list)
        # With 10 moves and SUBSTANTIVE_FRACTION=0.5, only 5 are eligible
        assert len(result) == 5

        # Each pattern should have required fields
        for pattern in result:
            assert "category" in pattern
            assert "severity" in pattern
            assert "trigger" in pattern
            assert "principle" in pattern
            assert "response" in pattern
            assert "quote" in pattern
            assert "source" in pattern
            assert "email_message_id" in pattern
            assert "email_date" in pattern

    def test_samples_have_distill_required_fields(self, tmp_path):
        """Clustered samples must have fields distill needs."""
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"

        moves = [_make_review_move(email_message_id=f"m{i}@test.com") for i in range(10)]
        _write_moves_jsonl(moves_path, moves)

        cluster_moves(moves_path, out_path)

        # Load and verify - patterns is now a flat list
        with open(out_path, encoding="utf-8") as f:
            patterns = json.load(f)

        assert isinstance(patterns, list)
        for pattern in patterns:
            assert "trigger" in pattern
            assert "principle" in pattern
            assert "response" in pattern
            assert "severity" in pattern
            assert "category" in pattern
            assert "quote" in pattern
            assert "source" in pattern
            assert "email_message_id" in pattern
            assert "email_date" in pattern

    def test_patterns_json_valid_for_distill(self, tmp_path):
        """patterns.json should be valid input for distill_skill."""
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"

        moves = [
            _make_review_move(category="testing", email_message_id=f"t{i}@test.com")
            for i in range(5)
        ] + [
            _make_review_move(category="correctness", email_message_id=f"c{i}@test.com")
            for i in range(5)
        ]
        _write_moves_jsonl(moves_path, moves)

        cluster_moves(moves_path, out_path)

        # Verify JSON is valid - now a flat list of patterns
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) > 0
        # Verify patterns have categories from both groups
        categories = {p["category"] for p in data}
        assert "testing" in categories
        assert "correctness" in categories


class TestFullPipelineSmokeTest:
    """Run the full pipeline on a small fixture with mocked LLM."""

    def test_pipeline_no_crashes(self, tmp_path):
        """Full pipeline should complete without crashes."""
        # Create test emails
        emails = [
            _make_email(
                message_id=f"pipeline-test-{i}@example.com",
                subject=f"Re: Fix {i}",
                body=f"This is a substantive review comment {i} that has enough length to pass the minimum body length requirement of one hundred characters. The code has issues that need to be addressed.",
            )
            for i in range(5)
        ]

        # Stage 1: Classify
        classified = list(classify_corpus(emails))
        reviews = [e for e, label in classified if label == "review"]

        assert len(reviews) > 0, "Should have at least one review"

        # Stage 2: Extract (mocked)
        moves_path = tmp_path / "moves.jsonl"
        extract_results = []

        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.return_value = {
                "moves": [
                    {
                        "trigger": "issue detected",
                        "principle": "fix the issue",
                        "response": "this needs to be fixed",
                        "severity": "request-changes",
                        "category": "correctness",
                    }
                ]
            }

            for email in reviews:
                result = extract_moves(email)
                extract_results.append(result)

        assert len(extract_results) == len(reviews)

        # Write moves to file
        with open(moves_path, "w", encoding="utf-8") as f:
            for result in extract_results:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

        # Stage 3: Cluster
        out_path = tmp_path / "patterns.json"
        cluster_result = cluster_moves(moves_path, out_path)

        assert isinstance(cluster_result, list)
        assert len(cluster_result) > 0
        assert out_path.exists()

    def test_pipeline_preserves_data_integrity(self, tmp_path):
        """Data should flow through pipeline without corruption."""
        # Create emails with known content
        emails = [
            _make_email(
                message_id="integrity-1@example.com",
                subject="Re: Test 1",
                body="Review comment one that is substantive enough. "
                "The code needs improvement in error handling. "
                "This is important for correctness.",
            ),
            _make_email(
                message_id="integrity-2@example.com",
                subject="Re: Test 2",
                body="Review comment two that is substantive enough and has the required length. "
                "The tests are missing from this code. "
                "Add tests before merging this patch.",
            ),
        ]

        # Classify
        classified = list(classify_corpus(emails))
        reviews = [e for e, label in classified if label == "review"]

        # Both should be classified as reviews
        assert len(reviews) == 2

        # Extract with specific moves
        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.side_effect = [
                {
                    "moves": [
                        {
                            "trigger": "missing error handling",
                            "principle": "add error handling",
                            "response": "this needs error handling",
                            "severity": "reject",
                            "category": "error-handling",
                        }
                    ]
                },
                {
                    "moves": [
                        {
                            "trigger": "no tests",
                            "principle": "require tests",
                            "response": "add tests",
                            "severity": "reject",
                            "category": "testing",
                        }
                    ]
                },
            ]

            moves = []
            for email in reviews:
                result = extract_moves(email)
                moves.extend(result["moves"])

        # Verify extracted moves have correct structure
        assert len(moves) == 2
        categories = {m["category"] for m in moves}
        assert "error-handling" in categories
        assert "testing" in categories

    def test_pipeline_handles_empty_moves(self, tmp_path):
        """Pipeline should handle emails that produce no moves."""
        emails = [
            _make_email(
                message_id="empty-moves@example.com",
                subject="Re: Ack",
                body="This is a substantive email but with no review moves. "
                "It's just an acknowledgment. "
                "Nothing to extract here.",
            ),
        ]

        # Classify
        classified = list(classify_corpus(emails))
        reviews = [e for e, label in classified if label == "review"]

        # Extract with empty moves
        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.return_value = {"moves": []}

            for email in reviews:
                result = extract_moves(email)
                assert result["moves"] == []

        # Cluster should handle empty moves file
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"

        # Write empty result
        with open(moves_path, "w", encoding="utf-8") as f:
            f.write('{"email_message_id": "empty-moves@example.com", "moves": []}\n')

        # Should not crash - returns empty list for no moves
        result = cluster_moves(moves_path, out_path)
        assert isinstance(result, list)
        assert len(result) == 0


class TestDataFormatInvariants:
    """Verify that ReviewMove fields are consistent across stages."""

    def test_reviewmove_has_all_required_fields(self):
        """ReviewMove dataclass must have all fields needed by cluster and distill."""
        move = _make_review_move()

        # Fields required by cluster.py
        assert hasattr(move, "email_message_id")
        assert hasattr(move, "email_date")
        assert hasattr(move, "trigger")
        assert hasattr(move, "principle")
        assert hasattr(move, "response")
        assert hasattr(move, "severity")
        assert hasattr(move, "category")

    def test_extract_moves_match_reviewmove_schema(self):
        """Moves from extract_moves should match ReviewMove schema."""
        email = _make_email(message_id="schema-test@example.com")

        expected_fields = {"trigger", "principle", "response", "severity", "category"}

        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.return_value = {
                "moves": [
                    {
                        "trigger": "t",
                        "principle": "p",
                        "response": "r",
                        "severity": "reject",
                        "category": "testing",
                    }
                ]
            }
            result = extract_moves(email)

        move = result["moves"][0]
        assert set(move.keys()) == expected_fields

    def test_cluster_samples_have_required_fields(self, tmp_path):
        """Samples from cluster_moves must have fields distill needs."""
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"

        moves = [_make_review_move(email_message_id="field-test@test.com")]
        _write_moves_jsonl(moves_path, moves)

        cluster_moves(moves_path, out_path)

        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)

        # Data is now a flat list of patterns
        assert isinstance(data, list)

        # Each pattern should have these fields
        required_pattern_fields = {
            "trigger",
            "principle",
            "response",
            "severity",
            "category",
            "quote",
            "source",
            "email_message_id",
            "email_date",
        }

        for pattern in data:
            assert set(pattern.keys()) == required_pattern_fields, (
                f"Pattern missing fields: {required_pattern_fields - set(pattern.keys())}"
            )

    def test_severity_values_are_valid(self):
        """Severity values should be from the valid set."""
        valid_severities = {"reject", "request-changes", "nitpick", "approve", "discussion"}

        move = _make_review_move(severity="reject")
        assert move.severity in valid_severities

        move = _make_review_move(severity="request-changes")
        assert move.severity in valid_severities

    def test_category_values_are_valid(self):
        """Category values should be from the valid set."""
        from torvalds_skill.models import CATEGORIES

        move = _make_review_move(category="testing")
        assert move.category in CATEGORIES

        move = _make_review_move(category="correctness")
        assert move.category in CATEGORIES


class TestEdgeCases:
    """Test edge cases in pipeline data flow."""

    def test_email_with_multiple_moves(self, tmp_path):
        """Single email can produce multiple moves."""
        email = _make_email(
            message_id="multi-move@example.com",
            body="Review with multiple issues. "
            "First, the error handling is wrong. "
            "Second, there are no tests. "
            "Third, the naming is unclear. "
            "All need to be fixed.",
        )

        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.return_value = {
                "moves": [
                    {
                        "trigger": "bad error handling",
                        "principle": "fix error handling",
                        "response": "error handling is wrong",
                        "severity": "reject",
                        "category": "error-handling",
                    },
                    {
                        "trigger": "no tests",
                        "principle": "add tests",
                        "response": "no tests present",
                        "severity": "reject",
                        "category": "testing",
                    },
                ]
            }
            result = extract_moves(email)

        assert len(result["moves"]) == 2

        # Both moves should be clusterable
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"

        with open(moves_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

        cluster_result = cluster_moves(moves_path, out_path)
        assert isinstance(cluster_result, list)
        assert len(cluster_result) == 2

    def test_mixed_severity_moves(self, tmp_path):
        """Pipeline should handle moves with different severities."""
        moves = [
            _make_review_move(email_message_id="m1@test.com", severity="reject"),
            _make_review_move(email_message_id="m2@test.com", severity="approve"),
            _make_review_move(email_message_id="m3@test.com", severity="nitpick"),
            _make_review_move(email_message_id="m4@test.com", severity="request-changes"),
            _make_review_move(email_message_id="m5@test.com", severity="discussion"),
        ]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"

        _write_moves_jsonl(moves_path, moves)

        result = cluster_moves(moves_path, out_path)

        # Result is a flat list - count severities from the list
        assert isinstance(result, list)
        reject_count = sum(1 for p in result if p["severity"] == "reject")
        approve_count = sum(1 for p in result if p["severity"] == "approve")
        nitpick_count = sum(1 for p in result if p["severity"] == "nitpick")
        # With 5 moves and SUBSTANTIVE_FRACTION=0.5, only 2 are eligible
        assert reject_count + approve_count + nitpick_count == 2

    def test_large_batch_processing(self, tmp_path):
        """Pipeline should handle larger batches without issues."""
        # Create 20 emails
        emails = [
            _make_email(
                message_id=f"batch-{i}@example.com",
                subject=f"Re: Patch {i}",
                body=f"Substantive review comment {i} that has enough length to pass the minimum body length requirement of one hundred characters. The code needs attention.",
            )
            for i in range(20)
        ]

        # Classify
        classified = list(classify_corpus(emails))
        reviews = [e for e, label in classified if label == "review"]

        # Extract all
        with patch("torvalds_skill.extract._call_llm") as mock_llm:
            mock_llm.return_value = {
                "moves": [
                    {
                        "trigger": "issue",
                        "principle": "fix it",
                        "response": "needs fixing",
                        "severity": "request-changes",
                        "category": "correctness",
                    }
                ]
            }

            results = [extract_moves(e) for e in reviews]

        assert len(results) == len(reviews)
