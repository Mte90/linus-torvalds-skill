#!/usr/bin/env python3
"""
Blind evaluation: review held-out LKML patches with and without skill.

For each held-out patch, each reviewer model, and each arm (skill / baseline),
calls the LLM to produce a blind code review. The reviewer never sees Torvalds'
review — only the patch diff. Results are stored incrementally in
data/blind_eval_results.jsonl and are resume-safe by (patch_message_id, model, arm).

Usage:
  python3 scripts/run_blind_eval.py                         # all models, both arms
  python3 scripts/run_blind_eval.py --models gpt-oss-120b  # single model
  python3 scripts/run_blind_eval.py --skill-only            # skip baseline arm
  python3 scripts/run_blind_eval.py --baseline-only         # skip skill arm
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_REPORT = _ROOT / "report"
if str(_REPORT) not in sys.path:
    sys.path.insert(0, str(_REPORT))

from llm_review import call_llm  # noqa: E402

from torvalds_skill.profiles import get_profile  # noqa: E402
from torvalds_skill.skill_paths import skill_path as _skill_path  # noqa: E402

HELDOUT_REVIEWS = _ROOT / "data" / "heldout_reviews.jsonl"
OUTPUT_PATH = _ROOT / "data" / "blind_eval_results.jsonl"

MODELS: dict[str, Path] = {
    model: _skill_path(model)
    for model in ("gpt-oss-120b", "glm5.2", "mistral-small-4-119b", "qwen3.8-27b")
}

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

_FORMAT_BLOCK = """\
## Format

