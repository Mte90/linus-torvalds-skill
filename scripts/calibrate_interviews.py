"""
calibrate_interviews.py — compute severity calibration from merged email + interview moves.

Reads data/moves.jsonl (email) and data/interview_moves.jsonl (interview),
computes unified calibration statistics, and writes data/calibration.json.

Usage:
    python -m scripts.calibrate_interviews
    python -m scripts.calibrate_interviews --email-moves data/moves.jsonl --interview-moves data/interview_moves.jsonl --output data/calibration.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CANONICAL_CATEGORIES = (
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
)

CANONICAL_SEVERITIES = (
    "reject",
    "request-changes",
    "nitpick",
    "approve",
    "discussion",
)

CATEGORY_REMAP = {
    "security": "correctness",
    "api": "api-stability",
    "api-design": "api-stability",
    "compatibility": "api-stability",
    "stability": "api-stability",
    "reliability": "correctness",
    "maintainability": "complexity",
    "readability": "style",
    "redundancy": "complexity",
    "debugging": "correctness",
    "design": "abstraction",
}

SEVERITY_REMAP = {
    "process": "discussion",
}

STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "is", "it", "that", "this", "and", "or",
    "for", "on", "with", "as", "by", "be", "not", "but", "from", "at", "if",
    "are", "was", "were", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "must", "shall", "they",
    "you", "we", "i", "he", "she", "code", "function", "use", "using", "used",
    "line", "patch", "patches", "change", "changes", "make", "makes", "made",
    "get", "set", "new", "one", "two", "first", "when", "then", "than", "so",
    "no", "yes", "all", "any", "some", "more", "most", "other", "such", "only",
    "own", "same", "very", "just", "also", "into", "out", "up", "down", "over",
    "about", "what", "which", "who", "how", "why", "where", "there", "here",
    "now", "still", "even", "ever", "never", "always", "like", "well",
    "proposal", "suggestion", "handling", "kernel", "add", "adds", "existing",
    "instead", "without", "after", "before", "case", "specific", "user",
    "bit", "page", "memory", "flag", "interface", "behavior", "logic",
    "support", "series", "commit", "merge", "pull", "request", "tree",
    "system", "check", "return", "error", "name", "type", "value", "data",
    "struct", "int", "char", "void", "null", "true", "false", "default",
    "field", "list", "point", "point", "call", "calls", "called", "calling",
    "passed", "passing", "takes", "taken", "give", "given", "want", "need",
    "way", "thing", "things", "stuff", "lot", "big", "small", "long", "short",
    "good", "bad", "right", "wrong", "better", "worse", "best", "worst",
    "real", "actually", "really", "simply", "basically", "actually", "fact",
    "problem", "problems", "issue", "issues", "bug", "bugs", "fix", "fixed",
    "fixes", "broken", "wrong", "correct", "correctly", "incorrect",
}


def clean_category(cat: str) -> str | None:
    if cat in CANONICAL_CATEGORIES:
        return cat
    return CATEGORY_REMAP.get(cat)


def clean_severity(sev: str) -> str | None:
    if sev in CANONICAL_SEVERITIES:
        return sev
    return SEVERITY_REMAP.get(sev)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z_]+", text.lower())
    return [t for t in tokens if len(t) > 2 and t not in STOPWORDS]


def load_moves_from_jsonl(moves_path: Path, source: str) -> list[dict]:
    moves = []
    with open(moves_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            date = d.get("email_date", "")
            year = int(date[:4]) if date[:4].isdigit() else None
            for m in d.get("moves", []):
                cat = clean_category(m.get("category", ""))
                sev = clean_severity(m.get("severity", ""))
                if cat is None or sev is None:
                    continue
                moves.append({
                    "trigger": m.get("trigger", ""),
                    "principle": m.get("principle", ""),
                    "response": m.get("response", ""),
                    "severity": sev,
                    "category": cat,
                    "year": year,
                    "source": source,
                })
    return moves


def load_moves(moves_path: Path) -> list[dict]:
    return load_moves_from_jsonl(moves_path, "email")


def load_interview_moves(interview_moves_path: Path) -> list[dict]:
    return load_moves_from_jsonl(interview_moves_path, "interview")


def compute_severity_by_category(moves: list[dict]) -> dict:
    cat_sev = defaultdict(Counter)
    for m in moves:
        cat_sev[m["category"]][m["severity"]] += 1

    result = {}
    for cat in CANONICAL_CATEGORIES:
        counts = cat_sev.get(cat, Counter())
        total = sum(counts.values())
        if total == 0:
            continue
        dist = {sev: counts.get(sev, 0) for sev in CANONICAL_SEVERITIES}
        percentages = {sev: round(100 * cnt / total, 1) for sev, cnt in dist.items()}
        dominant = max(dist, key=dist.get)
        result[cat] = {
            "total": total,
            "distribution": dist,
            "percentages": percentages,
            "dominant_severity": dominant,
            "reject_rate": percentages["reject"],
            "request_changes_rate": percentages["request-changes"],
            "nitpick_rate": percentages["nitpick"],
        }
    return result


def compute_temporal_trends(moves: list[dict]) -> dict:
    year_cat = defaultdict(Counter)
    year_sev = defaultdict(Counter)
    year_total = Counter()

    for m in moves:
        if m["year"] is None:
            continue
        year_cat[m["year"]][m["category"]] += 1
        year_sev[m["year"]][m["severity"]] += 1
        year_total[m["year"]] += 1

    years = sorted(year_total.keys())
    result = {
        "year_range": [years[0], years[-1]] if years else [],
        "total_per_year": {str(y): year_total[y] for y in years},
        "top_category_per_year": {},
        "reject_rate_per_year": {},
    }

    for y in years:
        top_cat = year_cat[y].most_common(1)[0][0]
        result["top_category_per_year"][str(y)] = top_cat
        total = year_total[y]
        rejects = year_sev[y].get("reject", 0)
        result["reject_rate_per_year"][str(y)] = round(100 * rejects / total, 1)

    return result


def compute_corpus_stats(moves: list[dict], email_count: int, interview_count: int) -> dict:
    sev_counts = Counter(m["severity"] for m in moves)
    cat_counts = Counter(m["category"] for m in moves)
    total = len(moves)

    return {
        "total_moves": total,
        "total_emails": email_count,
        "total_interviews": interview_count,
        "source_breakdown": {
            "email": email_count,
            "interview": interview_count,
        },
        "severity_distribution": {
            sev: {"count": sev_counts.get(sev, 0),
                  "percentage": round(100 * sev_counts.get(sev, 0) / total, 1)}
            for sev in CANONICAL_SEVERITIES
        },
        "category_distribution": {
            cat: {"count": cat_counts.get(cat, 0),
                  "percentage": round(100 * cat_counts.get(cat, 0) / total, 1)}
            for cat in CANONICAL_CATEGORIES
        },
    }


def calibrate_interviews(email_moves_path: str, interview_moves_path: str, output_path: str) -> dict:
    email_path = Path(email_moves_path)
    interview_path = Path(interview_moves_path)
    output = Path(output_path)

    if not email_path.exists():
        raise SystemExit(f"Email moves file not found: {email_path}")

    email_moves = load_moves(email_path)
    print(f"Loaded {len(email_moves)} clean email moves")

    if interview_path.exists():
        interview_moves = load_interview_moves(interview_path)
        print(f"Loaded {len(interview_moves)} clean interview moves")
    else:
        print(f"Warning: Interview moves file not found: {interview_path}. Falling back to email-only calibration.", file=sys.stderr)
        interview_moves = []

    all_moves = email_moves + interview_moves
    print(f"Total merged moves: {len(all_moves)}")

    calibration = {
        "corpus_stats": compute_corpus_stats(all_moves, len(email_moves), len(interview_moves)),
        "severity_by_category": compute_severity_by_category(all_moves),
        "temporal_trends": compute_temporal_trends(all_moves),
    }

    output.write_text(
        json.dumps(calibration, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote calibration to {output}")

    return calibration


def main():
    parser = argparse.ArgumentParser(
        description="Compute severity calibration from merged email + interview moves."
    )
    parser.add_argument(
        "--email-moves", type=str, default="data/moves.jsonl",
        help="Path to email moves.jsonl (default: data/moves.jsonl)",
    )
    parser.add_argument(
        "--interview-moves", type=str, default="data/interview_moves.jsonl",
        help="Path to interview moves.jsonl (default: data/interview_moves.jsonl)",
    )
    parser.add_argument(
        "--output", type=str, default="data/calibration.json",
        help="Output path (default: data/calibration.json)",
    )
    args = parser.parse_args()

    calibrate_interviews(args.email_moves, args.interview_moves, args.output)

    output_path = Path(args.output)
    calibration = json.loads(output_path.read_text(encoding="utf-8"))

    stats = calibration["corpus_stats"]
    print(f"\nCorpus: {stats['total_moves']} total moves ({stats['total_emails']} email, {stats['total_interviews']} interview)")
    print("Severity distribution:")
    for sev in CANONICAL_SEVERITIES:
        d = stats["severity_distribution"][sev]
        print(f"  {sev:20s} {d['count']:6d}  ({d['percentage']:.1f}%)")

    print("\nSeverity by category (reject rate):")
    for cat in CANONICAL_CATEGORIES:
        if cat in calibration["severity_by_category"]:
            c = calibration["severity_by_category"][cat]
            print(f"  {cat:20s} reject={c['reject_rate']:5.1f}%  "
                  f"req-changes={c['request_changes_rate']:5.1f}%  "
                  f"nitpick={c['nitpick_rate']:5.1f}%  (n={c['total']})")


if __name__ == "__main__":
    main()