"""Tests for audit.py decision logging and reporting.

Verifies log_decision, generate_audit_report, generate_flowchart,
generate_reproduce_script, and run_audit with temp directories and mock files.
"""

import json
import os
import stat
from unittest.mock import patch

from torvalds_skill.audit import (
    generate_audit_report,
    generate_flowchart,
    generate_reproduce_script,
    log_decision,
    run_audit,
)


class TestLogDecision:
    """Test log_decision appends JSON lines with correct fields."""

    def test_appends_json_line_with_timestamp_and_stage(self, tmp_path):
        """log_decision writes a JSON line with timestamp, stage, and kwargs."""
        with patch("torvalds_skill.audit.REPORT_DIR", tmp_path):
            log_decision("extract", model="gpt-oss-120b", seed=42)

            decisions_path = tmp_path / "decisions.jsonl"
            assert decisions_path.exists()

            lines = decisions_path.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 1

            record = json.loads(lines[0])
            assert "timestamp" in record
            assert record["stage"] == "extract"
            assert record["model"] == "gpt-oss-120b"
            assert record["seed"] == 42

    def test_creates_report_dir_if_missing(self, tmp_path):
        """log_decision creates report/ directory if it doesn't exist."""
        fake_report_dir = tmp_path / "nonexistent_report"
        assert not fake_report_dir.exists()

        with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
            log_decision("classify")

        assert fake_report_dir.exists()
        assert (fake_report_dir / "decisions.jsonl").exists()

    def test_idempotent_multiple_calls(self, tmp_path):
        """Multiple log_decision calls append without overwriting."""
        with patch("torvalds_skill.audit.REPORT_DIR", tmp_path):
            log_decision("extract", model="model1")
            log_decision("cluster", seed=42)
            log_decision("distill", top_n=40)

            decisions_path = tmp_path / "decisions.jsonl"
            lines = decisions_path.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 3

            records = [json.loads(line) for line in lines]
            assert records[0]["stage"] == "extract"
            assert records[1]["stage"] == "cluster"
            assert records[2]["stage"] == "distill"

    def test_kwargs_included_in_record(self, tmp_path):
        """All kwargs are included in the JSON record."""
        with patch("torvalds_skill.audit.REPORT_DIR", tmp_path):
            log_decision(
                "extract",
                model="gpt-oss-120b",
                prompt_hash="abc123",
                params={"temperature": 0.1},
                seed=42,
                truncation_handling=True,
            )

            decisions_path = tmp_path / "decisions.jsonl"
            record = json.loads(decisions_path.read_text(encoding="utf-8").strip())

            assert record["model"] == "gpt-oss-120b"
            assert record["prompt_hash"] == "abc123"
            assert record["params"] == {"temperature": 0.1}
            assert record["seed"] == 42
            assert record["truncation_handling"] is True


