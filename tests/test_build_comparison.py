"""Tests for build_comparison.py fuzzy matching fixes."""

import json
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "report"))

from build_comparison import (
    Finding,
    _title_similarity,
    classify_finding_core_vs_trivia,
    compare_skill_vs_baseline,
    compute_benchmark_metrics,
    load_benchmark,
    match_finding_to_benchmark,
)


def test_title_similarity_sigpipe():
    """Test _title_similarity for SIGPIPE titles."""
    similarity = _title_similarity("SIGPIPE not handled", "No SIGPIPE handling")
    assert similarity >= 0.30, f"Expected >= 0.30, got {similarity:.2f}"


def test_title_similarity_nick():
    """Test _title_similarity for nickname titles."""
    similarity = _title_similarity(
        "Nickname not null-terminated in createClient", "Nick not null-terminated in createClient"
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
        Finding(
            "CRITICAL", "Nickname not null-terminated in createClient", "smallchat-server.c:188"
        ),
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
    assert result["critical_overlap"] == 4, (
        f"Expected critical_overlap=4, got {result['critical_overlap']}"
    )

    # Assert skill_only_critical == 1 (the snprintf finding)
    assert result["skill_only_critical"] == 1, (
        f"Expected skill_only_critical=1, got {result['skill_only_critical']}"
    )

    # Assert baseline_only_critical == 0 (NOT 4)
    assert result["baseline_only_critical"] == 0, (
        f"Expected baseline_only_critical=0, got {result['baseline_only_critical']}"
    )


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
        Finding(
            "CRITICAL", "No bounds check on file descriptor in createClient", "smallchat-server.c"
        ),
        Finding("CRITICAL", "acceptClient return value not checked", "smallchat-server.c"),
        Finding(
            "CRITICAL",
            "No bounds check on file descriptor in createClient — out-of-bounds array write",
            "smallchat-server.c:73",
        ),
        Finding(
            "CRITICAL",
            "acceptClient return value not checked — fd=-1 passed to createClient",
            "smallchat-server.c:120",
        ),
        Finding(
            "CRITICAL", "Nickname not null-terminated in createClient", "smallchat-server.c:64"
        ),
        Finding(
            "CRITICAL",
            "SIGPIPE not handled — write to closed socket kills the server",
            "smallchat-server.c:97",
        ),
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
        Finding(
            "CRITICAL",
            "No bounds check on file descriptor in createClient — out-of-bounds array write",
            "smallchat-server.c:73",
        ),
        Finding(
            "CRITICAL", "Nickname not null-terminated in createClient", "smallchat-server.c:64"
        ),
        Finding(
            "CRITICAL",
            "SIGPIPE not handled — write to closed socket kills the server",
            "smallchat-server.c:97",
        ),
    ]

    deduped = _dedup_findings(findings)
    assert len(deduped) == 3, f"Expected 3 (no false dedup), got {len(deduped)}"


# ---- Benchmark matching tests ----


def test_load_benchmark_missing_file():
    """Test graceful handling of missing benchmark file."""
    result = load_benchmark(Path("/nonexistent/path.jsonl"))
    assert result is None


