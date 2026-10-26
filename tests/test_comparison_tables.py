#!/usr/bin/env python3
"""Test comparison table integrity and safe_truncate function."""

# Import safe_truncate from comparison_render
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "report"))
from comparison_render import safe_truncate


class TestMarkdownTables:
    """Tests for comparison.md table integrity."""

    def test_comparison_md_tables_have_matching_column_counts(self):
        """Test that all markdown tables have matching header and separator column counts."""
        comparison_path = Path(__file__).parent.parent / "report" / "comparison.md"
        if not comparison_path.exists():
            pytest.skip("comparison.md not found")

        content = comparison_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i]
            # Check if this is a table header (contains |)
            if "|" in line and not line.strip().startswith("#"):
                # Count columns in header
                header_cols = line.count("|") - 1  # Subtract 1 for the leading/trailing |

                # Next line should be separator
                if i + 1 < len(lines):
                    sep_line = lines[i + 1]
                    if "|" in sep_line and all(c in "|-:" for c in sep_line.replace("|", "")):
                        sep_cols = sep_line.count("|") - 1

                        assert header_cols == sep_cols, (
                            f"Table at line {i + 1} has mismatched columns: "
                            f"header={header_cols}, separator={sep_cols}"
                        )
                        i += 2  # Skip both header and separator
                        continue
            i += 1

    def test_comparison_md_no_open_backticks_in_tables(self):
        """Test that no table row has an odd number of backticks."""
        comparison_path = Path(__file__).parent.parent / "report" / "comparison.md"
        if not comparison_path.exists():
            pytest.skip("comparison.md not found")

        content = comparison_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        in_table = False
        for i, line in enumerate(lines):
            # Detect table start
            if "|" in line and not line.strip().startswith("#"):
                in_table = True

            # Check backtick count if in a table row
            if in_table and "|" in line:
                backtick_count = line.count("`")
                assert backtick_count % 2 == 0, (
                    f"Line {i + 1} has odd backtick count ({backtick_count}): {line[:80]}"
                )

            # Detect table end (empty line or non-table line)
            if in_table and line.strip() == "":
                in_table = False


class TestSafeTruncate:
    """Tests for the safe_truncate function."""

    def test_safe_truncate_closes_backticks(self):
        """Test that truncated text closes open backticks."""
        # Text with odd backticks should be closed
        result = safe_truncate("This is `code that is very long and needs truncation", 20)
        assert result.count("`") % 2 == 0, f"Backticks not closed: {result}"

        # Text with even backticks should remain even
        result = safe_truncate("This is `code` that is very long", 20)
        assert result.count("`") % 2 == 0, f"Backticks became odd: {result}"

    def test_safe_truncate_escapes_pipes(self):
        """Test that pipes are escaped in truncated text."""
        result = safe_truncate("This has | pipe characters", 15)
        assert "|" not in result or "\\|" in result, f"Pipes not escaped: {result}"

    def test_safe_truncate_only_appends_ellipsis_when_truncated(self):
        """Test that '...' is only appended when text is actually truncated."""
        # Short text should not get ellipsis
        short_text = "Short text"
        result = safe_truncate(short_text, 50)
        assert result == short_text, f"Short text modified: {result}"
        assert not result.endswith("..."), f"Ellipsis added to short text: {result}"

        # Long text should get ellipsis
        long_text = "This is a very long text that definitely needs to be truncated"
        result = safe_truncate(long_text, 20)
        assert result.endswith("..."), f"Ellipsis not added to truncated text: {result}"
        assert len(result) <= 23, f"Truncated text too long: {result}"  # 20 + "..."

    def test_safe_truncate_no_ellipsis_for_short_text(self):
        """Test that text shorter than limit does not get '...' appended."""
        short_text = "Short"
        result = safe_truncate(short_text, 100)
        assert result == "Short", f"Short text modified: {result}"
        assert not result.endswith("..."), f"Ellipsis added to short text: {result}"

    def test_safe_truncate_word_boundary(self):
        """Test that truncation happens at word boundaries when possible."""
        text = "This is a sentence with multiple words"
        result = safe_truncate(text, 15)
        # Should cut at a space, not in the middle of a word
        assert not result[:-3].endswith(" "), f"Should not end with space before ellipsis: {result}"


class TestSectionOrder:
    """Tests for comparison.md section ordering."""

    def test_no_headings_between_banners_and_about_report(self):
        """Test that no ## headings appear between warning banners and About this report."""
        comparison_path = Path(__file__).parent.parent / "report" / "comparison.md"
        if not comparison_path.exists():
            pytest.skip("comparison.md not found")

        content = comparison_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Find the first ## heading (should be About this report)
        first_section_line = None
        for i, line in enumerate(lines):
            if line.strip().startswith("## "):
                first_section_line = i
                break

        assert first_section_line is not None, "No ## headings found in comparison.md"
        assert "About this report" in lines[first_section_line], (
            f"First ## heading should be 'About this report', got: {lines[first_section_line]}"
        )

    def test_skill_generation_under_evidence(self):
        """Test that sections appear in correct order in cross_matrix.md."""
        cross_path = Path(__file__).parent.parent / "report" / "cross_matrix.md"
        if not cross_path.exists():
            pytest.skip("cross_matrix.md not found")

        content = cross_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        metrics_glossary_line = None
        verdict_line = None

        for i, line in enumerate(lines):
            if line.strip() == "## Metrics Glossary":
                metrics_glossary_line = i
            if line.strip() == "## Verdict":
                verdict_line = i

        assert metrics_glossary_line is not None, "## Metrics Glossary heading not found"
        assert verdict_line is not None, "## Verdict heading not found"
        assert verdict_line > metrics_glossary_line, (
            f"Verdict (line {verdict_line + 1}) should appear after "
            f"Metrics Glossary (line {metrics_glossary_line + 1})"
        )
