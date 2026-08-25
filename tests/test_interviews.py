"""Tests for interviews.py HTML extraction and URL handling.

Verifies the HTML text extraction logic and URL validation functions.
"""

import pytest

from src.torvalds_skill.interviews import HTMLTextExtractor, is_youtube_url, extract_text_from_html


class TestHTMLTextExtractor:
    """Test HTML text extraction from HTML content."""

    def test_get_text_ignores_structure_tags(self):
        """Structural tags should not appear in output."""
        html = "<p>Hello</p><div>World</div>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Hello" in text
        assert "World" in text
        assert "<p>" not in text
        assert "<div>" not in text

    def test_get_text_ignores_script_tags(self):
        """Script content should be ignored."""
        html = "<p>Real</p><script>var x = 1;</script><p>Text</p>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Real" in text
        assert "Text" in text
        assert "var x = 1" not in text

    def test_get_text_ignores_style_tags(self):
        """Style content should be ignored."""
        html = "<p>Content</p><style>.class { color: red; }</style><p>More</p>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Content" in text
        assert "More" in text
        assert "color: red" not in text

    def test_get_text_ignores_nav_footer_header(self):
        """Navigation, footer, and header content should be ignored."""
        html = """
        <header>Site Title</header>
        <nav>Menu</nav>
        <p>Main content</p>
        <footer>Copyright</footer>
        """
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Main content" in text
        assert "Site Title" not in text
        assert "Menu" not in text
        assert "Copyright" not in text

    def test_get_text_handles_nested_skip_tags(self):
        """Nested ignored tags should be handled correctly."""
        html = "<div><script>nested<script>content</script>script</script></div><p>Real</p>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Real" in text
        assert "nested" not in text
        assert "content" not in text

    def test_get_text_collapses_whitespace(self):
        """Multiple newlines should be collapsed."""
        html = "<p>Line1</p><p>Line2</p><p>Line3</p>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        # Should not have 3+ consecutive newlines
        assert "\n\n\n" not in text

    def test_get_text_collapses_inline_whitespace(self):
        """Multiple spaces/tabs should be collapsed."""
        html = "<p>Word1    Word2\t\tWord3</p>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        # Should have single spaces
        assert "Word1 Word2 Word3" in text

    def test_get_text_strips_empty_elements(self):
        """Empty elements should not add extra newlines."""
        html = "<p></p><p>Content</p><p></p>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert text == "Content"

    def test_get_text_with_blockquote(self):
        """Blockquote content should be extracted."""
        html = "<blockquote>Quoted text</blockquote>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Quoted text" in text

    def test_get_text_with_pre(self):
        """Preformatted text should be extracted."""
        html = "<pre>Code block</pre>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Code block" in text

    def test_get_text_with_headings(self):
        """Heading content should be extracted."""
        html = "<h1>Title</h1><h2>Subtitle</h2><p>Body</p>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Title" in text
        assert "Subtitle" in text
        assert "Body" in text

    def test_get_text_with_list(self):
        """List content should be extracted."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Item 1" in text
        assert "Item 2" in text

    def test_get_text_with_form_ignored(self):
        """Form content should be ignored."""
        html = "<form><input name='test'></form><p>Real text</p>"
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        assert "Real text" in text
        assert "test" not in text


class TestIsYoutubeUrl:
    """Test YouTube URL detection."""

    def test_youtube_watch_url(self):
        """youtube.com/watch URLs should be detected."""
        assert is_youtube_url("https://www.youtube.com/watch?v=abc123") is True
        assert is_youtube_url("http://youtube.com/watch?v=xyz") is True

    def test_youtube_short_url(self):
        """youtu.be/ URLs should be detected."""
        assert is_youtube_url("https://youtu.be/abc123") is True
        assert is_youtube_url("http://youtu.be/xyz") is True

    def test_non_youtube_url(self):
        """Non-YouTube URLs should not be detected."""
        assert is_youtube_url("https://vimeo.com/123") is False
        assert is_youtube_url("https://example.com/video") is False
        assert is_youtube_url("https://youtube.example.com") is False

    def test_empty_url(self):
        """Empty URL should not be detected."""
        assert is_youtube_url("") is False

    def test_partial_match_not_enough(self):
        """Partial youtube reference should not match."""
        assert is_youtube_url("I watched this on youtube") is False


class TestExtractTextFromHtml:
    """Test HTML text extraction function."""

    def test_simple_html(self):
        """Simple HTML should extract text correctly."""
        html = "<p>Hello World</p>"
        text = extract_text_from_html(html)
        assert text == "Hello World"

    def test_complex_html(self):
        """Complex HTML with multiple elements should extract all text."""
        html = """
        <html>
        <head><title>Title</title></head>
        <body>
            <h1>Main Title</h1>
            <p>First paragraph.</p>
            <p>Second paragraph.</p>
        </body>
        </html>
        """
        text = extract_text_from_html(html)
        assert "Main Title" in text
        assert "First paragraph." in text
        assert "Second paragraph." in text
        assert "<html>" not in text
        assert "<head>" not in text

    def test_html_with_scripts(self):
        """HTML with scripts should not include script content."""
        html = """
        <p>Real content</p>
        <script>
            var data = {key: "value"};
            console.log("test");
        </script>
        <p>More real content</p>
        """
        text = extract_text_from_html(html)
        assert "Real content" in text
        assert "More real content" in text
        assert "var data" not in text
        assert "console.log" not in text

    def test_empty_html(self):
        """Empty HTML should return empty string."""
        text = extract_text_from_html("")
        assert text == ""

    def test_html_only_scripts(self):
        """HTML with only scripts should return empty string."""
        html = "<script>var x = 1;</script>"
        text = extract_text_from_html(html)
        assert text == ""

    def test_nested_elements(self):
        """Nested HTML elements should extract all text."""
        html = "<div><p><span>Nested text</span></p></div>"
        text = extract_text_from_html(html)
        assert "Nested text" in text

    def test_mixed_content(self):
        """Mixed visible and hidden content should extract only visible."""
        html = """
        <header>Header</header>
        <main>
            <article>
                <h1>Article Title</h1>
                <p>Article content here.</p>
            </article>
        </main>
        <footer>Footer</footer>
        """
        text = extract_text_from_html(html)
        assert "Article Title" in text
        assert "Article content here." in text
        assert "Header" not in text
        assert "Footer" not in text