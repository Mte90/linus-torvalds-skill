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
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Models to include in the matrix
MODELS = ["gpt-oss-120b", "mistral-small-4-119b", "glm5.2", "qwen3.8-27b"]

ROOT = Path(__file__).resolve().parent.parent

# Import shared matcher + severity vocabulary from the src/ package
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from torvalds_skill.matching import (  # noqa: E402
    dedupe_records,
    finding_identity,
    match_finding_to_bug,
)
from torvalds_skill.provenance import (  # noqa: E402
    EvalProvenance,
)
from torvalds_skill.provenance import (
    banner as provenance_banner,
)
from torvalds_skill.provenance import (
    limitation as provenance_limitation,
)
from torvalds_skill.severity import GROUND_TRUTH_SEVERITIES as SEVERITY_ORDER  # noqa: E402

# Noise threshold for DS comparisons (used in overview note and verdict)
DS_NOISE_THRESHOLD = 0.03


def load_jsonl(path: Path) -> list[dict]:
    """Load JSONL file, returning empty list if missing or empty.

    Superseded records are dropped: the eval pipeline appends a re-run next to a
    judge-failed record instead of overwriting it, so the same evaluation can
    appear twice. The last one written wins, which is how the resume index
    itself resolves the collision.
    """
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
    return dedupe_records(records)


def _benchmark_to_diff_records(bugs: list[dict]) -> list[dict]:
    """Convert benchmark bugs into synthetic diff-records for compute_cell_metrics.

    Each bug becomes a record with id, file, bugs=[bug], expected='findings'
    so the renderer's matching logic works unchanged.
    """
    return [
        {
            "id": bug.get("id", f"SC-{i}"),
            "file": bug.get("file", "unknown"),
            "bugs": [bug],
            "expected": "findings",
        }
        for i, bug in enumerate(bugs)
    ]


