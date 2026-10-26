"""Tests for finding parsing in scripts/run_eval.py.

The parser is the only bridge between a reviewer's prose and the ground-truth matcher.
Every regression covered here silently corrupted the cross-matrix numbers before it was
fixed: lost severities, phantom preamble findings, and collapses to a single finding.
"""

import sys
from pathlib import Path

SRC = Path(__file__).parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts import run_eval
from scripts.run_eval import _parse_location, parse_findings_from_review

DIFF_RECORD = {"diff": "", "file": "smallchat-server.c"}


BRACKETED = """## Review

### [HIGH] Buffer overflow in snprintf
- **Type:** memory-safety
- **Trigger:** unmatched
- **Location:** smallchat-server.c:120
- **Issue:** writes past nick[32]
- **Fix:** bound the write

### [CRITICAL] fd used as array index
- **Type:** memory-safety
- **Trigger:** unmatched
- **Location:** smallchat-server.c:88
- **Issue:** clients[fd] out of bounds
- **Fix:** check fd < MAX_CLIENTS
"""

UNBRACKETED = """## Review

### HIGH Buffer overflow
- **Type:** memory-safety
- **Location:** smallchat-server.c:120
- **Issue:** writes past nick[32]
- **Fix:** bound it

### CRITICAL fd index
- **Type:** memory-safety
- **Location:** smallchat-server.c:88
- **Issue:** oob
- **Fix:** check
"""

NO_HEADINGS = """Here are the findings.

- **Type:** memory-safety
- **Location:** smallchat-server.c:120
- **Issue:** writes past nick[32]
- **Fix:** bound it

- **Type:** resource-leak
- **Location:** chatlib.c:14
- **Issue:** socket never closed
- **Fix:** close it
"""

MULTIPLE_UNDER_ONE_HEADING = """### [HIGH] Two problems in the accept loop
- **Type:** memory-safety
- **Location:** smallchat-server.c:88
- **Issue:** clients[fd] out of bounds
- **Fix:** check fd

- **Type:** resource-leak
- **Location:** smallchat-server.c:92
- **Issue:** accepted socket leaked on error
- **Fix:** close on failure
"""


class TestParseFindingsFromReview:
    def test_bracketed_headings_keep_their_severity(self):
        findings = parse_findings_from_review(BRACKETED, DIFF_RECORD)
        assert [f["severity"] for f in findings] == ["HIGH", "CRITICAL"]

    def test_unbracketed_headings_do_not_collapse_the_review(self):
        findings = parse_findings_from_review(UNBRACKETED, DIFF_RECORD)
        assert len(findings) == 2
        assert [f["severity"] for f in findings] == ["HIGH", "CRITICAL"]
        assert findings[1]["issue"] == "oob"

    def test_preamble_is_not_a_finding(self):
        findings = parse_findings_from_review(BRACKETED, DIFF_RECORD)
        assert len(findings) == 2
        assert all(f["issue"] != "no issue described" for f in findings)

    def test_multiple_findings_under_one_heading_are_all_kept(self):
        findings = parse_findings_from_review(MULTIPLE_UNDER_ONE_HEADING, DIFF_RECORD)
        assert len(findings) == 2
        assert [f["issue"] for f in findings] == [
            "clients[fd] out of bounds",
            "accepted socket leaked on error",
        ]

    def test_review_without_headings_still_parses(self):
        findings = parse_findings_from_review(NO_HEADINGS, DIFF_RECORD)
        assert len(findings) == 2
        assert findings[0]["line"] == 120
        assert findings[1]["file"] == "chatlib.c"

    def test_missing_fields_fall_back_to_explicit_defaults(self):
        review = """### [LOW] Bare finding
- **Location:** smallchat-server.c:10
"""
        findings = parse_findings_from_review(review, DIFF_RECORD)
        assert len(findings) == 1
        assert findings[0]["type"] == "unknown"
        assert findings[0]["trigger"] == "unmatched"
        assert findings[0]["issue"] == "no issue described"
        assert findings[0]["fix"] == "no fix proposed"

    def test_summary_only_review_returns_no_findings(self):
        review = "## Summary\n\nNo findings.\n\nThe code is clean.\n"
        assert parse_findings_from_review(review, DIFF_RECORD) == []

    def test_under_parsing_is_reported(self, capsys):
        # A duplicate "Issue" field inside one block means one finding was lost.
        review = """### [HIGH] Two issues, one boundary
- **Type:** memory-safety
- **Location:** smallchat-server.c:120
- **Issue:** first
- **Fix:** one

- **Issue:** second without a Type field
- **Fix:** two
"""
        findings = parse_findings_from_review(review, DIFF_RECORD)
        assert len(findings) == 1
        captured = capsys.readouterr()
        assert "parsed 1 of 2 issue field(s)" in captured.err


class TestParseLocation:
    def test_file_colon_line(self):
        assert _parse_location("smallchat-server.c:120", "fallback.c") == (
            "smallchat-server.c",
            120,
        )

    def test_line_range_uses_first_line(self):
        assert _parse_location("smallchat-server.c:120-130", "fallback.c") == (
            "smallchat-server.c",
            120,
        )

    def test_file_comma_line(self):
        assert _parse_location("server.c, line 42", "fallback.c") == ("server.c", 42)

    def test_line_keyword_without_file(self):
        assert _parse_location("line 77", "chatlib.h") == ("chatlib.h", 77)

    def test_bare_number(self):
        assert _parse_location("88", "chatlib.h") == ("chatlib.h", 88)

    def test_file_only_has_no_line(self):
        assert _parse_location("smallchat-server.c", "fallback.c") == ("smallchat-server.c", None)

    def test_empty_location_keeps_default_file(self):
        assert _parse_location("", "fallback.c") == ("fallback.c", None)


class TestNumberedSources:
    def test_sources_are_numbered_from_one(self, tmp_path, monkeypatch):
        (tmp_path / "a.c").write_text("int main(void) {\n    return 0;\n}\n")
        monkeypatch.setattr(run_eval, "SMALLCHAT_TARGET", tmp_path)
        monkeypatch.setattr(run_eval, "SMALLCHAT_FILES", ["a.c"])

        block = run_eval._read_smallchat_sources()

        assert "== SOURCE: a.c ==" in block
        assert "   1| int main(void) {" in block
        assert "   2|     return 0;" in block
        assert "   3| }" in block

    def test_missing_source_is_reported_not_numbered(self, tmp_path, monkeypatch):
        monkeypatch.setattr(run_eval, "SMALLCHAT_TARGET", tmp_path)
        monkeypatch.setattr(run_eval, "SMALLCHAT_FILES", ["gone.c"])

        block = run_eval._read_smallchat_sources()

        assert "(file not found: gone.c)" in block
