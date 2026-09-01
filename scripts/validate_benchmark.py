#!/usr/bin/env python3
"""
Validate benchmark.jsonl against the schema and project requirements.

Usage:
    python3 scripts/validate_benchmark.py [--benchmark data/benchmark.jsonl]
"""

import argparse
import json
import sys
from pathlib import Path


# Valid severities matching the skill calibration
VALID_SEVERITIES = {"reject", "request-changes", "nitpick"}

# Valid categories from calibration.json
VALID_CATEGORIES = {
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
}

# Valid SmallChat files
VALID_FILES = {"inputbuffer.c", "terminal.c", "chat-common.c", "smallchat-server.c", "smallchat-client.c", "chatlib.c", "chatlib.h", "Makefile"}

# SmallChat line range (approximate)
MIN_LINE = 1
MAX_LINE = 706


def load_schema(schema_path: Path) -> dict:
    """Load JSON schema file."""
    with open(schema_path, "r") as f:
        return json.load(f)


def load_benchmark(benchmark_path: Path) -> list[dict]:
    """Load JSONL benchmark file."""
    records = []
    with open(benchmark_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}")
    return records


def validate_record(record: dict, line_num: int) -> list[str]:
    """Validate a single benchmark record. Returns list of errors."""
    errors = []

    # Check required fields
    required_fields = ["id", "file", "line", "severity", "category", "trigger", "description", "expected_severity"]
    for field in required_fields:
        if field not in record:
            errors.append(f"Line {line_num}: Missing required field '{field}'")

    if errors:
        return errors

    # Validate id format
    id_val = record.get("id", "")
    if not isinstance(id_val, str) or not id_val.startswith("SC-") or len(id_val) != 6:
        errors.append(f"Line {line_num}: Invalid id format '{id_val}' (expected SC-XXX)")

    # Validate file
    file_val = record.get("file", "")
    if file_val not in VALID_FILES:
        errors.append(f"Line {line_num}: Invalid file '{file_val}' (must be one of {VALID_FILES})")

    # Validate line number
    line_val = record.get("line")
    if not isinstance(line_val, int) or line_val < MIN_LINE or line_val > MAX_LINE:
        errors.append(f"Line {line_num}: Invalid line number {line_val} (must be {MIN_LINE}-{MAX_LINE})")

    # Validate severity
    severity_val = record.get("severity", "")
    if severity_val not in VALID_SEVERITIES:
        errors.append(f"Line {line_num}: Invalid severity '{severity_val}' (must be one of {VALID_SEVERITIES})")

    # Validate category
    category_val = record.get("category", "")
    if category_val not in VALID_CATEGORIES:
        errors.append(f"Line {line_num}: Invalid category '{category_val}' (must be one of {VALID_CATEGORIES})")

    # Validate trigger
    trigger_val = record.get("trigger", "")
    if not isinstance(trigger_val, str) or not trigger_val.strip():
        errors.append(f"Line {line_num}: Trigger must be a non-empty string")

    # Validate description
    desc_val = record.get("description", "")
    if not isinstance(desc_val, str) or not desc_val.strip():
        errors.append(f"Line {line_num}: Description must be a non-empty string")

    # Validate expected_severity
    expected_val = record.get("expected_severity", "")
    if expected_val not in VALID_SEVERITIES:
        errors.append(f"Line {line_num}: Invalid expected_severity '{expected_val}' (must be one of {VALID_SEVERITIES})")

    # Check consistency between severity and expected_severity
    if severity_val != expected_val:
        errors.append(f"Line {line_num}: severity '{severity_val}' does not match expected_severity '{expected_val}'")

    return errors


def validate_schema_conformance(records: list[dict], schema: dict) -> list[str]:
    """Basic schema conformance check (without external jsonschema library)."""
    errors = []
    schema_props = schema.get("properties", {})
    schema_required = schema.get("required", [])

    for i, record in enumerate(records):
        # Check required fields
        for field in schema_required:
            if field not in record:
                errors.append(f"Record {i+1}: Missing required field '{field}' per schema")

        # Check for additional properties
        for key in record:
            if key not in schema_props:
                errors.append(f"Record {i+1}: Unexpected field '{key}' not in schema")

    return errors


