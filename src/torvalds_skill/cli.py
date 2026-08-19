"""
cli.py — pipeline orchestration: classify → extract → cluster → distill

Usage:
  python -m torvalds_skill classify
  python -m torvalds_skill extract --sample 2000 --workers 10
  python -m torvalds_skill cluster
  python -m torvalds_skill distill
  python -m torvalds_skill run --sample 2000 --workers 10
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import config
from .models import iter_corpus, EmailRecord
from .classify import is_review
from .extract import extract_moves
from .cluster import cluster_moves
from .distill import distill_skill
from .classify_interviews import classify_interviews
from .extract_interviews import extract_interviews
from .cluster_interviews import cluster_interviews
from .validate import validate_all

DATA = Path("data")
SKILL_DIR = Path("linus-torvalds-skill")

CORPUS = DATA / "corpus.jsonl"
REVIEWS = DATA / "reviews.jsonl"
MOVES = DATA / "moves.jsonl"
PATTERNS = DATA / "patterns.json"
CALIBRATION = DATA / "calibration.json"
SKILL = SKILL_DIR / "SKILL.md"
SKIP_LIST = DATA / "skip_list.json"
CHECKPOINT = DATA / "checkpoint.jsonl"


def _save_checkpoint(processed_ids: set[str]):
    """Persist processed email IDs for crash recovery."""
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        for msg_id in sorted(processed_ids):
            f.write(msg_id + "\n")


def _load_checkpoint() -> set[str]:
    """Load previously processed email IDs from checkpoint."""
    if CHECKPOINT.exists():
        with open(CHECKPOINT, encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()  # message_ids that returned 0 moves — skip on future runs


def _load_skip_list() -> set:
    if not SKIP_LIST.exists():
        return set()
    ids = set()
    try:
        for line in SKIP_LIST.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                ids.add(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return ids


def _save_skip_id(message_id: str) -> None:
    """Append a message_id to the skip list (line-delimited JSON for crash safety)."""
    with open(SKIP_LIST, "a", encoding="utf-8") as f:
        f.write(json.dumps(message_id, ensure_ascii=False) + "\n")


def stage_classify():
    """Filter corpus.jsonl → reviews.jsonl (only review emails)."""
    print("classifying corpus...")
    count = 0
    total = 0
    with open(REVIEWS, "w", encoding="utf-8") as f:
        for email in iter_corpus(CORPUS):
            total += 1
            if is_review(email):
                f.write(json.dumps({
                    "message_id": email.message_id,
                    "from_name": email.from_name,
                    "from_email": email.from_email,
                    "date": email.date,
                    "subject": email.subject,
                    "in_reply_to": email.in_reply_to,
                    "body": email.body,
                }, ensure_ascii=False) + "\n")
                count += 1
    print(f"  {count}/{total} emails are reviews ({count/total*100:.1f}%)")
    print(f"  → {REVIEWS}")


def _sample_reviews(sample_size: int) -> list[EmailRecord]:
    """Stratified sample: by year and body length."""
    all_reviews = list(iter_corpus(REVIEWS))
    print(f"  {len(all_reviews)} reviews available")

    if sample_size <= 0 or sample_size >= len(all_reviews):
        print(f"  using all {len(all_reviews)} reviews")
        return all_reviews

    # bucket by year
    by_year: dict[str, list[EmailRecord]] = {}
    for r in all_reviews:
        year = r.date[:4] if r.date else "unknown"
        by_year.setdefault(year, []).append(r)

    # within each year, prefer longer bodies (more signal)
    for year in by_year:
        by_year[year].sort(key=lambda r: len(r.body), reverse=True)

    # distribute sample_size across years, weighted by count
    total = len(all_reviews)
    sample = []
    for year, emails in sorted(by_year.items()):
        n = max(1, int(sample_size * len(emails) / total))
        sample.extend(emails[:n])

    # trim or pad
    if len(sample) > sample_size:
        sample = sample[:sample_size]
    elif len(sample) < sample_size:
        remaining = [r for r in all_reviews if r not in sample]
        random.shuffle(remaining)
        sample.extend(remaining[:sample_size - len(sample)])

    print(f"  sampled {len(sample)} reviews (stratified by year + body length)")
    return sample


def stage_extract(sample_size: int, workers: int, resume: bool):
    """Extract review moves from sampled emails → moves.jsonl."""
    reviews = _sample_reviews(sample_size)

    mode = "a" if resume else "w"
    done_ids = set()
    if resume and MOVES.exists():
        with open(MOVES, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done_ids.add(json.loads(line).get("email_message_id"))
        reviews = [r for r in reviews if r.message_id not in done_ids]
        print(f"  resuming: {len(done_ids)} already done")

    # Skip list: emails that previously returned 0 moves (announcements, git-pulls, etc.)
    skip_ids = _load_skip_list() if resume else set()
    if skip_ids:
        before = len(reviews)
        reviews = [r for r in reviews if r.message_id not in skip_ids]
        print(f"  skip list: {len(skip_ids)} known 0-move emails, {before - len(reviews)} skipped")

    if done_ids or skip_ids:
        print(f"  {len(reviews)} remaining to process")

    if not reviews:
        print("  nothing to do")
        return

    print(f"  extracting moves from {len(reviews)} emails with {workers} workers...")

    total = len(reviews)
    processed = 0
    moves_count = 0
    errors = 0
    checkpoint_interval = 1000  # save checkpoint every N emails
    processed_ids = set()  # track IDs for checkpoint
    start_time = time.time()

    def write_result(result):
        with open(MOVES, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    batch_size = workers * 3

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(0, total, batch_size):
            batch = reviews[i:i + batch_size]
            futures = {pool.submit(extract_moves, email): email for email in batch}

            for future in as_completed(futures):
                result = future.result()
                write_result(result)
                processed += 1
                if result.get("error"):
                    errors += 1
                else:
                    n_moves = len(result.get("moves", []))
                    moves_count += n_moves
                    # Persist 0-move emails to skip list for future runs
                    if n_moves == 0 and result.get("email_message_id"):
                        _save_skip_id(result["email_message_id"])
                    # Track processed ID for checkpoint
                    if result.get("email_message_id"):
                        processed_ids.add(result["email_message_id"])

                if processed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (total - processed) / rate if rate > 0 else 0
                    print(
                        f"  {processed}/{total} — "
                        f"{moves_count} moves, {errors} errors — "
                        f"{rate:.1f}/s, ETA {eta:.0f}s"
                    )

                # Save checkpoint every N emails
                if processed % checkpoint_interval == 0 and processed > 0:
                    _save_checkpoint(processed_ids)
                    print(f"  checkpoint: {len(processed_ids)} emails persisted")

    elapsed = time.time() - start_time
    print(
        f"done: {processed} emails, {moves_count} moves, "
        f"{errors} errors in {elapsed:.0f}s"
    )


def stage_cluster():
    """Cluster moves.jsonl → patterns.json."""
    if not MOVES.exists():
        print(f"error: {MOVES} not found. Run extract first.")
        sys.exit(1)
    cluster_moves(MOVES, PATTERNS)


def stage_distill(top_n: int, model: str = None, out: str = None):
    """Distill patterns.json → SKILL.md (or custom output path)."""
    if not PATTERNS.exists():
        print(f"error: {PATTERNS} not found. Run cluster first.")
        sys.exit(1)
    target = Path(out) if out else SKILL
    distill_skill(PATTERNS, target, top_n=top_n, model=model,
                  calibration_path=CALIBRATION)


def stage_run(sample_size: int, workers: int):
    """Run the full pipeline."""
    stage_classify()
    stage_extract(sample_size, workers, resume=False)
    stage_cluster()
    stage_distill(top_n=40)


def stage_interviews_pipeline(model: str, resume: bool):
    """Run the full interview pipeline: classify → extract → cluster → calibrate."""
    # Step 1: Classify interviews
    print("Step 1/4: Classifying interviews...")
    classified_count = classify_interviews("data/interviews/", "data/interviews_classified.jsonl")
    print(f"  Classified {classified_count} passages")

    # Step 2: Extract moves from interviews
    print("Step 2/4: Extracting interview moves...")
    extracted_count = extract_interviews(
        "data/interviews_classified.jsonl",
        "data/interview_moves.jsonl",
        model=model,
        resume=resume
    )
    print(f"  Extracted {extracted_count} moves")

    # Step 3: Cluster interviews with email moves
    print("Step 3/4: Clustering interviews...")
    pattern_count = cluster_interviews(
        "data/moves.jsonl",
        "data/interview_moves.jsonl",
        "data/patterns.json"
    )
    print(f"  Generated {pattern_count} patterns")

    # Step 4: Calibrate interviews
    print("Step 4/4: Calibrating interviews...")
    # Import calibrate_interviews from scripts (needs sys.path manipulation)
    import sys
    from pathlib import Path
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from calibrate_interviews import calibrate_interviews
    calibrate_interviews(
        "data/moves.jsonl",
        "data/interview_moves.jsonl",
        "data/calibration.json"
    )
    print("  Calibration complete")


def stage_classify_interviews():
    """Run classify_interviews stage."""
    count = classify_interviews("data/interviews/", "data/interviews_classified.jsonl")
    print(f"Classified {count} passages")


def stage_extract_interviews(model: str, resume: bool):
    """Run extract_interviews stage."""
    count = extract_interviews(
        "data/interviews_classified.jsonl",
        "data/interview_moves.jsonl",
        model=model,
        resume=resume
    )
    print(f"Extracted {count} moves")


def stage_cluster_interviews():
    """Run cluster_interviews stage."""
    count = cluster_interviews(
        "data/moves.jsonl",
        "data/interview_moves.jsonl",
        "data/patterns.json"
    )
    print(f"Generated {count} patterns")


def stage_calibrate_interviews():
    """Run calibrate_interviews stage."""
    import sys
    from pathlib import Path
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from calibrate_interviews import calibrate_interviews
    calibrate_interviews(
        "data/moves.jsonl",
        "data/interview_moves.jsonl",
        "data/calibration.json"
    )


def stage_validate():
    """Run validate_all()."""
    is_valid, errors = validate_all("data")
    if is_valid:
        print("All validation checks passed.")
    else:
        print(f"Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="torvalds_skill",
        description="Distill Torvalds' review method from LKML into a skill",
    )
    sub = parser.add_subparsers(dest="stage", required=True)

    sub.add_parser("classify", help="filter corpus → reviews")

    p_extract = sub.add_parser("extract", help="extract review moves via LLM")
    p_extract.add_argument("--sample", type=int, default=2000,
                           help="number of emails to sample (0 = all)")
    p_extract.add_argument("--workers", type=int, default=8,
                           help="concurrent LLM calls")
    p_extract.add_argument("--resume", action="store_true",
                           help="skip already-processed emails")

    sub.add_parser("cluster", help="cluster moves → patterns")

    p_distill = sub.add_parser("distill", help="distill patterns → skill")
    p_distill.add_argument("--top-n", type=int, default=40,
                           help="top N patterns to include")
    p_distill.add_argument("--model", type=str, default=None,
                           help="override LLM model (default: from config)")
    p_distill.add_argument("--out", type=str, default=None,
                           help="output file path (default: linus-torvalds-skill/SKILL.md)")

    p_run = sub.add_parser("run", help="run full pipeline")
    p_run.add_argument("--sample", type=int, default=2000,
                       help="number of emails to sample")
    p_run.add_argument("--workers", type=int, default=8,
                       help="concurrent LLM calls")

    p_soul = sub.add_parser("soul", help="generate AI assistant soul document")
    p_soul.add_argument("--model", type=str, default=None,
                        help="override LLM model (default: from config)")
    p_soul.add_argument("--out", type=str, default=None,
                        help="output file path (default: soul/soul.md)")

    sub.add_parser("interviews", help="fetch interview transcripts from configured sources")

    # Interview pipeline subcommand
    p_interviews_pipeline = sub.add_parser("interviews-pipeline", help="run full interview pipeline")
    p_interviews_pipeline.add_argument("--model", type=str, default="gpt-oss-120b",
                                       help="LLM model for extraction (default: gpt-oss-120b)")
    p_interviews_pipeline.add_argument("--resume", action="store_true",
                                       help="resume from checkpoint")

    # Individual interview stage subcommands
    sub.add_parser("classify-interviews", help="classify interview transcripts")

    p_extract_interviews = sub.add_parser("extract-interviews", help="extract moves from interviews")
    p_extract_interviews.add_argument("--model", type=str, default="gpt-oss-120b",
                                      help="LLM model (default: gpt-oss-120b)")
    p_extract_interviews.add_argument("--resume", action="store_true",
                                      help="resume from checkpoint")

    sub.add_parser("cluster-interviews", help="cluster interview moves with email moves")

    sub.add_parser("calibrate-interviews", help="compute severity calibration")

    sub.add_parser("validate", help="validate data files")

    args = parser.parse_args()

    print(f"config: model={config.MODEL}, host={config.HOST}")

    if args.stage == "classify":
        stage_classify()
    elif args.stage == "extract":
        stage_extract(args.sample, args.workers, args.resume)
    elif args.stage == "cluster":
        stage_cluster()
    elif args.stage == "distill":
        stage_distill(args.top_n, model=args.model, out=args.out)
    elif args.stage == "run":
        stage_run(args.sample, args.workers)
    elif args.stage == "soul":
        from .soul import generate_soul
        patterns_path = Path(__file__).parent.parent.parent / "data" / "patterns.json"
        if not patterns_path.exists():
            print(f"ERROR: {patterns_path} not found. Run clustering first.")
            return 1
        output_path = Path(args.out) if args.out else Path(__file__).parent.parent.parent / "soul" / "soul.md"
        generate_soul(patterns_path, output_path, model=args.model)
    elif args.stage == "interviews":
        from .interviews import fetch_interviews
        fetch_interviews()
    elif args.stage == "interviews-pipeline":
        try:
            stage_interviews_pipeline(model=args.model, resume=args.resume)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    elif args.stage == "classify-interviews":
        try:
            stage_classify_interviews()
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    elif args.stage == "extract-interviews":
        try:
            stage_extract_interviews(model=args.model, resume=args.resume)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    elif args.stage == "cluster-interviews":
        try:
            stage_cluster_interviews()
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    elif args.stage == "calibrate-interviews":
        try:
            stage_calibrate_interviews()
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    elif args.stage == "validate":
        stage_validate()


if __name__ == "__main__":
    main()
