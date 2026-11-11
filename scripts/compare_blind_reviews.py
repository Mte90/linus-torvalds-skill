#!/usr/bin/env python3
"""
compare_blind_reviews.py — Compare model reviews to Torvalds' ground truth.

For each (patch, model, arm), parses model findings, matches them to Torvalds'
findings using a semantic judge (GLM5.2), and computes recall/precision/F1.

Outputs:
  data/blind_comparison_results.jsonl  — per-(patch, model, arm) records
  report/blind_comparison.md           — human-readable report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "report"))

from llm_review import call_llm  # noqa: E402
from run_eval import parse_findings_from_review  # noqa: E402

JUDGE_MODEL = "glm5.2"
EVAL_FILE = _ROOT / "data" / "blind_eval_results.jsonl"
FINDINGS_FILE = _ROOT / "data" / "heldout_findings.jsonl"
RESULTS_FILE = _ROOT / "data" / "blind_comparison_results.jsonl"
REPORT_FILE = _ROOT / "report" / "blind_comparison.md"


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def build_judge_prompt(model_finding, torvalds_findings):
    lines = [
        "You are a judge comparing a code reviewer's finding to Linus Torvalds' findings.",
        "Determine if the reviewer's finding describes the SAME issue as any of Torvalds' findings.",
        "A match means both findings identify the same underlying problem, even if worded differently.",
        "",
        "Torvalds' findings for this patch:",
    ]
    for i, tf in enumerate(torvalds_findings):
        sev = tf.get("severity", "?")
        f = tf.get("file", "?")
        issue = tf.get("issue", "?")
        lines.append(f"  {i}. [{sev}] {f}: {issue}")
    lines.append("")
    lines.append("Reviewer's finding:")
    lines.append(f"  - Severity: {model_finding.get('severity', '?')}")
    lines.append(f"  - File: {model_finding.get('file', '?')}")
    lines.append(f"  - Line: {model_finding.get('line', '?')}")
    lines.append(f"  - Issue: {model_finding.get('issue', '?')}")
    lines.append("")
    lines.append("Does the reviewer's finding match any of Torvalds' findings?")
    lines.append("")
    lines.append("Respond with ONLY a JSON object, no other text:")
    lines.append(
        '{"matched": true, "torvalds_idx": <0-based index>, "confidence": <0.0-1.0>, "reason": "brief"}'
    )
    lines.append("or:")
    lines.append('{"matched": false, "reason": "brief"}')
    return "\n".join(lines)


def call_judge(model_finding, torvalds_findings):
    """Call the judge to match a model finding to Torvalds' findings."""
    if not torvalds_findings:
        return {"matched": False, "reason": "no Torvalds findings"}
    prompt = build_judge_prompt(model_finding, torvalds_findings)
    try:
        response = call_llm(
            model=JUDGE_MODEL,
            prompt=prompt,
            timeout=120,
            temperature=0.0,
        )
        json_match = re.search(r"\{[^}]+\}", response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as exc:
        print(f"  judge error: {exc}", file=sys.stderr)
    return None


def load_completed():
    """Load already-completed comparison records for resume."""
    completed = {}
    if RESULTS_FILE.exists():
        for rec in load_jsonl(RESULTS_FILE):
            key = f"{rec['review_message_id']}|{rec['model']}|{rec['arm']}"
            completed[key] = rec
    return completed


def compare_patch(torvalds_findings, model_findings):
    """Match model findings to Torvalds' findings for one patch."""
    matched_torvalds = set()
    matched_model_indices = []
    judge_details = []

    for mi, mf in enumerate(model_findings):
        if not torvalds_findings:
            judge_details.append(
                {"model_idx": mi, "matched": False, "reason": "no Torvalds findings"}
            )
            continue

        result = call_judge(mf, torvalds_findings)
        if result is None:
            judge_details.append({"model_idx": mi, "matched": False, "reason": "judge error"})
            continue

        matched = result.get("matched", False)
        t_idx = result.get("torvalds_idx")
        reason = result.get("reason", "")
        confidence = result.get("confidence", 0.0)

        judge_details.append(
            {
                "model_idx": mi,
                "matched": matched,
                "torvalds_idx": t_idx,
                "confidence": confidence,
                "reason": reason,
            }
        )

        if (
            matched
            and t_idx is not None
            and isinstance(t_idx, int)
            and 0 <= t_idx < len(torvalds_findings)
        ):
            if t_idx not in matched_torvalds:
                matched_torvalds.add(t_idx)
                matched_model_indices.append(mi)

    tp = len(matched_torvalds)
    fp = len(model_findings) - len(matched_model_indices)
    fn = len(torvalds_findings) - tp

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "judge_details": judge_details,
    }


