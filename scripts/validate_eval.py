#!/usr/bin/env python3
"""
Validate eval_diffs.jsonl against the schema and project requirements.

Usage:
    python3 scripts/validate_eval.py [--eval data/eval_diffs.jsonl]
"""

import argparse
import json
import sys
from pathlib import Path

# Valid categories matching the skill calibration
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

# Valid severities matching the skill calibration
VALID_SEVERITIES = {"reject", "request-changes", "nitpick"}

# Valid expected values
VALID_EXPECTED = {"findings", "no-findings", "refuse-to-conclude"}

# Valid languages
VALID_LANGUAGES = {"c", "python", "rust"}

# Minimum records required
MIN_RECORDS = 30


def load_schema(schema_path: Path) -> dict:
    """Load JSON schema file."""
    with open(schema_path) as f:
        return json.load(f)


def load_eval(eval_path: Path) -> list[dict]:
    """Load JSONL eval file."""
    records = []
    with open(eval_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}") from e
    return records


def validate_record(record: dict, line_num: int) -> list[str]:
    """Validate a single eval record. Returns list of errors."""
    errors = []

    # Check required fields
    required_fields = ["id", "diff", "language", "file", "expected", "bugs"]
    for field in required_fields:
        if field not in record:
            errors.append(f"Line {line_num}: Missing required field '{field}'")

    if errors:
        return errors

    # Validate id format
    id_val = record.get("id", "")
    if not isinstance(id_val, str) or not id_val.startswith("DIFF-") or len(id_val) != 8:
        errors.append(f"Line {line_num}: Invalid id format '{id_val}' (expected DIFF-XXX)")

    # Validate diff
    diff_val = record.get("diff", "")
    if not isinstance(diff_val, str) or len(diff_val) < 100:
        errors.append(
            f"Line {line_num}: Diff must be a non-empty string with at least 100 characters"
        )

    # Check diff line count (10-40 lines)
    diff_lines = diff_val.split("\n")
    if len(diff_lines) < 10 or len(diff_lines) > 40:
        errors.append(f"Line {line_num}: Diff must have 10-40 lines, got {len(diff_lines)} lines")

    # Check no line > 2000 chars
    for i, line in enumerate(diff_lines):
        if len(line) > 2000:
            errors.append(
                f"Line {line_num}: Diff line {i + 1} exceeds 2000 characters ({len(line)} chars)"
            )

    # Validate language
    lang_val = record.get("language", "")
    if lang_val not in VALID_LANGUAGES:
        errors.append(
            f"Line {line_num}: Invalid language '{lang_val}' (must be one of {VALID_LANGUAGES})"
        )

    # Validate file
    file_val = record.get("file", "")
    if not isinstance(file_val, str) or not file_val.strip():
        errors.append(f"Line {line_num}: File must be a non-empty string")

    # Validate expected
    expected_val = record.get("expected", "")
    if expected_val not in VALID_EXPECTED:
        errors.append(
            f"Line {line_num}: Invalid expected '{expected_val}' (must be one of {VALID_EXPECTED})"
        )

    # Validate bugs
    bugs_val = record.get("bugs")
    if not isinstance(bugs_val, list):
        errors.append(f"Line {line_num}: Bugs must be an array")
    else:
        # For no-findings and refuse-to-conclude, bugs must be empty
        if expected_val in {"no-findings", "refuse-to-conclude"}:
            if len(bugs_val) != 0:
                errors.append(f"Line {line_num}: Bugs must be empty for expected='{expected_val}'")

        # Validate each bug
        for bug_idx, bug in enumerate(bugs_val):
            if not isinstance(bug, dict):
                errors.append(f"Line {line_num}: Bug {bug_idx + 1} must be an object")
                continue

            # Check required bug fields
            bug_required = ["line", "category", "severity", "description"]
            for field in bug_required:
                if field not in bug:
                    errors.append(
                        f"Line {line_num}: Bug {bug_idx + 1} missing required field '{field}'"
                    )

            if "line" in bug:
                line_val = bug.get("line")
                if not isinstance(line_val, int) or line_val < 1:
                    errors.append(
                        f"Line {line_num}: Bug {bug_idx + 1} has invalid line number {line_val}"
                    )

            if "category" in bug:
                cat_val = bug.get("category", "")
                if cat_val not in VALID_CATEGORIES:
                    errors.append(
                        f"Line {line_num}: Bug {bug_idx + 1} has invalid category '{cat_val}'"
                    )

            if "severity" in bug:
                sev_val = bug.get("severity", "")
                if sev_val not in VALID_SEVERITIES:
                    errors.append(
                        f"Line {line_num}: Bug {bug_idx + 1} has invalid severity '{sev_val}'"
                    )

            if "description" in bug:
                desc_val = bug.get("description", "")
                if not isinstance(desc_val, str) or not desc_val.strip():
                    errors.append(
                        f"Line {line_num}: Bug {bug_idx + 1} description must be non-empty"
                    )

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
                errors.append(f"Record {i + 1}: Missing required field '{field}' per schema")

        # Check for additional properties
        for key in record:
            if key not in schema_props:
                errors.append(f"Record {i + 1}: Unexpected field '{key}' not in schema")

    return errors