class TestGenerateAuditReport:
    """Test generate_audit_report aggregates counts correctly."""

    def test_returns_dict_with_all_expected_keys(self, tmp_path):
        """Report contains all required keys even with missing files."""
        fake_data_dir = tmp_path / "data"
        fake_report_dir = tmp_path / "report"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
            with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    report = generate_audit_report()

        assert "emails_in" in report
        assert "moves_extracted" in report
        assert "moves_sampled" in report
        assert "skill_words_out" in report
        assert "decisions_logged" in report

    def test_emails_in_from_mbox(self, tmp_path):
        """emails_in counts lines from torvalds.mbox."""
        fake_data_dir = tmp_path / "data"
        fake_data_dir.mkdir()
        mbox_path = fake_data_dir / "torvalds.mbox"
        mbox_path.write_text("email1\nemail2\nemail3\n", encoding="utf-8")

        fake_report_dir = tmp_path / "report"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
            with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    report = generate_audit_report()

        assert report["emails_in"] == 3

    def test_moves_extracted_from_moves_jsonl(self, tmp_path):
        """moves_extracted counts lines from moves.jsonl."""
        fake_data_dir = tmp_path / "data"
        fake_data_dir.mkdir()
        moves_path = fake_data_dir / "moves.jsonl"
        moves_path.write_text('{"moves": []}\n{"moves": []}\n', encoding="utf-8")

        fake_report_dir = tmp_path / "report"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
            with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    report = generate_audit_report()

        assert report["moves_extracted"] == 2

    def test_moves_sampled_from_patterns_json(self, tmp_path):
        """moves_sampled sums samples_by_category from patterns.json."""
        fake_data_dir = tmp_path / "data"
        fake_data_dir.mkdir()
        patterns_path = fake_data_dir / "patterns.json"
        patterns_path.write_text(
            json.dumps(
                {
                    "samples_by_category": {
                        "category1": [{"trigger": "a"}, {"trigger": "b"}],
                        "category2": [{"trigger": "c"}],
                    }
                }
            ),
            encoding="utf-8",
        )

        fake_report_dir = tmp_path / "report"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
            with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    report = generate_audit_report()

        assert report["moves_sampled"] == 3

    def test_skill_words_out_from_skill_md(self, tmp_path):
        """skill_words_out counts words from SKILL.md."""
        fake_skill_dir = tmp_path / "skill"
        fake_skill_dir.mkdir()
        skill_path = fake_skill_dir / "SKILL.md"
        skill_path.write_text("one two three four five", encoding="utf-8")

        fake_data_dir = tmp_path / "data"
        fake_report_dir = tmp_path / "report"

        with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
            with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    report = generate_audit_report()

        assert report["skill_words_out"] == 5

    def test_decisions_logged_from_decisions_jsonl(self, tmp_path):
        """decisions_logged counts lines from decisions.jsonl."""
        fake_report_dir = tmp_path / "report"
        fake_report_dir.mkdir()
        decisions_path = fake_report_dir / "decisions.jsonl"
        decisions_path.write_text('{"stage": "extract"}\n{"stage": "cluster"}\n', encoding="utf-8")

        fake_data_dir = tmp_path / "data"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
            with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    report = generate_audit_report()

        assert report["decisions_logged"] == 2

    def test_writes_audit_report_json(self, tmp_path):
        """generate_audit_report writes report/audit_report.json."""
        fake_report_dir = tmp_path / "report"
        fake_data_dir = tmp_path / "data"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
            with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    generate_audit_report()

        report_path = fake_report_dir / "audit_report.json"
        assert report_path.exists()

        saved_report = json.loads(report_path.read_text(encoding="utf-8"))
        assert "emails_in" in saved_report

    def test_missing_input_files_graceful_handling(self, tmp_path):
        """Missing files result in zeros, not crashes."""
        fake_data_dir = tmp_path / "data"
        fake_report_dir = tmp_path / "report"
        fake_skill_dir = tmp_path / "skill"

        # Don't create any files - all should be zeros
        with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
            with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    report = generate_audit_report()

        assert report["emails_in"] == 0
        assert report["moves_extracted"] == 0
        assert report["moves_sampled"] == 0
        assert report["skill_words_out"] == 0
        assert report["decisions_logged"] == 0


class TestGenerateFlowchart:
    """Test generate_flowchart produces valid Mermaid syntax."""

    def test_contains_mermaid_flowchart_syntax(self, tmp_path):
        """Flowchart contains 'flowchart' or 'graph' and arrows '-->'."""
        fake_report_dir = tmp_path / "report"
        fake_data_dir = tmp_path / "data"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
            with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    flowchart = generate_flowchart()

        assert "flowchart" in flowchart or "graph" in flowchart
        assert "-->" in flowchart

    def test_writes_pipeline_flowchart_mmd(self, tmp_path):
        """Flowchart is written to report/pipeline_flowchart.mmd."""
        fake_report_dir = tmp_path / "report"
        fake_data_dir = tmp_path / "data"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
            with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    generate_flowchart()

        flowchart_path = fake_report_dir / "pipeline_flowchart.mmd"
        assert flowchart_path.exists()

    def test_includes_counts_from_report(self, tmp_path):
        """Flowchart includes counts from audit_report.json."""
        fake_report_dir = tmp_path / "report"
        fake_report_dir.mkdir()
        fake_data_dir = tmp_path / "data"
        fake_skill_dir = tmp_path / "skill"

        # Create a mock audit report
        report_path = fake_report_dir / "audit_report.json"
        report_path.write_text(
            json.dumps(
                {
                    "emails_in": 100,
                    "moves_extracted": 50,
                    "moves_sampled": 25,
                    "skill_words_out": 5000,
                    "decisions_logged": 10,
                }
            ),
            encoding="utf-8",
        )

        with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
            with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    flowchart = generate_flowchart()

        assert "100" in flowchart
        assert "5000" in flowchart

    def test_shows_pipeline_stages(self, tmp_path):
        """Flowchart shows all pipeline stages."""
        fake_report_dir = tmp_path / "report"
        fake_data_dir = tmp_path / "data"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
            with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
                with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                    flowchart = generate_flowchart()

        assert "classify" in flowchart
        assert "extract" in flowchart
        assert "cluster" in flowchart
        assert "calibrate" in flowchart
        assert "distill" in flowchart