def group_results_by_pairing(results: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group results by (model, skill) pairing.

    For diagonal records (no skill field), skill defaults to model.
    For cross records, skill is explicitly set.
    For baseline records, skill is "none".
    """
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for result in results:
        model = result.get("model", "unknown")
        skill = result.get("skill", model)
        grouped[(model, skill)].append(result)
    return dict(grouped)


def is_baseline_record(result: dict) -> bool:
    """Check if a result record is a baseline record (skill == "none")."""
    return result.get("skill") == "none"


def separate_baseline_from_skills(
    results: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Separate baseline records (skill=="none") from skill records.

    Returns:
        (baseline_results, skill_results) - baseline records first, then skill records
    """
    baseline = [r for r in results if is_baseline_record(r)]
    skills = [r for r in results if not is_baseline_record(r)]
    return baseline, skills


def match_finding_to_diff_bug(finding: dict, diff_record: dict) -> dict | None:
    """Return the matched ground-truth bug dict for a diff record, or None.

    Bugs inherit their file from the parent diff record; the shared matcher
    enforces the ±5 line tolerance.
    """
    return match_finding_to_bug(finding, diff_record.get("bugs", []), diff_record.get("file", ""))


def compute_cell_metrics(results: list[dict], diff_records: list[dict]) -> dict[str, Any]:
    """Compute metrics for a single (model, skill) cell.

    Also captures the matched bug identifiers with their severity and category
    so the renderer can produce per-severity and per-category rankings.
    """
    empty = {
        "precision": 0.0,
        "recall": 0.0,
        "ds": 0.0,
        "refusal_rate": 0.0,
        "judge_accuracy": 0.0,
        "judge_prioritization": 0.0,
        "judge_justification": 0.0,
        "judge_actionability": 0.0,
        "judge_mean": 0.0,
        "total_results": 0,
        "total_findings": 0,
        "matches_a_bug": 0,
        "unmatched": 0,
        "duplicate_findings": 0,
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
    # Repetitions re-run the same diff, so the same finding recurs across reps.
    # Deduplicating keeps precision and the severity/category rankings measuring
    # distinct findings instead of how many times a diff happened to be re-run.
    seen_findings: set[tuple[Any, ...]] = set()
    # (diff_id, bug line) pairs already credited to a finding, so a second finding
    # pointing at the same bug is classified as a duplicate rather than a new hit.
    claimed_bugs: set[tuple[Any, Any]] = set()
    matches_a_bug = 0
    unmatched_findings = 0
    duplicate_findings = 0
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
                bug_line = matched_bug.get("line")
                key = finding_identity(finding, diff_id)
                if key in seen_findings:
                    duplicate_findings += 1
                    break
                seen_findings.add(key)
                # Two findings can legitimately match the same bug (adjacent lines);
                # only the first is a hit, the rest are duplicates.
                claim = (diff_id, bug_line)
                if claim in claimed_bugs:
                    duplicate_findings += 1
                    break
                claimed_bugs.add(claim)
                matches_a_bug += 1
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
            else:
                unmatched_key = finding_identity(finding, None)
                if unmatched_key not in seen_findings:
                    seen_findings.add(unmatched_key)
                    unmatched_findings += 1

    hits = sorted(matched_diff_ids)
    misses = sorted([r["id"] for r in diff_records if r.get("id") not in matched_diff_ids])

    total_findings = len(seen_findings)
    precision = len(hits) / total_findings if total_findings > 0 else 0.0
    # Plan B: recall denominator = buggy diffs only (expected == "findings")
    # Plan B: recall denominator = buggy diffs only (expected == "findings")
    buggy_count = sum(1 for r in diff_records if r.get("expected") == "findings")
    recall = len(hits) / buggy_count if buggy_count > 0 else 0.0
    ds = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
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
        "ds": ds,
        "refusal_rate": refusal_rate,
        "matches_a_bug": matches_a_bug,
        "unmatched": unmatched_findings,
        "duplicate_findings": duplicate_findings,
        "judge_accuracy": judge_accuracy,
        "judge_prioritization": judge_prioritization,
        "judge_justification": judge_justification,
        "judge_actionability": judge_actionability,
        "judge_mean": judge_mean,
        "total_findings": total_findings,
        "total_results": len(results),
        "reps": len({r.get("rep", 0) for r in results}),
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
        (model_means, skill_means) where each maps name -> {ds, judge_mean, refusal_rate}
    """
    # Derive all unique skills from cell_data (they may differ from all_models in test fixtures)
    all_skills = sorted(set(s for (m, s) in cell_data.keys()))

    model_sums: dict[str, dict[str, float]] = {
        m: {"ds": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0} for m in all_models
    }
    model_counts: dict[str, int] = {m: 0 for m in all_models}
    skill_sums: dict[str, dict[str, float]] = {
        s: {"ds": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0} for s in all_skills
    }
    skill_counts: dict[str, int] = {s: 0 for s in all_skills}

    for (model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        ds = metrics.get("ds", 0.0)
        judge = metrics.get("judge_mean", 0.0)
        refusal = metrics.get("refusal_rate", 0.0)

        model_sums[model]["ds"] += ds
        model_sums[model]["judge_mean"] += judge
        model_sums[model]["refusal_rate"] += refusal
        model_counts[model] += 1

        skill_sums[skill]["ds"] += ds
        skill_sums[skill]["judge_mean"] += judge
        skill_sums[skill]["refusal_rate"] += refusal
        skill_counts[skill] += 1

    model_means = {}
    for model in all_models:
        count = model_counts[model]
        if count > 0:
            model_means[model] = {
                "ds": model_sums[model]["ds"] / count,
                "judge_mean": model_sums[model]["judge_mean"] / count,
                "refusal_rate": model_sums[model]["refusal_rate"] / count,
            }
        else:
            model_means[model] = {"ds": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0}

    skill_means = {}
    for skill in all_skills:
        count = skill_counts[skill]
        if count > 0:
            skill_means[skill] = {
                "ds": skill_sums[skill]["ds"] / count,
                "judge_mean": skill_sums[skill]["judge_mean"] / count,
                "refusal_rate": skill_sums[skill]["refusal_rate"] / count,
            }
        else:
            skill_means[skill] = {"ds": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0}

    # Add missing models/skills with zero values
    for model in all_models:
        if model not in model_means:
            model_means[model] = {"ds": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0}
    for skill in all_models:
        if skill not in skill_means:
            skill_means[skill] = {"ds": 0.0, "judge_mean": 0.0, "refusal_rate": 0.0}

    return model_means, skill_means


def rank_by_verdict(means: dict[str, dict[str, float]]) -> list[tuple[str, float, float, float]]:
    """Rank items by Detection Score (desc), tiebreak by judge mean (desc), then refusal (asc)."""
    items = [
        (name, data["ds"], data["judge_mean"], data["refusal_rate"]) for name, data in means.items()
    ]
    items.sort(key=lambda x: (-x[1], -x[2], x[3]))
    return items


def collect_unmatched_findings(
    all_results: list[dict], diff_records: list[dict]
) -> tuple[list[dict], dict[tuple[str, str], int]]:
    """Collect findings that match NO ground-truth bug.

    Matches findings against diff_records directly (same logic as compute_cell_metrics),
    NOT via diff_id lookup. This ensures the unmatched count equals the pairing table's
    unmatched value. Baseline records (skill=="none") are excluded so the list lines
    up 1:1 with the "Bugs Found per Pairing" table.
    """
    unmatched = []
    counts: dict[tuple[str, str], int] = defaultdict(int)

    for result in all_results:
        # Skip baseline records to match the pairing table
        if is_baseline_record(result):
            continue

        model = result.get("model", "unknown")
        skill = result.get("skill", model)
        findings = result.get("findings", [])

        for finding in findings:
            # Match against all diff_records (same logic as compute_cell_metrics)
            matched = None
            for diff_record in diff_records:
                matched = match_finding_to_diff_bug(finding, diff_record)
                if matched is not None:
                    break

            if matched is None:
                file_path = finding.get("file", "unknown")
                line = finding.get("line")
                severity = finding.get("severity", "unknown")
                issue = (finding.get("issue") or "")[:100]
                if not issue.strip() or issue.strip() == "no issue described":
                    continue
                unmatched.append(
                    {
                        "diff_id": result.get("diff_id", "unknown"),
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
            matched = match_finding_to_bug(finding, bugs, diff_record.get("file", ""))
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


def metrics_total(cell_data: dict, key: tuple[str, str]) -> int:
    """Total distinct findings for a cell, or 0 when the cell is missing."""
    return cell_data.get(key, {}).get("total_findings", 0)


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
    baseline_cell_data: dict[str, dict[str, Any]] | None = None,
    has_baseline: bool = False,
    eval_provenance: EvalProvenance = "decontaminated",
    codebase_mode: bool = False,
) -> None:
    """Render the cross-model evaluation matrix as markdown with extended sections.

    Args:
        cell_data: Dict mapping (model, skill) -> metrics dict
        all_models: List of all model/skill names
        diff_records: Ground-truth diff records
        out_path: Output file path
        model_ranked: Pre-computed model rankings
        skill_ranked: Pre-computed skill rankings (excludes baseline)
        unmatched: Unmatched findings
        unmatched_counts: Unmatched counts by pairing
        cross_only: Cross-only discoveries
        cross_only_counts: Cross-only counts by skill
        eval_provenance: Which reviewer-prompt version produced the results being rendered.
            Stated in the report header so a report cannot silently claim clean data.
        baseline_cell_data: Dict mapping model -> baseline metrics (skill="none")
        has_baseline: Whether baseline data exists
    """
    lines: list[str] = []

    # Dataset composition counts (also used by the glossary)
    buggy_count = sum(1 for r in diff_records if r.get("expected") == "findings")
    clean_count = sum(1 for r in diff_records if r.get("expected") == "no-findings")
    refuse_count = sum(1 for r in diff_records if r.get("expected") == "refuse-to-conclude")

    # Header: each fact stated exactly once
    lines.append("# Cross-Model Evaluation Matrix\n")
    if codebase_mode:
        lines.append(
            f"Source: full SmallChat review ([data/eval_results_codebase.jsonl](data/eval_results_codebase.jsonl)) scored against "
            f"{len(diff_records)} ground-truth bugs from [benchmark.jsonl](data/benchmark.jsonl).\n"
        )
    else:
        lines.append(
            "Diagonal data from `data/eval_results.jsonl`, cross-data from `data/eval_results_cross.jsonl`.\n"
        )
        lines.append(
            f"Dataset: {len(diff_records)} diff scenarios = {buggy_count} buggy, {clean_count} clean "
            f"(no findings expected), {refuse_count} refuse-to-conclude (correct answer is uncertainty).\n"
        )
    lines.append(
        "Judge: GLM5.2, a fixed external model applied at generation time (`--judge-model`). "
        "It also reviews here, so judge scores may carry self-preference.\n"
    )
    lines.append(provenance_banner(eval_provenance) + "\n")

    # About this report
    lines.append("## About this report\n")
    if codebase_mode:
        lines.append(
            "This report answers: **which model+skill combination detects bugs best?** "
            "It is a cross-model evaluation on the real SmallChat codebase "
            "(43 ground-truth bugs).\n"
        )
    else:
        lines.append(
            "This report answers: **which model+skill combination detects bugs best?** "
            "It is a cross-model evaluation on 45 synthetic diffs.\n"
        )
    lines.append(
        "Three roles are at play:\n\n"
        "1. **Reviewer model** — the model that reads the code and produces findings. "
        "It determines *which* bugs are found and drives the true-positive count.\n"
        "2. **Skill** — the prompt/skill applied to the reviewer. It influences precision "
        "(false-positive rate) but rarely changes which bugs are detected.\n"
        "3. **Judge model** — scores the *quality* of each review on four axes "
        "(accuracy, prioritization, justification, actionability). The judge does **not** "
        "affect the Detection Score, true positives, recall, or precision. "
        "It can be disabled with `--no-judge`.\n\n"
        "A pairing is written `A × B`: reviewer model `A` reads the code using the skill "
        "written by `B`. `A × A` is the native pairing. "
        "For baseline-vs-skill analysis (does the skill help or hurt each model?), see "
        "[report/comparison.md](report/comparison.md).\n"
    )

    # Plain-language verdict (computed up-front from the whole matrix)
    total_bugs_ground_truth = buggy_count  # Plan B: buggy diffs only
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
        ds = metrics.get("ds", 0.0)
        if best_ds_pair is None or ds > best_ds_pair[2]:
            best_ds_pair = (model, skill, ds)
        jm = metrics.get("judge_mean", 0.0)
        if best_judge_pair is None or jm > best_judge_pair[2]:
            best_judge_pair = (model, skill, jm)

    # Best skill per model: highest-DS skill for each model (native or cross) - TIE-AWARE
    best_skill_per_model: dict[str, list[tuple[str, float]]] = {}
    for model in all_models:
        best_ds: float = -1.0
        tied_skills: list[str] = []
        for skill in all_models:
            cell = cell_data.get((model, skill))
            if not cell or cell.get("total_results", 0) == 0:
                continue
            ds = cell.get("ds", 0.0)
            if ds > best_ds:
                best_ds = ds
                tied_skills = [skill]
            elif ds == best_ds:
                tied_skills.append(skill)
        if tied_skills:
            best_skill_per_model[model] = [(s, best_ds) for s in tied_skills]

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

    # Native pairing advantage summary for verdict. Structured, so the verdict can
    # summarise the pattern once instead of repeating one line per model.
    skill_impact_data: list[tuple[str, float | None, float | None]] = []
    for model in all_models:
        native = cell_data.get((model, model))
        native_ds = native.get("ds", 0.0) if native and native.get("total_results", 0) > 0 else None
        cross_dss = []
        for skill in all_models:
            if skill == model:
                continue
            cell = cell_data.get((model, skill))
            if cell and cell.get("total_results", 0) > 0:
                cross_dss.append(cell.get("ds", 0.0))
        cross_mean = sum(cross_dss) / len(cross_dss) if cross_dss else None
        if native_ds is None and cross_mean is None:
            continue
        skill_impact_data.append((model, native_ds, cross_mean))

    if best_pair:
        # Tie-aware: collect all models/skills tied at max bug count
        best_model_bugs = -1
        best_models_list: list[str] = []
        for model, bugs in model_bug_counts.items():
            if len(bugs) > best_model_bugs:
                best_model_bugs = len(bugs)
                best_models_list = [model]
            elif len(bugs) == best_model_bugs:
                best_models_list.append(model)

        best_skill_bugs = -1
        best_skills_list: list[str] = []
        for skill, bugs in skill_bug_counts.items():
            if len(bugs) > best_skill_bugs:
                best_skill_bugs = len(bugs)
                best_skills_list = [skill]
            elif len(bugs) == best_skill_bugs:
                best_skills_list.append(skill)

        def cell_stats(model: str, skill: str) -> tuple[int, int, int, int, float, float]:
            """Return (bugs found, findings, duplicates, false alarms, DS, judge) for one cell."""
            metrics = cell_data.get((model, skill), {})
            return (
                metrics.get("matches_a_bug", 0),
                metrics.get("total_findings", 0),
                metrics.get("duplicate_findings", 0),
                metrics.get("unmatched", 0),
                metrics.get("ds", 0.0),
                metrics.get("judge_mean", 0.0),
            )

        def times(count: int, singular: str, plural_form: str | None = None) -> str:
            return singular if count == 1 else (plural_form or singular + "s")

        def findings_breakdown(bugs: int, reported: int, dups: int, wrong: int) -> str:
            """Spell out what a cell's findings turned into, so no glossary lookup is needed."""
            parts = [f"{bugs} matched a real bug"]
            if dups:
                parts.append(f"{dups} {times(dups, 'was', 'were')} a duplicate")
            if wrong:
                parts.append(f"{wrong} matched nothing")
            return f"{reported} findings: " + ", ".join(parts)

        verdict: list[str] = ["## Verdict", ""]
        verdict.append(
            "A **pairing** is one reviewer model plus one skill, written `A × B`: reviewer `A` "
            "reads the code using the skill written by `B`. `A × A` is the **native** pairing, "
            "where a model uses its own skill."
        )
        best_tp, best_reported, best_dups, best_fp, _, _ = cell_stats(best_pair[0], best_pair[1])

        verdict += ["", "**Most bugs found**", ""]
        verdict.append(
            f"- `{best_pair[0]}` × `{best_pair[1]}` — **{best_tp} of "
            f"{total_bugs_ground_truth}** real bugs. {findings_breakdown(best_tp, best_reported, best_dups, best_fp).capitalize()}."
        )

        verdict += ["", "**Cleanest review (Detection Score)**", ""]
        verdict.append(
            "Detection Score weighs bugs found against findings that were not bugs, so a "
            "review that buries real bugs in noise scores lower than its bug count suggests."
        )
        verdict.append("")
        if best_ds_pair:
            ds_tp, ds_reported, ds_dups, ds_fp, ds_val, _ = cell_stats(
                best_ds_pair[0], best_ds_pair[1]
            )
            native = " *(native)*" if best_ds_pair[0] == best_ds_pair[1] else ""
            verdict.append(
                f"- Highest: `{best_ds_pair[0]}` × `{best_ds_pair[1]}`{native} — "
                f"{ds_val:.2f}, from {findings_breakdown(ds_tp, ds_reported, ds_dups, ds_fp)}."
            )
            if best_ds_pair[:2] != best_pair[:2]:
                penalty = (
                    "those extra findings are mostly not bugs"
                    if best_fp * 2 > best_reported
                    else "it pays for the extra bugs with more wrong findings"
                )
                verdict.append(
                    f"- The bug-count leader lands lower ({findings_breakdown(best_tp, best_reported, best_dups, best_fp)}) "
                    f"because {penalty}."
                )

        verdict += ["", "**Best-written review (judge score)**", ""]
        verdict.append(
            "A separate judge model (GLM5.2) rates the write-up for clarity, prioritisation, "
            "justification and actionability. It never checks whether a finding is a real bug, "
            "so a well-argued review of nothing scores well."
        )
        verdict.append("")
        if best_judge_pair:
            judge_tp, _, _, _, _, judge_val = cell_stats(best_judge_pair[0], best_judge_pair[1])
            native = " *(native)*" if best_judge_pair[0] == best_judge_pair[1] else ""
            verdict.append(
                f"- Highest: `{best_judge_pair[0]}` × `{best_judge_pair[1]}`{native} — "
                f"{judge_val:.1f}/2, while finding {judge_tp} of "
                f"{total_bugs_ground_truth} real bugs."
            )

        pair_crit: dict[tuple[str, str], int] = {}
        for (model, skill), metrics in cell_data.items():
            if metrics.get("total_results", 0) == 0:
                continue
            pair_crit[(model, skill)] = metrics.get("severity_counts", {}).get("reject", 0)
        best_crit_val = max(pair_crit.values()) if pair_crit else 0
        best_crit_pairs = [p for p, v in pair_crit.items() if v == best_crit_val]
        if best_crit_val > 0:
            verdict += ["", "**Most serious bugs**", ""]
            verdict.append(
                "Serious bugs are the ones marked `reject`-severity: a reviewer would block a "
                "merge over them."
            )
            verdict.append("")
            by_model: dict[str, list[str]] = defaultdict(list)
            for model, skill in best_crit_pairs:
                by_model[model].append(skill)
            groups = "; ".join(
                f"`{m}` × {{{', '.join(f'`{s}`' for s in skills)}}}"
                for m, skills in by_model.items()
            )
            verdict.append(
                f"- Tied at **{best_crit_val}** {times(best_crit_val, 'bug')} across "
                f"{len(best_crit_pairs)} {times(len(best_crit_pairs), 'pairing')} — {groups}."
            )

        verdict += ["", "**Across the whole matrix**", ""]
        if best_models_list:
            model_str = ", ".join(f"`{m}`" for m in best_models_list)
            coverage_pct = (
                best_model_bugs / total_bugs_ground_truth * 100
                if total_bugs_ground_truth > 0
                else 0
            )
            verdict.append(
                f"- Best reviewer, counting every bug it found with any of its skills: "
                f"{model_str} — **{best_model_bugs} of {total_bugs_ground_truth}** "
                f"({coverage_pct:.0f}%). This rewards breadth, so a noisy reviewer can win here."
            )
        if best_skills_list:
            skill_str = ", ".join(f"`{s}`" for s in best_skills_list)
            coverage_pct = (
                best_skill_bugs / total_bugs_ground_truth * 100
                if total_bugs_ground_truth > 0
                else 0
            )
            verdict.append(
                f"- Best skill, counting every bug any reviewer found while using it: "
                f"{skill_str} — **{best_skill_bugs} of {total_bugs_ground_truth}** "
                f"({coverage_pct:.0f}%)."
            )
        verdict.append(
            f"- Consensus over {num_models} models: {full_consensus_count} "
            f"{times(full_consensus_count, 'bug')} found by all of them (easy to spot), "
            f"{sole_count} by exactly one (contestable), {missed_count} by none."
        )

        verdict += ["", "**Native skill or a borrowed one**", ""]
        verdict.append(
            "Delta = the model's own skill minus the average of its three borrowed skills. "
            "Negative means borrowing another model's skill scored better."
        )
        verdict.append("")
        comparable = [(m, n, c) for m, n, c in skill_impact_data if n is not None and c is not None]
        cross_better = [t for t in comparable if t[1] - t[2] < -0.01]
        native_better = [t for t in comparable if t[1] - t[2] > 0.01]
        if comparable and len(cross_better) == len(comparable) and not native_better:
            widest = max(cross_better, key=lambda t: t[2] - t[1])
            verdict.append(
                f"- Borrowed skills beat the native one for all {len(comparable)} models. "
                f"Widest gap: `{widest[0]}` — own skill {widest[1]:.2f} vs borrowed "
                f"{widest[2]:.2f}."
            )
        elif comparable and len(native_better) == len(comparable) and not cross_better:
            verdict.append(
                f"- The model's own skill beats every borrowed one, for all "
                f"{len(comparable)} models."
            )
        elif comparable:
            verdict.append(
                f"- Own skill wins for {len(native_better)} of {len(comparable)} models, "
                f"a borrowed skill for {len(cross_better)}."
            )

        native_best = sum(
            1
            for model, skill_list in best_skill_per_model.items()
            if any(s == model for s, _ in skill_list)
        )
        cross_best = len(best_skill_per_model) - native_best
        verdict.append(
            f"- Best skill per model: {native_best} of {len(best_skill_per_model)} "
            f"{times(len(best_skill_per_model), 'model')} do best with their own skill, "
            f"{cross_best} with a borrowed one."
        )

        granularity = (
            f"{total_bugs_ground_truth} bugs is a small sample: one extra bug moves Detection "
            f"Score by about {1 / total_bugs_ground_truth:.2f}, so gaps under ~0.05 are ties."
            if total_bugs_ground_truth > 0
            else "Ground-truth bug list is empty, so every score here is zero."
        )
        same_data = (
            "Both reports use the same codebase."
            if codebase_mode
            else "The two reports use different datasets, so do not compare numbers across them."
        )
        verdict += ["", f"**How much to trust this:** {granularity}"]
        verdict += [
            "",
            f"Baseline-vs-skill (does a skill help or hurt a model at all?) is in "
            f"[report/comparison.md](report/comparison.md). {same_data}",
        ]
        lines.append("\n".join(verdict) + "\n")

    # Overview Matrix
    lines.append("\n---\n")
    lines.append("## Overview Matrix\n")
    lines.append(
        "Rows = skill applied to the reviewer; columns = reviewer model. Each cell shows Detection "
        "Score (DS). `*(native)*` marks diagonal pairings (model == skill). The highest DS in the "
        "matrix is shown in **bold** with a ★.\n"
    )
    max_reps = max((cell.get("reps", 1) for cell in cell_data.values()), default=1)
    run_note = (
        f"{max_reps} run{'s' if max_reps != 1 else ''} per cell"
        if max_reps > 1
        else "1 run per cell"
    )
    if codebase_mode:
        lines.append(
            f"**Note**: n={buggy_count} ground-truth bugs, {run_note}; intra-skill Detection Score "
            f"differences of ~{DS_NOISE_THRESHOLD} are not significant.\n"
        )
    else:
        lines.append(
            f"**Note**: n=45 scenarios (25 buggy), {run_note}; intra-skill Detection Score "
            f"differences of ~{DS_NOISE_THRESHOLD} are not significant.\n"
        )

    # Best DS across all cells — highlighted with ★ in the Overview Matrix
    best_ds_value = -1.0
    for (_model, _skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        ds = metrics.get("ds", 0.0)
        if ds > best_ds_value:
            best_ds_value = ds

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
                ds = metrics.get("ds", 0.0)
                ds_str = f"DS={ds:.2f}"
                native_marker = " *(native)*" if model == skill else ""
                is_best = best_ds_value >= 0 and abs(ds - best_ds_value) < 1e-9
                cell_text = f"{ds_str}{native_marker}"
                if is_best:
                    cell_text = f"**{cell_text} ★**"
                row += f" {cell_text} |"
            else:
                row += " — |"
        lines.append(row)

    # Baseline row (No skill)
    if has_baseline and baseline_cell_data:
        row = "| **No skill (baseline)** |"
        for model in all_models:
            metrics = baseline_cell_data.get(model)
            if metrics and metrics["total_results"] > 0:
                ds_str = f"DS={metrics.get('ds', 0):.2f}"
                row += f" {ds_str} |"
            else:
                row += " — |"
        lines.append(row)

    lines.append("\n")

    # Judge Score Matrix (separate table below Overview)
    lines.append("### Judge Score Matrix (J, 0-2 scale)\n")
    lines.append(
        "Rows = skill applied, columns = reviewer model. Judge scores only (J, 0–2 scale). "
        "The highest J in the matrix is shown in **bold** with a ★. "
        "Note: J does not affect DS.\n"
    )

    # Best J across all cells
    best_j_value = -1.0
    for (_model, _skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        j = metrics.get("judge_mean", 0.0)
        if j > best_j_value:
            best_j_value = j

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
                j = metrics.get("judge_mean", 0.0)
                j_str = f"J={j:.1f}/2"
                native_marker = " *(native)*" if model == skill else ""
                is_best = best_j_value >= 0 and abs(j - best_j_value) < 1e-9
                cell_text = f"{j_str}{native_marker}"
                if is_best:
                    cell_text = f"**{cell_text} ★**"
                row += f" {cell_text} |"
            else:
                row += " — |"
        lines.append(row)

    # Baseline row (No skill) for Judge Score Matrix
    if has_baseline and baseline_cell_data:
        row = "| **No skill (baseline)** |"
        for model in all_models:
            metrics = baseline_cell_data.get(model)
            if metrics and metrics["total_results"] > 0:
                j_str = f"J={metrics.get('judge_mean', 0):.1f}/2"
                row += f" {j_str} |"
            else:
                row += " — |"
        lines.append(row)

    lines.append("\n")

    # Footnote for Overview Matrix
    lines.append(
        "*DS = Detection Score (precision-weighted recall). J = Judge Score (0–3 quality rating by GLM5.2). "
        "Cells use `reviewer × skill` notation. Bold ★ marks the best Detection Score.*\n"
    )

    if codebase_mode and unmatched:
        unlocated = sum(1 for finding in unmatched if finding.get("line") is None)
        if unlocated:
            lines.append(
                f"**Unlocatable findings**: {unlocated} finding(s) in this run cite no line number. "
                "They cannot be matched against a ground-truth bug and are counted as false "
                "positives.\n"
            )

    # Per-metric matrices
    lines.append("## Precision Matrix\n")
    lines.append(
        "Rows = skill applied, columns = reviewing model. Fraction of reported findings "
        "that matched a real bug — higher is better; low values flag noisy reviewers.\n"
    )
    lines.append("| Skill \\\\ Model | " + " | ".join(all_models) + " |")
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

    # Baseline row (No skill)
    if has_baseline and baseline_cell_data:
        row = "| No skill (baseline) |"
        for model in all_models:
            metrics = baseline_cell_data.get(model)
            if metrics and metrics["total_results"] > 0 and "precision" in metrics:
                row += f" {metrics['precision']:.2f} |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("\n")

    lines.append("## Recall Matrix\n")
    lines.append(
        "Rows = skill applied, columns = reviewing model. Matched findings per "
        + ("ground-truth bug" if codebase_mode else "buggy diff scenario")
        + f" ({buggy_count} ground-truth bugs) — higher is better.\n"
    )
    lines.append("| Skill \\\\ Model | " + " | ".join(all_models) + " |")
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

    # Baseline row (No skill)
    if has_baseline and baseline_cell_data:
        row = "| No skill (baseline) |"
        for model in all_models:
            metrics = baseline_cell_data.get(model)
            if metrics and metrics["total_results"] > 0 and "recall" in metrics:
                row += f" {metrics['recall']:.2f} |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("\n")

    # Judge score matrices — moved to Judge Score Detail appendix at end of report

    # Native Pairing Ranking (model == skill, diagonal cells only)
    native_rows: list[tuple[str, float, int, float, float]] = []
    for model in all_models:
        metrics = cell_data.get((model, model))
        if metrics and metrics.get("total_results", 0) > 0:
            native_rows.append(
                (
                    model,
                    metrics.get("ds", 0.0),
                    len(metrics.get("hits", [])),
                    metrics.get("refusal_rate", 0.0),
                    metrics.get("judge_mean", 0.0),
                )
            )
    if native_rows:
        native_rows.sort(key=lambda x: x[1], reverse=True)
        lines.append("## Native Pairing Ranking (model == skill)\n")
        lines.append("Diagonal cells only — each model using its own skill.\n")
        lines.append("| Model | Detection Score | Bugs Found | Judge Score |")
        lines.append("|-------|-----------------|------------|-------------|")
        for model, ds, bugs, _ref, judge in native_rows:
            lines.append(
                f"| {model} | {ds:.2f} | {bugs}/{total_bugs_ground_truth} | {judge:.1f}/2 |"
            )
        lines.append("")

    # Best pairing section (tie-aware)
    lines.append("## Best Pairing by Metric\n")
    lines.append("The best pairing(s) for each headline metric (ties shown).\n")

    # Best Detection Score (tie-aware)
    best_ds_val = -1.0
    best_ds_pairs: list[tuple[str, str]] = []
    for (model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        ds = metrics.get("ds", 0.0)
        if ds > best_ds_val:
            best_ds_val = ds
            best_ds_pairs = [(model, skill)]
        elif ds == best_ds_val:
            best_ds_pairs.append((model, skill))

    # Best Judge Score (tie-aware)
    best_judge_val = -1.0
    best_judge_pairs: list[tuple[str, str]] = []
    for (model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        jm = metrics.get("judge_mean", 0.0)
        if jm > best_judge_val:
            best_judge_val = jm
            best_judge_pairs = [(model, skill)]
        elif jm == best_judge_val:
            best_judge_pairs.append((model, skill))

    if best_ds_pairs:
        if len(best_ds_pairs) == 1:
            model, skill = best_ds_pairs[0]
            native = " *(native)*" if model == skill else ""
            lines.append(
                f"- **Best Detection Score**: {model} × {skill}{native} (DS={best_ds_val:.2f})\n"
            )
        else:
            pair_strs = [f"{m} × {s}" for m, s in best_ds_pairs]
            lines.append(
                f"- **Best Detection Score** (tie): {', '.join(pair_strs)} (DS={best_ds_val:.2f})\n"
            )
    if best_judge_pairs:
        if len(best_judge_pairs) == 1:
            model, skill = best_judge_pairs[0]
            native = " *(native)*" if model == skill else ""
            lines.append(
                f"- **Best Judge Score**: {model} × {skill}{native} (J={best_judge_val:.1f}/2)\n"
            )
        else:
            pair_strs = [f"{m} × {s}" for m, s in best_judge_pairs]
            lines.append(
                f"- **Best Judge Score** (tie): {', '.join(pair_strs)} (J={best_judge_val:.1f}/2)\n"
            )

    # Marginal Analysis
    lines.append("\n---\n")
    lines.append("## Marginal Analysis\n")
    lines.append(
        "Row means (per reviewing model across skills) and column means (per skill across models).\n"
    )

    if model_ranked:
        best_model, best_model_ds, best_judge, _ = model_ranked[0]
        lines.append(
            f"**Best Model**: {best_model} (row-mean DS={best_model_ds:.2f}, judge={best_judge:.1f})\n"
        )

    if skill_ranked:
        best_skill, best_skill_ds, best_judge, _ = skill_ranked[0]
        lines.append(
            f"**Best Skill**: {best_skill} (column-mean DS={best_skill_ds:.2f}, judge={best_judge:.1f})\n"
        )

    lines.append("\n### Model Rankings (by row-mean Detection Score)\n")
    lines.append("| Rank | Model | Detection Score | Judge Mean | Rarity Score |")
    lines.append("|------|-------|-----------------|------------|--------------|")
    for rank, (model, ds, judge, _refusal) in enumerate(model_ranked or [], 1):
        rarity = model_rarity.get(model, 0.0)
        lines.append(f"| {rank} | {model} | {ds:.2f} | {judge:.1f} | {rarity:.2f} |")

    lines.append("\n### Skill Rankings (by column-mean Detection Score)\n")
    lines.append("| Rank | Skill | Detection Score | Judge Mean | Rarity Score |")
    lines.append("|------|-------|-----------------|------------|--------------|")
    for rank, (skill, ds, judge, _refusal) in enumerate(skill_ranked or [], 1):
        rarity = skill_rarity.get(skill, 0.0)
        lines.append(f"| {rank} | {skill} | {ds:.2f} | {judge:.1f} | {rarity:.2f} |")

    # Bug Discovery Ranking
    lines.append("\n---\n")
    lines.append("## Bug Discovery Ranking\n")
    lines.append(
        "How many ground-truth bugs each pairing, model, and skill actually found, "
        "broken down by severity and category. Raw counts — no precision penalty.\n"
    )
    total_bugs = buggy_count  # Plan B: buggy diffs only
    lines.append(f"Ground-truth bugs: **{total_bugs}**\n")

    lines.append("### Bugs Found per Pairing (findings classified)\n")
    lines.append("| Model | Skill | TP | Duplicates | Unmatched | Total findings |")
    lines.append("|-------|-------|----|------------|-----------|----------------|")
    pair_tp: list[tuple[str, str, int, int, int]] = []
    for (model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        pair_tp.append(
            (
                model,
                skill,
                len(metrics.get("hits", [])),
                metrics.get("duplicate_findings", 0),
                metrics.get("unmatched", 0),
            )
        )
    pair_tp.sort(key=lambda x: -x[2])
    for model, skill, tp, dup, cell_unmatched in pair_tp:
        native = " *(native)*" if model == skill else ""
        total_f = metrics_total(cell_data, (model, skill))
        lines.append(f"| {model} | {skill}{native} | {tp} | {dup} | {cell_unmatched} | {total_f} |")

    lines.append("\n### Bugs Found per Model and per Skill\n")
    lines.append("| Group | Name | Total Found | Coverage | Exclusive |")
    lines.append("|-------|------|-------------|----------|-----------|")
    model_hits: dict[str, set[str]] = defaultdict(set)
    for (model, _skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) > 0:
            model_hits[model].update(metrics.get("hits", []))
    # Model rows first (sorted by Total Found desc)
    for model, hits_set in sorted(model_hits.items(), key=lambda x: -len(x[1])):
        pct = len(hits_set) / total_bugs * 100 if total_bugs > 0 else 0
        excl = len(model_exclusive.get(model, set()))
        lines.append(f"| Model | {model} | {len(hits_set)} | {pct:.0f}% | {excl} |")

    skill_hits: dict[str, set[str]] = defaultdict(set)
    for (_model, skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) > 0:
            skill_hits[skill].update(metrics.get("hits", []))
    # Skill rows second (sorted by Total Found desc)
    for skill, hits_set in sorted(skill_hits.items(), key=lambda x: -len(x[1])):
        pct = len(hits_set) / total_bugs * 100 if total_bugs > 0 else 0
        excl = len(skill_exclusive.get(skill, set()))
        lines.append(f"| Skill | {skill} | {len(hits_set)} | {pct:.0f}% | {excl} |")

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

    # Severity Ranking - distinct bugs from diff_records (ground truth)
    lines.append("\n### Bugs Found by Severity (distinct from ground truth)\n")
    # Compute distinct bugs from diff_records, not sum across cells
    severity_totals: dict[str, int] = defaultdict(int)
    for diff_record in diff_records:
        for bug in diff_record.get("bugs", []):
            sev = bug.get("severity", "unknown")
            severity_totals[sev] += 1
    if severity_totals:
        lines.append("| Severity | Ground Truth |")
        lines.append("|----------|--------------|")
        ordered_sev = sorted(
            severity_totals.items(),
            key=lambda x: (
                SEVERITY_ORDER.index(x[0]) if x[0] in SEVERITY_ORDER else len(SEVERITY_ORDER),
                -x[1],
            ),
        )
        for sev, count in ordered_sev:
            lines.append(f"| {sev} | {count} |")
    else:
        lines.append("No severity data available.\n")

    lines.append("\n### Severity Breakdown per Model and per Skill\n")
    lines.append("| Group | Name | " + " | ".join(SEVERITY_ORDER) + " | Total |")
    lines.append(
        "|-------|------|" + "|".join(["-------"] * (len(SEVERITY_ORDER) + 1)) + "|-------|"
    )
    model_severity: dict[str, dict[str, int]] = {
        m: {s: 0 for s in SEVERITY_ORDER} for m in model_hits
    }
    for (model, _skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        for sev, count in metrics.get("severity_counts", {}).items():
            if sev in model_severity.get(model, {}):
                model_severity[model][sev] += count
    # Model rows first
    for model in sorted(model_hits.keys()):
        row = f"| {model} |"
        total = 0
        for sev in SEVERITY_ORDER:
            count = model_severity[model][sev]
            total += count
            row += f" {count} |"
        row += f" {total} |"
        lines.append(row)

    # Skill rows second
    lines.append("| Group | Name | " + " | ".join(SEVERITY_ORDER) + " | Total |")
    lines.append(
        "|-------|------|" + "|".join(["-------"] * (len(SEVERITY_ORDER) + 1)) + "|-------|"
    )
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
            lines.append(f"| {model}{native} | {skill} | {crit} | {pair_total[(model, skill)]} |")
    else:
        lines.append("No per-pairing severity data available.\n")

    # Category Ranking - distinct bugs from diff_records (ground truth)
    lines.append("\n### Bugs Found by Category (distinct from ground truth)\n")
    # Compute distinct bugs from diff_records, not sum across cells
    category_totals: dict[str, int] = defaultdict(int)
    for diff_record in diff_records:
        for bug in diff_record.get("bugs", []):
            cat = bug.get("category", "unknown")
            category_totals[cat] += 1
    if category_totals:
        lines.append("| Category | Ground Truth |")
        lines.append("|----------|--------------|")
        # Sort descending by count, then alphabetically for ties
        for cat, count in sorted(category_totals.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"| {cat} | {count} |")
    else:
        lines.append("No category data available.\n")

    lines.append("\n### Category Breakdown per Model and per Skill\n")
    all_categories = sorted(category_totals.keys())
    lines.append("| Group | Name | " + " | ".join(all_categories) + " | Total |")
    lines.append(
        "|-------|------|" + "|".join(["-------"] * (len(all_categories) + 1)) + "|-------|"
    )
    model_category: dict[str, dict[str, int]] = {
        m: {c: 0 for c in all_categories} for m in model_hits
    }
    for (model, _skill), metrics in cell_data.items():
        if metrics.get("total_results", 0) == 0:
            continue
        for cat, count in metrics.get("category_counts", {}).items():
            if cat in model_category.get(model, {}):
                model_category[model][cat] += count
    # Model rows first
    for model in sorted(model_hits.keys()):
        row = f"| {model} |"
        total = 0
        for cat in all_categories:
            count = model_category[model][cat]
            total += count
            row += f" {count} |"
        row += f" {total} |"
        lines.append(row)

    # Skill rows second
    lines.append("| Group | Name | " + " | ".join(all_categories) + " | Total |")
    lines.append(
        "|-------|------|" + "|".join(["-------"] * (len(all_categories) + 1)) + "|-------|"
    )
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
        # One row per source location: the same finding shows up in many cells and
        # sometimes with two different severities, which repeats the line needlessly.
        severity_order = {"reject": 0, "request-changes": 1, "nitpick": 2}
        grouped_unmatched: dict[str, dict[str, object]] = {}
        for u in unmatched:
            issue = (u["issue"] or "").strip()
            if (
                not issue
                or issue.lower() == "no issue described"
                or re.match(r"^no .*issues? found", issue, re.IGNORECASE)
            ):
                continue
            loc = f"{u['file']}:{u['line']}" if u["line"] else u["file"]
            rank = severity_order.get(u["severity"], 99)
            entry = grouped_unmatched.get(loc)
            if entry is None:
                grouped_unmatched[loc] = {
                    "severity": u["severity"],
                    "rank": rank,
                    "issue": issue[:100],
                    "count": 1,
                }
                continue
            entry["count"] = int(entry["count"]) + 1
            if rank < int(entry["rank"]):
                entry["rank"] = rank
                entry["severity"] = u["severity"]
                entry["issue"] = issue[:100]

        # Sort by cell count descending, then severity, then location
        sorted_locs = sorted(
            grouped_unmatched,
            key=lambda loc: (
                -int(grouped_unmatched[loc]["count"]),
                int(grouped_unmatched[loc]["rank"]),
                loc,
            ),
        )

        lines.append("| File:Line | Severity | Issue | Reported by |")
        lines.append("|-----------|----------|-------|-------------|")
        for loc in sorted_locs:
            entry = grouped_unmatched[loc]
            lines.append(
                f"| {loc} | {entry['severity']} | {entry['issue']} | "
                f"{int(entry['count'])} cell(s) |"
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

    # Build a lookup from bug_id to its metadata for detailed listings
    bug_meta: dict[str, dict] = {}
    for dr in diff_records:
        for b in dr.get("bugs", []):
            bid = b.get("id", dr.get("id", ""))
            if bid:
                bug_meta[bid] = b

    # Detailed bug listings per consensus bucket
    lines.append("### Bug Details by Consensus\n")
    for count in range(4, 0, -1):
        bugs = sorted(consensus_buckets.get(count, []))
        if not bugs:
            continue
        label = {
            4: "Full Consensus (4/4 models)",
            3: "Three Models (3/4)",
            2: "Two Models (2/4)",
            1: "Sole Discovery (1/4 model)",
        }[count]
        lines.append(f"#### {label}\n")
        if count == 1:
            lines.append("| Bug ID | File | Severity | Category | Description | Found By |")
            lines.append("|--------|------|----------|----------|-------------|-----------|")
            for bug in bugs:
                meta = bug_meta.get(bug, {})
                finder = bug_finders.get(bug, ["?"])[0]
                lines.append(
                    f"| {bug} | {meta.get('file', '?')} | {meta.get('severity', '?')} "
                    f"| {meta.get('category', '?')} | {meta.get('description', '?')} | {finder} |"
                )
        else:
            lines.append("| Bug ID | File | Severity | Category | Description | Found By |")
            lines.append("|--------|------|----------|----------|-------------|-----------|")
            for bug in bugs:
                meta = bug_meta.get(bug, {})
                finders_str = ", ".join(sorted(bug_finders.get(bug, [])))
                lines.append(
                    f"| {bug} | {meta.get('file', '?')} | {meta.get('severity', '?')} "
                    f"| {meta.get('category', '?')} | {meta.get('description', '?')} | {finders_str} |"
                )
        lines.append("")

    if missed > 0:
        found_bug_ids = set(finder_counts.keys())
        all_bug_ids = {
            b.get("id", dr.get("id", "")) for dr in diff_records for b in dr.get("bugs", [])
        }
        missed_ids = sorted(all_bug_ids - found_bug_ids)
        if missed_ids:
            lines.append("#### Missed by All Models (0/4)\n")
            lines.append("| Bug ID | File | Severity | Category | Description |")
            lines.append("|--------|------|----------|----------|-------------|")
            for bug in missed_ids:
                meta = bug_meta.get(bug, {})
                lines.append(
                    f"| {bug} | {meta.get('file', '?')} | {meta.get('severity', '?')} "
                    f"| {meta.get('category', '?')} | {meta.get('description', '?')} |"
                )
            lines.append("")
        lines.append(
            f"**{missed} bug(s) missed by every model** — these may require skill refinement "
            "or represent subtle defects beyond current detection capability.\n"
        )

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

    # Native Pairing Advantage: native vs cross-skill Detection Score per model
    lines.append("\n---\n")
    lines.append("## Native Pairing Advantage\n")
    lines.append(
        "For each model, compare its native skill (model == skill) against the mean of "
        "cross-skills (model != skill). Positive delta = native skill helps; "
        "negative = cross-skill helps. This measures native-skill advantage, not "
        "skill-on vs skill-off — for that comparison see [report/comparison.md](report/comparison.md).\n"
    )
    lines.append("| Model | Native DS | Cross-Skill Mean DS | Delta | Verdict |")
    lines.append("|-------|----------|---------------------|-------|---------|")
    for model in all_models:
        native = cell_data.get((model, model))
        native_ds = native.get("ds", 0.0) if native and native.get("total_results", 0) > 0 else None
        cross_dss = []
        for skill in all_models:
            if skill == model:
                continue
            cell = cell_data.get((model, skill))
            if cell and cell.get("total_results", 0) > 0:
                cross_dss.append(cell.get("ds", 0.0))
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
    lines.append("| Model | Best Skill(s) | DS | Recommendation |")
    lines.append("|-------|--------------|----|----------------|")
    for model in all_models:
        if model not in best_skill_per_model:
            lines.append(f"| {model} | — | — | no data |")
            continue
        skill_list = best_skill_per_model[model]
        best_ds = skill_list[0][1]  # All tied have same DS
        if len(skill_list) == 1:
            best_skill = skill_list[0][0]
            if best_skill == model:
                rec = "native skill"
            else:
                rec = f"cross-skill `{best_skill}`"
            lines.append(f"| {model} | {best_skill} | {best_ds:.2f} | {rec} |")
        else:
            skill_str = ", ".join(s for s, _ in skill_list)
            is_native = any(s == model for s, _ in skill_list)
            if is_native:
                rec = "native skill (tied)"
            else:
                rec = f"cross-skills {skill_str} (tied)"
            lines.append(f"| {model} | {skill_str} | {best_ds:.2f} | {rec} |")
    lines.append("")

    # Judge sub-score detail (appendix)
    lines.append("\n---\n")
    lines.append("## Judge Score Detail\n")
    lines.append(
        "**Secondary metric.** The judge does **not** affect the Detection Score (DS), "
        "true positives, recall, or precision — all detection metrics are computed by "
        "matching findings to ground truth. The judge only provides four quality sub-scores "
        "(accuracy, prioritization, justification, actionability) on a 0–2 scale, aggregated "
        "into the Judge Score (J) shown in the matrices above. Use J to break ties, never to rank. "
        "Disable with `--no-judge`.\n"
    )
    lines.append(
        "> **Conflict of interest**: the judge (GLM5.2) also participates in the evaluation as a reviewer, "
        "so its self-scored reviews may reflect self-preference.\n\n"
    )
    lines.append(
        "Each sub-score is the mean over evaluated "
        + ("reviews " if codebase_mode else "diffs ")
        + "on a 0–2 scale; values vary little across pairings, so they are shown as appendix detail.\n"
    )
    for axis in ["accuracy", "prioritization", "justification", "actionability"]:
        lines.append(f"### Judge {axis.title()} Matrix\n")
        header = "| Skill \\\\ Model |"
        for model in all_models:
            header += f" {model} |"
        lines.append(header)
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

        # Baseline row (No skill)
        if has_baseline and baseline_cell_data:
            row = "| No skill (baseline) |"
            for model in all_models:
                metrics = baseline_cell_data.get(model)
                key = f"judge_{axis}"
                if metrics and metrics["total_results"] > 0 and key in metrics:
                    row += f" {metrics[key]:.1f} |"
                else:
                    row += " — |"
            lines.append(row)
        lines.append("\n")

    # Phase 4: Add Limitations section (skeleton part 4)
    lines.append("## Limitations\n")
    if codebase_mode:
        lines.append(
            f"- **n={len(diff_records)} ground-truth bugs**: Evaluation based on the real SmallChat codebase with {len(diff_records)} known bugs.\n"
        )
    else:
        lines.append(
            "- **n=45 (25 buggy)**: Evaluation based on 45 diff scenarios, of which 25 contain ground-truth bugs.\n"
        )
    lines.append(
        f"- **Repetitions**: each model+skill pairing was evaluated {max((cell.get('reps', 1) for cell in cell_data.values()), default=1)}x per "
        + ("bug.\n" if codebase_mode else "diff scenario.\n")
    )
    lines.append(
        "- **Judge COI**: The judge (GLM5.2) also participates as a reviewer, so judge scores may reflect self-preference.\n"
    )
    lines.append(provenance_limitation(eval_provenance) + "\n")
    lines.append(
        "- **Denominator choice**: Recall denominator uses only "
        + ("ground-truth bugs" if codebase_mode else "buggy diffs")
        + (
            "; any finding that matches no ground-truth bug counts as a false positive.\n"
            if codebase_mode
            else ' (expected=="findings"); findings on clean or refusal scenarios count as false positives.\n'
        )
    )
    lines.append("\n")

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
    parser.add_argument(
        "--eval-provenance",
        choices=["decontaminated", "pre-decontamination"],
        default="decontaminated",
        help=(
            "Which reviewer-prompt version produced the results being rendered. "
            "Stated in the report header so a report cannot claim clean data when it "
            "was produced from a contaminated run."
        ),
    )
    parser.add_argument(
        "--codebase",
        action="store_true",
        help=(
            "Codebase mode: load results from data/eval_results_codebase.jsonl "
            "and ground truth from data/benchmark.jsonl (full SmallChat review). "
            "Overrides --results, --cross-results, and --diffs defaults."
        ),
    )
    parser.add_argument(
        "--codebase-results",
        type=Path,
        default=Path("data/eval_results_codebase.jsonl"),
        help="Codebase eval results file (default: data/eval_results_codebase.jsonl)",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("data/benchmark.jsonl"),
        help="Ground truth bugs file for codebase mode (default: data/benchmark.jsonl)",
    )

    args = parser.parse_args()

    if args.codebase:
        all_results = load_jsonl(args.codebase_results)
        benchmark_bugs = load_jsonl(args.benchmark)
        diff_records = _benchmark_to_diff_records(benchmark_bugs)
    else:
        diagonal_results = load_jsonl(args.results)
        cross_results = load_jsonl(args.cross_results)
        diff_records = load_jsonl(args.diffs)
        all_results = diagonal_results + cross_results

    # Separate baseline records (skill=="none") from skill records
    baseline_results, skill_results = separate_baseline_from_skills(all_results)

    if not all_results:
        print("No eval results found. Generating empty matrix.")
        models = MODELS
        cell_data: dict[tuple[str, str], dict[str, Any]] = {}
        for model in models:
            for skill in models:
                cell_data[(model, skill)] = {"total_results": 0}
        render_markdown(
            cell_data,
            models,
            diff_records,
            args.out,
            eval_provenance=args.eval_provenance,
        )
        print(f"Empty matrix written to {args.out}")
        return

    # Group skill results by (model, skill) pairing (baseline excluded)
    grouped = group_results_by_pairing(skill_results)

    # Also group baseline results by model (skill="none")
    baseline_grouped = group_results_by_pairing(baseline_results)

    derived_models = sorted(
        set(m for (m, s) in grouped.keys()) | set(s for (m, s) in grouped.keys())
    )

    cell_data = {}
    for (model, skill), results in grouped.items():
        metrics = compute_cell_metrics(results, diff_records)
        cell_data[(model, skill)] = metrics

    # Add baseline cells: (model, "none") for each model
    baseline_cell_data: dict[str, dict[str, Any]] = {}
    for model in derived_models:
        if (model, "none") in baseline_grouped:
            metrics = compute_cell_metrics(baseline_grouped[(model, "none")], diff_records)
            baseline_cell_data[model] = metrics
        else:
            baseline_cell_data[model] = {"total_results": 0}

    # Fill missing skill cells with zeros
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
        baseline_cell_data=baseline_cell_data,
        has_baseline=len(baseline_results) > 0,
        eval_provenance=args.eval_provenance,
        codebase_mode=bool(args.codebase),
    )
    print(f"Matrix written to {args.out}")


if __name__ == "__main__":
    main()
