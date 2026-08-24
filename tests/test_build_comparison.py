"""Parser tests for build_comparison.py."""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "report"))

from build_comparison import parse_review, parse_review_file, Finding


class TestParseReview:
    """Tests for the unified parse_review function."""

    def test_empty_input_returns_empty_list(self):
        """Empty input should return empty list."""
        result = parse_review("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        """Whitespace-only input should return empty list."""
        result = parse_review("   \n\n   ")
        assert result == []

    def test_critical_heading_with_no_fields(self):
        """### [CRITICAL] heading with no fields should return Finding with location=None."""
        content = """### [CRITICAL] Buffer overflow
Some description here.
"""
        result = parse_review(content)
        assert len(result) == 1
        assert result[0].severity == "CRITICAL"
        assert result[0].title == "Buffer overflow"
        assert result[0].location is None
        assert result[0].file is None
        assert result[0].line is None

    def test_four_hash_heading_not_missed(self):
        """#### [CRITICAL] heading (4 hashes) must not be missed."""
        content = """#### [HIGH] Memory leak
- **Location:** server.c:100
"""
        result = parse_review(content)
        assert len(result) == 1
        assert result[0].severity == "HIGH"
        assert result[0].title == "Memory leak"

    def test_location_colon_inside_bold(self):
        """**Location:** format (colon inside bold) should be parsed."""
        content = """### [MEDIUM] Race condition
- **Location:** client.c:45
"""
        result = parse_review(content)
        assert len(result) == 1
        assert result[0].location == "client.c:45"
        # normalize_filename converts client.c -> smallchat-client.c
        assert result[0].file == "smallchat-client.c"
        assert result[0].line == 45

    def test_location_colon_outside_bold(self):
        """**Location**: format (colon outside bold) should be parsed."""
        content = """### [LOW] Style issue
- **Location**: server.c:200
"""
        result = parse_review(content)
        assert len(result) == 1
        assert result[0].location == "server.c:200"
        # normalize_filename converts server.c -> smallchat-server.c
        assert result[0].file == "smallchat-server.c"
        assert result[0].line == 200

    def test_file_line_range_extracts_first_line(self):
        """file:line-range (e.g., server.c:188-189) should extract line=188."""
        content = """### [CRITICAL] Use after free
- **Location:** server.c:188-189
"""
        result = parse_review(content)
        assert len(result) == 1
        # normalize_filename converts server.c -> smallchat-server.c
        assert result[0].file == "smallchat-server.c"
        assert result[0].line == 188

    def test_lines_format_no_file(self):
        """lines 85, 127-128 (no file) should return line=85, file=None."""
        content = """### [HIGH] Null pointer
- **Location:** lines 85, 127-128
"""
        result = parse_review(content)
        assert len(result) == 1
        assert result[0].line == 85
        assert result[0].file is None

    def test_malformed_severity_ignored(self):
        """Malformed severity [BOGUS] should be ignored."""
        content = """### [BOGUS] Invalid severity
- **Location:** server.c:100

### [CRITICAL] Valid severity
- **Location:** server.c:200
"""
        result = parse_review(content)
        assert len(result) == 1
        assert result[0].severity == "CRITICAL"
        assert result[0].line == 200

    def test_multiple_findings_parsed(self):
        """Multiple findings should all be parsed."""
        content = """### [CRITICAL] First issue
- **Location:** server.c:100

### [HIGH] Second issue
- **Location:** client.c:200

### [MEDIUM] Third issue
- **Location:** chatlib.c:300
"""
        result = parse_review(content)
        assert len(result) == 3
        assert result[0].severity == "CRITICAL"
        assert result[1].severity == "HIGH"
        assert result[2].severity == "MEDIUM"

    def test_trigger_field_parsed(self):
        """Trigger field should be parsed."""
        content = """### [CRITICAL] Buffer overflow
- **Location:** server.c:100
- **Trigger:** buffer-overflow-check
"""
        result = parse_review(content)
        assert len(result) == 1
        assert result[0].trigger == "buffer-overflow-check"

    def test_type_field_parsed(self):
        """Type field should be parsed."""
        content = """### [HIGH] Memory leak
- **Location:** server.c:100
- **Type:** memory-leak
"""
        result = parse_review(content)
        assert len(result) == 1
        assert result[0].finding_type == "memory-leak"

    def test_track_section_file_assigns_file(self):
        """When track_section_file=True, ### filename.c should assign file to findings."""
        content = """### server.c

### [CRITICAL] Issue in server
- **Location:** 100
"""
        result = parse_review(content, track_section_file=True)
        assert len(result) == 1
        # normalize_filename converts server.c -> smallchat-server.c
        assert result[0].file == "smallchat-server.c"
        assert result[0].line == 100


class TestParseReviewFile:
    """Tests for parse_review_file function."""

    def test_missing_file_returns_empty_list(self):
        """Missing file should return empty list."""
        result = parse_review_file(Path("/nonexistent/file.md"))
        assert result == []

    def test_nonexistent_path_no_crash(self):
        """Nonexistent path should not crash."""
        result = parse_review_file(Path("/tmp/does_not_exist_12345.md"))
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])