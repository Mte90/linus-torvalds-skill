"""Tests for verify_skill.py validation functions.

Verifies the skill file validation logic that checks for forbidden terms,
tables, quotes, and text normalization.
"""

import pytest
from pathlib import Path

from scripts.verify_skill import (
    normalize, check_forbidden_terms, check_no_tables, check_interview_quotes,
    score_skill_quality, _score_trigger_diversity, _score_severity_distribution,
    _score_language_agnosticism, _score_section_coverage
)


class TestNormalize:
    """Test unicode normalization for section matching."""

    def test_curly_double_quotes_to_straight(self):
        """Curly double quotes should be converted to straight quotes."""
        text = 'He said "hello" to her'
        result = normalize(text)
        assert result == 'He said "hello" to her'

    def test_curly_single_quotes_to_straight(self):
        """Curly single quotes should be converted to straight quotes."""
        text = "It's a test with 'quotes'"
        result = normalize(text)
        assert result == "It's a test with 'quotes'"

    def test_en_dash_to_hyphen(self):
        """En dash should be converted to hyphen."""
        text = "pre-order and well-known"
        result = normalize(text)
        assert result == "pre-order and well-known"

    def test_em_dash_to_hyphen(self):
        """Em dash should be converted to hyphen."""
        text = "this—that—the other"
        result = normalize(text)
        assert result == "this-that-the other"

    def test_hyphen_variants(self):
        """All hyphen variants should normalize to standard hyphen."""
        # \u2010 = hyphen, \u2011 = non-breaking hyphen, \u2012 = figure dash
        text = "test\u2010case\u2011and\u2012more"
        result = normalize(text)
        assert result == "test-case-and-more"

    def test_figure_dash_to_hyphen(self):
        """Figure dash should be converted to hyphen."""
        text = "1\u20122\u20123 sequence"
        result = normalize(text)
        assert result == "1-2-3 sequence"

    def test_empty_string(self):
        """Empty string should return empty string."""
        result = normalize("")
        assert result == ""

    def test_no_special_characters(self):
        """Text without special characters should pass through unchanged."""
        text = "Regular ASCII text with normal hyphens"
        result = normalize(text)
        assert result == text

    def test_mixed_quotes(self):
        """Mixed curly and straight quotes should all normalize."""
        text = 'He said "hello" and she said \'hi\' with "mixed"'
        result = normalize(text)
        assert result == 'He said "hello" and she said \'hi\' with "mixed"'


class TestCheckForbiddenTerms:
    """Test forbidden terms detection outside quote blocks."""

    def test_no_violations_clean_file(self, tmp_path):
        """Clean file without forbidden terms should return empty list."""
        skill_file = tmp_path / "clean.md"
        skill_file.write_text("""# Review Mindset

This is a clean skill file with no forbidden C terms.
It discusses testing and correctness properly.
""")
        violations = check_forbidden_terms(skill_file)
        assert violations == []

    def test_forbidden_term_in_plain_text(self, tmp_path):
        """Forbidden term in plain text should be flagged."""
        skill_file = tmp_path / "violation.md"
        skill_file.write_text("""# Code Review

You should use kmalloc for memory allocation.
""")
        violations = check_forbidden_terms(skill_file)
        assert len(violations) == 1
        line_num, term, line = violations[0]
        assert term == "kmalloc"
        assert "kmalloc" in line

    def test_forbidden_term_in_quotes_exempt(self, tmp_path):
        """Forbidden term inside quotes should be exempt."""
        skill_file = tmp_path / "quoted.md"
        skill_file.write_text("""# Example

As Linus said: "I use kmalloc all the time"
""")
        violations = check_forbidden_terms(skill_file)
        assert violations == []

    def test_forbidden_term_in_curly_quotes_exempt(self, tmp_path):
        """Forbidden term inside curly quotes should be exempt."""
        skill_file = tmp_path / "curly_quoted.md"
        skill_file.write_text("""# Example

Linus noted: "the kmalloc pattern is common"
""")
        violations = check_forbidden_terms(skill_file)
        assert violations == []

    def test_forbidden_term_in_inline_code_exempt(self, tmp_path):
        """Forbidden term inside inline code should be exempt."""
        skill_file = tmp_path / "code.md"
        skill_file.write_text("""# Usage

Use `kmalloc` for allocations.
""")
        violations = check_forbidden_terms(skill_file)
        assert violations == []

    def test_blockquote_line_exempt(self, tmp_path):
        """Forbidden term in blockquote line should be exempt."""
        skill_file = tmp_path / "blockquote.md"
        skill_file.write_text("""# Quote

> You must use kmalloc here
> And kfree when done
""")
        violations = check_forbidden_terms(skill_file)
        assert violations == []

    def test_multiple_violations(self, tmp_path):
        """Multiple forbidden terms should all be reported."""
        skill_file = tmp_path / "multi.md"
        skill_file.write_text("""# Bad File

Use kmalloc and kfree properly.
Also avoid spin_lock without reason.
""")
        violations = check_forbidden_terms(skill_file)
        assert len(violations) == 3

    def test_multiple_terms_same_line(self, tmp_path):
        """Multiple forbidden terms on same line should each be reported."""
        skill_file = tmp_path / "same_line.md"
        skill_file.write_text("""# Bad

Use kmalloc and kfree together.
""")
        violations = check_forbidden_terms(skill_file)
        assert len(violations) == 2