def validate_benchmark_requirements(records: list[dict]) -> list[str]:
    """Validate benchmark meets minimum requirements."""
    errors = []

    # Check minimum entries
    if len(records) < 30:
        errors.append(f"Benchmark has {len(records)} entries, minimum is 30")

    # Check file coverage (at least 8 files)
    files_covered = set(r.get("file", "") for r in records)
    if len(files_covered) < 8:
        errors.append(f"Benchmark covers {len(files_covered)} files, minimum is 8")

    # Check severity coverage (all 3 severities)
    severities_covered = set(r.get("severity", "") for r in records)
    missing_severities = VALID_SEVERITIES - severities_covered
    if missing_severities:
        errors.append(f"Benchmark missing severities: {missing_severities}")

    # Check category coverage (at least 8 categories)
    categories_covered = set(r.get("category", "") for r in records)
    if len(categories_covered) < 8:
        errors.append(f"Benchmark covers {len(categories_covered)} categories, minimum is 8")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate benchmark.jsonl against schema and requirements")
    parser.add_argument(
        "--benchmark",
        default="data/benchmark.jsonl",
        help="Path to benchmark JSONL file (default: data/benchmark.jsonl)",
    )
    parser.add_argument(
        "--schema",
        default="data/benchmark.schema.json",
        help="Path to JSON schema file (default: data/benchmark.schema.json)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    benchmark_path = project_root / args.benchmark
    schema_path = project_root / args.schema

    # Check file existence
    if not benchmark_path.exists():
        print(f"ERROR: Benchmark file not found: {benchmark_path}", file=sys.stderr)
        sys.exit(1)

    if not schema_path.exists():
        print(f"ERROR: Schema file not found: {schema_path}", file=sys.stderr)
        sys.exit(1)

    all_errors = []

    # Load schema
    try:
        schema = load_schema(schema_path)
        print(f"✓ Loaded schema: {schema_path}")
    except Exception as e:
        print(f"ERROR: Failed to load schema: {e}", file=sys.stderr)
        sys.exit(1)

    # Load benchmark
    try:
        records = load_benchmark(benchmark_path)
        print(f"✓ Loaded benchmark: {len(records)} records from {benchmark_path}")
    except Exception as e:
        print(f"ERROR: Failed to load benchmark: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate each record
    print("\nValidating individual records...")
    for i, record in enumerate(records):
        errors = validate_record(record, i + 1)
        all_errors.extend(errors)

    if all_errors:
        print(f"✗ Record validation failed with {len(all_errors)} error(s):")
        for err in all_errors:
            print(f"  - {err}")
        sys.exit(1)

    print("✓ All records passed field validation")

    # Schema conformance
    print("\nValidating schema conformance...")
    schema_errors = validate_schema_conformance(records, schema)
    if schema_errors:
        print(f"✗ Schema conformance failed with {len(schema_errors)} error(s):")
        for err in schema_errors:
            print(f"  - {err}")
        sys.exit(1)

    print("✓ Schema conformance passed")

    # Benchmark requirements
    print("\nValidating benchmark requirements...")
    req_errors = validate_benchmark_requirements(records)
    if req_errors:
        print(f"✗ Benchmark requirements failed with {len(req_errors)} error(s):")
        for err in req_errors:
            print(f"  - {err}")
        sys.exit(1)

    print("✓ Benchmark requirements met")

    # Summary
    files_covered = set(r.get("file", "") for r in records)
    severities_covered = set(r.get("severity", "") for r in records)
    categories_covered = set(r.get("category", "") for r in records)

    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Total records: {len(records)}")
    print(f"Files covered: {len(files_covered)} ({', '.join(sorted(files_covered))})")
    print(f"Severities covered: {len(severities_covered)} ({', '.join(sorted(severities_covered))})")
    print(f"Categories covered: {len(categories_covered)} ({', '.join(sorted(categories_covered))})")
    print("=" * 50)
    print("✓ All validations passed!")

    sys.exit(0)


if __name__ == "__main__":
    main()