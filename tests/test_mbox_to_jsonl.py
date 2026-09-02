"""Tests for mbox_to_jsonl.py body cleaning logic.

Verifies the body cleaning function that strips quoted lines, signatures,
and mailing-list footers.
"""

from scripts.mbox_to_jsonl import clean_body


class TestCleanBody:
    """Test body cleaning function."""

    def test_strips_quoted_lines(self):
        """Lines starting with > should be stripped."""
        raw = """This is my response.

> This is quoted text
> That should be removed

More of my response."""
        result = clean_body(raw)
        assert "> This is quoted text" not in result
        assert "> That should be removed" not in result
        assert "This is my response." in result
        assert "More of my response." in result

    def test_strips_signature(self):
        """Signature separator -- should cut off everything after."""
        raw = """This is the main body.

--
Linus Torvalds
torvalds@linux.org"""
        result = clean_body(raw)
        assert "--" not in result
        assert "Linus Torvalds" not in result
        assert "torvalds@linux.org" not in result
        assert "This is the main body." in result

    def test_strips_footer_mark(self):
        """Mailing-list footer should be stripped."""
        raw = """This is my comment.

_______________________________________________
Linux kernel mailing list"""
        result = clean_body(raw)
        assert "_______________________________________________" not in result
        assert "Linux kernel mailing list" not in result
        assert "This is my comment." in result

    def test_collapse_whitespace(self):
        """3+ blank lines should collapse to 2."""
        raw = """Line one.




Line two."""
        result = clean_body(raw)
        # Should not have 3+ consecutive newlines
        assert "\n\n\n" not in result
        assert "Line one." in result
        assert "Line two." in result

    def test_empty_input(self):
        """Empty string should return empty string."""
        result = clean_body("")
        assert result == ""

    def test_whitespace_only(self):
        """Whitespace-only input should return empty string."""
        result = clean_body("   \n\n   ")
        assert result == ""

    def test_strips_trailing_whitespace(self):
        """Trailing whitespace should be stripped."""
        raw = """Content here.

"""
        result = clean_body(raw)
        assert result == "Content here."

    def test_strips_leading_whitespace(self):
        """Leading whitespace should be stripped."""
        raw = """

Content here."""
        result = clean_body(raw)
        assert result == "Content here."

    def test_combined_cleanup(self):
        """All cleanup operations should work together."""
        raw = """My response text.

> Quoted text that goes
> on for multiple lines

More response.

--
Signature line

_______________________________________________
Footer mark"""
        result = clean_body(raw)

        # Should have content
        assert "My response text." in result
        assert "More response." in result

        # Should not have removed content
        assert ">" not in result
        assert "--" not in result
        assert "Signature line" not in result
        assert "_______________________________________________" not in result
        assert "Footer mark" not in result

        # Should be stripped
        assert result == result.strip()

    def test_signature_in_middle_preserved(self):
        """Text containing '--' in middle of line should be preserved."""
        raw = """This has -- dashes -- in it.

More text."""
        result = clean_body(raw)
        # The -- in middle of line is not a signature separator
        assert "--" in result

    def test_signature_separator_only_strips(self):
        """Only standalone -- should trigger signature cut."""
        raw = """Text before.
--
Text after signature."""
        result = clean_body(raw)
        assert "Text before." in result
        assert "Text after signature." not in result

    def test_quoted_text_preserved_in_body(self):
        """Text with > character not at start should be preserved."""
        raw = """The pattern > 5 is important.

> This quoted line should go."""
        result = clean_body(raw)
        assert "> 5" in result
        assert "> This quoted line" not in result

    def test_multiple_footers(self):
        """Multiple footer marks should all be stripped."""
        raw = """Content.

_______________________________________________
Footer 1

_______________________________________________
Footer 2"""
        result = clean_body(raw)
        assert "_______________________________________________" not in result
        assert "Footer 1" not in result
        assert "Footer 2" not in result
        assert "Content." in result
