"""Tests for --codebase mode in run_eval.py and render_cross.py.

Codebase mode replaces the synthetic-diff pipeline with a full SmallChat
codebase review. These tests verify the prompt builder, the benchmark-to-diff
adapter, and the CLI surface — without making LLM calls or cloning repos.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "run_eval.py"
RENDER = ROOT / "scripts" / "render_cross.py"

sys.path.insert(0, str(ROOT))
from scripts.render_cross import _benchmark_to_diff_records  # noqa: E402
from scripts.run_eval import (  # noqa: E402
    benchmark_to_diff_records,
    build_codebase_prompt,
    load_benchmark_bugs,
)


class TestBuildCodebasePrompt:
    """Tests for build_codebase_prompt."""

    def test_prompt_contains_skill_block(self):
        prompt = build_codebase_prompt("=== MY SKILL TEXT ===")
        assert "=== MY SKILL TEXT ===" in prompt

    def test_prompt_baseline_omits_skill_section(self):
        prompt = build_codebase_prompt(None)
        assert "== SKILL ==" not in prompt

    def test_prompt_includes_review_instructions(self):
        prompt = build_codebase_prompt(None)
        assert "Pass 1" in prompt
        assert "Pass 2" in prompt
        assert "SEVERITY" in prompt

    def test_prompt_has_no_ground_truth_leak(self):
        """The codebase prompt must not contain bug answers."""
        prompt = build_codebase_prompt("skill text")
        # Ground-truth bug IDs from benchmark.jsonl must not appear
        assert "SC-001" not in prompt
        assert "SC-002" not in prompt
        assert "Fatal assertion" not in prompt
        assert "Unbounded format-string" not in prompt


class TestBenchmarkToDiffRecords:
    """Tests for benchmark_to_diff_records (run_eval side)."""

    def test_converts_bugs_to_diff_records(self):
        bugs = [
            {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
            {"id": "SC-002", "file": "smallchat-server.c", "line": 30, "severity": "reject"},
        ]
        records = benchmark_to_diff_records(bugs)
        assert len(records) == 2
        assert records[0]["id"] == "SC-001"
        assert records[0]["file"] == "smallchat-server.c"
        assert records[0]["bugs"] == [bugs[0]]
        assert records[0]["expected"] == "findings"

    def test_empty_bugs_produce_empty_list(self):
        assert benchmark_to_diff_records([]) == []

    def test_missing_id_gets_synthetic_id(self):
        bugs = [{"file": "x.c", "line": 1, "severity": "LOW"}]
        records = benchmark_to_diff_records(bugs)
        assert records[0]["id"] == "SC-0"


class TestRenderCrossBenchmarkAdapter:
    """Tests for _benchmark_to_diff_records (render_cross side)."""

    def test_converts_bugs_to_diff_records(self):
        bugs = [
            {"id": "SC-001", "file": "smallchat-server.c", "line": 45, "severity": "reject"},
            {"id": "SC-002", "file": "chatlib.c", "line": 30, "severity": "reject"},
        ]
        records = _benchmark_to_diff_records(bugs)
        assert len(records) == 2
        assert records[0]["id"] == "SC-001"
        assert records[0]["bugs"] == [bugs[0]]
        assert records[0]["expected"] == "findings"

    def test_empty_bugs(self):
        assert _benchmark_to_diff_records([]) == []


class TestLoadBenchmarkBugs:
    """Tests for load_benchmark_bugs."""

    def test_loads_real_benchmark_file(self):
        """The real data/benchmark.jsonl should load without error."""
        benchmark = ROOT / "data" / "benchmark.jsonl"
        if not benchmark.exists():
            pytest.skip("data/benchmark.jsonl not found")
        bugs = load_benchmark_bugs()
        assert len(bugs) > 0
        # Each bug must have the fields compute_cell_metrics expects
        for bug in bugs:
            assert "file" in bug
            assert "line" in bug
            assert "severity" in bug

    def test_loads_synthetic_benchmark(self, tmp_path: Path):
        bench = tmp_path / "benchmark.jsonl"
        with open(bench, "w") as f:
            f.write(json.dumps({"id": "X-1", "file": "a.c", "line": 10, "severity": "HIGH"}) + "\n")
            f.write(json.dumps({"id": "X-2", "file": "b.c", "line": 20, "severity": "LOW"}) + "\n")
        # load_benchmark_bugs reads from BENCHMARK_PATH global, so we
        # test via benchmark_to_diff_records on manually loaded data
        import scripts.run_eval as run_eval_mod

        original = run_eval_mod.BENCHMARK_PATH
        run_eval_mod.BENCHMARK_PATH = bench
        try:
            bugs = run_eval_mod.load_benchmark_bugs()
            assert len(bugs) == 2
            assert bugs[0]["id"] == "X-1"
        finally:
            run_eval_mod.BENCHMARK_PATH = original


class TestCodebaseDispatchOrder:
    """Regression: --codebase must dispatch before --out resolution.

    Previously main() resolved args.out to eval_results_cross.jsonl when --cross
    was set, THEN dispatched codebase mode. So codebase mode wrote to the old
    diff-based cross file, colliding with 1080 existing records and skipping
    11/12 pairings as 'already done'.
    """

    def test_codebase_dispatches_before_out_resolution(self):
        import ast
        import inspect

        import scripts.run_eval as run_eval_mod

        src = inspect.getsource(run_eval_mod.main)
        tree = ast.parse(src)
        codebase_line = None
        out_line = None
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                try:
                    cond = ast.unparse(node.test)
                    if "args.codebase" in cond and codebase_line is None:
                        codebase_line = node.lineno
                    if "args.out is None" in cond and out_line is None:
                        out_line = node.lineno
                except Exception:
                    pass
        assert codebase_line is not None, "args.codebase check not found in main()"
        assert out_line is not None, "args.out is None check not found in main()"
        assert codebase_line < out_line, (
            f"codebase dispatch (line {codebase_line}) must come before "
            f"out resolution (line {out_line})"
        )


class TestCodebaseCliFlag:
    """Tests that --codebase appears in --help for both scripts."""

    def test_run_eval_help_shows_codebase(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0
        assert "--codebase" in result.stdout

    def test_render_cross_help_shows_codebase(self):
        result = subprocess.run(
            [sys.executable, str(RENDER), "--help"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0
        assert "--codebase" in result.stdout


class TestCodebaseRenderEndToEnd:
    """End-to-end render test using synthetic codebase-mode results."""

    def test_render_codebase_mode_produces_report(self, tmp_path: Path):
        """render_cross.py --codebase renders a report from synthetic data."""
        # Write a small benchmark file
        benchmark = tmp_path / "benchmark.jsonl"
        with open(benchmark, "w") as f:
            f.write(
                json.dumps(
                    {
                        "id": "SC-1",
                        "file": "smallchat-server.c",
                        "line": 45,
                        "severity": "reject",
                        "category": "correctness",
                    }
                )
                + "\n"
            )

        # Write a codebase eval result that matches the bug
        results_path = tmp_path / "eval_results_codebase.jsonl"
        with open(results_path, "w") as f:
            f.write(
                json.dumps(
                    {
                        "diff_id": "SMALLCHAT",
                        "model": "glm5.2",
                        "skill": "glm5.2",
                        "expected": "findings",
                        "findings": [
                            {
                                "file": "smallchat-server.c",
                                "line": 45,
                                "severity": "CRITICAL",
                                "type": "correctness",
                                "trigger": "unmatched",
                                "issue": "assert aborts",
                                "fix": "return error",
                                "scores": {
                                    "accuracy": 1.0,
                                    "prioritization": 1.0,
                                    "justification": 1.0,
                                    "actionability": 1.0,
                                },
                            }
                        ],
                        "scores": {
                            "accuracy": 1.0,
                            "prioritization": 1.0,
                            "justification": 1.0,
                            "actionability": 1.0,
                        },
                        "refused": False,
                        "rep": 0,
                    }
                )
                + "\n"
            )

        out = tmp_path / "cross_matrix.md"
        result = subprocess.run(
            [
                sys.executable,
                str(RENDER),
                "--codebase",
                "--codebase-results",
                str(results_path),
                "--benchmark",
                str(benchmark),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, f"render failed: {result.stderr}"
        assert out.exists()
        content = out.read_text()
        assert "glm5.2" in content

    def test_consensus_detail_lists_bug_ids_and_finders(self, tmp_path: Path):
        """Consensus Analysis includes a detailed per-bug table with file, severity, finder."""
        benchmark = tmp_path / "benchmark.jsonl"
        bugs = [
            {
                "id": "SC-1",
                "file": "smallchat-server.c",
                "line": 45,
                "severity": "HIGH",
                "category": "correctness",
                "description": "use-after-free in handle_client",
            },
            {
                "id": "SC-2",
                "file": "smallchat-server.c",
                "line": 100,
                "severity": "MEDIUM",
                "category": "resource",
                "description": "fd leak in error path",
            },
        ]
        with open(benchmark, "w") as f:
            for b in bugs:
                f.write(json.dumps(b) + "\n")

        # glm5.2 finds SC-1, qwen3.8-27b finds SC-2 → both are sole discoveries
        results_path = tmp_path / "eval_results_codebase.jsonl"
        with open(results_path, "w") as f:
            for model in ("glm5.2", "qwen3.8-27b"):
                diff_id = "SC-1" if model == "glm5.2" else "SC-2"
                f.write(
                    json.dumps(
                        {
                            "diff_id": diff_id,
                            "model": model,
                            "skill": model,
                            "expected": "findings",
                            "findings": [
                                {
                                    "file": "smallchat-server.c",
                                    "line": 45 if diff_id == "SC-1" else 100,
                                    "severity": "CRITICAL",
                                    "type": "correctness",
                                    "trigger": "unmatched",
                                    "issue": "bug",
                                    "fix": "fix",
                                    "scores": {
                                        "accuracy": 1.0,
                                        "prioritization": 1.0,
                                        "justification": 1.0,
                                        "actionability": 1.0,
                                    },
                                },
                            ],
                            "scores": {
                                "accuracy": 1.0,
                                "prioritization": 1.0,
                                "justification": 1.0,
                                "actionability": 1.0,
                            },
                            "refused": False,
                            "rep": 0,
                        }
                    )
                    + "\n"
                )

        out = tmp_path / "cross_matrix.md"
        result = subprocess.run(
            [
                sys.executable,
                str(RENDER),
                "--codebase",
                "--codebase-results",
                str(results_path),
                "--benchmark",
                str(benchmark),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, f"render failed: {result.stderr}"
        content = out.read_text()
        # The detailed listing section must appear
        assert "Bug Details by Consensus" in content
        # Each sole-discovery bug must be listed with its metadata and finder
        assert "SC-1" in content
        assert "SC-2" in content
        assert "use-after-free in handle_client" in content
        assert "fd leak in error path" in content
        assert "Sole Discovery (1/4 model)" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
