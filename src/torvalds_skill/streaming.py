"""Streaming corpus processing with generators for memory-efficient iteration."""

import json
import sys
from pathlib import Path
from typing import Iterable


def iter_jsonl(path: str):
    """Yield one parsed JSON object per line from a JSONL file.
    
    Skips blank lines. Yields None and prints warning for malformed JSON.
    """
    file_path = Path(path)
    if not file_path.exists():
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as e:
                print(f"Warning: malformed JSON at {path}:{line_num}: {e}", file=sys.stderr)
                yield None


def iter_moves(path: str):
    """Yield flattened move dicts from moves.jsonl.
    
    Each move in the nested 'moves' array becomes a separate yielded dict
    with email_message_id added from the parent record.
    """
    for record in iter_jsonl(path):
        if record is None:
            continue
        email_message_id = record.get('email_message_id')
        moves = record.get('moves', [])
        for move in moves:
            yield {
                'email_message_id': email_message_id,
                'category': move.get('category'),
                'severity': move.get('severity'),
                'trigger': move.get('trigger'),
                'principle': move.get('principle'),
                'quote': move.get('quote'),
            }


def iter_patterns(path: str):
    """Yield pattern dicts from patterns.json.
    
    patterns.json is a JSON array (not JSONL). Uses json.load as fallback.
    """
    file_path = Path(path)
    if not file_path.exists():
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            patterns = json.load(f)
            for pattern in patterns:
                yield pattern
        except json.JSONDecodeError as e:
            print(f"Warning: malformed JSON in {path}: {e}", file=sys.stderr)


def count_jsonl(path: str) -> int:
    """Count lines in a JSONL file without parsing JSON."""
    file_path = Path(path)
    if not file_path.exists():
        return 0
    
    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def write_jsonl(path: str, records: Iterable[dict]):
    """Write records to a JSONL file one at a time (streaming write).
    
    Flushes every 100 records.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        for i, record in enumerate(records):
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            if (i + 1) % 100 == 0:
                f.flush()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Streaming corpus processing demo")
    parser.add_argument("--demo", action="store_true", help="Show streaming stats")
    args = parser.parse_args()
    
    if args.demo:
        base = Path.cwd() / "data"
        moves_path = base / "moves.jsonl"
        patterns_path = base / "patterns.json"
        
        if moves_path.exists():
            lines = count_jsonl(str(moves_path))
            move_count = sum(1 for _ in iter_moves(str(moves_path)))
            print(f"moves.jsonl: {lines} lines, {move_count} moves (streamed)")
        
        if patterns_path.exists():
            pattern_count = sum(1 for _ in iter_patterns(str(patterns_path)))
            print(f"patterns.json: {pattern_count} patterns (streamed)")