"""
audit.py — decision logging, audit reports, and reproducibility.

Provides:
- log_decision(): append JSON lines to report/decisions.jsonl
- generate_audit_report(): aggregate counts from pipeline stages
- generate_flowchart(): Mermaid CONSORT-style flowchart
- generate_reproduce_script(): bash script to rerun pipeline
- run_audit(): orchestrator that generates all outputs
"""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

# Project root relative to this module
ROOT = Path(__file__).resolve().parent.parent.parent
_report_dir_env = os.environ.get("TORVALDS_REPORT_DIR")
REPORT_DIR = Path(_report_dir_env) if _report_dir_env else ROOT / "report"
DATA_DIR = ROOT / "data"
SKILL_DIR = ROOT / "linus-torvalds-skill"


def log_decision(stage: str, **kwargs) -> None:
    """Append a JSON line to report/decisions.jsonl.

    Each line contains:
    - timestamp: ISO8601 with timezone
    - stage: pipeline stage name (classify, extract, cluster, calibrate, distill)
    - kwargs: any additional context (model, prompt_hash, params, seed, etc.)

    Creates report/ dir if missing. Idempotent: safe to call multiple times.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    record = {"timestamp": datetime.now(UTC).isoformat(), "stage": stage, **kwargs}

    decisions_path = REPORT_DIR / "decisions.jsonl"
    with open(decisions_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _count_lines(path: Path) -> int:
    """Count lines in a file. Returns 0 if file doesn't exist."""
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _word_count(path: Path) -> int:
    """Count words in a file. Returns 0 if file doesn't exist."""
    if not path.exists():
        return 0
    content = path.read_text(encoding="utf-8")
    return len(content.split())


def generate_audit_report() -> dict:
    """Aggregate counts from each pipeline stage.

    Returns a dict with:
    - emails_in: count from data/torvalds.mbox or data/moves.jsonl
    - moves_extracted: count lines in data/moves.jsonl
    - moves_sampled: count from patterns.json samples_by_category
    - skill_words_out: word count of linus-torvalds-skill/SKILL.md
    - decisions_logged: count lines in report/decisions.jsonl
    """
    # emails_in: try torvalds.mbox first, then moves.jsonl as fallback
    mbox_path = DATA_DIR / "torvalds.mbox"
    moves_path = DATA_DIR / "moves.jsonl"

    if mbox_path.exists():
        emails_in = _count_lines(mbox_path)
    elif moves_path.exists():
        # Fallback: count unique email IDs from moves
        emails_in = _count_lines(moves_path)
    else:
        emails_in = 0

    # moves_extracted: lines in moves.jsonl
    moves_extracted = _count_lines(moves_path) if moves_path.exists() else 0

    # moves_sampled: from patterns.json
    patterns_path = DATA_DIR / "patterns.json"
    moves_sampled = 0
    if patterns_path.exists():
        try:
            patterns_data = json.loads(patterns_path.read_text(encoding="utf-8"))
            samples_by_category = patterns_data.get("samples_by_category", {})
            moves_sampled = sum(len(samples) for samples in samples_by_category.values())
        except (json.JSONDecodeError, KeyError):
            moves_sampled = 0

    # skill_words_out: word count of SKILL.md
    skill_path = SKILL_DIR / "SKILL.md"
    skill_words_out = _word_count(skill_path)

    # decisions_logged: lines in decisions.jsonl
    decisions_path = REPORT_DIR / "decisions.jsonl"
    decisions_logged = _count_lines(decisions_path) if decisions_path.exists() else 0

    report = {
        "emails_in": emails_in,
        "moves_extracted": moves_extracted,
        "moves_sampled": moves_sampled,
        "skill_words_out": skill_words_out,
        "decisions_logged": decisions_logged,
    }

    # Write the report
    report_path = REPORT_DIR / "audit_report.json"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def generate_flowchart() -> str:
    """Generate a Mermaid flowchart (CONSORT-style) showing pipeline stages.

    Writes report/pipeline_flowchart.mmd and returns the mermaid string.

    Flowchart shows:
    - Raw mbox → classify → extract → cluster → calibrate → distill → SKILL.md
    - Decision points marked with diamonds
    - Counts at each stage (read from audit_report.json)
    """
    # Load the audit report
    report_path = REPORT_DIR / "audit_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        report = generate_audit_report()

    emails_in = report.get("emails_in", 0)
    moves_extracted = report.get("moves_extracted", 0)
    moves_sampled = report.get("moves_sampled", 0)
    skill_words_out = report.get("skill_words_out", 0)

    mermaid = f"""flowchart TD
    A[/"Raw mbox: {emails_in} emails"/] --> B{("{classify}")}
    B --> C{("{extract}")}
    C --> D{("{cluster}")}
    D --> E{("{calibrate}")}
    E --> F{("{distill}")}
    F --> G[/"SKILL.md: {skill_words_out} words"/]

    C -.->|"moves extracted: {moves_extracted}"| D
    D -.->|"moves sampled: {moves_sampled}"| E
"""

    # Write the flowchart
    flowchart_path = REPORT_DIR / "pipeline_flowchart.mmd"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    flowchart_path.write_text(mermaid, encoding="utf-8")

    return mermaid