def compute_metrics(results):
    """Aggregate TP/FP/FN per (model, arm)."""
    metrics = {}
    for rec in results:
        key = (rec["model"], rec["arm"])
        if key not in metrics:
            metrics[key] = {"tp": 0, "fp": 0, "fn": 0, "patches": 0}
        metrics[key]["tp"] += rec["tp"]
        metrics[key]["fp"] += rec["fp"]
        metrics[key]["fn"] += rec["fn"]
        metrics[key]["patches"] += 1

    for m in metrics.values():
        tp = m["tp"]
        fp = m["fp"]
        fn = m["fn"]
        m["precision"] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        m["recall"] = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        m["f1"] = (
            2 * m["precision"] * m["recall"] / (m["precision"] + m["recall"])
            if (m["precision"] + m["recall"]) > 0
            else 0.0
        )

    return metrics


def generate_report(results, metrics):
    """Generate the human-readable markdown report."""
    lines = [
        "# Blind Review Comparison Report",
        "",
        "This report compares model reviews (with and without the Torvalds skill)",
        "to Linus Torvalds' actual reviews on the same patches.",
        "",
        f"- **Patches evaluated**: {len(set(r['patch_message_id'] for r in results))}",
        f"- **Models**: {', '.join(sorted(set(r['model'] for r in results)))}",
        "- **Arms**: skill (with Torvalds skill), baseline (no skill)",
        f"- **Judge**: {JUDGE_MODEL} (semantic matching, COI: same model used as reviewer in some cells)",
        f"- **Ground truth**: {sum({r['patch_message_id']: r['torvalds_finding_count'] for r in results}.values())} Torvalds findings (pilot set)",
        "",
        "## Summary Metrics",
        "",
        "| Model | Arm | Patches | TP | FP | FN | Precision | Recall | F1 |",
        "|-------|-----|---------|----|----|----|-----------|---------|-----|",
    ]

    for model, arm in sorted(metrics.keys()):
        m = metrics[(model, arm)]
        lines.append(
            f"| {model} | {arm} | {m['patches']} | {m['tp']} | {m['fp']} | {m['fn']} | "
            f"{m['precision']:.1%} | {m['recall']:.1%} | {m['f1']:.1%} |"
        )

    lines.append("")
    lines.append("## Per-Patch Results")
    lines.append("")

    for patch_id in sorted(set(r["review_message_id"] for r in results)):
        patch_recs = [r for r in results if r["review_message_id"] == patch_id]
        subject = patch_recs[0]["patch_subject"] if patch_recs else patch_id
        torvalds_count = patch_recs[0]["torvalds_finding_count"] if patch_recs else 0
        lines.append(f"### {subject}")
        lines.append("")
        lines.append(f"Torvalds found **{torvalds_count}** issue(s) in this patch.")
        lines.append("")
        lines.append("| Model | Arm | Model findings | TP | FP | FN |")
        lines.append("|-------|-----|---------------|----|----|----|")
        for r in sorted(patch_recs, key=lambda x: (x["model"], x["arm"])):
            model_finding_count = r.get("model_finding_count", 0)
            lines.append(
                f"| {r['model']} | {r['arm']} | {model_finding_count} | {r['tp']} | {r['fp']} | {r['fn']} |"
            )
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare blind reviews to Torvalds ground truth")
    parser.add_argument("--models", nargs="*", help="Filter to specific models")
    parser.add_argument(
        "--report-only", action="store_true", help="Only regenerate report from existing results"
    )
    args = parser.parse_args()

    if args.report_only:
        if not RESULTS_FILE.exists():
            print("No comparison results found", file=sys.stderr)
            sys.exit(1)
        results = load_jsonl(RESULTS_FILE)
        metrics = compute_metrics(results)
        REPORT_FILE.parent.mkdir(exist_ok=True)
        REPORT_FILE.write_text(generate_report(results, metrics))
        print(f"Report written to {REPORT_FILE}")
        return

    eval_records = load_jsonl(EVAL_FILE)
    findings_records = load_jsonl(FINDINGS_FILE)

    # Filter out error records and deduplicate by (review_message_id, model, arm).
    # Keep last-write-wins among non-error records.
    seen: dict[str, dict] = {}
    for rec in eval_records:
        if rec.get("error") is not None:
            continue
        if not rec.get("review", "").strip():
            continue
        key = f"{rec['review_message_id']}|{rec['model']}|{rec['arm']}"
        seen[key] = rec
    eval_records = list(seen.values())

    # Build ground-truth lookup: review_message_id -> findings
    # (eval records share the same review_message_id as the findings file)
    torvalds_by_patch = {}
    for fr in findings_records:
        torvalds_by_patch[fr["review_message_id"]] = fr.get("findings", [])

    # Group eval records by (patch_message_id, model, arm)
    results = list(load_jsonl(RESULTS_FILE)) if RESULTS_FILE.exists() else []

    # Build a set of keys already in results (use review_message_id to match loop key)
    done_keys = set()
    for r in results:
        done_keys.add(
            f"{r.get('review_message_id', r.get('patch_message_id', ''))}|{r['model']}|{r['arm']}"
        )

    total = len(eval_records)
    processed = 0

    for rec in eval_records:
        review_msg_id = rec["review_message_id"]
        model = rec["model"]
        arm = rec["arm"]
        key = f"{review_msg_id}|{model}|{arm}"

        if args.models and model not in args.models:
            continue

        if key in done_keys:
            processed += 1
            continue

        torvalds_findings = torvalds_by_patch.get(review_msg_id, [])
        review_text = rec.get("review", "")
        patch_files = rec.get("patch_files", ["unknown"])

        diff_record = {
            "diff": rec.get("patch_diff", ""),
            "file": patch_files[0] if patch_files else "unknown",
        }

        model_findings = parse_findings_from_review(review_text, diff_record)

        print(f"[{processed + 1}/{total}] {model}/{arm}/{rec['patch_subject'][:50]}")
        print(
            f"  Model findings: {len(model_findings)}, Torvalds findings: {len(torvalds_findings)}"
        )

        if model_findings:
            comparison = compare_patch(torvalds_findings, model_findings)
        else:
            comparison = {"tp": 0, "fp": 0, "fn": len(torvalds_findings), "judge_details": []}

        result_rec = {
            "patch_message_id": rec["patch_message_id"],
            "review_message_id": review_msg_id,
            "patch_subject": rec["patch_subject"],
            "model": model,
            "arm": arm,
            "model_finding_count": len(model_findings),
            "torvalds_finding_count": len(torvalds_findings),
            "tp": comparison["tp"],
            "fp": comparison["fp"],
            "fn": comparison["fn"],
            "judge_details": comparison["judge_details"],
        }

        results.append(result_rec)
        done_keys.add(key)

        # Append to results file immediately (resume-safe)
        with open(RESULTS_FILE, "a") as f:
            f.write(json.dumps(result_rec) + "\n")

        print(f"  TP={comparison['tp']} FP={comparison['fp']} FN={comparison['fn']}")
        processed += 1

    # Generate report
    metrics = compute_metrics(results)
    REPORT_FILE.parent.mkdir(exist_ok=True)
    REPORT_FILE.write_text(generate_report(results, metrics))
    print(f"\nReport written to {REPORT_FILE}")
    print(f"Results: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