class TestGenerateReproduceScript:
    """Test generate_reproduce_script produces valid bash script."""

    def test_contains_pipeline_commands(self, tmp_path):
        """Script contains torvalds_skill subcommands."""
        fake_root = tmp_path

        with patch("torvalds_skill.audit.ROOT", fake_root):
            script = generate_reproduce_script()

        assert "python -m torvalds_skill.classify" in script
        assert "python -m torvalds_skill.extract" in script
        assert "python -m torvalds_skill.cluster" in script
        assert "python -m torvalds_skill.distill" in script

    def test_writes_reproduce_sh_at_root(self, tmp_path):
        """Script is written to repo root as reproduce.sh."""
        fake_root = tmp_path

        with patch("torvalds_skill.audit.ROOT", fake_root):
            generate_reproduce_script()

        script_path = fake_root / "reproduce.sh"
        assert script_path.exists()

    def test_makes_script_executable(self, tmp_path):
        """Script has executable permissions."""
        fake_root = tmp_path

        with patch("torvalds_skill.audit.ROOT", fake_root):
            generate_reproduce_script()

        script_path = fake_root / "reproduce.sh"
        mode = os.stat(script_path).st_mode
        assert mode & stat.S_IXUSR  # User execute bit

    def test_script_has_shebang(self, tmp_path):
        """Script starts with shebang."""
        fake_root = tmp_path

        with patch("torvalds_skill.audit.ROOT", fake_root):
            script = generate_reproduce_script()

        assert script.startswith("#!/usr/bin/env bash")


class TestRunAudit:
    """Test run_audit orchestrator produces all output files."""

    def test_produces_all_four_output_files(self, tmp_path):
        """run_audit creates decisions.jsonl, audit_report.json, pipeline_flowchart.mmd, reproduce.sh."""
        fake_root = tmp_path
        fake_data_dir = tmp_path / "data"
        fake_report_dir = tmp_path / "report"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.ROOT", fake_root):
            with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
                with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                    with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                        # Log a decision first to create the file
                        log_decision("test", extra_field="test")
                        run_audit()

        assert (fake_report_dir / "decisions.jsonl").exists()
        assert (fake_report_dir / "audit_report.json").exists()
        assert (fake_report_dir / "pipeline_flowchart.mmd").exists()
        assert (fake_root / "reproduce.sh").exists()

    def test_returns_audit_report_dict(self, tmp_path):
        """run_audit returns the audit report dict."""
        fake_root = tmp_path
        fake_data_dir = tmp_path / "data"
        fake_report_dir = tmp_path / "report"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.ROOT", fake_root):
            with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
                with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                    with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                        report = run_audit()

        assert isinstance(report, dict)
        assert "emails_in" in report
        assert "moves_extracted" in report

    def test_prints_summary_to_stdout(self, tmp_path, capsys):
        """run_audit prints a summary with counts."""
        fake_root = tmp_path
        fake_data_dir = tmp_path / "data"
        fake_report_dir = tmp_path / "report"
        fake_skill_dir = tmp_path / "skill"

        with patch("torvalds_skill.audit.ROOT", fake_root):
            with patch("torvalds_skill.audit.DATA_DIR", fake_data_dir):
                with patch("torvalds_skill.audit.REPORT_DIR", fake_report_dir):
                    with patch("torvalds_skill.audit.SKILL_DIR", fake_skill_dir):
                        run_audit()

        captured = capsys.readouterr()
        assert "AUDIT SUMMARY" in captured.out
        assert "Emails in corpus" in captured.out
