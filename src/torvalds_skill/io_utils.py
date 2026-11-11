"""Shared I/O utilities for JSONL loading."""

import json
from pathlib import Path

from .matching import dedupe_records


def load_jsonl(path: Path) -> list[dict]:
    """Load JSONL file, returning empty list if missing or empty.

    Skips malformed JSON lines and applies deduplication.
    Superseded records are dropped: the eval pipeline appends a re-run next to a
    judge-failed record instead of overwriting it, so the same evaluation can
    appear twice. The last one written wins, which is how the resume index
    itself resolves the collision.
    """
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return dedupe_records(records)


def load_benchmark_records(path: str) -> list[dict]:
    """Load benchmark JSONL file.

    Skips malformed lines but does NOT apply deduplication (benchmark is curated).
    """
    path_obj = Path(path)
    if not path_obj.exists():
        return []

    records = []
    with open(path_obj, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records
