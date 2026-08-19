"""
cluster_interviews.py — merge email and interview moves, sample by category+severity.

Reads both data/moves.jsonl (email) and data/interview_moves.jsonl (interview),
flattens into unified moves with source field, performs stratified sampling
(25 per category × 14 categories = 350 patterns), writes merged patterns.json.

Falls back to email-only if interview_moves.jsonl is missing.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from .models import CATEGORIES

SAMPLES_PER_CATEGORY = 25


def _load_email_moves(moves_path: Path) -> list[dict]:
    """Load email moves from jsonl file. Each line has email_message_id, email_date, moves[]."""
    moves = []
    with open(moves_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            email_date = record.get("email_date", "")
            for move in record.get("moves", []):
                moves.append({
                    "category": move["category"],
                    "severity": move["severity"],
                    "trigger": move["trigger"],
                    "principle": move["principle"],
                    "quote": move["response"],
                    "source": "email",
                    "email_date": email_date,
                })
    return moves


def _load_interview_moves(moves_path: Path) -> list[dict]:
    """Load interview moves from jsonl file. Each line has passage_id, source_file, moves[]."""
    moves = []
    with open(moves_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            for move in record.get("moves", []):
                moves.append({
                    "category": move["category"],
                    "severity": move["severity"],
                    "trigger": move["trigger"],
                    "principle": move["principle"],
                    "quote": move.get("response", move.get("quote", "")),
                    "source": "interview",
                })
    return moves


def _stratified_sample_diverse(
    moves_by_cat_sev: dict[tuple[str, str], list[dict]],
    target_per_category: int,
    rng: random.Random,
) -> list[dict]:
    """Sample target_per_category moves per category with source diversity.

    For each category, distribute sampling across severities and ensure
    both email and interview sources are represented when possible.
    """
    all_sampled = []

    # Only sample from the 13 standard categories
    for category in CATEGORIES:
        cat_moves = []
        # Get all severities present for this category
        for (cat, sev), bucket in moves_by_cat_sev.items():
            if cat == category:
                cat_moves.extend(bucket)

        if not cat_moves:
            continue

        # Group by source for diversity
        by_source = defaultdict(list)
        for m in cat_moves:
            by_source[m["source"]].append(m)

        # Target samples from each source (prioritize balance)
        sources = list(by_source.keys())
        if len(sources) == 1:
            # Only one source available
            source_samples = {sources[0]: target_per_category}
        else:
            # Split roughly evenly, prefer interview if available
            interview_target = min(len(by_source.get("interview", [])), target_per_category // 2 + target_per_category % 2)
            email_target = min(len(by_source.get("email", [])), target_per_category - interview_target)
            source_samples = {"interview": interview_target, "email": email_target}

        # Sample from each source
        cat_sampled = []
        for source, target in source_samples.items():
            available = by_source.get(source, [])
            if target >= len(available):
                cat_sampled.extend(available)
            else:
                rng.shuffle(available)
                cat_sampled.extend(available[:target])

        # If under-sampled, fill from any source
        if len(cat_sampled) < target_per_category:
            current_ids = {id(m) for m in cat_sampled}
            remaining = [m for m in cat_moves if id(m) not in current_ids]
            rng.shuffle(remaining)
            needed = target_per_category - len(cat_sampled)
            cat_sampled.extend(remaining[:needed])

        # Trim if over-sampled
        if len(cat_sampled) > target_per_category:
            cat_sampled = cat_sampled[:target_per_category]

        all_sampled.extend(cat_sampled)

    return all_sampled


def cluster_interviews(email_moves_path: str, interview_moves_path: str, output_path: str) -> int:
    """Read email and interview moves, sample by category, write patterns.json.

    Args:
        email_moves_path: Path to data/moves.jsonl
        interview_moves_path: Path to data/interview_moves.jsonl
        output_path: Path to write data/patterns.json

    Returns:
        Count of patterns written
    """
    email_path = Path(email_moves_path)
    interview_path = Path(interview_moves_path)
    output = Path(output_path)

    # Load email moves
    if not email_path.exists():
        print(f"Error: email moves file not found: {email_path}", file=sys.stderr)
        return 0

    email_moves = _load_email_moves(email_path)

    # Load interview moves (optional)
    interview_moves = []
    if interview_path.exists():
        interview_moves = _load_interview_moves(interview_path)
    else:
        print(f"Warning: interview moves file not found: {interview_path}. Using email-only patterns.", file=sys.stderr)

    # Combine with source tracking
    all_moves = email_moves + interview_moves

    # Group by (category, severity)
    moves_by_cat_sev: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for m in all_moves:
        key = (m["category"], m["severity"])
        moves_by_cat_sev[key].append(m)

    # Sample with diversity
    rng = random.Random(42)
    sampled = _stratified_sample_diverse(moves_by_cat_sev, SAMPLES_PER_CATEGORY, rng)

    # Write output (strip internal fields)
    patterns = []
    for m in sampled:
        patterns.append({
            "category": m["category"],
            "severity": m["severity"],
            "trigger": m["trigger"],
            "principle": m["principle"],
            "quote": m["quote"],
            "source": m["source"],
        })

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)

    # Report stats
    email_count = sum(1 for p in patterns if p["source"] == "email")
    interview_count = sum(1 for p in patterns if p["source"] == "interview")
    cats = set(p["category"] for p in patterns)

    print(f"Total patterns: {len(patterns)}")
    print(f"Email: {email_count}, Interview: {interview_count}")
    print(f"Categories: {len(cats)}")

    return len(patterns)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cluster interview moves with email moves, sample by category"
    )
    parser.add_argument(
        "--email-moves",
        default="data/moves.jsonl",
        help="Path to email moves jsonl (default: data/moves.jsonl)"
    )
    parser.add_argument(
        "--interview-moves",
        default="data/interview_moves.jsonl",
        help="Path to interview moves jsonl (default: data/interview_moves.jsonl)"
    )
    parser.add_argument(
        "--output",
        default="data/patterns.json",
        help="Output patterns.json path (default: data/patterns.json)"
    )

    args = parser.parse_args()
    cluster_interviews(args.email_moves, args.interview_moves, args.output)