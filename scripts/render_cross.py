#!/usr/bin/env python3
"""
Render cross-model evaluation matrix from eval results.

Loads diagonal (data/eval_results.jsonl) and cross (data/eval_results_cross.jsonl)
evaluations, groups by (model, skill) pairing, and generates a markdown matrix
showing F1, recall, and judge scores for all 4x4 model/skill combinations.

Run from repository root: python3 scripts/render_cross.py
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Models to include in the matrix
MODELS = ["gpt-oss-120b", "mistral-small-4-119b", "glm5.2", "qwen3.8-27b"]

ROOT = Path(__file__).resolve().parent.parent

# Import match function from run_eval (sibling script)
_RUN_EVAL = Path(__file__).resolve().parent
if str(_RUN_EVAL) not in sys.path:
    sys.path.insert(0, str(_RUN_EVAL))
from run_eval import match_finding_to_diff_bug as run_eval_match_finding_to_diff_bug  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    """Load JSONL file, returning empty list if missing or empty."""
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
    return records


def group_results_by_pairing(results: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group results by (model, skill) pairing.

    For diagonal records (no skill field), skill defaults to model.
    For cross records, skill is explicitly set.
    """
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for result in results:
        model = result.get("model", "unknown")
        skill = result.get("skill", model)
        grouped[(model, skill)].append(result)
    return dict(grouped)


def normalize_filename(name: str) -> str:
    """Normalize file names for comparison."""
    name = name.strip().lower()
    name = name.split("/")[-1]
    aliases = {
        "server.c": "smallchat-server.c",
        "client.c": "smallchat-client.c",
    }
    return aliases.get(name, name)


def match_finding_to_diff_bug(finding: dict, diff_record: dict, line_tolerance: int = 5) -> bool:
    """Check if a finding matches any ground-truth bug of a diff record.

    Bugs inherit their file from the parent diff record, so matching traverses
    the record's bugs list (same file, any bug line within tolerance).

    Returns True if the finding matches, False otherwise.
    """
    matched = run_eval_match_finding_to_diff_bug(
        finding, diff_record.get("bugs", []), diff_record.get("file", "")
    )
    if matched is None:
        return False
    finding_line = finding.get("line")
    if finding_line is None:
        return False
    return abs(finding_line - matched.get("line", finding_line)) <= line_tolerance


def compute_cell_metrics(results: list[dict], diff_records: list[dict]) -> dict[str, Any]:
    """Compute metrics for a single (model, skill) cell."""
    if not results or not diff_records:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "refusal_rate": 0.0,
            "judge_accuracy": 0.0,
            "judge_prioritization": 0.0,
            "judge_justification": 0.0,
            "judge_actionability": 0.0,
            "judge_mean": 0.0,
            "total_results": 0,
            "hits": [],
            "misses": [r["id"] for r in diff_records],
        }

    matched_diff_ids = set()
    total_findings = 0
    score_sums = {
        "accuracy": 0.0,
        "prioritization": 0.0,
        "justification": 0.0,
        "actionability": 0.0,
    }
    score_counts = {"accuracy": 0, "prioritization": 0, "justification": 0, "actionability": 0}
    refusal_count = 0

    for result in results:
        findings = result.get("findings", [])
        total_findings += len(findings)

        if not findings or result.get("refused", False):
            refusal_count += 1

        scores = result.get("scores", {})
        for key in score_sums:
            if key in scores and scores[key] is not None:
                score_sums[key] += scores[key]
                score_counts[key] += 1

        for finding in findings:
            for diff_record in diff_records:
                if match_finding_to_diff_bug(finding, diff_record):
                    diff_id = diff_record.get("id")
                    if diff_id:
                        matched_diff_ids.add(diff_id)
                    break

    hits = sorted(matched_diff_ids)
    misses = sorted([r["id"] for r in diff_records if r.get("id") not in matched_diff_ids])

    precision = len(hits) / total_findings if total_findings > 0 else 0.0
    recall = len(hits) / len(diff_records) if diff_records else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    refusal_rate = refusal_count / len(results) if results else 0.0

    judge_accuracy = (
        score_sums["accuracy"] / score_counts["accuracy"] if score_counts["accuracy"] > 0 else 0.0
    )
    judge_prioritization = (
        score_sums["prioritization"] / score_counts["prioritization"]
        if score_counts["prioritization"] > 0
        else 0.0
    )
    judge_justification = (
        score_sums["justification"] / score_counts["justification"]
        if score_counts["justification"] > 0
        else 0.0
    )
    judge_actionability = (
        score_sums["actionability"] / score_counts["actionability"]
        if score_counts["actionability"] > 0
        else 0.0
    )
    judge_mean = (
        judge_accuracy + judge_prioritization + judge_justification + judge_actionability
    ) / 4.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "refusal_rate": refusal_rate,
        "judge_accuracy": judge_accuracy,
        "judge_prioritization": judge_prioritization,
        "judge_justification": judge_justification,
        "judge_actionability": judge_actionability,
        "judge_mean": judge_mean,
        "total_results": len(results),
        "hits": hits,
        "misses": misses,
    }


