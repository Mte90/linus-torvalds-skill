#!/usr/bin/env python3
"""
Render cross-model evaluation matrix from eval results.

Loads diagonal (data/eval_results.jsonl) and cross (data/eval_results_cross.jsonl)
evaluations, groups by (model, skill) pairing, and generates a markdown matrix
showing Detection Score, recall, and judge scores for all 4x4 model/skill combinations.

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


def match_finding_to_diff_bug(
    finding: dict, diff_record: dict, line_tolerance: int = 5
) -> dict | None:
    """Return the matched ground-truth bug dict, or None.

    Bugs inherit their file from the parent diff record, so matching traverses
    the record's bugs list (same file, any bug line within tolerance).
    """
    matched = run_eval_match_finding_to_diff_bug(
        finding, diff_record.get("bugs", []), diff_record.get("file", "")
    )
    if matched is None:
        return None
    finding_line = finding.get("line")
    if finding_line is None:
        return None
    if abs(finding_line - matched.get("line", finding_line)) > line_tolerance:
        return None
    return matched


SEVERITY_ORDER = ["reject", "request-changes", "nitpick"]


def compute_cell_metrics(results: list[dict], diff_records: list[dict]) -> dict[str, Any]:
    """Compute metrics for a single (model, skill) cell.

    Also captures the matched bug identifiers with their severity and category
    so the renderer can produce per-severity and per-category rankings.
    """
    empty = {
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
        "total_findings": 0,
        "hits": [],
        "matched_bugs": [],
        "severity_counts": {},
        "category_counts": {},
        "misses": [r["id"] for r in diff_records],
    }
    if not results or not diff_records:
        return empty

    matched_diff_ids: set[str] = set()
    matched_bugs: list[dict[str, Any]] = []
    severity_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
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
                matched_bug = match_finding_to_diff_bug(finding, diff_record)
                if matched_bug is None:
                    continue
                diff_id = diff_record.get("id")
                if diff_id:
                    matched_diff_ids.add(diff_id)
                bug_entry = {
                    "diff_id": diff_id,
                    "line": matched_bug.get("line"),
                    "severity": matched_bug.get("severity", "unknown"),
                    "category": matched_bug.get("category", "unknown"),
                    "description": matched_bug.get("description", ""),
                }
                matched_bugs.append(bug_entry)
                severity_counts[bug_entry["severity"]] += 1
                category_counts[bug_entry["category"]] += 1
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
        "total_findings": total_findings,
        "total_results": len(results),
        "hits": hits,
        "matched_bugs": matched_bugs,
        "severity_counts": dict(severity_counts),
        "category_counts": dict(category_counts),
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
    """Rank items by Detection Score (desc), tiebreak by judge mean (desc), then refusal (asc)."""
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
    lines.append("*Judge model: GLM5.2 (fixed external judge, applied via `--rescore-all`).*\n")

    # Plain-language verdict (computed up-front from the whole matrix)
    total_bugs_ground_truth = len(diff_records)
    best_pair: tuple[str, str, int] | None = None
    best_ds_pair: tuple[str, str, float] | None = None
    best_judge_pair: tuple[str, str, float] | None = None
    model_bug_counts: dict[str, set[str]] = defaultdict(set)
    skill_bug_counts: dict[str, set[str]] = defaultdict(set)
    for (model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        hits = metrics.get("hits", [])
        model_bug_counts[model].update(hits)
        skill_bug_counts[skill].update(hits)
        tp = len(hits)
        if best_pair is None or tp > best_pair[2]:
            best_pair = (model, skill, tp)
        ds = metrics.get("f1", 0.0)
        if best_ds_pair is None or ds > best_ds_pair[2]:
            best_ds_pair = (model, skill, ds)
        jm = metrics.get("judge_mean", 0.0)
        if best_judge_pair is None or jm > best_judge_pair[2]:
            best_judge_pair = (model, skill, jm)

    # Best skill per model: highest-DS skill for each model (native or cross)
    best_skill_per_model: dict[str, tuple[str, float]] = {}
    for model in all_models:
        best_skill: str | None = None
        best_ds: float = -1.0
        for skill in all_models:
            cell = cell_data.get((model, skill))
            if not cell or cell.get("total_results", 0) == 0:
                continue
            ds = cell.get("f1", 0.0)
            if ds > best_ds:
                best_ds = ds
                best_skill = skill
        if best_skill is not None:
            best_skill_per_model[model] = (best_skill, best_ds)

    # Exclusive bug counts: bugs found by this skill/model and no other
    model_exclusive: dict[str, set[str]] = {}
    for m, bugs in model_bug_counts.items():
        others = set().union(*(b for m2, b in model_bug_counts.items() if m2 != m))
        model_exclusive[m] = bugs - others
    skill_exclusive: dict[str, set[str]] = {}
    for s, bugs in skill_bug_counts.items():
        others = set().union(*(b for s2, b in skill_bug_counts.items() if s2 != s))
        skill_exclusive[s] = bugs - others

    # Rarity-weighted score: sum of 1/(finder count) for each bug found.
    # Bugs found by fewer models are worth more, rewarding rare discoveries.
    # Normalized by total ground-truth bugs to keep range 0–1.
    bug_finder_count: dict[str, int] = defaultdict(int)
    for bugs in model_bug_counts.values():
        for bug in bugs:
            bug_finder_count[bug] += 1
    model_rarity: dict[str, float] = {}
    for m, bugs in model_bug_counts.items():
        score = sum(1.0 / bug_finder_count[b] for b in bugs if bug_finder_count[b] > 0)
        model_rarity[m] = score / total_bugs_ground_truth if total_bugs_ground_truth > 0 else 0.0
    skill_rarity: dict[str, float] = {}
    for s, bugs in skill_bug_counts.items():
        score = sum(1.0 / bug_finder_count[b] for b in bugs if bug_finder_count[b] > 0)
        skill_rarity[s] = score / total_bugs_ground_truth if total_bugs_ground_truth > 0 else 0.0

    # Consensus summary for verdict
    bug_finders_verdict: dict[str, list[str]] = {}
    for model, bugs in model_bug_counts.items():
        for bug in bugs:
            bug_finders_verdict.setdefault(bug, []).append(model)
    num_models = len(all_models)
    full_consensus_count = sum(
        1 for models in bug_finders_verdict.values() if len(models) == num_models
    )
    sole_count = sum(1 for models in bug_finders_verdict.values() if len(models) == 1)
    missed_count = total_bugs_ground_truth - len(bug_finders_verdict)

    # Native pairing advantage summary for verdict
    skill_impact_lines: list[str] = []
    for model in all_models:
        native = cell_data.get((model, model))
        native_ds = (
            native.get("f1", 0.0) if native and native.get("total_results", 0) > 0 else None
        )
        cross_dss = []
        for skill in all_models:
            if skill == model:
                continue
            cell = cell_data.get((model, skill))
            if cell and cell.get("total_results", 0) > 0:
                cross_dss.append(cell.get("f1", 0.0))
        cross_mean = sum(cross_dss) / len(cross_dss) if cross_dss else None
        if native_ds is None and cross_mean is None:
            skill_impact_lines.append(f"{model}: no data")
            continue
        n_val = native_ds if native_ds is not None else 0.0
        c_val = cross_mean if cross_mean is not None else 0.0
        delta = n_val - c_val
        if abs(delta) < 0.01:
            skill_impact_lines.append(f"{model}: no difference")
        elif delta > 0:
            skill_impact_lines.append(f"{model}: native helps")
        else:
            skill_impact_lines.append(f"{model}: cross helps")

    if best_pair:
        best_model = max(model_bug_counts.items(), key=lambda x: len(x[1]), default=(None, set()))
        best_skill = max(skill_bug_counts.items(), key=lambda x: len(x[1]), default=(None, set()))
        m_name, m_bugs = best_model
        s_name, s_bugs = best_skill
        lines.append("## Verdict\n")
        lines.append(
            f"**Best pairing**: `{best_pair[0]}` reviewing with `{best_pair[1]}` skill found "
            f"**{best_pair[2]} bugs** out of {total_bugs_ground_truth} ground-truth bugs.\n"
        )
        if best_ds_pair:
            native = " *(native)*" if best_ds_pair[0] == best_ds_pair[1] else ""
            lines.append(
                f"**Best Detection Score**: `{best_ds_pair[0]}` on `{best_ds_pair[1]}`{native} "
                f"(DS={best_ds_pair[2]:.2f}).\n"
            )
        if best_judge_pair:
            native = " *(native)*" if best_judge_pair[0] == best_judge_pair[1] else ""
            lines.append(
                f"**Best Judge Score**: `{best_judge_pair[0]}` on `{best_judge_pair[1]}`{native} "
                f"(J={best_judge_pair[2]:.1f}/2).\n"
            )
        pair_crit: dict[tuple[str, str], int] = {}
        for (model, skill), metrics in cell_data.items():
            if metrics.get("total_results", 0) == 0:
                continue
            sc = metrics.get("severity_counts", {})
            pair_crit[(model, skill)] = sc.get("reject", 0)
        if pair_crit:
            best_crit = max(pair_crit.items(), key=lambda x: x[1])
            if best_crit[1] > 0:
                native = " *(native)*" if best_crit[0][0] == best_crit[0][1] else ""
                lines.append(
                    f"**Best critical-bug pairing**: `{best_crit[0][0]}` on `{best_crit[0][1]}`{native} "
                    f"found **{best_crit[1]}** `reject`-severity bugs.\n"
                )
        if m_name and m_bugs:
            coverage_pct = (
                len(m_bugs) / total_bugs_ground_truth * 100
                if total_bugs_ground_truth > 0
                else 0
            )
            lines.append(
                f"**Best reviewer model**: `{m_name}` found **{len(m_bugs)}** bugs "
                f"({coverage_pct:.0f}% coverage) across all skills.\n"
            )
        if s_name and s_bugs:
            coverage_pct = (
                len(s_bugs) / total_bugs_ground_truth * 100
                if total_bugs_ground_truth > 0
                else 0
            )
            lines.append(
                f"**Best skill**: `{s_name}` found **{len(s_bugs)}** bugs "
                f"({coverage_pct:.0f}% coverage) across all models.\n"
            )
        lines.append(
            f"**Consensus**: {full_consensus_count} bug(s) found by every model "
            f"(across all skill pairings), {sole_count} by only one model, "
            f"{missed_count} missed by all. This measures inter-model agreement, "
            f"not skill-on vs skill-off.\n"
        )
        impact_str = "; ".join(skill_impact_lines)
        lines.append(f"**Native pairing advantage**: {impact_str}.\n")
        # Best skill per model recommendation
        native_best = sum(
            1
            for model, (skill, _) in best_skill_per_model.items()
            if skill == model
        )
        cross_best = len(best_skill_per_model) - native_best
        lines.append(
            f"**Best skill per model**: {native_best} model(s) perform best with their native skill, "
            f"{cross_best} with a cross-skill. "
            "See the *Best Skill per Model* table below for specifics.\n"
        )
        lines.append(
            "See `report/comparison.md` for the baseline-vs-skill analysis "
            "(whether adding any skill helps or hurts each model).\n"
        )
        lines.append("\n")

    # Metrics Glossary (at top for visibility)
    lines.append("## Metrics Glossary\n")
    lines.append(
        "- **Detection Score (DS)**: Harmonic mean of precision and recall. "
        "Measures how well findings balance correctness (precision) against completeness (recall). "
        "Range 0–1; higher is better.\n"
    )
    lines.append(
        "- **Precision**: Of all findings reported, the fraction that matched a ground-truth bug. "
        "Low precision means many false positives.\n"
    )
    lines.append(
        "- **Recall**: Of all ground-truth bugs, the fraction that were found. "
        "Low recall means missed bugs.\n"
    )
    lines.append(
        "- **Refusal Rate (R)**: Fraction of diffs where the model refused to review. "
        "In this dataset R=0 for all pairings, so it is omitted from the tables.\n"
    )
    lines.append(
        "- **Judge Score (J)**: Mean of four sub-scores (accuracy, prioritization, justification, "
        "actionability) on a 0–2 scale. Reflects review quality as scored by the judge model.\n"
    )
    lines.append(
        "- **Native**: Diagonal pairing where the model reviews a diff using its own skill "
        "(model == skill).\n"
    )
    lines.append(
        "- **Exclusive**: Bugs found by this model/skill and no other model/skill. "
        "A high exclusive count means the pairing contributes unique value.\n"
    )

    # Overview Matrix
    lines.append("\n---\n")
    lines.append("## Overview Matrix\n")
    lines.append("Each cell shows: Detection Score (DS), and mean Judge score (0–2 scale).\n")
    lines.append("*(native)* indicates diagonal pairing (model == skill).\n")

    header = "| Skill \\\\ Model |"
    for model in all_models:
        header += f" {model} |"
    lines.append(header)

    separator = "|" + "---|" * (len(all_models) + 1)
    lines.append(separator)

    for skill in all_models:
        row = f"| **{skill}** |"
        for model in all_models:
            metrics = cell_data.get((model, skill))
            if metrics and metrics["total_results"] > 0:
                f1_str = f"DS={metrics.get('f1', 0):.2f}"
                j_str = f"J={metrics.get('judge_mean', 0):.1f}/2"
                native_marker = " *(native)*" if model == skill else ""
                row += f" {f1_str} {j_str}{native_marker} |"
            else:
                row += " — |"
        lines.append(row)

    lines.append("\n")

    # Per-metric matrices
    lines.append("## Precision Matrix\n")
    lines.append("| Skill \\\\ Model |" + " |".join(all_models) + " |")
    lines.append("|" + "---|" * (len(all_models) + 1))
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
    lines.append("|" + "---|" * (len(all_models) + 1))
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

    # Judge score matrices
    for axis in ["accuracy", "prioritization", "justification", "actionability"]:
        lines.append(f"## Judge {axis.title()} Matrix\n")
        lines.append("| Skill \\\\ Model |" + " |".join(all_models) + " |")
        lines.append("|" + "---|" * (len(all_models) + 1))
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

    # Native Pairing Ranking (model == skill, diagonal cells only)
    native_rows: list[tuple[str, float, int, float, float]] = []
    for model in all_models:
        metrics = cell_data.get((model, model))
        if metrics and metrics.get("total_results", 0) > 0:
            native_rows.append((
                model,
                metrics.get("f1", 0.0),
                len(metrics.get("hits", [])),
                metrics.get("refusal_rate", 0.0),
                metrics.get("judge_mean", 0.0),
            ))
    if native_rows:
        native_rows.sort(key=lambda x: x[1], reverse=True)
        lines.append("## Native Pairing Ranking (model == skill)\n")
        lines.append("Diagonal cells only — each model using its own skill.\n")
        lines.append("| Model | Detection Score | Bugs Found | Judge Score |")
        lines.append("|-------|-----------------|------------|-------------|")
        for model, f1, bugs, _ref, judge in native_rows:
            lines.append(
                f"| {model} | {f1:.2f} | {bugs}/{total_bugs_ground_truth} "
                f"| {judge:.1f}/2 |"
            )
        lines.append("")

    # Best pairing section
    lines.append("## Best Pairing by Metric\n")
    best_f1 = None
    best_f1_val = -1
    best_judge = None
    best_judge_val = -1

    for (model, skill), metrics in cell_data.items():
        if metrics["total_results"] == 0:
            continue
        if metrics["f1"] > best_f1_val:
            best_f1_val = metrics["f1"]
            best_f1 = (model, skill)
        if metrics["judge_mean"] > best_judge_val:
            best_judge_val = metrics["judge_mean"]
            best_judge = (model, skill)

    if best_f1:
        model, skill = best_f1
        native = " *(native)*" if model == skill else ""
        lines.append(f"- **Best Detection Score**: {model} on {skill}{native} (DS={best_f1_val:.2f})\n")
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
        best_model, best_f1, best_judge, _ = model_ranked[0]
        lines.append(
            f"**Best Model**: {best_model} (row-mean DS={best_f1:.2f}, judge={best_judge:.1f})\n"
        )

    if skill_ranked:
        best_skill, best_f1, best_judge, _ = skill_ranked[0]
        lines.append(
            f"**Best Skill**: {best_skill} (column-mean DS={best_f1:.2f}, judge={best_judge:.1f})\n"
        )

    lines.append("\n### Model Rankings (by row-mean Detection Score)\n")
    lines.append("| Rank | Model | Detection Score | Judge Mean | Rarity Score |")
    lines.append("|------|-------|-----------------|------------|--------------|")
    for rank, (model, f1, judge, _refusal) in enumerate(model_ranked or [], 1):
        rarity = model_rarity.get(model, 0.0)
        lines.append(f"| {rank} | {model} | {f1:.2f} | {judge:.1f} | {rarity:.2f} |")

    lines.append("\n### Skill Rankings (by column-mean Detection Score)\n")
    lines.append("| Rank | Skill | Detection Score | Judge Mean | Rarity Score |")
    lines.append("|------|-------|-----------------|------------|--------------|")
    for rank, (skill, f1, judge, _refusal) in enumerate(skill_ranked or [], 1):
        rarity = skill_rarity.get(skill, 0.0)
        lines.append(f"| {rank} | {skill} | {f1:.2f} | {judge:.1f} | {rarity:.2f} |")

    # Bug Discovery Ranking
    lines.append("\n---\n")
    lines.append("## Bug Discovery Ranking\n")
    total_bugs = len(diff_records)
    lines.append(f"Ground-truth bugs: **{total_bugs}**\n")

    lines.append("### Bugs Found per Pairing (True Positives)\n")
    lines.append("| Model | Skill | Bugs Found (TP) | False Positives | Total Findings |")
    lines.append("|-------|-------|-----------------|-----------------|----------------|")
    pair_tp: list[tuple[str, str, int, int, int]] = []
    for (model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        tp = len(metrics.get("hits", []))
        total_f = metrics.get("total_findings", 0)
        fp = total_f - tp
        pair_tp.append((model, skill, tp, fp, total_f))
    pair_tp.sort(key=lambda x: -x[2])
    for model, skill, tp, fp, total_f in pair_tp:
        native = " *(native)*" if model == skill else ""
        lines.append(f"| {model} | {skill}{native} | {tp} | {fp} | {total_f} |")

    lines.append("\n### Bugs Found per Model (union across all skills)\n")
    lines.append("| Model | Total Found | Coverage | Exclusive |")
    lines.append("|-------|-------------|----------|-----------|")
    model_hits: dict[str, set[str]] = defaultdict(set)
    for (model, _skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) > 0:
            model_hits[model].update(metrics.get("hits", []))
    for model, hits_set in sorted(model_hits.items(), key=lambda x: -len(x[1])):
        pct = len(hits_set) / total_bugs * 100 if total_bugs > 0 else 0
        excl = len(model_exclusive.get(model, set()))
        lines.append(f"| {model} | {len(hits_set)} | {pct:.0f}% | {excl} |")

    lines.append("\n### Bugs Found per Skill (union across all models)\n")
    lines.append("| Skill | Total Found | Coverage | Exclusive |")
    lines.append("|-------|-------------|----------|-----------|")
    skill_hits: dict[str, set[str]] = defaultdict(set)
    for (_model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) > 0:
            skill_hits[skill].update(metrics.get("hits", []))
    for skill, hits_set in sorted(skill_hits.items(), key=lambda x: -len(x[1])):
        pct = len(hits_set) / total_bugs * 100 if total_bugs > 0 else 0
        excl = len(skill_exclusive.get(skill, set()))
        lines.append(f"| {skill} | {len(hits_set)} | {pct:.0f}% | {excl} |")

    lines.append("\n### Bugs Found by Only One Model\n")
    bug_finders: dict[str, list[str]] = {}
    for model, hits_set in model_hits.items():
        for bug in hits_set:
            bug_finders.setdefault(bug, []).append(model)
    sole_discoveries = {bug: models[0] for bug, models in bug_finders.items() if len(models) == 1}
    if sole_discoveries:
        lines.append("| Bug ID | Found Only By |")
        lines.append("|--------|---------------|")
        for bug, model in sorted(sole_discoveries.items()):
            lines.append(f"| {bug} | {model} |")
    else:
        lines.append(
            "No bugs found by only one model — every discovered bug was found by at least two models.\n"
        )

    # Severity Ranking
    lines.append("\n### Bugs Found by Severity (union across all pairings)\n")
    severity_totals: dict[str, int] = defaultdict(int)
    for metrics in cell_data.values():
        if metrics.get("total_results", 0) == 0:
            continue
        for sev, count in metrics.get("severity_counts", {}).items():
            severity_totals[sev] += count
    if severity_totals:
        lines.append("| Severity | Total Bugs Found |")
        lines.append("|----------|------------------|")
        ordered_sev = sorted(
            severity_totals.items(),
            key=lambda x: (
                SEVERITY_ORDER.index(x[0])
                if x[0] in SEVERITY_ORDER
                else len(SEVERITY_ORDER),
                -x[1],
            ),
        )
        for sev, count in ordered_sev:
            lines.append(f"| {sev} | {count} |")
    else:
        lines.append("No severity data available.\n")

    lines.append("\n### Severity Breakdown per Model\n")
    lines.append("| Model |" + "|".join(SEVERITY_ORDER) + "| Total |")
    lines.append("|-------|" + "|".join(["------"] * len(SEVERITY_ORDER)) + "|-------|")
    model_severity: dict[str, dict[str, int]] = {
        m: {s: 0 for s in SEVERITY_ORDER} for m in model_hits
    }
    for (model, _skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        for sev, count in metrics.get("severity_counts", {}).items():
            if sev in model_severity.get(model, {}):
                model_severity[model][sev] += count
    for model in sorted(model_hits.keys()):
        row = f"| {model} |"
        total = 0
        for sev in SEVERITY_ORDER:
            count = model_severity[model][sev]
            total += count
            row += f" {count} |"
        row += f" {total} |"
        lines.append(row)

    lines.append("\n### Severity Breakdown per Skill\n")
    lines.append("| Skill |" + "|".join(SEVERITY_ORDER) + "| Total |")
    lines.append("|-------|" + "|".join(["------"] * len(SEVERITY_ORDER)) + "|-------|")
    skill_severity: dict[str, dict[str, int]] = {
        s: {sev: 0 for sev in SEVERITY_ORDER} for s in skill_hits
    }
    for (_model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        for sev, count in metrics.get("severity_counts", {}).items():
            if sev in skill_severity.get(skill, {}):
                skill_severity[skill][sev] += count
    for skill in sorted(skill_hits.keys()):
        row = f"| {skill} |"
        total = 0
        for sev in SEVERITY_ORDER:
            count = skill_severity[skill][sev]
            total += count
            row += f" {count} |"
        row += f" {total} |"
        lines.append(row)

    lines.append("\n### Severity Breakdown per Pairing\n")
    lines.append(
        "Critical (`reject`) bug counts for each (model, skill) cell. "
        "Higher is better for critical-bug detection.\n"
    )
    pair_crit: dict[tuple[str, str], int] = {}
    pair_total: dict[tuple[str, str], int] = {}
    for (model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        sc = metrics.get("severity_counts", {})
        pair_crit[(model, skill)] = sc.get("reject", 0)
        pair_total[(model, skill)] = sum(sc.values())
    if pair_crit:
        lines.append("| Model | Skill | reject | total |")
        lines.append("|-------|-------|--------|-------|")
        ranked = sorted(
            pair_crit.items(),
            key=lambda x: (-x[1], -pair_total.get(x[0], 0)),
        )
        for (model, skill), crit in ranked:
            native = " *(native)*" if model == skill else ""
            lines.append(
                f"| {model}{native} | {skill} | {crit} | {pair_total[(model, skill)]} |"
            )
    else:
        lines.append("No per-pairing severity data available.\n")

    # Category Ranking
    lines.append("\n### Bugs Found by Category (union across all pairings)\n")
    category_totals: dict[str, int] = defaultdict(int)
    for metrics in cell_data.values():
        if metrics.get("total_results", 0) == 0:
            continue
        for cat, count in metrics.get("category_counts", {}).items():
            category_totals[cat] += count
    if category_totals:
        lines.append("| Category | Total Bugs Found |")
        lines.append("|----------|------------------|")
        for cat, count in sorted(category_totals.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"| {cat} | {count} |")
    else:
        lines.append("No category data available.\n")

    lines.append("\n### Category Breakdown per Model\n")
    all_categories = sorted(category_totals.keys())
    lines.append("| Model |" + "|".join(all_categories) + "| Total |")
    lines.append("|-------|" + "|".join(["------"] * len(all_categories)) + "|-------|")
    model_category: dict[str, dict[str, int]] = {
        m: {c: 0 for c in all_categories} for m in model_hits
    }
    for (model, _skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        for cat, count in metrics.get("category_counts", {}).items():
            if cat in model_category.get(model, {}):
                model_category[model][cat] += count
    for model in sorted(model_hits.keys()):
        row = f"| {model} |"
        total = 0
        for cat in all_categories:
            count = model_category[model][cat]
            total += count
            row += f" {count} |"
        row += f" {total} |"
        lines.append(row)

    lines.append("\n### Category Breakdown per Skill\n")
    lines.append("| Skill |" + "|".join(all_categories) + "| Total |")
    lines.append("|-------|" + "|".join(["------"] * len(all_categories)) + "|-------|")
    skill_category: dict[str, dict[str, int]] = {
        s: {c: 0 for c in all_categories} for s in skill_hits
    }
    for (_model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        for cat, count in metrics.get("category_counts", {}).items():
            if cat in skill_category.get(skill, {}):
                skill_category[skill][cat] += count
    for skill in sorted(skill_hits.keys()):
        row = f"| {skill} |"
        total = 0
        for cat in all_categories:
            count = skill_category[skill][cat]
            total += count
            row += f" {count} |"
        row += f" {total} |"
        lines.append(row)

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

    # Consensus Analysis: for each ground-truth bug, how many of the four models found it
    lines.append("\n---\n")
    lines.append("## Consensus Analysis\n")
    lines.append(
        "For each ground-truth bug, how many of the four reviewing models found it "
        "(union across all skills). Full consensus = 4/4.\n"
    )
    # Reuse bug_finders computed earlier
    finder_counts = {bug: len(models) for bug, models in bug_finders.items()}
    consensus_buckets: dict[int, list[str]] = defaultdict(list)
    for bug, count in finder_counts.items():
        consensus_buckets[count].append(bug)
    total_gt = total_bugs_ground_truth if total_bugs_ground_truth > 0 else 1
    lines.append("| Finders | Bugs Found | % of Ground Truth |")
    lines.append("|---------|-------------|--------------------|")
    for count in range(4, 0, -1):
        bugs = consensus_buckets.get(count, [])
        pct = len(bugs) / total_gt * 100
        lines.append(f"| {count}/4 models | {len(bugs)} | {pct:.0f}% |")
    missed = total_bugs_ground_truth - len(finder_counts)
    missed_pct = missed / total_gt * 100 if total_gt > 0 else 0
    lines.append(f"| 0/4 models (missed) | {missed} | {missed_pct:.0f}% |")
    lines.append("")

    found_by_all = consensus_buckets.get(4, [])
    found_by_one = consensus_buckets.get(1, [])
    if found_by_all:
        lines.append(
            f"**{len(found_by_all)} bug(s) reached full consensus** — found by all four models. "
            "These represent the easiest-to-detect defects.\n"
        )
    if found_by_one:
        lines.append(
            f"**{len(found_by_one)} bug(s) found by only one model** — these highlight "
            "model-specific strengths and potential complementarity.\n"
        )
    if missed > 0:
        lines.append(
            f"**{missed} bug(s) missed by every model** — these may require skill refinement "
            "or represent subtle defects beyond current detection capability.\n"
        )

    # Native Pairing Advantage: native vs cross-skill Detection Score per model
    lines.append("\n---\n")
    lines.append("## Native Pairing Advantage\n")
    lines.append(
        "For each model, compare its native skill (model == skill) against the mean of "
        "cross-skills (model != skill). Positive delta = native skill helps; "
        "negative = cross-skill helps. This measures native-skill advantage, not "
        "skill-on vs skill-off — for that comparison see `report/comparison.md`.\n"
    )
    lines.append("| Model | Native DS | Cross-Skill Mean DS | Delta | Verdict |")
    lines.append("|-------|----------|---------------------|-------|---------|")
    for model in all_models:
        native = cell_data.get((model, model))
        native_ds = native.get("f1", 0.0) if native and native.get("total_results", 0) > 0 else None
        cross_dss = []
        for skill in all_models:
            if skill == model:
                continue
            cell = cell_data.get((model, skill))
            if cell and cell.get("total_results", 0) > 0:
                cross_dss.append(cell.get("f1", 0.0))
        cross_mean = sum(cross_dss) / len(cross_dss) if cross_dss else None
        if native_ds is None and cross_mean is None:
            lines.append(f"| {model} | — | — | — | no data |")
            continue
        n_val = native_ds if native_ds is not None else 0.0
        c_val = cross_mean if cross_mean is not None else 0.0
        delta = n_val - c_val
        if abs(delta) < 0.01:
            verdict = "no difference"
        elif delta > 0:
            verdict = "native helps"
        else:
            verdict = "cross helps"
        n_str = f"{n_val:.2f}" if native_ds is not None else "—"
        c_str = f"{c_val:.2f}" if cross_mean is not None else "—"
        lines.append(f"| {model} | {n_str} | {c_str} | {delta:+.2f} | {verdict} |")
    lines.append("")

    # Best Skill per Model: the highest-DS skill for each model
    lines.append("## Best Skill per Model\n")
    lines.append(
        "For each model, the skill that produces the highest Detection Score. "
        "Since true-positive counts are model-driven while the skill mainly affects "
        "the false-positive rate, the recommended skill is the one that maximizes DS "
        "(i.e., minimizes false positives).\n"
    )
    lines.append("| Model | Best Skill | DS | Recommendation |")
    lines.append("|-------|-----------|----|----------------|")
    for model in all_models:
        if model not in best_skill_per_model:
            lines.append(f"| {model} | — | — | no data |")
            continue
        best_skill, best_ds = best_skill_per_model[model]
        if best_skill == model:
            rec = "native skill"
        else:
            rec = f"cross-skill `{best_skill}`"
        lines.append(
            f"| {model} | {best_skill} | {best_ds:.2f} | {rec} |"
        )
    lines.append("")

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