def validate_eval_requirements(records: list[dict]) -> list[str]:
    """Validate eval dataset meets minimum requirements."""
    errors = []

    # Check minimum entries
    if len(records) < MIN_RECORDS:
        errors.append(f"Eval dataset has {len(records)} entries, minimum is {MIN_RECORDS}")

    # Check all 3 expected values are present
    expected_values = set(r.get("expected", "") for r in records)
    missing_expected = VALID_EXPECTED - expected_values
    if missing_expected:
        errors.append(f"Eval dataset missing expected values: {missing_expected}")

    # Check findings subset has >= 8 categories
    findings_records = [r for r in records if r.get("expected") == "findings"]
    if findings_records:
        categories_in_findings = set()
        for record in findings_records:
            for bug in record.get("bugs", []):
                categories_in_findings.add(bug.get("category", ""))

        if len(categories_in_findings) < 8:
            errors.append(
                f"Findings subset covers {len(categories_in_findings)} categories, minimum is 8"
            )

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate eval_diffs.jsonl against schema and requirements"
    )
    parser.add_argument(
        "--eval",
        default="data/eval_diffs.jsonl",
        help="Path to eval JSONL file (default: data/eval_diffs.jsonl)",
    )
    parser.add_argument(
        "--schema",
        default="data/eval_diffs.schema.json",
        help="Path to JSON schema file (default: data/eval_diffs.schema.json)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    eval_path = project_root / args.eval
    schema_path = project_root / args.schema

    # Check file existence
    if not eval_path.exists():
        print(f"ERROR: Eval file not found: {eval_path}", file=sys.stderr)
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

    # Load eval
    try:
        records = load_eval(eval_path)
        print(f"✓ Loaded eval: {len(records)} records from {eval_path}")
    except Exception as e:
        print(f"ERROR: Failed to load eval: {e}", file=sys.stderr)
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

    # Eval requirements
    print("\nValidating eval requirements...")
    req_errors = validate_eval_requirements(records)
    if req_errors:
        print(f"✗ Eval requirements failed with {len(req_errors)} error(s):")
        for err in req_errors:
            print(f"  - {err}")
        sys.exit(1)

    print("✓ Eval requirements met")

    # Summary
    expected_counts = {}
    languages_covered = set()
    categories_covered = set()

    for record in records:
        expected = record.get("expected", "")
        expected_counts[expected] = expected_counts.get(expected, 0) + 1
        languages_covered.add(record.get("language", ""))
        for bug in record.get("bugs", []):
            categories_covered.add(bug.get("category", ""))

    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Total records: {len(records)}")
    print(f"Expected distribution: {expected_counts}")
    print(f"Languages covered: {len(languages_covered)} ({', '.join(sorted(languages_covered))})")
    print(
        f"Categories covered: {len(categories_covered)} ({', '.join(sorted(categories_covered))})"
    )
    print("=" * 50)
    print("✓ All validations passed!")

    sys.exit(0)


if __name__ == "__main__":
    main()
