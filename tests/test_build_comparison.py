"""Parser tests for build_comparison.py."""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "report"))

from build_comparison import parse_review, parse_review_file, Finding
from build_comparison import parse_review, parse_review_file, Finding, generate_scorecard


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


class TestGenerateScorecard:
    """Tests for the generate_scorecard function."""
    
    def test_skill_adds_value_verdict(self):
        """Models with skill-only criticals > 0 and baseline_only = 0 should get 'Skill adds value'."""
        data = [
            {
                "model": "gpt-oss-120b",
                "skill_total": 10,
                "skill_critical": 2,
                "skill_only_critical": 2,
                "baseline_only_critical": 0,
            }
        ]
        result = generate_scorecard(data)
        assert "Skill adds value" in result
        assert "gpt-oss-120b" in result
        assert "2" in result  # skill_only_critical count
    
    def test_no_change_verdict(self):
        """Models with skill-only = 0 and baseline-only = 0 should get 'No change'."""
        data = [
            {
                "model": "glm5.2",
                "skill_total": 17,
                "skill_critical": 1,
                "skill_only_critical": 0,
                "baseline_only_critical": 0,
            }
        ]
        result = generate_scorecard(data)
        assert "No change" in result
        assert "glm5.2" in result
    
    def test_skill_reduces_coverage_verdict(self):
        """Models with baseline_only > skill_only should get 'Skill reduces coverage'."""
        data = [
            {
                "model": "test-model",
                "skill_total": 5,
                "skill_critical": 1,
                "skill_only_critical": 1,
                "baseline_only_critical": 3,
            }
        ]
        result = generate_scorecard(data)
        assert "Skill reduces coverage" in result
    
    def test_baseline_pending_verdict(self):
        """Models with N/A baseline should get 'Baseline pending'."""
        data = [
            {
                "model": "mistral",
                "skill_total": 16,
                "skill_critical": 3,
                "skill_only_critical": "N/A",
                "baseline_only_critical": "N/A",
            }
        ]
        result = generate_scorecard(data)
        assert "Baseline pending" in result
    
    def test_summary_sentence_generation(self):
        """Summary should mention the model with most skill-only criticals."""
        data = [
            {
                "model": "gpt-oss-120b",
                "skill_total": 10,
                "skill_critical": 2,
                "skill_only_critical": 2,
                "baseline_only_critical": 0,
            },
            {
                "model": "glm5.2",
                "skill_total": 17,
                "skill_critical": 1,
                "skill_only_critical": 1,
                "baseline_only_critical": 1,
            },
        ]
        result = generate_scorecard(data)
        # gpt-oss-120b has the most skill-only criticals (2)
        assert "gpt-oss-120b" in result
        assert "gained 2 critical finding(s)" in result
    
    def test_summary_neutral_coverage(self):
        """Summary should indicate neutral coverage when no model has skill-only criticals."""
        data = [
            {
                "model": "model-a",
                "skill_total": 5,
                "skill_critical": 1,
                "skill_only_critical": 0,
                "baseline_only_critical": 0,
            }
        ]
        result = generate_scorecard(data)
        assert "neutral critical coverage" in result
    
    def test_table_structure(self):
        """Scorecard should have proper markdown table structure."""
        data = [
            {
                "model": "test-model",
                "skill_total": 10,
                "skill_critical": 2,
                "skill_only_critical": 1,
                "baseline_only_critical": 0,
            }
        ]
        result = generate_scorecard(data)
        # Check for table header
        assert "| Model | Total Findings | Critical Findings | Skill-Only Critical | Verdict |" in result
        # Check for separator row
        assert "|-------|---------------|-------------------|---------------------|---------|" in result
        # Check for data row
        assert "| test-model | 10 | 2 | 1 |" in result
    
    def test_multiple_models(self):
        """Scorecard should handle multiple models correctly."""
        data = [
            {
                "model": "model-a",
                "skill_total": 10,
                "skill_critical": 2,
                "skill_only_critical": 2,
                "baseline_only_critical": 0,
            },
            {
                "model": "model-b",
                "skill_total": 15,
                "skill_critical": 3,
                "skill_only_critical": 0,
                "baseline_only_critical": 0,
            },
            {
                "model": "model-c",
                "skill_total": 8,
                "skill_critical": 1,
                "skill_only_critical": 1,
                "baseline_only_critical": 3,
            },
        ]
        result = generate_scorecard(data)
        assert "model-a" in result
        assert "model-b" in result
        assert "model-c" in result
        assert "Skill adds value" in result  # model-a
        assert "No change" in result  # model-b
        assert "Skill reduces coverage" in result  # model-c


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
