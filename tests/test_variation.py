"""Tests for variation.py context signal extraction.

Tests the rule-based functions for detecting thread phase, urgency,
and word counting, as well as JSON response parsing.
"""

import json

import pytest

from torvalds_skill.variation import (
    detect_thread_phase,
    detect_urgency,
    count_words,
    _parse_json_response,
)


class TestDetectThreadPhase:
    """Test detect_thread_phase pure function for thread phase detection."""

    def test_initial_review_no_in_reply_to(self):
        """Email without In-Reply-To header is initial review."""
        headers = {"In-Reply-To": ""}
        subject = "Some patch"
        phase = detect_thread_phase(headers, subject)
        assert phase == "initial_review"

    def test_initial_review_missing_in_reply_to_key(self):
        """Email without In-Reply-To key is initial review."""
        headers = {}
        subject = "Some patch"
        phase = detect_thread_phase(headers, subject)
        assert phase == "initial_review"

    def test_iteration_n_with_in_reply_to_no_finality(self):
        """Email with In-Reply-To and no finality signals is iteration_n."""
        headers = {"In-Reply-To": "parent@example.com"}
        subject = "Re: Fix memory leak"
        phase = detect_thread_phase(headers, subject)
        assert phase == "iteration_n"

    @pytest.mark.parametrize("subject", [
        "Re: Patch applied",
        "Re: Changes merged",
        "Re: Request rejected",
        "Re: Your patch is acked",
        "Re: Code pulled into tree",
    ])
    def test_final_decision_with_finality_signals(self, subject):
        """Subject with finality signals indicates final decision."""
        headers = {"In-Reply-To": "parent@example.com"}
        phase = detect_thread_phase(headers, subject)
        assert phase == "final_decision"

    @pytest.mark.parametrize("subject", [
        "Re: Patch APPLIED",
        "Re: Changes MERGED",
        "Re: Request REJECTED",
        "Re: Your patch is ACKED",
        "Re: Code PULLED into tree",
    ])
    def test_final_decision_case_insensitive(self, subject):
        """Finality signals are case-insensitive."""
        headers = {"In-Reply-To": "parent@example.com"}
        phase = detect_thread_phase(headers, subject)
        assert phase == "final_decision"

    def test_iteration_n_with_in_reply_to_and_applied(self):
        """In-Reply-To with 'applied' in subject is final_decision."""
        headers = {"In-Reply-To": "parent@example.com"}
        subject = "Re: Patch applied to tree"
        phase = detect_thread_phase(headers, subject)
        assert phase == "final_decision"

    def test_iteration_n_with_in_reply_to_and_merged(self):
        """In-Reply-To with 'merged' in subject is final_decision."""
        headers = {"In-Reply-To": "parent@example.com"}
        subject = "Re: Your changes merged"
        phase = detect_thread_phase(headers, subject)
        assert phase == "final_decision"

    def test_iteration_n_with_in_reply_to_and_rejected(self):
        """In-Reply-To with 'rejected' in subject is final_decision."""
        headers = {"In-Reply-To": "parent@example.com"}
        subject = "Re: Patch rejected"
        phase = detect_thread_phase(headers, subject)
        assert phase == "final_decision"

    def test_iteration_n_with_in_reply_to_and_acked(self):
        """In-Reply-To with 'acked' in subject is final_decision."""
        headers = {"In-Reply-To": "parent@example.com"}
        subject = "Re: Patch acked by maintainer"
        phase = detect_thread_phase(headers, subject)
        assert phase == "final_decision"

    def test_iteration_n_with_in_reply_to_and_pulled(self):
        """In-Reply-To with 'pulled' in subject is final_decision."""
        headers = {"In-Reply-To": "parent@example.com"}
        subject = "Re: Code pulled"
        phase = detect_thread_phase(headers, subject)
        assert phase == "final_decision"


class TestDetectUrgency:
    """Test detect_urgency pure function for urgency detection."""

    @pytest.mark.parametrize("subject", [
        "Fix for -rc1",
        "Critical fix -rc2",
        "Merge window patch",
        "Release blocker fix",
        "Critical fix release",
    ])
    def test_release_blocker_urgency_signals(self, subject):
        """Subject with urgency signals is release_blocker."""
        headers = {}
        urgency = detect_urgency(headers, subject)
        assert urgency == "release_blocker"

    @pytest.mark.parametrize("subject", [
        "Fix for -RC1",
        "Critical Fix -RC2",
        "MERGE WINDOW patch",
        "RELEASE BLOCKER fix",
    ])
    def test_release_blocker_case_insensitive(self, subject):
        """Urgency signals are case-insensitive."""
        headers = {}
        urgency = detect_urgency(headers, subject)
        assert urgency == "release_blocker"

    def test_release_blocker_date_rc_pattern(self):
        """Date with -rcN pattern is release_blocker."""
        headers = {"Date": "2024-01-15 -rc3"}
        subject = "Regular patch"
        urgency = detect_urgency(headers, subject)
        assert urgency == "release_blocker"

    def test_release_blocker_date_rc_pattern_lowercase(self):
        """Date with -rcN pattern (lowercase) is release_blocker."""
        headers = {"Date": "2024-01-15 -rc3"}
        subject = "Regular patch"
        urgency = detect_urgency(headers, subject)
        assert urgency == "release_blocker"

    @pytest.mark.parametrize("subject", [
        "Regular patch",
        "Documentation update",
        "Code cleanup",
        "Feature addition",
    ])
    def test_routine_urgency(self, subject):
        """Subject without urgency signals is routine."""
        headers = {}
        urgency = detect_urgency(headers, subject)
        assert urgency == "routine"

    def test_routine_with_regular_date(self):
        """Date without -rc pattern is routine."""
        headers = {"Date": "2024-01-15"}
        subject = "Regular patch"
        urgency = detect_urgency(headers, subject)
        assert urgency == "routine"

    def test_routine_with_empty_headers(self):
        """Empty headers and subject is routine."""
        headers = {}
        subject = "Patch"
        urgency = detect_urgency(headers, subject)
        assert urgency == "routine"


