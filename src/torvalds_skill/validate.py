"""
validate.py — JSON schema validation for pipeline intermediate files.

Validates moves.jsonl, patterns.json, and calibration.json against their schemas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .models import CATEGORIES, SEVERITIES

VALID_SEVERITIES = set(SEVERITIES)


def _validate_move(move: dict, line_num: int | None = None) -> list[str]:
    """Validate a single move object. Returns list of error strings."""
    errors = []
    prefix = f"Line {line_num}: " if line_num else ""

    required_fields = ["category", "severity", "trigger", "principle"]
    for field in required_fields:
        if field not in move:
            errors.append(f"{prefix}Missing required field: {field}")

    if "category" in move and move["category"] not in CATEGORIES:
        errors.append(
            f"{prefix}Invalid category '{move['category']}'. "
            f"Must be one of: {', '.join(CATEGORIES)}"
        )

    if "severity" in move and move["severity"] not in VALID_SEVERITIES:
        errors.append(
            f"{prefix}Invalid severity '{move['severity']}'. "
            f"Must be one of: {', '.join(sorted(VALID_SEVERITIES))}"
        )

    if "trigger" in move and not isinstance(move["trigger"], str):
        errors.append(f"{prefix}Field 'trigger' must be a string")

    if "principle" in move and not isinstance(move["principle"], str):
        errors.append(f"{prefix}Field 'principle' must be a string")

    if "quote" in move and not isinstance(move["quote"], str):
        errors.append(f"{prefix}Field 'quote' must be a string")

    return errors


def validate_moves(path: str) -> tuple[bool, list[str]]:
    """
    Validate moves.jsonl file.
    
    Returns (is_valid, errors) where errors is a list of human-readable error strings.
    """
    errors = []
    errors_path = Path(path)

    if not errors_path.exists():
        return False, [f"File not found: {path}"]

    try:
        with open(errors_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"Line {line_num}: Invalid JSON - {e}")
                    continue

                if "email_message_id" not in record:
                    errors.append(f"Line {line_num}: Missing required field 'email_message_id'")

                if "moves" not in record:
                    errors.append(f"Line {line_num}: Missing required field 'moves'")
                    continue

                if not isinstance(record["moves"], list):
                    errors.append(f"Line {line_num}: Field 'moves' must be an array")
                    continue

                for move in record["moves"]:
                    move_errors = _validate_move(move, line_num)
                    errors.extend(move_errors)

    except IOError as e:
        return False, [f"Error reading file: {e}"]

    return (len(errors) == 0, errors)


def validate_patterns(path: str) -> tuple[bool, list[str]]:
    """
    Validate patterns.json file.
    
    Returns (is_valid, errors) where errors is a list of human-readable error strings.
    """
    errors = []
    errors_path = Path(path)

    if not errors_path.exists():
        return False, [f"File not found: {path}"]

    try:
        with open(errors_path, encoding="utf-8") as f:
            patterns = json.load(f)

        if not isinstance(patterns, list):
            return False, ["File must contain a JSON array"]

        for idx, pattern in enumerate(patterns):
            if not isinstance(pattern, dict):
                errors.append(f"Pattern {idx}: Must be an object")
                continue

            required_fields = ["category", "severity", "trigger", "principle"]
            for field in required_fields:
                if field not in pattern:
                    errors.append(f"Pattern {idx}: Missing required field: {field}")

            if "category" in pattern and pattern["category"] not in CATEGORIES:
                errors.append(
                    f"Pattern {idx}: Invalid category '{pattern['category']}'. "
                    f"Must be one of: {', '.join(CATEGORIES)}"
                )

            if "severity" in pattern and pattern["severity"] not in VALID_SEVERITIES:
                errors.append(
                    f"Pattern {idx}: Invalid severity '{pattern['severity']}'. "
                    f"Must be one of: {', '.join(sorted(VALID_SEVERITIES))}"
                )

            if "trigger" in pattern and not isinstance(pattern["trigger"], str):
                errors.append(f"Pattern {idx}: Field 'trigger' must be a string")

            if "principle" in pattern and not isinstance(pattern["principle"], str):
                errors.append(f"Pattern {idx}: Field 'principle' must be a string")

            if "quote" in pattern and not isinstance(pattern["quote"], str):
                errors.append(f"Pattern {idx}: Field 'quote' must be a string")

            if "source" in pattern and pattern["source"] not in {"email", "interview"}:
                errors.append(
                    f"Pattern {idx}: Invalid source '{pattern['source']}'. "
                    "Must be 'email' or 'interview'"
                )

    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON - {e}"]
    except IOError as e:
        return False, [f"Error reading file: {e}"]

    return (len(errors) == 0, errors)


def validate_calibration(path: str) -> tuple[bool, list[str]]:
    """
    Validate calibration.json file.
    
    Returns (is_valid, errors) where errors is a list of human-readable error strings.
    """
    errors = []
    errors_path = Path(path)

    if not errors_path.exists():
        return False, [f"File not found: {path}"]

    try:
        with open(errors_path, encoding="utf-8") as f:
            calibration = json.load(f)

        if not isinstance(calibration, dict):
            return False, ["File must contain a JSON object"]

        required_fields = ["severity_by_category", "temporal_trends", "corpus_stats"]
        for field in required_fields:
            if field not in calibration:
                errors.append(f"Missing required field: {field}")
            elif not isinstance(calibration[field], dict):
                errors.append(f"Field '{field}' must be an object")

        if "corpus_stats" in calibration and isinstance(calibration["corpus_stats"], dict):
            if "total_moves" not in calibration["corpus_stats"]:
                errors.append("Field 'corpus_stats' must have 'total_moves' key")
            elif not isinstance(calibration["corpus_stats"]["total_moves"], int):
                errors.append("Field 'corpus_stats.total_moves' must be an integer")

    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON - {e}"]
    except IOError as e:
        return False, [f"Error reading file: {e}"]

    return (len(errors) == 0, errors)


def validate_all(data_dir: str = "data") -> tuple[bool, list[str]]:
    """
    Run all validators on the data directory.
    
    Returns (is_valid, errors) with aggregated results from all three validators.
    """
    all_errors = []
    data_path = Path(data_dir)

    validators = [
        ("moves.jsonl", validate_moves),
        ("patterns.json", validate_patterns),
        ("calibration.json", validate_calibration),
    ]

    for filename, validator in validators:
        filepath = data_path / filename
        is_valid, errors = validator(str(filepath))
        if not is_valid:
            all_errors.extend(errors)

    return (len(all_errors) == 0, all_errors)


if __name__ == "__main__":
    is_valid, errors = validate_all("data")

    if is_valid:
        print("All validation checks passed.")
        sys.exit(0)
    else:
        print(f"Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)