class TestCheckNoTables:
    """Test markdown table detection."""

    def test_no_tables_clean_file(self, tmp_path):
        """File without tables should return True and empty list."""
        skill_file = tmp_path / "clean.md"
        skill_file.write_text("""# Review Mindset

- Point one
- Point two
- Point three
""")
        is_clean, violations = check_no_tables(skill_file)
        assert is_clean is True
        assert violations == []

    def test_markdown_table_detected(self, tmp_path):
        """Markdown table should be detected."""
        skill_file = tmp_path / "table.md"
        skill_file.write_text("""# Severity Table

| Severity | Action |
|---|---|
| Reject | Request changes |
| Nitpick | Comment only |
""")
        is_clean, violations = check_no_tables(skill_file)
        assert is_clean is False
        assert len(violations) == 1

    def test_table_with_alignment(self, tmp_path):
        """Table with alignment markers should be detected."""
        skill_file = tmp_path / "aligned.md"
        skill_file.write_text("""| Column 1 | Column 2 |
|:---|---:|
| Left | Right |
""")
        is_clean, violations = check_no_tables(skill_file)
        assert is_clean is False
        assert len(violations) == 1

    def test_list_not_table(self, tmp_path):
        """List with pipes in text should not be detected as table."""
        skill_file = tmp_path / "list.md"
        skill_file.write_text("""# Points

- First point | with pipe
- Second point | another pipe
""")
        is_clean, violations = check_no_tables(skill_file)
        assert is_clean is True
        assert violations == []


class TestCheckInterviewQuotes:
    """Test interview citation detection."""

    def test_no_interview_quotes(self, tmp_path):
        """File without interview citations should return 0."""
        skill_file = tmp_path / "clean.md"
        skill_file.write_text("""# Review Mindset

This is a general review skill without specific citations.
""")
        count, patterns = check_interview_quotes(skill_file)
        assert count == 0
        assert patterns == []

    def test_interview_citation_detected(self, tmp_path):
        """Interview citation should be detected."""
        skill_file = tmp_path / "cited.md"
        skill_file.write_text("""# Quotes

As mentioned in (Interview: Linux Weekly News 2020)
""")
        count, patterns = check_interview_quotes(skill_file)
        assert count >= 1
        assert "(Interview: Linux Weekly News 2020)" in patterns

    def test_ted_citation_detected(self, tmp_path):
        """TED citation should be detected."""
        skill_file = tmp_path / "ted.md"
        skill_file.write_text("""# Talk

From his (TED 2016) presentation.
""")
        count, patterns = check_interview_quotes(skill_file)
        assert count >= 1
        assert "(TED 2016)" in patterns

    def test_multiple_citations(self, tmp_path):
        """Multiple citation types should all be detected."""
        skill_file = tmp_path / "multi.md"
        skill_file.write_text("""# Sources

(Interview: LWN 2020) and (TED 2016) and (Linux Journal 2021)
""")
        count, patterns = check_interview_quotes(skill_file)
        assert count >= 3


