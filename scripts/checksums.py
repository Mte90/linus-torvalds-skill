#!/usr/bin/env python3
"""SHA256 checksum management for pipeline intermediate files."""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Pipeline intermediate files to track
PIPELINE_FILES = [
    "moves.jsonl",
    "patterns.json",
    "calibration.json",
    "interview_moves.jsonl",
    "interviews_classified.jsonl",
    "skip_list.json",
]

CHUNK_SIZE = 64 * 1024  # 64KB chunks for memory efficiency


def compute_checksum(path: str) -> str:
    """Compute SHA256 hash of a file, reading in 64KB chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_checksums(data_dir: str = "data") -> dict:
    """Compute checksums for all pipeline intermediate files.

    Returns dict mapping filename to SHA256 hash.
    Skips missing files with a warning to stderr.
    """
    data_path = Path(data_dir)
    checksums = {}

    for filename in PIPELINE_FILES:
        filepath = data_path / filename
        if not filepath.exists():
            print(f"Warning: {filename} not found, skipping", file=sys.stderr)
            continue
        checksums[filename] = compute_checksum(str(filepath))

    return checksums


def write_checksums(data_dir: str = "data", output_path: str = "data/checksums.json") -> None:
    """Generate checksums and write to JSON file with metadata."""
    checksums = generate_checksums(data_dir)
    data_path = Path(data_dir)

    # Build output with metadata
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }

    for filename, sha256 in checksums.items():
        filepath = data_path / filename
        output["files"][filename] = {
            "sha256": sha256,
            "size_bytes": filepath.stat().st_size,
        }

    # Write pretty-printed JSON
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    print(f"Generated checksums for {len(checksums)} files")
    print(f"Output: {output_path}")


def verify_checksums(data_dir: str = "data", checksums_path: str = "data/checksums.json") -> tuple[bool, list[str]]:
    """Verify file checksums against stored values.

    Returns (all_valid, mismatches) where mismatches includes:
    - Missing files
    - Checksum mismatches
    - New files not in checksums
    """
    data_path = Path(data_dir)
    checksums_file = Path(checksums_path)
    mismatches = []

    if not checksums_file.exists():
        print(f"Error: Checksums file not found: {checksums_path}", file=sys.stderr)
        return False, ["Checksums file not found"]

    with open(checksums_file) as f:
        stored = json.load(f)

    stored_files = stored.get("files", {})

    # Check each stored file
    for filename, info in stored_files.items():
        filepath = data_path / filename
        if not filepath.exists():
            mismatches.append(f"{filename}: file missing")
            continue

        current_hash = compute_checksum(str(filepath))
        if current_hash != info["sha256"]:
            mismatches.append(f"{filename}: checksum mismatch")

    # Check for new files not in checksums
    for filename in PIPELINE_FILES:
        filepath = data_path / filename
        if filepath.exists() and filename not in stored_files:
            mismatches.append(f"{filename}: new file not in checksums")

    return len(mismatches) == 0, mismatches


def update_checksums(data_dir: str = "data") -> None:
    """Update checksums file and print summary."""
    write_checksums(data_dir)
    _, mismatches = verify_checksums(data_dir)
    if mismatches:
        print("Warning: Verification issues detected:", file=sys.stderr)
        for m in mismatches:
            print(f"  - {m}", file=sys.stderr)
    else:
        print("Verification: OK")


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: checksums.py <generate|verify|update>", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate":
        write_checksums()
    elif command == "verify":
        valid, mismatches = verify_checksums()
        if valid:
            print("All checksums valid")
        else:
            print("Checksum verification failed:", file=sys.stderr)
            for m in mismatches:
                print(f"  - {m}", file=sys.stderr)
            sys.exit(1)
    elif command == "update":
        update_checksums()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()