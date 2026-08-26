"""Tests for build_comparison.py fuzzy matching fixes."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "report"))

from build_comparison import Finding, compare_skill_vs_baseline, _title_similarity


def test_title_similarity_sigpipe():
    """Test _title_similarity for SIGPIPE titles."""
    similarity = _title_similarity("SIGPIPE not handled", "No SIGPIPE handling")
    assert similarity >= 0.30, f"Expected >= 0.30, got {similarity:.2f}"


def test_title_similarity_nick():
    """Test _title_similarity for nickname titles."""
    similarity = _title_similarity(
        "Nickname not null-terminated in createClient",
        "Nick not null-terminated in createClient"
    )
    assert similarity >= 0.30, f"Expected >= 0.30, got {similarity:.2f}"


def test_compare_skill_vs_baseline_glm52_scenario():
    """
    Regression test for GLM5.2 scenario:
    - Skill criticals: 5 findings (nick, acceptClient, fd bounds, SIGPIPE, snprintf)
    - Baseline criticals: 4 findings (same first 4 bugs, slightly different titles/lines)
    - Expected: 4 overlap, 1 skill-only, 0 baseline-only
    """
    # Skill criticals with file="smallchat-server.c", specific lines
    skill_findings = [
        Finding("CRITICAL", "Nickname not null-terminated in createClient", "smallchat-server.c:188"),
        Finding("CRITICAL", "acceptClient return value unchecked", "smallchat-server.c:143"),
        Finding("CRITICAL", "fd bounds check missing", "smallchat-server.c:145"),
        Finding("CRITICAL", "SIGPIPE not handled", "smallchat-server.c:290"),
        Finding("CRITICAL", "snprintf return value not checked", "smallchat-server.c:208"),
    ]
    
    # Baseline criticals with slightly different titles and line numbers (±3)
    baseline_findings = [
        Finding("CRITICAL", "Nick not null-terminated in createClient", "smallchat-server.c:185"),
        Finding("CRITICAL", "acceptClient return not checked", "smallchat-server.c:146"),
        Finding("CRITICAL", "Missing fd bounds check", "smallchat-server.c:148"),
        Finding("CRITICAL", "No SIGPIPE handling", "smallchat-server.c:288"),
    ]
    
    result = compare_skill_vs_baseline(skill_findings, baseline_findings, "glm5.2")
    
    # Assert critical_overlap == 4 (NOT 0)
    assert result["critical_overlap"] == 4, f"Expected critical_overlap=4, got {result['critical_overlap']}"
    
    # Assert skill_only_critical == 1 (the snprintf finding)
    assert result["skill_only_critical"] == 1, f"Expected skill_only_critical=1, got {result['skill_only_critical']}"
    
    # Assert baseline_only_critical == 0 (NOT 4)
    assert result["baseline_only_critical"] == 0, f"Expected baseline_only_critical=0, got {result['baseline_only_critical']}"


def test_compare_skill_vs_baseline_exact_match():
    """Test exact line match still works."""
    skill_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100"),
    ]
    baseline_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100"),
    ]
    
    result = compare_skill_vs_baseline(skill_findings, baseline_findings, "test")
    
    assert result["critical_overlap"] == 1
    assert result["skill_only_critical"] == 0
    assert result["baseline_only_critical"] == 0


def test_compare_skill_vs_baseline_no_match():
    """Test when there's no overlap."""
    skill_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100"),
    ]
    baseline_findings = [
        Finding("CRITICAL", "Memory leak", "client.c:50"),
    ]
    
    result = compare_skill_vs_baseline(skill_findings, baseline_findings, "test")
    
    assert result["critical_overlap"] == 0
    assert result["skill_only_critical"] == 1
    assert result["baseline_only_critical"] == 1

# ---- Dedup regression tests ----

def test_dedup_collapses_draft_and_full_report_duplicates():
    """Within a single review, draft headings (short title, no line) and full
    report headings (longer title, with line) for the same bug must collapse."""
    from build_comparison import _dedup_findings

    findings = [
        Finding("CRITICAL", "No bounds check on file descriptor in createClient", "smallchat-server.c"),
        Finding("CRITICAL", "acceptClient return value not checked", "smallchat-server.c"),
        Finding("CRITICAL", "No bounds check on file descriptor in createClient — out-of-bounds array write", "smallchat-server.c:73"),
        Finding("CRITICAL", "acceptClient return value not checked — fd=-1 passed to createClient", "smallchat-server.c:120"),
        Finding("CRITICAL", "Nickname not null-terminated in createClient", "smallchat-server.c:64"),
        Finding("CRITICAL", "SIGPIPE not handled — write to closed socket kills the server", "smallchat-server.c:97"),
    ]

    deduped = _dedup_findings(findings)
    assert len(deduped) == 4, f"Expected 4 after dedup, got {len(deduped)}"
    # The richer findings (with line numbers) should be kept over the draft ones
    lines = sorted(f.line for f in deduped if f.line)
    assert lines == [64, 73, 97, 120], f"Expected lines [64, 73, 97, 120], got {lines}"


def test_dedup_preserves_different_bugs_in_same_file():
    """Different bugs in the same file must NOT be deduped even when line
    numbers are close (within ±10)."""
    from build_comparison import _dedup_findings

    findings = [
        Finding("CRITICAL", "No bounds check on file descriptor in createClient — out-of-bounds array write", "smallchat-server.c:73"),
        Finding("CRITICAL", "Nickname not null-terminated in createClient", "smallchat-server.c:64"),
        Finding("CRITICAL", "SIGPIPE not handled — write to closed socket kills the server", "smallchat-server.c:97"),
    ]

    deduped = _dedup_findings(findings)
    assert len(deduped) == 3, f"Expected 3 (no false dedup), got {len(deduped)}"