class TestScoreSkillQuality:
    """Test the quality scoring function."""

    def test_score_nonexistent_file(self, tmp_path):
        """Non-existent file should return zero scores."""
        result = score_skill_quality(tmp_path / "nonexistent.md")
        assert result["total"] == 0
        assert result["trigger_diversity"] == 0
        assert result["severity_distribution"] == 0
        assert result["language_agnosticism"] == 0
        assert result["section_coverage"] == 0

    def test_score_empty_file(self, tmp_path):
        """Empty file should score poorly."""
        skill_file = tmp_path / "empty.md"
        skill_file.write_text("")
        result = score_skill_quality(skill_file)
        # Empty file: language_agnosticism = 25 (no forbidden terms), section_coverage = 0
        assert result["total"] == 25  # Only language_agnosticism passes
        assert result["language_agnosticism"] == 25  # Empty file has no forbidden terms
        assert result["section_coverage"] == 0  # No sections present

    def test_score_complete_skill(self, tmp_path):
        """Complete skill file should score well."""
        skill_file = tmp_path / "complete.md"
        skill_file.write_text("""# Reviewer Mindset

Some content here.

## Review Triggers

- **Trigger:** Test trigger one
  - **Type:** general-guideline
  - **Severity:** request-changes

- **Trigger:** Test trigger two
  - **Type:** invariant-false
  - **Severity:** reject

- **Trigger:** Test trigger three
  - **Type:** general-guideline
  - **Severity:** nitpick

## Precedence and Priorities

Content about precedence.

## Decision Cards

Some decision cards.

## Key Definitions

Definitions here.

## Anti-Patterns

Anti-patterns listed.

## Voice and Tone

Tone guidelines.

## Severity Calibration

Calibration info with reject, request-changes, nitpick, approve.

## Severity Decision Tree

Decision tree content.

As Linus said: "I use kmalloc all the time" (Interview: test.md)
"Another quote here for good measure" (TED 2016)
"Third quote to pass threshold" (Linux Journal 2021)
"Fourth quote for safety" (Hacker News 2020)
"Fifth quote to be sure" (O'Reilly 2019)
"Sixth quote for coverage" (Forbes 2018)
"Seventh quote for completeness" (Wired 2017)
"Eighth quote for good measure" (Interview: another.md)
"Ninth quote for safety" (Interview: third.md)
"Tenth quote to pass" (Interview: fourth.md)
"Eleventh quote for good" (Interview: fifth.md)
"Twelfth quote for measure" (Interview: sixth.md)
"Thirteenth quote for good" (Interview: seventh.md)
"Fourteenth quote for measure" (Interview: eighth.md)
"Fifteenth quote for good" (Interview: ninth.md)
"Sixteenth quote for measure" (Interview: tenth.md)
"Seventeenth quote for good" (Interview: eleventh.md)
"Eighteenth quote for measure" (Interview: twelfth.md)
"Nineteenth quote for good" (Interview: thirteenth.md)
"Twentieth quote for measure" (Interview: fourteenth.md)
"Twenty-first quote for good" (Interview: fifteenth.md)
"Twenty-second quote for measure" (Interview: sixteenth.md)
"Twenty-third quote for good" (Interview: seventeenth.md)
"Twenty-fourth quote for measure" (Interview: eighteenth.md)
"Twenty-fifth quote for good" (Interview: nineteenth.md)
"Twenty-sixth quote for measure" (Interview: twentieth.md)
"Twenty-seventh quote for good" (Interview: twenty-first.md)
"Twenty-eighth quote for measure" (Interview: twenty-second.md)
"Twenty-ninth quote for good" (Interview: twenty-third.md)
"Thirtieth quote for measure" (Interview: twenty-fourth.md)
"Thirty-first quote for good" (Interview: twenty-fifth.md)
"Thirty-second quote for measure" (Interview: twenty-sixth.md)
"Thirty-third quote for good" (Interview: twenty-seventh.md)
"Thirty-fourth quote for measure" (Interview: twenty-eighth.md)
"Thirty-fifth quote for good" (Interview: twenty-ninth.md)
"Thirty-sixth quote for measure" (Interview: thirtieth.md)
"Thirty-seventh quote for good" (Interview: thirty-first.md)
"Thirty-eighth quote for measure" (Interview: thirty-second.md)
"Thirty-ninth quote for good" (Interview: thirty-third.md)
"Fortieth quote for measure" (Interview: thirty-fourth.md)
"Forty-first quote for good" (Interview: thirty-fifth.md)
"Forty-second quote for measure" (Interview: thirty-sixth.md)
"Forty-third quote for good" (Interview: thirty-seventh.md)
"Forty-fourth quote for measure" (Interview: thirty-eighth.md)
"Forty-fifth quote for good" (Interview: thirty-ninth.md)
"Forty-sixth quote for measure" (Interview: fortieth.md)
"Forty-seventh quote for good" (Interview: forty-first.md)
"Forty-eighth quote for measure" (Interview: forty-second.md)
"Forty-ninth quote for good" (Interview: forty-third.md)
"Fiftieth quote for measure" (Interview: forty-fourth.md)
Testing, correctness, complexity, performance, concurrency, documentation, style, process, api-stability, error-handling, memory-safety, abstraction, security.
""")
        result = score_skill_quality(skill_file)
        
        # Should have good scores
        assert result["total"] > 50  # At least moderate score
        assert result["section_coverage"] == 25  # All sections present
        assert result["language_agnosticism"] == 25  # No forbidden terms (they're in quotes)


