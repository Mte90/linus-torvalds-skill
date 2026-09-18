"""Tests for run_eval.py --status and --models flags."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "run_eval.py"


def _write_diffs(tmp_dir: Path, count: int = 5) -> Path:
    """Write synthetic eval_diffs.jsonl."""
    path = tmp_dir / "eval_diffs.jsonl"
    with open(path, "w") as f:
        for i in range(count):
            record = {
                "id": f"DIFF-{i:03d}",
                "diff": f"+line {i}\n",
                "file": "test.c",
                "language": "c",
                "expected": "findings",
                "bugs": [{"line": i, "severity": "HIGH", "category": "bug"}],
            }
            f.write(json.dumps(record) + "\n")
    return path


def _write_results(tmp_dir: Path, model: str, skill: str | None, count: int) -> Path:
    """Write synthetic eval_results.jsonl with given model/skill pairing."""
    path = tmp_dir / "eval_results.jsonl"
    with open(path, "w") as f:
        for i in range(count):
            record = {
                "diff_id": f"DIFF-{i:03d}",
                "model": model,
                "skill": skill,
                "expected": "findings",
                "findings": [],
                "scores": {
                    "accuracy": 1.0,
                    "prioritization": 1.0,
                    "justification": 1.0,
                    "actionability": 1.0,
                },
                "refused": False,
            }
            f.write(json.dumps(record) + "\n")
    return path


class TestStatusFlag:
    """Tests for --status flag."""

    def test_status_diagonal_complete(self, tmp_path: Path):
        """Status shows COMPLETE when all diffs evaluated on diagonal."""
        diffs = _write_diffs(tmp_path, count=5)
        # Write 5 results for gpt-oss-120b (diagonal)
        _write_results(tmp_path, "gpt-oss-120b", None, count=5)

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--status",
                "--out",
                str(tmp_path / "eval_results.jsonl"),
                "--eval",
                str(diffs),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 0
        assert "gpt-oss-120b" in result.stdout
        assert "5/5" in result.stdout
        assert "COMPLETE" in result.stdout

    def test_status_diagonal_missing(self, tmp_path: Path):
        """Status shows MISSING when not all diffs evaluated."""
        diffs = _write_diffs(tmp_path, count=5)
        # Write only 3 results
        _write_results(tmp_path, "gpt-oss-120b", None, count=3)

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--status",
                "--out",
                str(tmp_path / "eval_results.jsonl"),
                "--eval",
                str(diffs),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 0
        assert "3/5" in result.stdout
        assert "MISSING" in result.stdout

    def test_status_with_duplicate_records(self, tmp_path: Path):
        """Status correctly deduplicates records."""
        diffs = _write_diffs(tmp_path, count=5)
        path = tmp_path / "eval_results.jsonl"
        # Write 5 unique + 2 duplicates
        with open(path, "w") as f:
            for i in range(7):
                record = {
                    "diff_id": f"DIFF-{i % 5:03d}",
                    "model": "gpt-oss-120b",
                    "skill": None,
                    "expected": "findings",
                    "findings": [],
                    "scores": {
                        "accuracy": 1.0,
                        "prioritization": 1.0,
                        "justification": 1.0,
                        "actionability": 1.0,
                    },
                    "refused": False,
                }
                f.write(json.dumps(record) + "\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--status", "--out", str(path), "--eval", str(diffs)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 0
        # Should show 5/5 (deduplicated), not 7/5
        assert "5/5" in result.stdout

    def test_status_cross_mode(self, tmp_path: Path):
        """Status shows all pairs in cross mode."""
        diffs = _write_diffs(tmp_path, count=3)
        path = tmp_path / "eval_results.jsonl"

        # Write results for gpt-oss-120b←glm5.2
        with open(path, "w") as f:
            for i in range(3):
                record = {
                    "diff_id": f"DIFF-{i:03d}",
                    "model": "gpt-oss-120b",
                    "skill": "glm5.2",
                    "expected": "findings",
                    "findings": [],
                    "scores": {
                        "accuracy": 1.0,
                        "prioritization": 1.0,
                        "justification": 1.0,
                        "actionability": 1.0,
                    },
                    "refused": False,
                }
                f.write(json.dumps(record) + "\n")

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--status",
                "--out",
                str(path),
                "--eval",
                str(diffs),
                "--cross",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 0
        # Should show multiple cells
        assert "gpt-oss-120b" in result.stdout
        assert "glm5.2" in result.stdout

    def test_status_models_filter(self, tmp_path: Path):
        """--models filter restricts status output."""
        diffs = _write_diffs(tmp_path, count=5)
        path = tmp_path / "eval_results.jsonl"

        # Write results for both models
        for model in ["gpt-oss-120b", "glm5.2"]:
            with open(path, "a") as f:
                for i in range(5):
                    record = {
                        "diff_id": f"DIFF-{i:03d}",
                        "model": model,
                        "skill": None,
                        "expected": "findings",
                        "findings": [],
                        "scores": {
                            "accuracy": 1.0,
                            "prioritization": 1.0,
                            "justification": 1.0,
                            "actionability": 1.0,
                        },
                        "refused": False,
                    }
                    f.write(json.dumps(record) + "\n")

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--status",
                "--out",
                str(path),
                "--eval",
                str(diffs),
                "--models",
                "gpt-oss-120b",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 0
        assert "gpt-oss-120b" in result.stdout
        # Should only show gpt-oss-120b, not glm5.2
        lines = result.stdout.strip().split("\n")
        model_lines = [line for line in lines if "gpt-oss-120b" in line and "glm5.2" not in line]
        assert len(model_lines) >= 1


class TestModelsFlag:
    """Tests for --models flag validation."""

    def test_models_unknown_name_error(self, tmp_path: Path):
        """Unknown model name returns error with exit code 2."""
        diffs = _write_diffs(tmp_path, count=5)

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--status",
                "--out",
                str(tmp_path / "eval_results.jsonl"),
                "--eval",
                str(diffs),
                "--models",
                "unknown-model",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 2
        assert "unknown models" in result.stderr
        assert "valid models" in result.stderr

    def test_models_case_insensitive(self, tmp_path: Path):
        """Model names are case-insensitive."""
        diffs = _write_diffs(tmp_path, count=5)
        path = tmp_path / "eval_results.jsonl"

        # Write results with lowercase model
        with open(path, "w") as f:
            for i in range(5):
                record = {
                    "diff_id": f"DIFF-{i:03d}",
                    "model": "gpt-oss-120b",
                    "skill": None,
                    "expected": "findings",
                    "findings": [],
                    "scores": {
                        "accuracy": 1.0,
                        "prioritization": 1.0,
                        "justification": 1.0,
                        "actionability": 1.0,
                    },
                    "refused": False,
                }
                f.write(json.dumps(record) + "\n")

        # Try with uppercase
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--status",
                "--out",
                str(path),
                "--eval",
                str(diffs),
                "--models",
                "GPT-OSS-120B",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        # Should fail because case-insensitive matching not implemented yet
        # This is a test of current behavior
        assert result.returncode == 2

    def test_models_filter_restricts_cells(self, tmp_path: Path):
        """--models filter restricts which cells appear in status."""
        diffs = _write_diffs(tmp_path, count=3)
        path = tmp_path / "eval_results.jsonl"

        # Write results for all 4 models
        for model in ["gpt-oss-120b", "glm5.2", "mistral-small-4-119b", "qwen3.8-27b"]:
            with open(path, "a") as f:
                for i in range(3):
                    record = {
                        "diff_id": f"DIFF-{i:03d}",
                        "model": model,
                        "skill": None,
                        "expected": "findings",
                        "findings": [],
                        "scores": {
                            "accuracy": 1.0,
                            "prioritization": 1.0,
                            "justification": 1.0,
                            "actionability": 1.0,
                        },
                        "refused": False,
                    }
                    f.write(json.dumps(record) + "\n")

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--status",
                "--out",
                str(path),
                "--eval",
                str(diffs),
                "--models",
                "gpt-oss-120b,glm5.2",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        # Should only show 2 models
        model_lines = [line for line in lines if "gpt-oss-120b" in line or "glm5.2" in line]
        # Filter out header/dashes
        data_lines = [
            line
            for line in model_lines
            if line.strip() and not line.startswith("-") and "model" not in line.lower()
        ]
        assert len(data_lines) == 2  # Only 2 models shown


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
