"""
cluster.py — sample review moves by category for the distill LLM.

The original approach used lexical Jaccard clustering on principles. This
failed at scale: principles are LLM-generated freeform sentences, nearly
all unique, so lexical similarity is near zero even for semantically
identical principles ("don't break userspace" vs "we don't break existing
setups" share no words).

The fix: skip lexical clustering. Stratified-sample substantive moves per
category (diverse across year and severity, preferring longer responses
which carry more signal) and send them to the distill LLM, which does
semantic grouping in one pass — far better than Jaccard on freeform text.

Output: patterns.json with:
  - corpus statistics (honest counts)
  - samples_by_category: {cat: [{trigger, principle, response, severity, date}]}
  - the distill LLM finds themes from these raw moves
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from .models import iter_moves, CATEGORIES

# Moves per category in the distill prompt. 25 * 14 categories = 350 moves.
# At ~400 chars/move that's ~140K chars (~35K tokens) — safe context for gpt-oss-120b.
SAMPLES_PER_CATEGORY = 25

# Prefer substantive responses — longer responses carry more reviewing signal.
# Short "Ack"/"NACKed" replies are valid data points for severity stats but
# add little to the distill prompt. We sample from the top half by response length.
SUBSTANTIVE_FRACTION = 0.5


def _year_of(date_str: str) -> str:
    """Extract year from ISO date string for stratification."""
    return date_str[:4] if date_str else "unknown"


def _stratified_sample(moves: list, n: int, seed: int = 42) -> list:
    """Sample n moves with diversity across year and severity.

    Strategy: bucket by (year, severity), distribute n across buckets
    proportionally, pick randomly within each bucket. Falls back to
    random sample if buckets are too few.
    """
    if len(moves) <= n:
        return moves

    rng = random.Random(seed)
    buckets: dict[tuple, list] = defaultdict(list)
    for m in moves:
        buckets[(_year_of(m.email_date), m.severity)].append(m)

    # proportional allocation per bucket, at least 1 if bucket exists
    n_buckets = len(buckets)
    per_bucket = max(1, n // n_buckets)

    sampled = []
    for bucket in buckets.values():
        rng.shuffle(bucket)
        sampled.extend(bucket[:per_bucket])

    # if over-sampled, trim; if under, fill from remainder
    if len(sampled) > n:
        rng.shuffle(sampled)
        sampled = sampled[:n]
    elif len(sampled) < n:
        remaining = [m for m in moves if m not in sampled]
        rng.shuffle(remaining)
        sampled.extend(remaining[: n - len(sampled)])

    return sampled


def cluster_moves(moves_path: Path, output_path: Path, top_n: int = SAMPLES_PER_CATEGORY):
    """Sample moves by category and write patterns.json for distill."""
    moves = list(iter_moves(moves_path))
    total_moves = len(moves)

    # group by category
    by_category: dict[str, list] = defaultdict(list)
    for m in moves:
        by_category[m.category].append(m)

    samples_by_category: dict[str, list] = {}
    for cat in CATEGORIES:
        cat_moves = by_category.get(cat, [])
        if not cat_moves:
            continue

        # prefer substantive (longer) responses — more reviewing signal
        cat_moves.sort(key=lambda m: len(m.response), reverse=True)
        substantive = cat_moves[: max(1, int(len(cat_moves) * SUBSTANTIVE_FRACTION))]

        sampled = _stratified_sample(substantive, top_n, seed=42)

        samples_by_category[cat] = [
            {
                "trigger": m.trigger,
                "principle": m.principle,
                "response": m.response,
                "severity": m.severity,
                "date": m.email_date,
            }
            for m in sampled
        ]

    output = {
        "total_moves": total_moves,
        "categories": {
            cat: len(by_category.get(cat, []))
            for cat in CATEGORIES
            if by_category.get(cat)
        },
        "severity_distribution": dict(Counter(m.severity for m in moves)),
        "samples_per_category": top_n,
        "samples_by_category": samples_by_category,
    }

    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"sampled {total_moves} moves: {sum(len(v) for v in samples_by_category.values())} samples across {len(samples_by_category)} categories")
    print(f"categories: {output['categories']}")
    print(f"severities: {output['severity_distribution']}")

    return output
