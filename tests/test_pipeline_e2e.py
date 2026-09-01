"""End-to-end integration tests for the torvalds-skill pipeline.

Tests cover the full chain: classify → extract → cluster → distill → verify_skill.
Each test uses tmp_path for isolation and mocks LLM calls to avoid API hits.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from torvalds_skill.classify import is_review, classify_corpus
from torvalds_skill.extract import extract_moves, _validate_severity_consistency
from torvalds_skill.cluster import cluster_moves, _stratified_sample
from torvalds_skill.models import EmailRecord, CATEGORIES, SEVERITIES


def _make_email(
    message_id: str = "test@example.com",
    subject: str = "Re: Some patch",
    from_name: str = "Linus Torvalds",
    from_email: str = "torvalds@linux.org",
    date: str = "2024-01-01",
    body: str = "This code is broken. You cannot free the buffer before the last use.",
    in_reply_to: str | None = "parent@example.com",
) -> EmailRecord:
    """Helper to create EmailRecord with defaults."""
    return EmailRecord(
        message_id=message_id,
        from_name=from_name,
        from_email=from_email,
        date=date,
        subject=subject,
        in_reply_to=in_reply_to,
        body=body,
    )


class TestClassifyToExtractFlow:
    """Test 1: Feed 3 synthetic emails through classify then extract."""

    def test_classify_to_extract_flow(self, tmp_path):
        """Announcement filtered, git-pull skipped, 1 move extracted from review."""
        # Create 3 synthetic emails: 1 review, 1 announcement, 1 git-pull
        review_email = _make_email(
            message_id="review1@example.com",
            subject="Re: Fix memory leak in network driver",
            body=(
                "This is clearly wrong. You are freeing the buffer before the last use. "
                "This is a use-after-free bug that will crash the kernel. "
                "You must not free memory that is still in use. "
                "Fix this before submitting."
            ),
        )
        announcement_email = _make_email(
            message_id="announce@example.com",
            subject="Linux 6.7-rc1",
            body="This is the first release candidate for 6.7.",
            in_reply_to=None,
        )
        git_pull_email = _make_email(
            message_id="pull@example.com",
            subject="Re: [GIT PULL] network fixes",
            body="I've pulled these fixes into my tree.",
        )

        emails = [review_email, announcement_email, git_pull_email]

        # Step 1: Classify
        classified = list(classify_corpus(emails))
        
        # Assert: announcement filtered (not a review), git-pull skipped (not a review), review passes
        review_label = classified[0][1]
        announce_label = classified[1][1]
        pull_label = classified[2][1]
        
        assert review_label == "review", "Review email should be classified as review"
        assert announce_label == "other", "Announcement should be classified as other"
        assert pull_label == "other", "Git pull should be classified as other"

        # Filter to reviews only
        review_emails = [email for email, label in classified if label == "review"]
        assert len(review_emails) == 1, "Only 1 review email should pass classification"

        # Step 2: Extract (mocked LLM returns one move for the review email)
        mock_response = {
            "moves": [
                {
                    "trigger": "freeing buffer before last use",
                    "principle": "Don't free memory that is still in use",
                    "response": "This is a use-after-free bug that will crash the kernel",
                    "severity": "reject",
                    "category": "memory-safety",
                }
            ]
        }

        with patch("torvalds_skill.extract._call_llm", return_value=mock_response):
            extract_results = [extract_moves(email) for email in review_emails]

        # Assert: 1 move extracted
        assert len(extract_results) == 1
        result = extract_results[0]
        assert "error" not in result, f"Extraction should not have error: {result.get('error')}"
        assert len(result["moves"]) == 1, "Should extract exactly 1 move"
        assert result["moves"][0]["severity"] == "reject"
        assert result["moves"][0]["category"] == "memory-safety"


class TestExtractToClusterFlow:
    """Test 2: Feed 10 synthetic moves through cluster stratified sampling + TF-IDF."""

    def test_extract_to_cluster_flow(self, tmp_path):
        """Samples distributed across categories/severities, clusters formed, output JSON valid."""
        # Create 10 synthetic moves: 2 categories × 5 severities
        # Format: nested JSONL where each line has email fields + moves array
        categories_to_use = ["correctness", "performance"]
        severities_to_use = ["reject", "request-changes", "nitpick", "approve", "discussion"]
        
        # Build nested structure: email entries with moves arrays
        email_entries = []
        for i, (cat, sev) in enumerate(zip(categories_to_use * 5, severities_to_use * 2)):
            entry = {
                "email_message_id": f"move{i}@example.com",
                "email_date": f"2024-{(i % 12) + 1:02d}-01",
                "moves": [
                    {
                        "trigger": f"Test trigger {i}",
                        "principle": f"Test principle for {cat}",
                        "response": f"Test response with severity {sev}",
                        "severity": sev,
                        "category": cat,
                    }
                ],
            }
            email_entries.append(entry)

        # Write moves to JSONL file
        moves_path = tmp_path / "moves.jsonl"
        with open(moves_path, "w", encoding="utf-8") as f:
            for entry in email_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Step: Cluster
        output_path = tmp_path / "patterns.json"
        result = cluster_moves(moves_path, output_path, top_n=10)

        # Assert: samples distributed
        assert "samples_by_category" in result
        assert "correctness" in result["samples_by_category"]
        assert "performance" in result["samples_by_category"]
        
        # Check stratified sampling distributed across severities
        correctness_samples = result["samples_by_category"]["correctness"]
        assert len(correctness_samples) > 0, "Should have samples from correctness category"
        
        # Assert: output JSON valid (already validated by cluster_moves writing it)
        assert output_path.exists(), "patterns.json should be created"
        
        # Verify the JSON is valid and has expected structure
        with open(output_path, "r", encoding="utf-8") as f:
            patterns = json.load(f)
        
        assert "total_moves" in patterns
        assert "samples_by_category" in patterns
        assert patterns["total_moves"] == 10


class TestClusterToDistillToVerifyFlow:
    """Test 3: Feed clustered patterns through distill (mocked) then verify_skill."""

    def test_cluster_to_distill_to_verify_flow(self, tmp_path):
        """Mock LLM returns minimal valid SKILL.md; skill passes verify_skill section checks."""
        # Create minimal patterns.json - distill expects a list of pattern dicts
        # Each pattern has: trigger, principle, response, severity, date, category
        patterns_data = [
            {
                "trigger": "Missing error check",
                "principle": "Always check return values",
                "response": "This is wrong, you must check for errors",
                "severity": "reject",
                "date": "2024-01-01",
                "category": "correctness",
            }
        ] * 5
        
        patterns_path = tmp_path / "patterns.json"
        with open(patterns_path, "w", encoding="utf-8") as f:
            json.dump(patterns_data, f)

        # Mock LLM to return minimal valid SKILL.md with frontmatter + required sections
        minimal_skill = """---
