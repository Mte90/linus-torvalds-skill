"""Tests for evaluation-provenance statements in both report generators.

A report must not be able to claim clean data when it was rendered from a
contaminated run, so the provenance is an explicit input to both generators and
an unknown value fails loudly instead of falling back to a default banner.
"""

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
for extra in (ROOT, ROOT / "report"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from build_comparison import match_findings_across_models
from comparison_render import generate_markdown

from scripts.render_cross import (
    collect_unmatched_findings,
    compute_cell_metrics,
    load_jsonl,
    render_markdown,
)
from torvalds_skill.matching import dedupe_records
from torvalds_skill.provenance import banner, limitation


class TestProvenanceModule:
    """The shared provenance vocabulary."""

    def test_decontaminated_banner_states_no_ground_truth(self):
        text = banner("decontaminated")
        assert "never the ground-truth bug list" in text
        assert "WARNING" not in text

    def test_pre_decontamination_banner_warns(self):
        text = banner("pre-decontamination")
        assert "WARNING: pre-decontamination data" in text
        assert "transcription fidelity" in text

    def test_limitations_differ_by_provenance(self):
        assert banner("decontaminated") != banner("pre-decontamination")
        assert "Prompt provenance" in limitation("decontaminated")
        assert "Pre-decontamination status" in limitation("pre-decontamination")

    @pytest.mark.parametrize("accessor", [banner, limitation])
    def test_unknown_provenance_fails_loudly(self, accessor):
        with pytest.raises(ValueError, match="contaminated"):
            accessor("probably-fine")


def _render_cross(tmp_path, provenance, reps=3):
    cell_data = {
        ("gpt-oss-120b", "gpt-oss-120b"): {"total_results": 3, "reps": reps},
    }
    out_path = tmp_path / "matrix.md"
    render_markdown(
        cell_data,
        ["gpt-oss-120b"],
        [],
        out_path,
        eval_provenance=provenance,
    )
    return out_path.read_text()


def _render_comparison(provenance, repetitions=3):
    return generate_markdown(
        report_dir=Path("."),
        metrics={},
        matched_groups=[],
        severity_disagreements=[],
        trigger_coverage={},
        skill_vs_baseline=[],
        missing_files=[],
        repetitions=repetitions,
        eval_provenance=provenance,
    )


class TestCrossMatrixProvenance:
    """scripts/render_cross.py must state which prompt version produced the data."""

    def test_decontaminated_banner_replaces_warning(self, tmp_path):
        content = _render_cross(tmp_path, "decontaminated")
        assert "never the ground-truth bug list" in content
        assert "WARNING: pre-decontamination data" not in content

    def test_contaminated_data_still_gets_the_warning(self, tmp_path):
        content = _render_cross(tmp_path, "pre-decontamination")
        assert "WARNING: pre-decontamination data" in content

    def test_repetitions_bullet_comes_from_the_data(self, tmp_path):
        content = _render_cross(tmp_path, "decontaminated", reps=3)
        assert "evaluated 3x per diff scenario" in content

    def test_single_run_is_reported_as_one(self, tmp_path):
        content = _render_cross(tmp_path, "decontaminated", reps=1)
        assert "evaluated 1x per diff scenario" in content
        assert "Single-run-per-cell" not in content


class TestConsensusColumnCountsMarks:
    """Consensus must count the ✓ marks rendered, not group membership.

    Regression: a finding already shown on an earlier row renders as ✗ but was
    still counted in that row's consensus, inflating it (audit P1-5b follow-up).
    """

    def _findings(self, items):
        from build_comparison import Finding

        return [Finding(sev, title, loc) for sev, title, loc in items]

    def test_a_finding_already_shown_does_not_inflate_the_row(self):
        model_a = self._findings(
            [
                ("CRITICAL", "buffer overflow in parse", "server.c:100"),
                ("HIGH", "buffer overflow in parse", "server.c:100"),
            ],
        )
        groups = match_findings_across_models({"a": model_a, "b": []})
        content = generate_markdown(
            report_dir=Path("."),
            metrics={
                "a": {"total_findings": 2, "findings": [], "critical": 1},
                "b": {"total_findings": 0, "findings": [], "critical": 0},
            },
            matched_groups=groups,
            severity_disagreements=[],
            trigger_coverage={},
            skill_vs_baseline=[],
            missing_files=[],
            model_names=["a", "b"],
        )
        matrix = content[content.find("## Finding Consensus Matrix") :]
        matrix = matrix[: matrix.find("## Severity Disagreement Table")]
        data_rows = [
            ln
            for ln in matrix.splitlines()
            if ln.startswith("| ")
            and "|" in ln
            and not ln.startswith("| #")
            and not ln.startswith("|---")
        ]
        assert data_rows, "expected at least one consensus row"
        for row in data_rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            marks, consensus = cells[2:4], cells[4]
            checkmarks = sum(1 for m in marks if m.startswith("✓"))
            # A row must never claim a finding for a model whose cell shows ✗.
            if consensus.endswith("/2"):
                assert consensus == f"{checkmarks}/2", (
                    f"row claims {consensus} but shows {checkmarks} checkmarks: {row}"
                )
            elif consensus.endswith("only"):
                claimed = consensus.split(" ")[0]
                assert marks[cells[2:4].index(claimed)].startswith("✓"), (
                    f"row claims '{consensus}' but that model shows ✗: {row}"
                )
            else:
                assert consensus == "—" or checkmarks > 0, (
                    f"empty consensus but {checkmarks} checkmarks shown: {row}"
                )


class TestDedupeRecords:
    """Superseded records are dropped: last one written wins.

    The eval pipeline is append-only and re-runs judge-failed records by
    appending, so a poisoned record and its replacement end up side by side.
    """

    def test_last_record_for_a_key_wins(self):
        records = [
            {"diff_id": "D1", "model": "a", "skill": "a", "scores": {"accuracy": 0.0}},
            {"diff_id": "D1", "model": "a", "skill": "a", "scores": {"accuracy": 2.0}},
        ]
        result = dedupe_records(records)
        assert len(result) == 1
        assert result[0]["scores"]["accuracy"] == 2.0

    def test_distinct_repetitions_are_kept(self):
        records = [
            {"diff_id": "D1", "model": "a", "skill": "a", "rep": 0},
            {"diff_id": "D1", "model": "a", "skill": "a", "rep": 1},
            {"diff_id": "D1", "model": "a", "skill": "a", "rep": 2},
        ]
        assert len(dedupe_records(records)) == 3

    def test_missing_skill_falls_back_to_model(self):
        records = [
            {"diff_id": "D1", "model": "a"},
            {"diff_id": "D1", "model": "a", "skill": "a"},
        ]
        assert len(dedupe_records(records)) == 1

    def test_missing_rep_is_treated_as_repetition_zero(self):
        records = [
            {"diff_id": "D1", "model": "a", "skill": "a"},
            {"diff_id": "D1", "model": "a", "skill": "a", "rep": 0},
        ]
        assert len(dedupe_records(records)) == 1

    def test_different_cells_are_untouched(self):
        records = [
            {"diff_id": "D1", "model": "a", "skill": "a"},
            {"diff_id": "D1", "model": "a", "skill": "b"},
            {"diff_id": "D2", "model": "a", "skill": "a"},
        ]
        assert len(dedupe_records(records)) == 3

    def test_load_jsonl_applies_the_dedup(self, tmp_path):
        path = tmp_path / "results.jsonl"
        path.write_text(
            '{"diff_id":"D1","model":"a","skill":"a","findings":[],"tag":"stale"}\n'
            '{"diff_id":"D1","model":"a","skill":"a","findings":[],"tag":"fresh"}\n'
            '{"diff_id":"D2","model":"a","skill":"a","findings":[]}\n'
        )
        records = load_jsonl(path)
        assert len(records) == 2
        assert {r.get("tag") for r in records if r.get("tag")} == {"fresh"}


class TestTriggerCoverageNote:
    """Findings that fire no skill trigger are excluded from the trigger table."""

    def _render(self, coverage):
        return generate_markdown(
            report_dir=Path("."),
            metrics={
                "gpt-oss-120b": {"total_findings": 8, "findings": [], "critical": 0},
                "glm5.2": {"total_findings": 2, "findings": [], "critical": 0},
            },
            matched_groups=[],
            severity_disagreements=[],
            trigger_coverage=coverage,
            skill_vs_baseline=[],
            missing_files=[],
            model_names=["gpt-oss-120b", "glm5.2"],
        )

    def test_unmatched_findings_are_explained_and_counted(self):
        content = self._render({"gpt-oss-120b": {"unused_variable": 3, "unmatched": 5}})
        assert "5 finding(s) fired no skill trigger" in content
        assert "gpt-oss-120b=5" in content
        assert "excluded from" in content
        assert "still counted as findings in the metrics tables" in content

    def test_unmatched_rows_stay_out_of_the_table(self):
        content = self._render({"gpt-oss-120b": {"unused_variable": 3, "unmatched": 5}})
        header = content[content.find("| Trigger theme") :]
        rows = [ln for ln in header.splitlines() if ln.startswith("|")]
        assert any("unused_variable" in r for r in rows)
        assert not any("unmatched" in r for r in rows[1:])

    def test_no_note_when_every_finding_matched_a_trigger(self):
        content = self._render({"gpt-oss-120b": {"unused_variable": 3}})
        assert "fired no skill trigger" not in content


class TestRenderWithRealisticData:
    """Full render with a populated pairing table AND unmatched findings.

    Regression: the per-pairing classification loop used to bind a variable named
    `unmatched`, shadowing the `unmatched` findings parameter for the rest of
    render_markdown. With real data (both tables populated) that made
    `unmatched[:50]` iterate an int and raised TypeError. Fixture-only tests
    never hit it because they leave one of the two empty.
    """

    DIFFS = [
        {
            "id": "DIFF-001",
            "file": "server.c",
            "expected": "findings",
            "bugs": [{"line": 100, "severity": "HIGH", "category": "memory-safety"}],
        },
    ]

    def _results(self):
        return [
            {
                "diff_id": "DIFF-001",
                "model": "gpt-oss-120b",
                "skill": "gpt-oss-120b",
                "expected": "findings",
                "findings": [
                    {"file": "server.c", "line": 100, "issue": "use after free"},
                    {"file": "other.c", "line": 7, "issue": "hallucinated nit"},
                ],
                "scores": {"accuracy": 2.0},
            },
        ]

    def test_full_render_survives_both_tables(self, tmp_path):
        results = self._results()
        metrics = compute_cell_metrics(results, self.DIFFS)
        cell_data = {("gpt-oss-120b", "gpt-oss-120b"): metrics}
        unmatched, unmatched_counts = collect_unmatched_findings(results, self.DIFFS)
        assert unmatched, "fixture must produce an unmatched finding"

        out = tmp_path / "matrix.md"
        render_markdown(
            cell_data,
            ["gpt-oss-120b"],
            self.DIFFS,
            out,
            unmatched=unmatched,
            unmatched_counts=unmatched_counts,
        )
        content = out.read_text()
        assert "Bugs Found per Pairing (findings classified)" in content
        assert "| gpt-oss-120b | gpt-oss-120b *(native)* | 1 | 0 | 1 | 2 |" in content
        assert "## New Bug Candidates" in content
        assert "hallucinated nit" in content

    def test_classification_loop_does_not_shadow_the_parameter(self):
        """The `unmatched` parameter must survive the pairing-table loop."""
        import inspect

        src = inspect.getsource(render_markdown)
        assert "for model, skill, tp, dup, unmatched in pair_tp" not in src
        assert "for model, skill, tp, dup, cell_unmatched in pair_tp" in src


class TestComparisonProvenance:
    """report/comparison_render.py must state which prompt version produced the data."""

    def test_decontaminated_banner_replaces_warning(self):
        content = _render_comparison("decontaminated")
        assert "never the ground-truth bug list" in content
        assert "WARNING: pre-decontamination data" not in content

    def test_contaminated_data_still_gets_the_warning(self):
        content = _render_comparison("pre-decontamination")
        assert "WARNING: pre-decontamination data" in content

    def test_repetitions_bullet_comes_from_the_caller(self):
        content = _render_comparison("decontaminated", repetitions=3)
        assert "evaluated 3x per diff scenario" in content
        assert "Single-run-per-cell" not in content

    def test_single_run_declares_the_missing_variance(self):
        content = _render_comparison("decontaminated", repetitions=1)
        assert "evaluated 1x per diff scenario" in content
        assert "No variance estimate" in content
        assert "read as noise" in content

    def test_both_reports_declare_ds_the_primary_metric(self):
        """DS is ground-truth based; judge scores are one model's opinion (audit P1-1)."""
        comparison = generate_markdown(
            report_dir=Path("."),
            metrics={},
            matched_groups=[],
            severity_disagreements=[],
            trigger_coverage={},
            skill_vs_baseline=[],
            missing_files=[],
            diff_eval_metrics={
                "gpt-oss-120b_skill": {"total_benchmark": 45, "total_findings": 10, "ds": 0.2},
            },
        )
        assert "DS is the primary metric" in comparison
        assert "not to rank" in comparison

        with tempfile.TemporaryDirectory() as tmpdir:
            cell = {("gpt-oss-120b", "gpt-oss-120b"): {"total_results": 1, "reps": 1}}
            out = Path(tmpdir) / "m.md"
            render_markdown(cell, ["gpt-oss-120b"], [], out)
            cross = out.read_text()
        assert "Secondary metric" in cross
        assert "to rank" in cross

    def test_repeated_runs_do_not_claim_missing_variance(self):
        content = _render_comparison("decontaminated", repetitions=3)
        assert "No variance estimate" not in content