def generate_reproduce_script() -> str:
    """Generate a bash script that reruns the full pipeline.

    Writes reproduce.sh at repo root and makes it executable.
    Returns the script content.

    Uses the CLI subcommand pattern from cli.py:
    - classify
    - extract --sample N --workers N
    - cluster
    - distill --top-n N
    """
    script = """#!/usr/bin/env bash
# reproduce.sh — rerun the full torvalds-skill pipeline
# Generated by audit.py

set -euo pipefail

echo "=== Torvalds Skill Pipeline Reproduction Script ==="
echo "Starting at: $(date -Iseconds)"
echo ""

# Step 1: Classify corpus
echo "Step 1/4: Classifying corpus..."
python -m torvalds_skill.classify
echo ""

# Step 2: Extract moves
echo "Step 2/4: Extracting moves..."
python -m torvalds_skill.extract --sample 2000 --workers 8
echo ""

# Step 3: Cluster moves
echo "Step 3/4: Clustering moves..."
python -m torvalds_skill.cluster
echo ""

# Step 4: Distill skill
echo "Step 4/4: Distilling skill..."
python -m torvalds_skill.distill --top-n 40
echo ""

echo "=== Pipeline complete ==="
echo "Finished at: $(date -Iseconds)"
echo "Output: linus-torvalds-skill/SKILL.md"
"""

    script_path = ROOT / "reproduce.sh"
    script_path.write_text(script, encoding="utf-8")

    # Make executable
    current_mode = os.stat(script_path).st_mode
    os.chmod(script_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return script


def run_audit() -> dict:
    """Orchestrator: generate all audit outputs and print summary.

    Calls:
    - generate_audit_report()
    - generate_flowchart()
    - generate_reproduce_script()

    Prints a summary to stdout and returns the audit report dict.
    """
    print("Generating audit report...", flush=True)
    report = generate_audit_report()

    print("Generating pipeline flowchart...", flush=True)
    generate_flowchart()

    print("Generating reproduction script...", flush=True)
    generate_reproduce_script()

    # Print summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Emails in corpus:        {report['emails_in']:,}")
    print(f"Moves extracted:         {report['moves_extracted']:,}")
    print(f"Moves sampled:           {report['moves_sampled']:,}")
    print(f"Skill words out:         {report['skill_words_out']:,}")
    print(f"Decisions logged:        {report['decisions_logged']:,}")
    print("=" * 60)
    print("\nGenerated files:")
    print(f"  - {REPORT_DIR / 'decisions.jsonl'}")
    print(f"  - {REPORT_DIR / 'audit_report.json'}")
    print(f"  - {REPORT_DIR / 'pipeline_flowchart.mmd'}")
    print(f"  - {ROOT / 'reproduce.sh'}")
    print("=" * 60)

    return report
