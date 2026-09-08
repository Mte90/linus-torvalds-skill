#!/usr/bin/env python3
"""Torvalds Skill Pipeline Orchestrator.

Run with: python3 scripts/run_pipeline.py
Dry-run: python3 scripts/run_pipeline.py --dry-run
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_stage(name: str, cmd: list[str], dry_run: bool = False) -> bool:
    """Run a single pipeline stage."""
    print(f"📝 Stage: {name}")
    if dry_run:
        print(f"  [DRY-RUN] {' '.join(cmd)}")
        return True
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Stage {name} failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Torvalds Skill Pipeline Orchestrator"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show commands without executing",
    )
    parser.add_argument(
        "--stage",
        choices=[
            "calibrate",
            "distill",
            "verify",
            "soul",
            "review",
            "comparison",
            "stats",
            "all",
        ],
        default="all",
        help="Stage to run (default: all)",
    )
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    os.chdir(root)

    stages = [
        ("calibrate", ["python3", "scripts/calibrate.py"]),
        ("distill", ["python3", "-m", "torvalds_skill", "distill", "--out", "linus-torvalds-skill/SKILL.md"]),
        ("verify", ["python3", "scripts/verify_skill.py", "linus-torvalds-skill/SKILL.md"]),
        ("soul", ["python3", "-m", "torvalds_skill", "soul", "--out", "soul/soul.md"]),
        ("review", ["python3", "report/run_review.py"]),
        ("comparison", ["python3", "report/build_comparison.py"]),
        ("stats", ["python3", "scripts/generate_variant_table.py"]),
    ]

    if args.stage != "all":
        stages = [s for s in stages if s[0] == args.stage]

    print(f"🚀 Running pipeline (stage: {args.stage})")
    if args.dry_run:
        print("  [DRY-RUN MODE]")
    print()

    failed = []
    for name, cmd in stages:
        if not run_stage(name, cmd, args.dry_run):
            failed.append(name)
            if not args.dry_run:
                print(f"\n⛔ Pipeline stopped at {name}")
                break

    print()
    if failed:
        print(f"❌ Failed stages: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("✅ Full pipeline complete")
        sys.exit(0)


if __name__ == "__main__":
    main()