def compute_marginal_means(
    cell_data: dict[tuple[str, str], dict[str, Any]], all_models: list[str]
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    """Compute row means (per model) and column means (per skill).

    Args:
        cell_data: Dict mapping (model, skill) -> metrics dict
        all_models: List of all model/skill names (models and skills share the same set)

    Returns:
        (model_means, skill_means) where each maps name -> {f1, judge_mean, refusal_rate}
    """
    # Derive all unique skills from cell_data (they may differ from all_models in test fixtures)
    all_skills = sorted(set(s for (m, s) in cell_data.keys()))

    model_sums: dict[str, dict[str, float]] = {
        m: {"f1": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0} for m in all_models
    }
    model_counts: dict[str, int] = {m: 0 for m in all_models}
    skill_sums: dict[str, dict[str, float]] = {
        s: {"f1": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0} for s in all_skills
    }
    skill_counts: dict[str, int] = {s: 0 for s in all_skills}

    for (model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        f1 = metrics.get("f1", 0.0)
        judge = metrics.get("judge_mean", 0.0)
        refusal = metrics.get("refusal_rate", 0.0)

        model_sums[model]["f1"] += f1
        model_sums[model]["judge_mean"] += judge
        model_sums[model]["refusal_rate"] += refusal
        model_counts[model] += 1

        skill_sums[skill]["f1"] += f1
        skill_sums[skill]["judge_mean"] += judge
        skill_sums[skill]["refusal_rate"] += refusal
        skill_counts[skill] += 1

    model_means = {}
    for model in all_models:
        count = model_counts[model]
        if count > 0:
            model_means[model] = {
                "f1": model_sums[model]["f1"] / count,
                "judge_mean": model_sums[model]["judge_mean"] / count,
                "refusal_rate": model_sums[model]["refusal_rate"] / count,
            }
        else:
            model_means[model] = {"f1": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0}

    skill_means = {}
    for skill in all_skills:
        count = skill_counts[skill]
        if count > 0:
            skill_means[skill] = {
                "f1": skill_sums[skill]["f1"] / count,
                "judge_mean": skill_sums[skill]["judge_mean"] / count,
                "refusal_rate": skill_sums[skill]["refusal_rate"] / count,
            }
        else:
            skill_means[skill] = {"f1": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0}

    # Add missing models/skills with zero values
    for model in all_models:
        if model not in model_means:
            model_means[model] = {"f1": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0}
    for skill in all_models:
        if skill not in skill_means:
            skill_means[skill] = {"f1": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0}

    return model_means, skill_means


def rank_by_verdict(means: dict[str, dict[str, float]]) -> list[tuple[str, float, float, float]]:
    """Rank items by F1 (desc), tiebreak by judge mean (desc), then refusal (asc)."""
    items = [
        (name, data["f1"], data["judge_mean"], data["refusal_rate"]) for name, data in means.items()
    ]
    items.sort(key=lambda x: (-x[1], -x[2], x[3]))
    return items


def collect_unmatched_findings(
    all_results: list[dict], diff_records: list[dict]
) -> tuple[list[dict], dict[tuple[str, str], int]]:
    """Collect findings that match NO ground-truth bug."""
    diff_lookup = {d["id"]: d for d in diff_records}
    unmatched = []
    counts: dict[tuple[str, str], int] = defaultdict(int)

    for result in all_results:
        diff_id = result.get("diff_id", "unknown")
        model = result.get("model", "unknown")
        skill = result.get("skill", model)
        findings = result.get("findings", [])

        diff_record = diff_lookup.get(diff_id, {})
        bugs = diff_record.get("bugs", [])

        for finding in findings:
            matched = run_eval_match_finding_to_diff_bug(finding, bugs, diff_record.get("file", ""))
            if matched is None:
                file_path = finding.get("file", "unknown")
                line = finding.get("line")
                severity = finding.get("severity", "unknown")
                issue = (finding.get("issue") or "")[:100]
                if not issue.strip() or issue.strip() == "no issue described":
                    continue
                unmatched.append(
                    {
                        "diff_id": diff_id,
                        "model": model,
                        "skill": skill,
                        "file": file_path,
                        "line": line,
                        "severity": severity,
                        "issue": issue,
                    }
                )
                counts[(model, skill)] += 1

    return unmatched, dict(counts)


def collect_cross_only_discoveries(
    all_results: list[dict], diff_records: list[dict]
) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Find bugs matched only when cross-applying skills (not by native pair)."""
    diff_lookup = {d["id"]: d for d in diff_records}
    matched_bugs_by_cell: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for result in all_results:
        diff_id = result.get("diff_id", "unknown")
        model = result.get("model", "unknown")
        skill = result.get("skill", model)
        findings = result.get("findings", [])

        diff_record = diff_lookup.get(diff_id, {})
        bugs = diff_record.get("bugs", [])

        for finding in findings:
            matched = run_eval_match_finding_to_diff_bug(finding, bugs, diff_record.get("file", ""))
            if matched:
                bug_desc = matched.get("description", "unknown")
                matched_bugs_by_cell[(diff_id, model, skill)].add(bug_desc)

    discoveries_by_diff: dict[str, list[dict]] = defaultdict(list)
    counts_by_skill: dict[str, int] = defaultdict(int)

    all_bug_matches: dict[str, set[str]] = defaultdict(set)
    for (diff_id, _model, _skill), bugs in matched_bugs_by_cell.items():
        all_bug_matches[diff_id].update(bugs)

    for diff_id, _all_bugs in all_bug_matches.items():
        native_matched: set[str] = set()
        for (d, model, skill), bugs in matched_bugs_by_cell.items():
            if d == diff_id and model == skill:
                native_matched.update(bugs)

        for (d, model, skill), bugs in matched_bugs_by_cell.items():
            if d != diff_id:
                continue
            if model == skill:
                continue
            cross_only_bugs = bugs - native_matched
            for bug_desc in cross_only_bugs:
                discoveries_by_diff[diff_id].append(
                    {
                        "bug_desc": bug_desc[:80],
                        "found_by_model": model,
                        "found_by_skill": skill,
                    }
                )
                counts_by_skill[skill] += 1

    return dict(discoveries_by_diff), dict(counts_by_skill)


def render_markdown(
    cell_data: dict[tuple[str, str], dict[str, Any]],
    all_models: list[str],
    diff_records: list[dict],
    out_path: Path,
    model_ranked: list[tuple[str, float, float, float]] | None = None,
    skill_ranked: list[tuple[str, float, float, float]] | None = None,
    unmatched: list[dict] | None = None,
    unmatched_counts: dict[tuple[str, str], int] | None = None,
    cross_only: dict[str, list[dict]] | None = None,
    cross_only_counts: dict[str, int] | None = None,
) -> None:
    """Render the cross-model evaluation matrix as markdown with extended sections."""
    lines: list[str] = []

    # Header
    lines.append("# Cross-Model Evaluation Matrix\n")
    lines.append(
        "Diagonal data from `data/eval_results.jsonl`, cross-data from `data/eval_results_cross.jsonl`.\n"
    )
    lines.append("*Note: Each model judges its own reviews (self-judge).*\n")

    # Overview Matrix
    lines.append("## Overview Matrix\n")
    lines.append("Each cell shows: F1 score, Refusal rate, and mean Judge score (0–2 scale).\n")
    lines.append("*(native)* indicates diagonal pairing (model == skill).\n")

    header = "| Skill \\\\ Model |"
    for model in all_models:
        header += f" {model} |"
    lines.append(header)

    separator = "|"
    for _ in all_models:
        separator += "---|"
    lines.append(separator)

    for skill in all_models:
        row = f"| **{skill}** |"
        for model in all_models:
            metrics = cell_data.get((model, skill))
            if metrics and metrics["total_results"] > 0:
                f1_str = f"F1={metrics.get('f1', 0):.2f}"
                ref_str = f"R={metrics.get('refusal_rate', 0) * 100:.0f}%"
                j_str = f"J={metrics.get('judge_mean', 0):.1f}/2"
                native_marker = " *(native)*" if model == skill else ""
                row += f" {f1_str} {ref_str} {j_str}{native_marker} |"
            else:
                row += " — |"
        lines.append(row)

    lines.append("\n")

    # Per-metric matrices
    lines.append("## Precision Matrix\n")
    lines.append("| Skill \\\\ Model |" + " |".join(all_models) + " |")
    lines.append("|" + "---|" * len(all_models))
    for skill in all_models:
        row = f"| {skill} |"
        for model in all_models:
            metrics = cell_data.get((model, skill))
            if metrics and metrics["total_results"] > 0 and "precision" in metrics:
                row += f" {metrics['precision']:.2f} |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("\n")

    lines.append("## Recall Matrix\n")
    lines.append("| Skill \\\\ Model |" + " |".join(all_models) + " |")
    lines.append("|" + "---|" * len(all_models))
    for skill in all_models:
        row = f"| {skill} |"
        for model in all_models:
            metrics = cell_data.get((model, skill))
            if metrics and metrics["total_results"] > 0 and "recall" in metrics:
                row += f" {metrics['recall']:.2f} |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("\n")

    lines.append("## Refusal Rate Matrix\n")
    lines.append("| Skill \\\\ Model |" + " |".join(all_models) + " |")
    lines.append("|" + "---|" * len(all_models))
    for skill in all_models:
        row = f"| {skill} |"
        for model in all_models:
            metrics = cell_data.get((model, skill))
            if metrics and metrics["total_results"] > 0 and "refusal_rate" in metrics:
                row += f" {metrics['refusal_rate'] * 100:.0f}% |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("\n")

    # Judge score matrices
    for axis in ["accuracy", "prioritization", "justification", "actionability"]:
        lines.append(f"## Judge {axis.title()} Matrix\n")
        lines.append("| Skill \\\\ Model |" + " |".join(all_models) + " |")
        lines.append("|" + "---|" * len(all_models))
        for skill in all_models:
            row = f"| {skill} |"
            for model in all_models:
                metrics = cell_data.get((model, skill))
                key = f"judge_{axis}"
                if metrics and metrics["total_results"] > 0 and key in metrics:
                    row += f" {metrics[key]:.1f} |"
                else:
                    row += " — |"
            lines.append(row)
        lines.append("\n")

    # Best pairing section
    lines.append("## Best Pairing by Metric\n")
    best_f1 = None
    best_f1_val = -1
    best_refusal = None
    best_refusal_val = 1.0
    best_judge = None
    best_judge_val = -1

    for (model, skill), metrics in cell_data.items():
        if metrics["total_results"] == 0:
            continue
        if metrics["f1"] > best_f1_val:
            best_f1_val = metrics["f1"]
            best_f1 = (model, skill)
        if metrics["refusal_rate"] < best_refusal_val:
            best_refusal_val = metrics["refusal_rate"]
            best_refusal = (model, skill)
        if metrics["judge_mean"] > best_judge_val:
            best_judge_val = metrics["judge_mean"]
            best_judge = (model, skill)

    if best_f1:
        model, skill = best_f1
        native = " *(native)*" if model == skill else ""
        lines.append(f"- **Best F1**: {model} on {skill}{native} (F1={best_f1_val:.2f})\n")
    if best_refusal:
        model, skill = best_refusal
        native = " *(native)*" if model == skill else ""
        lines.append(
            f"- **Best Refusal Rate**: {model} on {skill}{native} (R={best_refusal_val * 100:.0f}%)\n"
        )
    if best_judge:
        model, skill = best_judge
        native = " *(native)*" if model == skill else ""
        lines.append(
            f"- **Best Judge Score**: {model} on {skill}{native} (J={best_judge_val:.1f}/2)\n"
        )

    # Marginal Analysis
    lines.append("\n---\n")
    lines.append("## Marginal Analysis\n")
    lines.append(
        "Row means (per reviewing model across skills) and column means (per skill across models).\n"
    )

    if model_ranked:
        best_model, best_f1, best_judge, best_refusal = model_ranked[0]
        lines.append(
            f"**Best Model**: {best_model} (row-mean F1={best_f1:.2f}, judge={best_judge:.1f}, refusal={best_refusal * 100:.0f}%)\n"
        )

    if skill_ranked:
        best_skill, best_f1, best_judge, best_refusal = skill_ranked[0]
        lines.append(
            f"**Best Skill**: {best_skill} (column-mean F1={best_f1:.2f}, judge={best_judge:.1f}, refusal={best_refusal * 100:.0f}%)\n"
        )

    lines.append("\n### Model Rankings (by row-mean F1)\n")
    lines.append("| Rank | Model | F1 | Judge Mean | Refusal Rate |")
    lines.append("|------|-------|----|------------|-------------|")
    for rank, (model, f1, judge, refusal) in enumerate(model_ranked or [], 1):
        lines.append(f"| {rank} | {model} | {f1:.2f} | {judge:.1f} | {refusal * 100:.0f}% |")

    lines.append("\n### Skill Rankings (by column-mean F1)\n")
    lines.append("| Rank | Skill | F1 | Judge Mean | Refusal Rate |")
    lines.append("|------|-------|----|------------|-------------|")
    for rank, (skill, f1, judge, refusal) in enumerate(skill_ranked or [], 1):
        lines.append(f"| {rank} | {skill} | {f1:.2f} | {judge:.1f} | {refusal * 100:.0f}% |")

    # New Bug Candidates
    lines.append("\n---\n")
    lines.append("## New Bug Candidates\n")
    lines.append(
        "Findings that match NO ground-truth bug — candidates for ground-truth expansion (require human triage).\n"
    )

    if unmatched:
        lines.append("| Diff ID | Model | Skill | File:Line | Severity | Issue |")
        lines.append("|---------|-------|-------|-----------|----------|-------|")
        for u in unmatched[:50]:
            loc = f"{u['file']}:{u['line']}" if u["line"] else u["file"]
            lines.append(
                f"| {u['diff_id']} | {u['model']} | {u['skill']} | {loc} | {u['severity']} | {u['issue']} |"
            )

        lines.append("\n### Unmatched Count by Pairing\n")
        for (model, skill), count in sorted(unmatched_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {model}×{skill}: {count} unmatched")
        lines.append(
            "\n*Note: High unmatched rates may indicate hallucinated findings rather than new bugs.*\n"
        )
    else:
        lines.append("No unmatched findings.\n")

    # Cross-Only Discoveries
    lines.append("\n---\n")
    lines.append("## Cross-Only Discoveries\n")
    lines.append("Bugs found only when cross-applying skills (not by native pair).\n")

    if cross_only:
        for diff_id, discoveries in sorted(cross_only.items()):
            lines.append(f"\n### Diff {diff_id}\n")
            for disc in discoveries:
                lines.append(
                    f"- {disc['bug_desc']} — found by {disc['found_by_model']}×{disc['found_by_skill']}\n"
                )

        lines.append("\n### Cross-Only Count by Skill\n")
        for skill, count in sorted(cross_only_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {skill}: {count} cross-only discoveries")
    else:
        lines.append("No cross-only discoveries.\n")

    # Footer
    lines.append("\n---\n")
    lines.append(
        "*Generated from `data/eval_results.jsonl` (diagonal) and `data/eval_results_cross.jsonl` (cross).*\n"
    )
    lines.append("*Each model judges its own reviews (self-judge).*\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Render cross-model evaluation matrix from eval results."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("report/cross_matrix.md"),
        help="Output markdown file path (default: report/cross_matrix.md)",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("data/eval_results.jsonl"),
        help="Diagonal eval results file (default: data/eval_results.jsonl)",
    )
    parser.add_argument(
        "--cross-results",
        type=Path,
        default=Path("data/eval_results_cross.jsonl"),
        help="Cross eval results file (default: data/eval_results_cross.jsonl)",
    )
    parser.add_argument(
        "--diffs",
        type=Path,
        default=Path("data/eval_diffs.jsonl"),
        help="Ground truth diffs file (default: data/eval_diffs.jsonl)",
    )

    args = parser.parse_args()

    diagonal_results = load_jsonl(args.results)
    cross_results = load_jsonl(args.cross_results)
    diff_records = load_jsonl(args.diffs)

    all_results = diagonal_results + cross_results

    if not all_results:
        print("No eval results found. Generating empty matrix.")
        models = MODELS
        cell_data: dict[tuple[str, str], dict[str, Any]] = {}
        for model in models:
            for skill in models:
                cell_data[(model, skill)] = {"total_results": 0}
        render_markdown(cell_data, models, diff_records, args.out)
        print(f"Empty matrix written to {args.out}")
        return

    grouped = group_results_by_pairing(all_results)

    derived_models = sorted(
        set(m for (m, s) in grouped.keys()) | set(s for (m, s) in grouped.keys())
    )

    cell_data = {}
    for (model, skill), results in grouped.items():
        metrics = compute_cell_metrics(results, diff_records)
        cell_data[(model, skill)] = metrics

    for model in derived_models:
        for skill in derived_models:
            if (model, skill) not in cell_data:
                cell_data[(model, skill)] = {"total_results": 0}

    model_means, skill_means = compute_marginal_means(cell_data, derived_models)
    model_ranked = rank_by_verdict(model_means)
    skill_ranked = rank_by_verdict(skill_means)

    unmatched, unmatched_counts = collect_unmatched_findings(all_results, diff_records)
    cross_only, cross_only_counts = collect_cross_only_discoveries(all_results, diff_records)

    render_markdown(
        cell_data,
        derived_models,
        diff_records,
        args.out,
        model_ranked=model_ranked,
        skill_ranked=skill_ranked,
        unmatched=unmatched,
        unmatched_counts=unmatched_counts,
        cross_only=cross_only,
        cross_only_counts=cross_only_counts,
    )
    print(f"Matrix written to {args.out}")


if __name__ == "__main__":
    main()