For each finding use:
### [SEVERITY] Finding title
- **Type:** bug | security | memory | concurrency | performance | code-quality
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings
- Use `**Field:**` format (colon inside bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

## Rules

- Cover the entire patch
- Be concrete: cite line numbers, name functions, quote code
- Don't invent problems. If the patch is clean, say "No findings."
- Reference line numbers from the diff context
- English

Write your review to stdout.
"""


def build_skill_prompt(
    patch_diff: str, patch_files: str, patch_subject: str, skill_text: str
) -> str:
    """Build the with-skill review prompt."""
    return (
        "You are a code reviewer applying the Linus Torvalds reviewer skill to a kernel patch.\n"
        "\nDo NOT use any tools. Everything you need is inlined below."
        "\n== SKILL ==\n"
        f"{skill_text}"
        "\n== PATCH ==\n"
        f"File: {patch_files}\n"
        "Language: C\n"
        f"Subject: {patch_subject}\n\n"
        f"{patch_diff}\n"
        "\n## Task\n\n"
        "Review the patch above using the Torvalds skill. Find bugs, security issues, "
        "memory safety problems, and code quality issues.\n"
        f"{_FORMAT_BLOCK}"
    )


def build_baseline_prompt(patch_diff: str, patch_files: str, patch_subject: str) -> str:
    """Build the baseline (no-skill) review prompt."""
    return (
        "You are a code reviewer reviewing a kernel patch.\n"
        "\nDo NOT use any tools. Everything you need is inlined below."
        "\n== PATCH ==\n"
        f"File: {patch_files}\n"
        "Language: C\n"
        f"Subject: {patch_subject}\n\n"
        f"{patch_diff}\n"
        "\n## Task\n\n"
        "Review the patch above. Find bugs, security issues, memory safety problems, "
        "and code quality issues.\n"
        f"{_FORMAT_BLOCK}"
    )


# ---------------------------------------------------------------------------
# Resume logic
# ---------------------------------------------------------------------------


def load_completed_keys() -> set[tuple[str, str, str]]:
    """Return set of (patch_message_id, model, arm) already successfully completed.

    Error records are NOT counted as completed so they get retried on resume.
    """
    keys: set[tuple[str, str, str]] = set()
    if not OUTPUT_PATH.exists():
        return keys
    with open(OUTPUT_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("error") is not None:
                continue
            if not rec.get("review", "").strip():
                continue
            key = (rec["patch_message_id"], rec["model"], rec["arm"])
            keys.add(key)
    return keys


def append_result(record: dict) -> None:
    """Append a result record to the output file (JSONL)."""
    with open(OUTPUT_PATH, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_review(
    model: str,
    prompt: str,
    patch_id: str,
    arm: str,
) -> dict:
    """Call the LLM and return a result record. Retries once on reasoning-only."""
    profile = get_profile(model)
    timeout = getattr(profile, "review_timeout", 600)

    response = None
    error = None

    for attempt in range(2):
        try:
            response = call_llm(model, prompt, timeout=timeout)
            if response.strip():
                break
            print(
                f"  warning: empty response (attempt {attempt + 1})",
                file=sys.stderr,
            )
            response = None
        except Exception as e:
            error = str(e)
            print(
                f"  error (attempt {attempt + 1}) for {model}/{arm}/{patch_id[:30]}: {e}",
                file=sys.stderr,
            )
            response = None

    return {
        "review": response or "",
        "review_words": len(response.split()) if response else 0,
        "error": error if response is None else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind evaluation harness")
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated model names (default: all)",
    )
    parser.add_argument("--skill-only", action="store_true", help="Skip baseline arm")
    parser.add_argument("--baseline-only", action="store_true", help="Skip skill arm")
    args = parser.parse_args()

    if args.skill_only and args.baseline_only:
        print("error: --skill-only and --baseline-only are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    model_list = args.models.split(",") if args.models else list(MODELS.keys())
    for m in model_list:
        if m not in MODELS:
            print(f"error: unknown model '{m}'. Valid: {', '.join(MODELS)}", file=sys.stderr)
            sys.exit(1)

    arms: list[str] = []
    if not args.baseline_only:
        arms.append("skill")
    if not args.skill_only:
        arms.append("baseline")

    # Load held-out patches
    if not HELDOUT_REVIEWS.exists():
        print(f"error: {HELDOUT_REVIEWS} not found", file=sys.stderr)
        sys.exit(1)

    patches = []
    with open(HELDOUT_REVIEWS) as f:
        for line in f:
            line = line.strip()
            if line:
                patches.append(json.loads(line))

    print(f"Loaded {len(patches)} held-out patches", file=sys.stderr)
    print(f"Models: {', '.join(model_list)}", file=sys.stderr)
    print(f"Arms: {', '.join(arms)}", file=sys.stderr)

    total = len(patches) * len(model_list) * len(arms)
    print(f"Total reviews: {total}", file=sys.stderr)

    completed_keys = load_completed_keys()
    print(f"Already completed: {len(completed_keys)}", file=sys.stderr)

    done = 0
    for patch in patches:
        patch_id = patch["patch_message_id"]
        patch_subject = patch.get("patch_subject", "unknown")
        patch_diff = patch.get("patch_diff", "")
        patch_files = ", ".join(patch.get("patch_files", []))

        for model in model_list:
            skill_file = MODELS[model]
            skill_text = skill_file.read_text() if skill_file.exists() else ""

            for arm in arms:
                key = (patch_id, model, arm)
                if key in completed_keys:
                    done += 1
                    print(
                        f"[{done}/{total}] SKIP {model}/{arm}/{patch_subject[:50]}",
                        file=sys.stderr,
                    )
                    continue

                if arm == "skill":
                    prompt = build_skill_prompt(patch_diff, patch_files, patch_subject, skill_text)
                else:
                    prompt = build_baseline_prompt(patch_diff, patch_files, patch_subject)

                t0 = time.time()
                print(
                    f"[{done + 1}/{total}] {model}/{arm}/{patch_subject[:50]}",
                    file=sys.stderr,
                )

                result = run_review(model, prompt, patch_id, arm)
                elapsed = time.time() - t0

                record = {
                    "patch_message_id": patch_id,
                    "patch_subject": patch_subject,
                    "patch_files": patch.get("patch_files", []),
                    "review_message_id": patch.get("review_message_id", ""),
                    "review_subject": patch.get("review_subject", ""),
                    "model": model,
                    "arm": arm,
                    "skill_model": model,
                    "review": result["review"],
                    "review_words": result["review_words"],
                    "error": result["error"],
                    "elapsed_seconds": round(elapsed, 1),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                append_result(record)
                completed_keys.add(key)
                done += 1
                status = "OK" if result["error"] is None else f"ERR: {result['error']}"
                print(
                    f"  {status} ({result['review_words']} words, {elapsed:.0f}s)",
                    file=sys.stderr,
                )

    print(f"\nDone: {done}/{total} reviews completed", file=sys.stderr)


if __name__ == "__main__":
    main()