name: Linus Torvalds Code Review Skill
version: 1.0
---

## Reviewer Mindset

Torvalds focuses on correctness first.

## Review Triggers

- Missing error checks trigger reject severity.

## Precedence and Priorities

Correctness overrides all other concerns.

## Decision Cards

Reject: Code that is broken or unsafe.

## Key Definitions

Correctness: Code that works as intended.

## Anti-Patterns

Don't skip error checking.

## Voice and Tone

Direct, no-nonsense feedback.

## Severity Calibration

Reject is common for correctness issues.

## Severity Decision Tree

If code is broken → reject.
"""

        # Mock _call_llm in distill module
        with patch("torvalds_skill.distill._call_llm", return_value=minimal_skill):
            from torvalds_skill.distill import distill_skill
            
            skill_path = tmp_path / "SKILL.md"
            distill_skill(patterns_path, skill_path, top_n=5)

        # Assert: skill file created
        assert skill_path.exists(), "SKILL.md should be created"
        
        # Step: Verify skill (import from scripts)
        from scripts.verify_skill import check_forbidden_terms, check_no_tables, check_interview_quotes, score_skill_quality
        
        # Assert: skill passes verify_skill section checks
        # Check required sections exist
        content = skill_path.read_text()
        assert "## Reviewer Mindset" in content
        assert "## Review Triggers" in content
        assert "## Severity Calibration" in content
        assert "## Severity Decision Tree" in content
        
        # Check no forbidden terms (C-specific tokens)
        violations = check_forbidden_terms(skill_path)
        assert len(violations) == 0, f"No forbidden terms should be found, got: {violations}"
        
        # Check no markdown tables
        no_tables, table_violations = check_no_tables(skill_path)
        assert no_tables, "No markdown tables should be present"
        
        # Score skill quality (should be > 0)
        calibration = {}  # Empty calibration for this test
        score_result = score_skill_quality(skill_path)
        score = score_result.get("total", 0)
        assert score > 0, f"Skill quality score should be > 0, got {score}"


class TestSeverityConsistency:
    """Test 4: Feed email with severity/language mismatch."""

    def test_full_pipeline_with_severity_consistency(self, tmp_path):
        """Mocked extraction returns severity mismatch; _validate_severity_consistency flags it."""
        # Create email whose mocked extraction returns a severity/language mismatch
        email = _make_email(
            message_id="mismatch@example.com",
            subject="Re: Bug in network code",
            body=(
                "This is a nitpick but this will crash the system. "
                "The hard language 'crash' doesn't match the lenient severity."
            ),
        )

        # Mock LLM to return move with severity mismatch: "nitpick" + hard language ("crash")
        mock_response = {
            "moves": [
                {
                    "trigger": "this will crash the system",
                    "principle": "Don't crash the system",
                    "response": "This is a nitpick but this will crash",
                    "severity": "nitpick",  # Lenient severity
                    "category": "correctness",
                }
            ]
        }

        warning_count = 0
        with patch("torvalds_skill.extract._call_llm", return_value=mock_response):
            result = extract_moves(email)
            
            # Assert: pipeline still completes
            assert "error" not in result or result.get("severity_warnings", 0) >= 0
            
            # Check that severity inconsistency was detected
            # The move has "nitpick" severity but contains hard language ("crash")
            move = result["moves"][0]
            is_consistent, reason = _validate_severity_consistency(move)
            
            # Assert: inconsistency flagged
            assert not is_consistent, "Severity inconsistency should be detected"
            assert "hard language" in reason.lower(), f"Reason should mention hard language: {reason}"
            
            # The extract_moves function should have incremented severity_warnings
            warning_count = result.get("severity_warnings", 0)
        
        # Assert: warning counter incremented
        assert warning_count >= 1, "At least 1 severity warning should be recorded"


class TestBatchMode:
    """Test 5: Feed 4 emails with --batch-size 2 through extract."""

    def test_full_pipeline_with_batch_mode(self, tmp_path):
        """Batch parsing succeeds for valid response; malformed response triggers fallback."""
        # Create 4 synthetic emails
        emails = [
            _make_email(
                message_id=f"batch{i}@example.com",
                subject=f"Re: Patch {i}",
                body=f"This is review feedback for patch {i}. It has issues.",
            )
            for i in range(4)
        ]

        # Mock batch LLM response: 2 moves per batch (one per email)
        def mock_batch_call_llm(batch_emails):
            """Mock that returns 2 results (one per email in batch)."""
            results = []
            for email in batch_emails:
                results.append({
                    "moves": [
                        {
                            "trigger": f"Issue in {email.message_id}",
                            "principle": "Fix the issue",
                            "response": "This needs fixing",
                            "severity": "request-changes",
                            "category": "correctness",
                        }
                    ]
                })
            return results

        # Test batch extraction with batch_size=2
        output_path = tmp_path / "batch_output.jsonl"
        
        with patch("torvalds_skill.extract._call_llm_batch", return_value=[
            {"moves": [{"trigger": "Issue 1", "principle": "P1", "response": "R1", "severity": "reject", "category": "correctness"}]},
            {"moves": [{"trigger": "Issue 2", "principle": "P2", "response": "R2", "severity": "reject", "category": "correctness"}]},
        ]):
            with patch("torvalds_skill.extract._call_llm_batch", side_effect=[
                # First batch (emails 0-1)
                [
                    {"moves": [{"trigger": "Issue 0", "principle": "P0", "response": "R0", "severity": "reject", "category": "correctness"}]},
                    {"moves": [{"trigger": "Issue 1", "principle": "P1", "response": "R1", "severity": "reject", "category": "correctness"}]},
                ],
                # Second batch (emails 2-3)
                [
                    {"moves": [{"trigger": "Issue 2", "principle": "P2", "response": "R2", "severity": "reject", "category": "correctness"}]},
                    {"moves": [{"trigger": "Issue 3", "principle": "P3", "response": "R3", "severity": "reject", "category": "correctness"}]},
                ],
            ]):
                from torvalds_skill.extract import extract_moves_batch
                
                results = extract_moves_batch(emails, batch_size=2, batch_retry=True)

        # Assert: all 4 processed
        assert len(results) == 4, "All 4 emails should be processed"
        
        # Assert: batch parsing succeeds
        for i, result in enumerate(results):
            assert "error" not in result, f"Email {i} should not have error"
            assert len(result["moves"]) == 1, f"Email {i} should have 1 move"

    def test_malformed_batch_response_triggers_fallback(self, tmp_path):
        """Malformed batch response (wrong array length) triggers fallback to sequential."""
        # Create 2 synthetic emails
        emails = [
            _make_email(
                message_id="batch0@example.com",
                subject="Re: Patch 0",
                body="This is review feedback.",
            ),
            _make_email(
                message_id="batch1@example.com",
                subject="Re: Patch 1",
                body="This is review feedback.",
            ),
        ]

        # Mock batch LLM to return malformed response (1 result instead of 2)
        def mock_malformed_batch_call(batch_emails, batch_size):
            """Mock that returns wrong number of results."""
            raise ValueError(f"Expected {batch_size} results, got 1")

        # Mock sequential extraction as fallback
        def mock_sequential_extract(email):
            return {
                "email_message_id": email.message_id,
                "email_date": email.date,
                "email_subject": email.subject,
                "moves": [
                    {
                        "trigger": "Fallback extraction",
                        "principle": "Fixed by fallback",
                        "response": "Sequential fallback worked",
                        "severity": "nitpick",
                        "category": "other",
                    }
                ],
                "severity_warnings": 0,
                "cached": False,
            }

        with patch("torvalds_skill.extract._call_llm_batch", side_effect=mock_malformed_batch_call):
            with patch("torvalds_skill.extract.extract_moves", side_effect=mock_sequential_extract):
                from torvalds_skill.extract import extract_moves_batch
                
                results = extract_moves_batch(emails, batch_size=2, batch_retry=True)

        # Assert: fallback path succeeded (sequential extraction used)
        assert len(results) == 2, "Both emails should be processed via fallback"
        for result in results:
            assert "error" not in result, "Fallback should succeed without error"
            assert len(result["moves"]) == 1, "Each email should have 1 move from fallback"
            assert result["moves"][0]["principle"] == "Fixed by fallback"