class TestScoreTriggerDiversity:
    """Test trigger diversity scoring."""

    def test_no_triggers(self):
        """Text without triggers should score low."""
        score, details = _score_trigger_diversity("Just some text without triggers")
        assert score == 0
        assert details["total_triggers"] == 0

    def test_few_triggers(self):
        """Text with few triggers should score proportionally."""
        text = """
        - **Trigger:** First trigger
        - **Trigger:** Second trigger
        - **Trigger:** Third trigger
        """
        score, details = _score_trigger_diversity(text)
        assert details["explicit_triggers_found"] == 3
        assert score > 0
        assert score < 25

    def test_many_triggers(self):
        """Text with 15+ triggers should cap at 25."""
        triggers = "\n".join([f"- **Trigger:** Trigger {i}" for i in range(20)])
        score, details = _score_trigger_diversity(triggers)
        assert details["explicit_triggers_found"] == 20
        assert score == 25

    def test_theme_based_estimation(self):
        """Theme trigger patterns should be estimated."""
        text = """
        - **Theme**: Test Theme
        Triggers (3-6 each): 1. First trigger. 2. Second trigger.
        """
        score, details = _score_trigger_diversity(text)
        assert details["estimated_from_themes"] >= 3


class TestScoreSeverityDistribution:
    """Test severity distribution scoring."""

    def test_no_severity_mentions(self, tmp_path):
        """Text without severity mentions should score 0."""
        # Temporarily create calibration.json
        calibration_file = Path(__file__).parent.parent / "data" / "calibration.json"
        if not calibration_file.exists():
            pytest.skip("calibration.json not found")
        
        score, details = _score_severity_distribution("just some text")
        assert score == 0
        assert "error" in details

    def test_severity_mentions(self, tmp_path):
        """Text with severity mentions should score based on distribution."""
        calibration_file = Path(__file__).parent.parent / "data" / "calibration.json"
        if not calibration_file.exists():
            pytest.skip("calibration.json not found")
        
        # Text with balanced severity mentions
        text = "reject request-changes nitpick approve discussion"
        score, details = _score_severity_distribution(text)
        assert score >= 0
        assert score <= 25
        assert details["total_mentions"] == 5


class TestScoreLanguageAgnosticism:
    """Test language-agnosticism scoring."""

    def test_clean_file(self, tmp_path):
        """File without forbidden terms should score 25."""
        skill_file = tmp_path / "clean.md"
        skill_file.write_text("""# Review Mindset

This is a clean skill file.
""")
        score, details = _score_language_agnosticism(skill_file)
        assert score == 25
        assert details["passed"] is True

    def test_forbidden_terms(self, tmp_path):
        """File with forbidden terms should score 0."""
        skill_file = tmp_path / "bad.md"
        skill_file.write_text("""# Review Mindset

Use kmalloc for allocations.
""")
        score, details = _score_language_agnosticism(skill_file)
        assert score == 0
        assert details["passed"] is False
        assert details["violations"] > 0


class TestScoreSectionCoverage:
    """Test section coverage scoring."""

    def test_all_sections_present(self):
        """Text with all sections should score 25."""
        text = """
        Reviewer Mindset
        Review Triggers
        Precedence and Priorities
        Decision Cards
        Key Definitions
        Anti-Patterns
        Voice and Tone
        Severity Calibration
        Severity Decision Tree
        """
        score, details = _score_section_coverage(text)
        assert score == 25
        assert details["missing"] == 0

    def test_missing_sections(self):
        """Text with missing sections should be penalized."""
        text = """
        Reviewer Mindset
        Review Triggers
        """
        score, details = _score_section_coverage(text)
        assert score == 0  # 25 - (7 * 5) = 25 - 35 = -10, but max(0, ...) = 0
        assert details["missing"] == 7

    def test_partial_sections(self):
        """Text with some sections should score proportionally."""
        text = """
        Reviewer Mindset
        Review Triggers
        Precedence and Priorities
        Decision Cards
        Key Definitions
        """
        score, details = _score_section_coverage(text)
        assert score == 5  # 25 - (4 * 5) = 5
        assert details["present"] == 5
        assert details["missing"] == 4