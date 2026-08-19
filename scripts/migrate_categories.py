#!/usr/bin/env python3
"""
migrate_categories.py — fix vocabulary drift and field-swap bugs in moves.jsonl.

Remaps non-canonical categories to the 14-category taxonomy:
  - debugging → correctness
  - design → abstraction
  - compatibility → api-stability
  - api-design → api-stability
  - stability → api-stability
  - api → api-stability
  - maintainability → complexity
  - redundancy → complexity
  - reliability → error-handling
  - readability → style

Fixes the field-swap bug at line 4808, move 3 where severity="process".

Usage:
    python scripts/migrate_categories.py              # Apply changes
    python scripts/migrate_categories.py --dry-run    # Preview without writing
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

# Vocabulary drift remapping
CATEGORY_REMAP = {
    "debugging": "correctness",
    "design": "abstraction",
    "compatibility": "api-stability",
    "api-design": "api-stability",
    "stability": "api-stability",
    "api": "api-stability",
    "maintainability": "complexity",
    "redundancy": "complexity",
    "reliability": "error-handling",
    "readability": "style",
}

# Field-swap bug fix: line 4808, move 3 has severity="process" (a category name)
# The trigger/principle is about "commit only after someone reports it works"
# This is a process gate → severity should be "discussion"
FIELD_SWAP_FIX = {
    "email_message_id": "<Pine.LNX.4.58.0409251513290.2317@ppc970.osdl.org>",
    "move_index": 2,  # 0-based index (3rd move)
    "correct_severity": "discussion",
}


def migrate_record(record: dict) -> tuple[dict, list[str]]:
    """Migrate a single record, returning the migrated record and list of changes."""
    changes = []
    migrated = record.copy()
    moves = migrated.get("moves", [])
    
    for i, move in enumerate(moves):
        move_changes = []
        old_category = move.get("category", "")
        old_severity = move.get("severity", "")
        
        # Check for field-swap bug
        if (
            record.get("email_message_id") == FIELD_SWAP_FIX["email_message_id"]
            and i == FIELD_SWAP_FIX["move_index"]
            and old_severity == "process"
        ):
            move["severity"] = FIELD_SWAP_FIX["correct_severity"]
            move_changes.append(
                f"move {i+1}: severity '{old_severity}' → '{FIELD_SWAP_FIX['correct_severity']}' (field-swap fix)"
            )
        
        # Remap category
        if old_category in CATEGORY_REMAP:
            move["category"] = CATEGORY_REMAP[old_category]
            move_changes.append(
                f"move {i+1}: category '{old_category}' → '{CATEGORY_REMAP[old_category]}'"
            )
        
        if move_changes:
            changes.extend(move_changes)
    
    return migrated, changes


def main():
    parser = argparse.ArgumentParser(
        description="Migrate moves.jsonl to canonical 14-category taxonomy."
    )
    parser.add_argument(
        "--moves",
        type=Path,
        default=Path("data/moves.jsonl"),
        help="Path to moves.jsonl (default: data/moves.jsonl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing",
    )
    args = parser.parse_args()
    
    if not args.moves.exists():
        raise SystemExit(f"Moves file not found: {args.moves}")
    
    # Backup the file
    backup_path = args.moves.with_suffix(".jsonl.bak")
    if not args.dry_run:
        shutil.copy2(args.moves, backup_path)
        print(f"backed up {args.moves} → {backup_path}")
    
    # Read and migrate
    records = []
    all_changes = []
    
    with open(args.moves, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            migrated, changes = migrate_record(record)
            records.append(migrated)
            if changes:
                all_changes.append((line_num, changes))
    
    # Print summary
    total_migrated = len(all_changes)
    total_moves_affected = sum(len(changes) for _, changes in all_changes)
    
    print(f"\nmigration summary:")
    print(f"  records with changes: {total_migrated}")
    print(f"  total moves remapped: {total_moves_affected}")
    
    if all_changes:
        print(f"\ndetails:")
        for line_num, changes in all_changes[:10]:  # Show first 10
            for change in changes:
                print(f"  line {line_num}: {change}")
        if len(all_changes) > 10:
            print(f"  ... and {len(all_changes) - 10} more")
    
    if args.dry_run:
        print(f"\ndry-run: no changes written")
        return 0
    
    # Write migrated data
    with open(args.moves, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    print(f"\nwrote migrated data to {args.moves}")
    return 0


if __name__ == "__main__":
    exit(main())