def test_match_finding_to_benchmark_exact_match():
    """Test exact file+line match to benchmark record."""
    benchmark_records = [
        {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
        {"id": "SC-002", "file": "smallchat-server.c", "line": 30, "severity": "reject"},
    ]

    finding = Finding("CRITICAL", "Test finding", "smallchat-server.c:45")
    matched = match_finding_to_benchmark(finding, benchmark_records)

    assert matched is not None
    assert matched["id"] == "SC-001"


def test_match_finding_to_benchmark_line_tolerance():
    """Test matching within ±10 line tolerance."""
    benchmark_records = [
        {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
    ]

    # Finding at line 52 (within ±10 of 45)
    finding = Finding("CRITICAL", "Test finding", "smallchat-server.c:52")
    matched = match_finding_to_benchmark(finding, benchmark_records)

    assert matched is not None
    assert matched["id"] == "SC-001"

    # Finding at line 60 (outside ±10 of 45)
    finding_outside = Finding("CRITICAL", "Test finding", "smallchat-server.c:60")
    matched_outside = match_finding_to_benchmark(finding_outside, benchmark_records)

    assert matched_outside is None


def test_match_finding_to_benchmark_no_file():
    """Test that findings without file don't match."""
    benchmark_records = [
        {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
    ]

    finding = Finding("CRITICAL", "Test finding", "45")  # No file specified
    matched = match_finding_to_benchmark(finding, benchmark_records)

    assert matched is None


def test_compute_benchmark_metrics_all_hits():
    """Test metrics when all benchmark records are found."""
    benchmark_records = [
        {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
        {"id": "SC-002", "file": "smallchat-server.c", "line": 30, "severity": "reject"},
    ]

    findings = [
        Finding("CRITICAL", "Test 1", "smallchat-server.c:45"),
        Finding("CRITICAL", "Test 2", "smallchat-server.c:30"),
    ]

    metrics = compute_benchmark_metrics(findings, benchmark_records)

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert len(metrics["hits"]) == 2
    assert len(metrics["misses"]) == 0


def test_compute_benchmark_metrics_no_hits():
    """Test metrics when no benchmark records are found."""
    benchmark_records = [
        {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
    ]

    findings = [
        Finding("CRITICAL", "Test", "client.c:100"),  # Different file
    ]

    metrics = compute_benchmark_metrics(findings, benchmark_records)

    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0
    assert len(metrics["hits"]) == 0
    assert len(metrics["misses"]) == 1
    assert metrics["misses"][0] == "SC-001"


def test_compute_benchmark_metrics_partial_hits():
    """Test metrics with partial benchmark coverage."""
    benchmark_records = [
        {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
        {"id": "SC-002", "file": "smallchat-server.c", "line": 30, "severity": "reject"},
        {"id": "SC-003", "file": "smallchat-server.c", "line": 71, "severity": "request-changes"},
    ]

    findings = [
        Finding("CRITICAL", "Test 1", "smallchat-server.c:45"),  # Hits SC-001
        Finding("HIGH", "Test 2", "other.c:100"),  # No match
    ]

    metrics = compute_benchmark_metrics(findings, benchmark_records)

    # Precision: 1 hit / 2 findings = 0.5
    assert metrics["precision"] == 0.5
    # Recall: 1 hit / 3 benchmark = 0.333...
    assert abs(metrics["recall"] - 1 / 3) < 0.01
    # F1: 2 * 0.5 * 0.333 / (0.5 + 0.333) ≈ 0.4
    assert abs(metrics["f1"] - 0.4) < 0.01
    assert len(metrics["hits"]) == 1
    assert len(metrics["misses"]) == 2


def test_compute_benchmark_metrics_empty_findings():
    """Test metrics with no findings."""
    benchmark_records = [
        {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
    ]

    metrics = compute_benchmark_metrics([], benchmark_records)

    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0
    assert len(metrics["hits"]) == 0
    assert len(metrics["misses"]) == 1


def test_compute_benchmark_metrics_empty_benchmark():
    """Test metrics with empty benchmark."""
    findings = [
        Finding("CRITICAL", "Test", "smallchat-server.c:45"),
    ]

    metrics = compute_benchmark_metrics(findings, [])

    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0
    assert len(metrics["hits"]) == 0
    assert len(metrics["misses"]) == 0


# ---- Core-vs-trivia classifier tests ----


def test_classify_core_by_severity_critical():
    """CRITICAL severity is always CORE."""
    f = Finding("CRITICAL", "Buffer overflow", "server.c:100")
    assert classify_finding_core_vs_trivia(f) == "CORE"


def test_classify_core_by_severity_high():
    """HIGH severity is always CORE."""
    f = Finding("HIGH", "Potential overflow", "server.c:100")
    assert classify_finding_core_vs_trivia(f) == "CORE"


def test_classify_core_by_trigger_sigpipe():
    """Trigger containing 'sigpipe' is CORE."""
    f = Finding("MEDIUM", "SIGPIPE not handled", "server.c:290", trigger="sigpipe")
    assert classify_finding_core_vs_trivia(f) == "CORE"


def test_classify_core_by_trigger_bounds():
    """Trigger containing 'bounds' is CORE."""
    f = Finding("MEDIUM", "No bounds check", "server.c:145", trigger="bounds-check")
    assert classify_finding_core_vs_trivia(f) == "CORE"


def test_classify_core_by_trigger_null():
    """Trigger containing 'null' is CORE."""
    f = Finding("HIGH", "Null check missing", "server.c:64", trigger="null-check")
    assert classify_finding_core_vs_trivia(f) == "CORE"


def test_classify_trivia_by_severity_low_and_trigger_style():
    """LOW severity with style trigger is TRIVIA."""
    f = Finding("LOW", "Code style issue", "server.c:10", trigger="style")
    assert classify_finding_core_vs_trivia(f) == "TRIVIA"


def test_classify_trivia_by_trigger_docs():
    """Trigger containing 'docs' is TRIVIA."""
    f = Finding("LOW", "Missing documentation", "server.c:5", trigger="docs")
    assert classify_finding_core_vs_trivia(f) == "TRIVIA"


def test_classify_core_default_for_medium_without_trivia():
    """MEDIUM severity without trivia markers defaults to CORE."""
    f = Finding("MEDIUM", "Potential issue", "server.c:100")
    assert classify_finding_core_vs_trivia(f) == "CORE"


def test_classify_core_by_trigger_buffer():
    """Trigger containing 'buffer' is CORE."""
    f = Finding("LOW", "Buffer risk", "server.c:50", trigger="buffer")
    assert classify_finding_core_vs_trivia(f) == "CORE"


# ---- Focus gate tests ----


def test_focus_drift_warning_when_core_pct_below_50():
    """FOCUS DRIFT warning when with-skill CORE% < 50%."""
    # Create findings: 2 CORE, 3 TRIVIA = 40% CORE
    skill_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100"),  # CORE
        Finding("HIGH", "Null check", "server.c:101"),  # CORE
        Finding("LOW", "Style issue", "server.c:102", trigger="style"),  # TRIVIA
        Finding("LOW", "Docs missing", "server.c:103", trigger="docs"),  # TRIVIA
        Finding("LOW", "Convention", "server.c:104", trigger="convention"),  # TRIVIA
    ]
    baseline_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100"),  # Matched
    ]

    result = compare_skill_vs_baseline(skill_findings, baseline_findings, "test-model")

    assert result["focus_drift_warning"] is True
    assert result["skill_core_pct"] == 40.0


def test_critical_focus_failure_when_baseline_has_critical_and_skill_is_trivia():
    """CRITICAL FOCUS FAILURE when baseline-only has CRITICAL and skill-only is majority trivia."""
    # Skill findings: all trivia (different file to avoid matching)
    skill_findings = [
        Finding("LOW", "Style issue", "server.c:102", trigger="style"),  # TRIVIA
        Finding("LOW", "Docs missing", "client.c:103", trigger="docs"),  # TRIVIA
    ]
    # Baseline findings: one CRITICAL that skill missed (different file)
    baseline_findings = [
        Finding("CRITICAL", "Buffer overflow", "other.c:100"),  # baseline-only, CRITICAL
    ]

    result = compare_skill_vs_baseline(skill_findings, baseline_findings, "test-model")

    assert result["critical_focus_failure"] is True
    assert result["baseline_only_critical"] == 1


def test_no_focus_drift_when_core_pct_above_50():
    """No FOCUS DRIFT when with-skill CORE% >= 50%."""
    # Create findings: 3 CORE, 2 TRIVIA = 60% CORE
    skill_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100"),  # CORE
        Finding("HIGH", "Null check", "server.c:101"),  # CORE
        Finding("MEDIUM", "Potential issue", "server.c:102"),  # CORE (default)
        Finding("LOW", "Style issue", "server.c:103", trigger="style"),  # TRIVIA
        Finding("LOW", "Docs missing", "server.c:104", trigger="docs"),  # TRIVIA
    ]
    baseline_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100"),  # Matched
    ]

    result = compare_skill_vs_baseline(skill_findings, baseline_findings, "test-model")

    assert result["focus_drift_warning"] is False
    assert result["skill_core_pct"] == 60.0


def test_no_critical_focus_failure_when_skill_has_core_findings():
    """No CRITICAL FOCUS FAILURE when skill-only has CORE findings."""
    # Skill findings: mix of CORE and TRIVIA
    skill_findings = [
        Finding("CRITICAL", "New bug found", "server.c:200"),  # CORE
        Finding("LOW", "Style issue", "server.c:102", trigger="style"),  # TRIVIA
    ]
    # Baseline findings: one CRITICAL that skill missed
    baseline_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100"),  # baseline-only, CRITICAL
    ]

    result = compare_skill_vs_baseline(skill_findings, baseline_findings, "test-model")

    # Skill-only has 1 CORE, 1 TRIVIA -> not majority trivia
    assert result["critical_focus_failure"] is False


def test_unmatched_label_in_baseline_only_coverage():
    """Verify that unmatched findings get 'unmatched' label (not 'out of scope')."""
    skill_findings = [
        Finding("CRITICAL", "Buffer overflow", "server.c:100", trigger="bounds-check"),
    ]
    baseline_findings = [
        Finding("HIGH", "Style issue", "server.c:200"),  # No matching trigger
    ]

    result = compare_skill_vs_baseline(skill_findings, baseline_findings, "test-model")

    # Check that baseline_only_with_coverage has unmatched trigger
    assert len(result["baseline_only_with_coverage"]) == 1
    coverage = result["baseline_only_with_coverage"][0]
    assert coverage["matched_trigger"] is None  # No trigger matched


def test_benchmark_records_match_triggers():
    """Test that benchmark records match skill triggers (coverage check).

    This ensures the skill covers most benchmark scenarios.
    Some benchmarks may not be covered if the skill doesn't have
    triggers for those specific patterns (e.g., SC-008 SIGPIPE,
    SC-040 control flow complexity).

    Expected coverage: 39/43 (91%) - SC-005, SC-008, SC-029, SC-037 are known gaps
    after skill regeneration (format-string, security-as-bugfix, naming triggers
    not present in regenerated skill).
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent / "report"))
    from build_comparison import Finding, match_finding_to_trigger
    from trigger_patterns import extract_triggers

    # Load benchmark
    benchmark_path = Path(__file__).parent.parent / "data" / "benchmark.jsonl"
    assert benchmark_path.exists(), f"Benchmark not found: {benchmark_path}"

    # Load triggers from SKILL.md - use auto-detection
    skill_path = Path(__file__).parent.parent / "linus-torvalds-skill" / "SKILL.md"
    content = skill_path.read_text()

    # Auto-detect style based on content
    if "**What to look for**:" in content:
        style = "gpt-oss"
    elif "**Trigger**:" in content:
        style = "glm"
    elif re.search(r"^\s*-\s*\*\*[A-Z]", content, re.MULTILINE):
        style = "mistral"
    else:
        style = "gpt-oss"  # Default

    triggers = extract_triggers(content, style=style)
    trigger_texts = [desc for (_title, desc) in triggers if desc]

    # Check each benchmark record
    uncovered = []
    with open(benchmark_path) as f:
        for line in f:
            record = json.loads(line.strip())
            finding = Finding(
                severity=record.get("severity", "MEDIUM"),
                title=record.get("trigger", record.get("description", "")),
                location=f"{record.get('file', '')}:{record.get('line', 0)}",
            )

            matched_trigger, score = match_finding_to_trigger(finding, trigger_texts)
            if matched_trigger is None:
                uncovered.append(record.get("id", "UNKNOWN"))

    # Report coverage
    total = 43  # Total benchmark records
    covered = total - len(uncovered)
    coverage_pct = covered / total * 100

    # Expected: 39/43 (91%) coverage
    # Known gaps after regeneration: SC-005, SC-008, SC-029, SC-037
    assert len(uncovered) <= 4, f"Too many uncovered records: {uncovered}"
    assert coverage_pct >= 88, f"Coverage too low: {coverage_pct:.1f}% ({covered}/{total})"
