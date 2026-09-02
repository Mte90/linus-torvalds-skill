#!/usr/bin/env python3
"""
Tests for benchmark dataset validation.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent
BENCHMARK_PATH = PROJECT_ROOT / "data" / "benchmark.jsonl"
SCHEMA_PATH = PROJECT_ROOT / "data" / "benchmark.schema.json"
VALIDATE_SCRIPT = PROJECT_ROOT / "scripts" / "validate_benchmark.py"


class TestSchemaValidation:
    """Test schema structure and validity."""

    def test_schema_file_exists(self):
        """Schema file should exist."""
        assert SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}"

    def test_schema_is_valid_json(self):
        """Schema file should be valid JSON."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        assert isinstance(schema, dict)

    def test_schema_has_required_fields(self):
        """Schema should define required fields."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        assert "required" in schema
        required_fields = schema["required"]
        assert "id" in required_fields
        assert "file" in required_fields
        assert "line" in required_fields
        assert "severity" in required_fields
        assert "category" in required_fields
        assert "trigger" in required_fields
        assert "description" in required_fields
        assert "expected_severity" in required_fields

    def test_schema_severity_enum(self):
        """Schema should define valid severities."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        severity_enum = schema["properties"]["severity"]["enum"]
        assert "reject" in severity_enum
        assert "request-changes" in severity_enum
        assert "nitpick" in severity_enum

    def test_schema_category_enum(self):
        """Schema should define valid categories."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        category_enum = schema["properties"]["category"]["enum"]
        expected_categories = [
            "api-stability",
            "performance",
            "correctness",
            "complexity",
            "style",
            "process",
            "error-handling",
            "concurrency",
            "memory-safety",
            "abstraction",
            "testing",
            "documentation",
            "other",
        ]
        for cat in expected_categories:
            assert cat in category_enum, f"Missing category: {cat}"


class TestFileLoading:
    """Test benchmark file loading and structure."""

    @pytest.fixture
    def benchmark_records(self):
        """Load benchmark records for testing."""
        if not BENCHMARK_PATH.exists():
            pytest.skip(f"Benchmark file not found: {BENCHMARK_PATH}")
        records = []
        with open(BENCHMARK_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def test_benchmark_file_exists(self):
        """Benchmark file should exist."""
        assert BENCHMARK_PATH.exists(), f"Benchmark file not found: {BENCHMARK_PATH}"

    def test_benchmark_is_valid_jsonl(self, benchmark_records):
        """Benchmark file should be valid JSONL."""
        assert isinstance(benchmark_records, list)
        assert len(benchmark_records) > 0

    def test_each_record_is_dict(self, benchmark_records):
        """Each record should be a dictionary."""
        for i, record in enumerate(benchmark_records):
            assert isinstance(record, dict), f"Record {i} is not a dict"

    def test_records_have_required_fields(self, benchmark_records):
        """All records should have required fields."""
        required_fields = [
            "id",
            "file",
            "line",
            "severity",
            "category",
            "trigger",
            "description",
            "expected_severity",
        ]
        for i, record in enumerate(benchmark_records):
            for field in required_fields:
                assert field in record, f"Record {i} missing field: {field}"


class TestBenchmarkRequirements:
    """Test benchmark meets minimum requirements."""

    @pytest.fixture
    def benchmark_records(self):
        """Load benchmark records for testing."""
        if not BENCHMARK_PATH.exists():
            pytest.skip(f"Benchmark file not found: {BENCHMARK_PATH}")
        records = []
        with open(BENCHMARK_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def test_minimum_entries(self, benchmark_records):
        """Benchmark should have at least 30 entries."""
        assert len(benchmark_records) >= 30, (
            f"Benchmark has {len(benchmark_records)} entries, minimum is 30"
        )

    def test_file_coverage(self, benchmark_records):
        """Benchmark should cover at least 8 files."""
        files = set(r["file"] for r in benchmark_records)
        assert len(files) >= 8, f"Benchmark covers {len(files)} files, minimum is 8"

    def test_severity_coverage(self, benchmark_records):
        """Benchmark should cover all 3 severities."""
        severities = set(r["severity"] for r in benchmark_records)
        expected = {"reject", "request-changes", "nitpick"}
        assert expected.issubset(severities), f"Missing severities: {expected - severities}"

    def test_category_coverage(self, benchmark_records):
        """Benchmark should cover at least 8 categories."""
        categories = set(r["category"] for r in benchmark_records)
        assert len(categories) >= 8, f"Benchmark covers {len(categories)} categories, minimum is 8"

    def test_line_numbers_positive(self, benchmark_records):
        """All line numbers should be positive."""
        for i, record in enumerate(benchmark_records):
            assert record["line"] > 0, f"Record {i} has non-positive line number: {record['line']}"

    def test_id_format(self, benchmark_records):
        """All IDs should match SC-XXX format."""
        import re

        pattern = re.compile(r"^SC-\d{3}$")
        for i, record in enumerate(benchmark_records):
            assert pattern.match(record["id"]), f"Record {i} has invalid ID format: {record['id']}"

    def test_trigger_non_empty(self, benchmark_records):
        """All triggers should be non-empty."""
        for i, record in enumerate(benchmark_records):
            assert record["trigger"].strip(), f"Record {i} has empty trigger"

    def test_description_non_empty(self, benchmark_records):
        """All descriptions should be non-empty."""
        for i, record in enumerate(benchmark_records):
            assert record["description"].strip(), f"Record {i} has empty description"


class TestValidationScript:
    """Test the validation script."""

    def test_validation_script_exists(self):
        """Validation script should exist."""
        assert VALIDATE_SCRIPT.exists(), f"Validation script not found: {VALIDATE_SCRIPT}"

    def test_validation_script_runs(self):
        """Validation script should run successfully."""
        result = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"Validation script failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    def test_validation_script_with_explicit_path(self):
        """Validation script should work with explicit benchmark path."""
        result = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), "--benchmark", "data/benchmark.jsonl"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"Validation script failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )


class TestSeverityConsistency:
    """Test severity consistency across records."""

    @pytest.fixture
    def benchmark_records(self):
        """Load benchmark records for testing."""
        if not BENCHMARK_PATH.exists():
            pytest.skip(f"Benchmark file not found: {BENCHMARK_PATH}")
        records = []
        with open(BENCHMARK_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def test_severity_matches_expected(self, benchmark_records):
        """severity field should match expected_severity."""
        for i, record in enumerate(benchmark_records):
            assert record["severity"] == record["expected_severity"], (
                f"Record {i} severity mismatch: {record['severity']} != {record['expected_severity']}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