class TestCountWords:
    """Test count_words pure function for word counting."""

    def test_empty_string(self):
        """Empty string returns 0 words."""
        assert count_words("") == 0

    def test_single_word(self):
        """Single word returns 1."""
        assert count_words("hello") == 1

    def test_multiple_words(self):
        """Multiple words separated by spaces."""
        assert count_words("hello world") == 2

    def test_multiple_spaces(self):
        """Multiple spaces between words are handled."""
        assert count_words("hello   world") == 2

    def test_newlines(self):
        """Newlines separate words."""
        assert count_words("hello\nworld") == 2

    def test_tabs(self):
        """Tabs separate words."""
        assert count_words("hello\tworld") == 2

    def test_mixed_whitespace(self):
        """Mixed whitespace characters separate words."""
        assert count_words("hello  \n\t  world") == 2

    def test_punctuation_attached(self):
        """Punctuation attached to words counts as part of word."""
        assert count_words("hello, world!") == 2

    def test_numbers(self):
        """Numbers count as words."""
        assert count_words("123 456") == 2

    def test_special_characters(self):
        """Special characters attached to words count as part of word."""
        assert count_words("foo@bar.com test") == 2


class TestParseJsonResponse:
    """Test _parse_json_response pure function for JSON parsing."""

    def test_plain_json(self):
        """Plain JSON without fences is parsed correctly."""
        text = '{"stakes": "high", "risk": "safety_critical"}'
        result = _parse_json_response(text)
        assert result == {"stakes": "high", "risk": "safety_critical"}

    def test_json_with_markdown_fences(self):
        """JSON wrapped in markdown fences is parsed correctly."""
        text = '```\n{"stakes": "high", "risk": "safety_critical"}\n```'
        result = _parse_json_response(text)
        assert result == {"stakes": "high", "risk": "safety_critical"}

    def test_json_with_language_fence(self):
        """JSON wrapped in ```json fences is parsed correctly."""
        text = '```json\n{"stakes": "medium", "risk": "correctness"}\n```'
        result = _parse_json_response(text)
        assert result == {"stakes": "medium", "risk": "correctness"}

    def test_json_with_trailing_newlines(self):
        """JSON with trailing newlines is parsed correctly."""
        text = '{"stakes": "low", "risk": "cosmetic"}\n\n\n'
        result = _parse_json_response(text)
        assert result == {"stakes": "low", "risk": "cosmetic"}

    def test_json_with_leading_newlines(self):
        """JSON with leading newlines is parsed correctly."""
        text = '\n\n{"stakes": "high", "risk": "safety_critical"}'
        result = _parse_json_response(text)
        assert result == {"stakes": "high", "risk": "safety_critical"}

    def test_json_with_whitespace_only_fences(self):
        """JSON with only whitespace inside fences is parsed correctly."""
        text = '```\n   \n{"stakes": "medium", "risk": "correctness"}\n   \n```'
        result = _parse_json_response(text)
        assert result == {"stakes": "medium", "risk": "correctness"}

    def test_invalid_json(self):
        """Invalid JSON raises JSONDecodeError."""
        text = 'not valid json'
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(text)

    def test_invalid_json_with_fences(self):
        """Invalid JSON with fences raises JSONDecodeError."""
        text = '```\nnot valid json\n```'
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(text)

    def test_empty_string(self):
        """Empty string raises JSONDecodeError."""
        text = ''
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(text)

    def test_only_fences(self):
        """Only fence markers raises JSONDecodeError."""
        text = '```'
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(text)

    def test_json_with_extra_text_before_fences(self):
        """JSON with text before opening fence - only fence content is parsed."""
        text = 'Here is the JSON:\n```json\n{"stakes": "high", "risk": "safety_critical"}\n```'
        # The function strips leading fences, so this should fail
        # because "Here is the JSON:" is not valid JSON
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(text)

    def test_json_with_extra_text_after_fences(self):
        """JSON with text after closing fence - only fence content is parsed."""
        text = '```\n{"stakes": "high", "risk": "safety_critical"}\n```\nEnd of response'
        # The function only strips the last line if it starts with ```
        # So "End of response" will cause a parse error
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(text)

    def test_single_fence_line(self):
        """Single fence line is treated as content."""
        text = '```'
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(text)

    def test_json_with_comments_in_fences(self):
        """JSON with comment-like content in fences is parsed as-is."""
        text = '```\n// This is a comment\n{"stakes": "high", "risk": "safety_critical"}\n```'
        # The comment line will cause JSON parse error
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response(text)