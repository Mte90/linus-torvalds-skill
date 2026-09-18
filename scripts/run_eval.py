#!/usr/bin/env python3
"""
Eval runner: judge model performance on diff-based bug detection.

Reads data/eval_diffs.jsonl (diff records with expected bugs), runs each model
against each diff, matches findings to ground-truth bugs, scores with a 4-axis
judge prompt, and writes results to data/eval_results.jsonl.

Usage:
  python3 scripts/run_eval.py                    # run all models with judge
  python3 scripts/run_eval.py --no-judge         # offline mode, zero scores
  python3 scripts/run_eval.py --models glm5.2    # run single model
  python3 scripts/run_eval.py --force            # regenerate all results
  python3 scripts/run_eval.py --rescore-zeros    # re-judge poisoned records
  python3 scripts/run_eval.py --parallel         # run models in parallel (max 2 workers)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

# Import project config
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Add report/ to path for llm_review import
_REPORT = Path(__file__).resolve().parent.parent / "report"
if str(_REPORT) not in sys.path:
    sys.path.insert(0, str(_REPORT))

# Import call_llm and _WallClockTimeout from llm_review (import-safe: no module-level side effects)
from llm_review import _WallClockTimeout, call_llm  # noqa: E402

from torvalds_skill import config as project_config  # noqa: E402
from torvalds_skill.profiles import get_profile  # noqa: E402

# Configuration
ROOT = Path(__file__).resolve().parent.parent
EVAL_INPUT = ROOT / "data" / "eval_diffs.jsonl"
EVAL_OUTPUT = ROOT / "data" / "eval_results.jsonl"

# Thread-safe JSONL append lock
_results_lock = Lock()

# Data-driven model configuration (same as run_review.py)
SKILL_DIR = ROOT / "linus-torvalds-skill"
MODELS = {
    "gpt-oss-120b": SKILL_DIR / "SKILL.md",
    "glm5.2": SKILL_DIR / "SKILL-GLM.md",
    "mistral-small-4-119b": SKILL_DIR / "SKILL-Mistral.md",
    "qwen3.8-27b": SKILL_DIR / "SKILL-Qwen.md",
}

JUDGE_PROMPT = """You are a code review quality assessor. Evaluate a finding against ground-truth bugs using a 4-axis rubric.

## Input

**Diff Record:**
{diff_text}

**Ground Truth Bugs:**
{bugs_text}

**Model Finding:**
{finding_text}

## Rubric (score each 0-2)

### 1. Technical Accuracy (0-2)
Does the finding correctly identify a real problem?
- 0: Finding is incorrect, hallucinated, or describes non-existent code
- 1: Finding has minor technical errors but identifies a real issue area
- 2: Finding is technically correct and precise

### 2. Prioritization (0-2)
Is the severity/urgency appropriate?
- 0: Severity is completely wrong (e.g., nitpick for security vulnerability)
- 1: Severity is reasonable but slightly off (e.g., HIGH instead of CRITICAL)
- 2: Severity matches the actual impact of the bug

### 3. Justification (0-2)
Is the reasoning sound and well-supported?
- 0: No justification, or reasoning is nonsensical
- 1: Some reasoning present but weak or incomplete
- 2: Clear, logical reasoning with concrete evidence (line numbers, code quotes)

### 4. Actionability (0-2)
Can a developer act on this finding?
- 0: No fix proposed, or fix is impossible/incorrect
- 1: Fix is vague or incomplete
- 2: Fix is concrete, specific, and implementable

## Output Format

Return exactly this JSON structure (no markdown, no extra text):
{{
  "accuracy": <0-2>,
  "prioritization": <0-2>,
  "justification": <0-2>,
  "actionability": <0-2>
}}

## Rules

- Score based on the finding's content, not the model's reputation
- If no matching bug exists in ground truth, score generously if the finding is legitimate
- Don't be overly strict — reward good-faith attempts
- If the finding matches a different bug than expected, still score it if valid
"""


def build_diff_prompt(diff_record: dict, skill_text: str) -> str:
    """Build diff-only review prompt.

    Args:
        diff_record: Record from eval_diffs.jsonl with id, diff, language, file, expected, bugs
        skill_text: Torvalds skill text to apply

    Returns:
        Prompt string for LLM
    """
    diff_id = diff_record.get("id", "unknown")
    diff_text = diff_record.get("diff", "")
    file_path = diff_record.get("file", "unknown")
    language = diff_record.get("language", "unknown")

    # Build bugs section
    bugs = diff_record.get("bugs", [])
    bugs_text = ""
    if bugs:
        bugs_text = "Ground truth bugs present in this diff:\n"
        for i, bug in enumerate(bugs, 1):
            severity = bug.get("severity", "unknown")
            category = bug.get("category", "unknown")
            line = bug.get("line", "unknown")
            desc = bug.get("description", "no description")
            bugs_text += f"  {i}. [{severity}] {category} at line {line}: {desc}\n"
    else:
        bugs_text = "No ground truth bugs (this diff should be clean)."

    return f"""You are a code reviewer applying the Linus Torvalds reviewer skill to a code diff.

Do NOT use any tools. Everything you need is inlined below.

== SKILL ==
{skill_text}

== DIFF ==
File: {file_path}
Language: {language}
Diff ID: {diff_id}

{diff_text}

{bugs_text}

## Task

Review the diff above using the Torvalds skill. Find bugs, security issues, memory safety problems, and code quality issues.

## Format

For each finding use:
### [SEVERITY] Finding title
- **Type:** (the trigger from the skill that fired, or "unmatched" if none matches)
- **Trigger:** (the trigger from the skill that fired, or "unmatched" if none matches)
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings
- Use `**Field:**` format (colon inside bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

## Rules

- Cover the entire diff
- Report every real bug you find. Map each finding to the closest matching skill trigger when one exists; if none matches, set Trigger: unmatched — do NOT suppress real bugs.
- Use the skill's severity calibration and precedence hierarchy
- Be concrete: cite line numbers, name functions, quote code
- Don't invent problems. If the diff is clean, say "No findings."
- Reference line numbers from the diff context (not absolute source lines)
- English

Write your review to stdout.
"""


def match_finding_to_diff_bug(finding: dict, bugs: list[dict], diff_file: str = "") -> dict | None:
    """Match a finding to a ground-truth bug using file and line-number tolerance.

    Bugs inherit their file from the parent diff record (they carry only
    line/category/severity/description), so the caller passes the diff's file.

    Args:
        finding: Finding dict with 'file' and 'line' keys
        bugs: List of bug dicts with 'line' keys
        diff_file: File path from the parent diff record

    Returns:
        Matching bug dict if found (same file, line ±5 tolerance), None otherwise
    """
    finding_file = finding.get("file", "")
    finding_line = finding.get("line")

    if finding_line is None or not finding_file or not diff_file:
        return None

    if finding_file.split("/")[-1].lower() != diff_file.split("/")[-1].lower():
        return None

    for bug in bugs:
        bug_line = bug.get("line")

        if bug_line is None:
            continue

        # Same file (checked above) and line within tolerance
        if abs(finding_line - bug_line) <= 5:
            return bug

    return None


def _extract_json_from_content(content: str) -> dict | None:
    """Extract JSON object from content, handling markdown fences and balanced braces.

    Args:
        content: Raw response content (may have markdown fences or extra text)

    Returns:
        Parsed dict if successful, None otherwise
    """
    import re

    # Strip markdown code fences
    content = re.sub(r"^```(?:json)?\s*\n?", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n?```\s*$", "", content, flags=re.MULTILINE)
    content = content.strip()

    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting first balanced {...} substring
    brace_count = 0
    start = None
    for i, ch in enumerate(content):
        if ch == "{":
            if brace_count == 0:
                start = i
            brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0 and start is not None:
                try:
                    return json.loads(content[start : i + 1])
                except json.JSONDecodeError:
                    start = None
                    continue
    return None


def score_finding_with_judge(
    finding: dict, bug: dict | None, judge_model: str, no_judge: bool = False
) -> dict:
    """Score a finding using the 4-axis judge rubric.

    Args:
        finding: Finding dict from model review
        bug: Matching ground-truth bug (or None if no match)
        judge_model: Model to use for judging
        no_judge: If True, return zeros (offline mode)

    Returns:
        Dict with keys: accuracy, prioritization, justification, actionability (all 0-2 ints)
        If API/parse fails, includes "judge_error": true alongside zeroed scores.
    """
    if no_judge:
        return {
            "accuracy": 0,
            "prioritization": 0,
            "justification": 0,
            "actionability": 0,
        }

    # Get judge profile and set token budget
    profile = get_profile(judge_model)
    # Reasoning models need generous budget (burn tokens on thinking phase)
    max_tokens = 16000 if profile.reasoning else 500

    # Build judge prompt
    diff_text = finding.get("diff_text", "No diff available")
    bugs_text = (
        "No ground truth bugs."
        if bug is None
        else f"Expected bug: {bug.get('description', 'unknown')}"
    )
    finding_text = f"""
File: {finding.get("file", "unknown")}
Line: {finding.get("line", "unknown")}
Severity: {finding.get("severity", "unknown")}
Type: {finding.get("type", "unknown")}
Issue: {finding.get("issue", "no issue described")}
Fix: {finding.get("fix", "no fix proposed")}
"""

    prompt = JUDGE_PROMPT.format(
        diff_text=diff_text, bugs_text=bugs_text, finding_text=finding_text
    )

    payload = {
        "model": judge_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "stream": False,
    }

    def _call_judge(judge_prompt: str) -> dict | None:
        """Make a single judge API call with wall-clock timeout. Returns scores dict or None on failure."""
        # Get timeout from profile (fallback 600)
        timeout = getattr(profile, "review_timeout", 600)

        with _WallClockTimeout(timeout):
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                project_config.CHAT_URL, data=body, headers=project_config.headers(), method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=project_config.READ_TIMEOUT) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    content = result.get("choices", [{}])[0].get("message", {}).get("content") or ""
                    if not content.strip():
                        return None
                    return _extract_json_from_content(content)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
                return None

    # First attempt
    scores_data = _call_judge(prompt)

    # Retry once with stricter prompt if empty/unparseable
    if scores_data is None:
        retry_prompt = prompt + "\n\nRespond with ONLY the JSON object."
        payload["messages"] = [{"role": "user", "content": retry_prompt}]
        scores_data = _call_judge(retry_prompt)

    # Final failure
    if scores_data is None:
        return {
            "accuracy": 0,
            "prioritization": 0,
            "justification": 0,
            "actionability": 0,
            "judge_error": True,
        }

    return {
        "accuracy": int(scores_data.get("accuracy", 0)),
        "prioritization": int(scores_data.get("prioritization", 0)),
        "justification": int(scores_data.get("justification", 0)),
        "actionability": int(scores_data.get("actionability", 0)),
    }


def parse_findings_from_review(review_text: str, diff_record: dict) -> list[dict]:
    """Parse findings from a model's review text.

    Args:
        review_text: Raw review text from LLM
        diff_record: Original diff record (for file/diff context)

    Returns:
        List of finding dicts with keys: file, line, severity, type, issue, fix
    """
    import re

    findings = []
    diff_text = diff_record.get("diff", "")

    # Match severity headings: ### [SEVERITY]
    heading_re = re.compile(r"^###\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+(.+)$", re.MULTILINE)

    # Match fields
    type_re = re.compile(r"^\s*-?\s*\*\*Type:\*\*\s*(.+)", re.MULTILINE)
    trigger_re = re.compile(r"^\s*-?\s*\*\*Trigger:\*\*\s*(.+)", re.MULTILINE)
    location_re = re.compile(r"^\s*-?\s*\*\*Location:\*\*\s*(.+)", re.MULTILINE)
    issue_re = re.compile(r"^\s*-?\s*\*\*Issue:\*\*\s*(.+)", re.MULTILINE)
    fix_re = re.compile(r"^\s*-?\s*\*\*Fix:\*\*\s*(.+)", re.MULTILINE)

    # Split into finding blocks
    blocks = re.split(
        r"^#{3,4}\s+\[(?:CRITICAL|HIGH|MEDIUM|LOW)\]\s+", review_text, flags=re.MULTILINE
    )

    for block in blocks:
        if not block.strip():
            continue

        # Extract severity from heading (we split on it, so need to find it)
        heading_re.search("### [" + block.split("\n")[0][:20] + "]" if block else "")
        severity = "MEDIUM"  # Default

        # Parse fields
        type_match = type_re.search(block)
        trigger_match = trigger_re.search(block)
        location_match = location_re.search(block)
        issue_match = issue_re.search(block)
        fix_match = fix_re.search(block)

        # Extract line number from location (format: file:line)
        line = None
        file_path = diff_record.get("file", "")

        if location_match:
            location = location_match.group(1).strip()
            if ":" in location:
                parts = location.split(":")
                file_path = parts[0]
                try:
                    line = int(parts[1])
                except ValueError:
                    line = None

        finding = {
            "file": file_path,
            "line": line,
            "severity": severity,
            "type": type_match.group(1).strip() if type_match else "unknown",
            "trigger": trigger_match.group(1).strip() if trigger_match else "unmatched",
            "issue": issue_match.group(1).strip() if issue_match else "no issue described",
            "fix": fix_match.group(1).strip() if fix_match else "no fix proposed",
            "diff_text": diff_text,
        }
        findings.append(finding)

    return findings


def check_refused(response: str, findings: list[dict]) -> bool:
    """Check if model refused to conclude.

    Args:
        response: Raw LLM response
        findings: Parsed findings list

    Returns:
        True if response contains refusal indicators
    """
    refusal_indicators = [
        "I cannot tell",
        "I cannot determine",
        "unable to assess",
        "insufficient information",
        "cannot conclude",
    ]

    response_lower = response.lower()
    if any(indicator in response_lower for indicator in refusal_indicators):
        return True

    # Empty findings on a non-trivial diff is also a refusal
    if not findings and len(response.strip()) > 100:
        return True

    return False


def run_model_on_diff(
    model: str,
    diff_record: dict,
    no_judge: bool,
    judge_model: str | None = None,
    skill_model: str | None = None,
) -> dict:
    """Run a single model on a single diff record.

    Args:
        model: Model label used for the review call
        diff_record: Diff record from eval_diffs.jsonl
        no_judge: If True, skip judging (offline mode)
        judge_model: Model to use for judging (defaults to same as review model)
        skill_model: Whose skill to apply (defaults to model itself; set for cross runs)

    Returns:
        Result dict with: diff_id, model, expected, findings, scores, refused
    """
    skill_file = MODELS.get(skill_model or model)
    if not skill_file or not skill_file.exists():
        print(f"error: skill file not found: {skill_file}", file=sys.stderr)
        return None

    skill_text = skill_file.read_text()
    diff_id = diff_record.get("id", "unknown")

    # Build prompt and call model
    prompt = build_diff_prompt(diff_record, skill_text)

    profile = get_profile(model)

    # Get timeout from profile (fallback 600)
    timeout = getattr(profile, "review_timeout", 600)

    # Call LLM with retry: on exception OR empty response, retry once
    response = None
    for attempt in range(2):
        try:
            response = call_llm(model, prompt, timeout=timeout)
            if response.strip():
                break
            print(
                f"warning: empty response (attempt {attempt + 1}) for {model} on {diff_id}",
                file=sys.stderr,
            )
            response = None
        except Exception as e:
            print(
                f"error: API call failed for {model} on {diff_id} (attempt {attempt + 1}): {e}",
                file=sys.stderr,
            )
            response = None

    if response is None or not response.strip():
        return None

    # Parse findings
    findings = parse_findings_from_review(response, diff_record)

    # Check for refusal
    refused = check_refused(response, findings)

    # Get ground truth bugs
    bugs = diff_record.get("bugs", [])

    # Score each finding
    scores_list = []
    for finding in findings:
        bug = match_finding_to_diff_bug(finding, bugs, diff_record.get("file", ""))
        scores = score_finding_with_judge(finding, bug, judge_model or model, no_judge)
        finding["scores"] = scores
        scores_list.append(scores)

    # Aggregate scores
    if scores_list:
        avg_scores = {
            "accuracy": sum(s["accuracy"] for s in scores_list) / len(scores_list),
            "prioritization": sum(s["prioritization"] for s in scores_list) / len(scores_list),
            "justification": sum(s["justification"] for s in scores_list) / len(scores_list),
            "actionability": sum(s["actionability"] for s in scores_list) / len(scores_list),
        }
    else:
        avg_scores = {
            "accuracy": 0,
            "prioritization": 0,
            "justification": 0,
            "actionability": 0,
        }

    result = {
        "diff_id": diff_id,
        "model": model,
        "expected": diff_record.get("expected", ""),
        "findings": findings,
        "scores": avg_scores,
        "refused": refused,
    }
    if skill_model:
        result["skill"] = skill_model
    return result


def _cross_pairs(
    models_filter: list[str], skills_filter: list[str] | None = None
) -> list[tuple[str, str]]:
    """Build cross-mode (model, skill) pairs for a filtered model list.

    Args:
        models_filter: List of model names to use as reviewers
        skills_filter: Optional list of skill-source models; None spans all MODELS

    Returns:
        List of (model, skill) tuples where model != skill and skill spans
        skills_filter (or all MODELS when skills_filter is None)
    """
    skill_sources = skills_filter if skills_filter else list(MODELS.keys())
    return [(m, s) for m in models_filter for s in skill_sources if m != s]


def _status_cells(
    models_filter: list[str],
    cross_mode: bool,
    skills_filter: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Build (model, skill) cells for status table display.

    Args:
        models_filter: List of model names to display
        cross_mode: If True, show off-diagonal pairs; if False, show diagonal only
        skills_filter: Optional list of skill-source models; None spans all MODELS

    Returns:
        List of (model, skill) tuples
    """
    if cross_mode:
        skill_sources = skills_filter if skills_filter else list(MODELS.keys())
        return [(m, s) for m in models_filter for s in skill_sources if m != s]
    return [(m, m) for m in models_filter]


def _print_status_table(
    out_path: str,
    eval_path: Path,
    models_filter: str | None,
    cross_mode: bool,
    skills_filter: str | None = None,
) -> None:
    """Print completion status table for (model, skill) cells.

    Args:
        out_path: Output results file path
        eval_path: Path to eval diffs file
        models_filter: Optional comma-separated model filter
        cross_mode: If True, show all pairs; if False, show diagonal only
        skills_filter: Optional comma-separated skill-source filter (cross mode only)
    """
    # Load diff records for total count
    diff_records = []
    with open(eval_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    diff_records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    total_diffs = len(diff_records)

    # Load existing results (deduplicated by key)
    output_path = Path(out_path)
    existing_results: dict[tuple[str, str, str | None], dict] = {}
    if output_path.exists():
        with open(output_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        key = (
                            record.get("diff_id"),
                            record.get("model"),
                            record.get("skill") or record.get("model"),
                        )
                        existing_results[key] = record
                    except json.JSONDecodeError:
                        continue

    # Determine models to show
    if models_filter:
        models_to_show = [m.strip() for m in models_filter.split(",")]
        missing = [m for m in models_to_show if m not in MODELS]
        if missing:
            print(f"error: unknown models: {', '.join(missing)}", file=sys.stderr)
            print(f"valid models: {', '.join(MODELS.keys())}", file=sys.stderr)
            sys.exit(2)
    else:
        models_to_show = list(MODELS.keys())

    # Determine cells to show
    skills_to_show: list[str] | None = None
    if skills_filter:
        skills_to_show = [s.strip() for s in skills_filter.split(",")]
        missing = [s for s in skills_to_show if s not in MODELS]
        if missing:
            print(f"error: unknown skills: {', '.join(missing)}", file=sys.stderr)
            print(f"valid models: {', '.join(MODELS.keys())}", file=sys.stderr)
            sys.exit(2)
    cells = _status_cells(models_to_show, cross_mode, skills_to_show)

    # Count done per cell
    print(f"{'model':<18} {'skill':<18} {'done/total':<14} {'status'}")
    print("-" * 60)

    for model, skill in cells:
        count = 0
        for (_diff_id, m, s), _ in existing_results.items():
            if m == model and s == skill:
                count += 1
        status = "COMPLETE" if count >= total_diffs else "MISSING"
        print(f"{model:<18} {skill:<18} {count}/{total_diffs:<12} {status}")


def _rescore_zeros(
    results_path: Path, diffs_path: Path, no_judge: bool, judge_model: str | None
) -> None:
    """Re-judge findings with all-zero scores or judge_error.

    Args:
        results_path: Path to eval results JSONL file
        diffs_path: Path to eval diffs JSONL file
        no_judge: If True, skip judging (offline mode)
        judge_model: Model to use for judging
    """
    # Load diffs for match_finding_to_diff_bug
    diffs_by_id = {}
    with open(diffs_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    diffs_by_id[record["id"]] = record
                except json.JSONDecodeError:
                    continue

    # Load existing results
    results = []
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Find records/findings to rescore
    records_touched = 0
    findings_rescored = 0
    still_failing = 0

    for record in results:
        findings = record.get("findings", [])
        needs_rescore = False
        for finding in findings:
            scores = finding.get("scores", {})
            # Check for all-zero scores or explicit judge_error
            is_zero = (
                scores.get("accuracy", 0) == 0
                and scores.get("prioritization", 0) == 0
                and scores.get("justification", 0) == 0
                and scores.get("actionability", 0) == 0
            )
            if is_zero or scores.get("judge_error"):
                needs_rescore = True
                break

        if not needs_rescore:
            continue

        records_touched += 1
        diff_id = record.get("diff_id")
        diff_record = diffs_by_id.get(diff_id, {})
        bugs = diff_record.get("bugs", [])

        for i, finding in enumerate(findings, 1):
            scores = finding.get("scores", {})
            is_zero = (
                scores.get("accuracy", 0) == 0
                and scores.get("prioritization", 0) == 0
                and scores.get("justification", 0) == 0
                and scores.get("actionability", 0) == 0
            )
            if is_zero or scores.get("judge_error"):
                print(
                    f"rescore {diff_id} finding {i}/{len(findings)}: {finding.get('file')}:{finding.get('line')}",
                    flush=True,
                )
                bug = match_finding_to_diff_bug(finding, bugs, diff_record.get("file", ""))
                # Inject diff_text into finding for judge
                finding["diff_text"] = diff_record.get("diff", "")
                new_scores = score_finding_with_judge(
                    finding, bug, judge_model or record.get("model", "gpt-oss-120b"), no_judge
                )
                finding["scores"] = new_scores
                if new_scores.get("judge_error"):
                    still_failing += 1
                findings_rescored += 1

        # Recompute the record-level average so renderers see the new scores
        rescored = [f.get("scores", {}) for f in findings]
        if rescored:
            record["scores"] = {
                k: sum(s.get(k, 0) for s in rescored) / len(rescored)
                for k in (
                    "accuracy",
                    "prioritization",
                    "justification",
                    "actionability",
                )
            }

    # Write back atomically (persist the re-judged findings)
    tmp_path = results_path.with_suffix(".tmp")
    tmp_path.write_text("\n".join(json.dumps(r) for r in results) + "\n")
    tmp_path.replace(results_path)

    print()
    print("Rescore complete:")
    print(f"  Records touched: {records_touched}")
    print(f"  Findings re-judged: {findings_rescored}")
    print(f"  Still failing (judge_error): {still_failing}")


def _run_pair(
    model: str,
    skill_model: str,
    diff_records: list[dict],
    no_judge: bool,
    judge_model: str | None,
    existing_results: dict,
    output_path: Path,
    force: bool,
) -> tuple[str, int, int]:
    """Run all diffs for one (model, skill) pair.

    Args:
        model: Model label
        skill_model: Skill file to apply
        diff_records: List of diff records to process
        no_judge: If True, skip judging
        judge_model: Model to use for judging
        existing_results: Dict of already-computed results (keyed by (diff_id, model, skill))
        output_path: Path to output JSONL file
        force: If True, regenerate all results

    Returns:
        Tuple of (label, findings_count, judge_err_count)
    """
    label = model if model == skill_model else f"{model}←{skill_model}"
    print(f"[{label}] processing {len(diff_records)} diffs...", flush=True)
    cell_start = time.time()
    cell_judge_err = 0
    findings_count = 0

    for idx, diff_record in enumerate(diff_records, 1):
        diff_id = diff_record.get("id", "unknown")
        key = (diff_id, model, skill_model)

        # Skip if already computed (unless force mode)
        if not force and key in existing_results:
            continue

        result = run_model_on_diff(model, diff_record, no_judge, judge_model, skill_model)
        if result:
            # Thread-safe append to JSONL
            with _results_lock:
                with open(output_path, "a") as out_f:
                    out_f.write(json.dumps(result) + "\n")
                    out_f.flush()

            findings_count += len(result.get("findings", []))
            # Track judge errors
            for f in result.get("findings", []):
                if f.get("scores", {}).get("judge_error"):
                    cell_judge_err += 1

        # Per-record progress
        elapsed = int(time.time() - cell_start)
        if result:
            findings_count = len(result.get("findings", []))
            print(
                f"[{label}] {idx}/{len(diff_records)} diff_id={diff_id} findings={findings_count} "
                f"refused={result.get('refused', False)} "
                f"judge_err={cell_judge_err} elapsed={elapsed}s",
                flush=True,
            )
        else:
            print(
                f"[{label}] {idx}/{len(diff_records)} diff_id={diff_id} status=error elapsed={elapsed}s",
                flush=True,
            )

    # Cell end summary
    elapsed_total = int(time.time() - cell_start)
    print(
        f"[{label}] complete: {len(diff_records)}/{len(diff_records)}, judge_err={cell_judge_err}, {elapsed_total}s",
        flush=True,
    )

    return label, findings_count, cell_judge_err


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run eval pipeline: judge model performance on diff-based bug detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/run_eval.py                    # run all models with judge
  python3 scripts/run_eval.py --no-judge         # offline mode, zero scores
  python3 scripts/run_eval.py --models glm5.2    # run single model
  python3 scripts/run_eval.py --force            # regenerate all results
  python3 scripts/run_eval.py --rescore-zeros    # re-judge poisoned records
  python3 scripts/run_eval.py --parallel         # run models in parallel (max 2 workers)
""",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated subset of models to run (e.g., --models glm5.2). Default: all models.",
    )
    parser.add_argument(
        "--skills",
        type=str,
        default=None,
        help=(
            "Comma-separated subset of skill-source models for cross mode "
            "(e.g., --skills gpt-oss-120b). Requires --cross. Default: all skills."
        ),
    )
    parser.add_argument(
        "--eval",
        type=str,
        default=str(EVAL_INPUT),
        help=f"Path to eval diffs JSONL file. Default: {EVAL_INPUT}",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(EVAL_OUTPUT),
        help=f"Path to output results JSONL file. Default: {EVAL_OUTPUT}",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Offline mode: skip judging, return zero scores (for CI/tests without API key)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate all results (override skip-existing)",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="Model used to score findings. Default: each model judges itself.",
    )
    parser.add_argument(
        "--cross",
        action="store_true",
        help="Run off-diagonal skill×model pairings (skill of model X applied by model Y).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print completion status table and exit (no evaluation run).",
    )
    parser.add_argument(
        "--rescore-zeros",
        action="store_true",
        help="Re-judge findings with all-zero scores or judge_error (no model re-run).",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run (model, skill) pairs in parallel with max 2 workers (default: sequential).",
    )
    args = parser.parse_args()

    # Load eval diffs
    eval_path = Path(args.eval)
    if not eval_path.exists():
        print(f"error: eval file not found: {args.eval}", file=sys.stderr)
        sys.exit(1)

    diff_records = []
    with open(eval_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    diff_records.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"warning: invalid JSON in {eval_path}: {line[:100]}", file=sys.stderr)
                    continue

    if not diff_records:
        print(f"error: no valid records in {args.eval}", file=sys.stderr)
        sys.exit(1)

    # --status: print completion table and exit
    if args.status:
        _print_status_table(args.out, Path(args.eval), args.models, args.cross, args.skills)
        sys.exit(0)

    # --rescore-zeros: re-judge poisoned records
    if args.rescore_zeros:
        _rescore_zeros(Path(args.out), Path(args.eval), args.no_judge, args.judge_model)
        sys.exit(0)

    # Determine pairings to run
    if args.models:
        models_to_run = [m.strip() for m in args.models.split(",")]
        missing = [m for m in models_to_run if m not in MODELS]
        if missing:
            print(f"error: unknown models: {', '.join(missing)}", file=sys.stderr)
            print(f"valid models: {', '.join(MODELS.keys())}", file=sys.stderr)
            sys.exit(2)
    else:
        models_to_run = list(MODELS.keys())

    skills_filter: list[str] | None = None
    if args.skills:
        if not args.cross:
            print("error: --skills requires --cross", file=sys.stderr)
            sys.exit(2)
        skills_filter = [s.strip() for s in args.skills.split(",")]
        missing = [s for s in skills_filter if s not in MODELS]
        if missing:
            print(f"error: unknown skills: {', '.join(missing)}", file=sys.stderr)
            print(f"valid models: {', '.join(MODELS.keys())}", file=sys.stderr)
            sys.exit(2)

    if args.cross:
        pairs = _cross_pairs(models_to_run, skills_filter)
    else:
        pairs = [(m, m) for m in models_to_run]

    print(f"Running eval: {len(diff_records)} diffs × {len(pairs)} pairings")
    print(f"  Input: {args.eval}")
    print(f"  Output: {args.out}")
    print(f"  Pairings (model←skill): {', '.join(f'{m}←{s}' for m, s in pairs)}")
    print(f"  Judge: {args.judge_model or 'self (per-model)'}")
    print(f"  Judge mode: {'disabled' if args.no_judge else 'enabled'}")
    print(f"  Parallel: {args.parallel} ({'max 2 workers' if args.parallel else 'sequential'})")
    print()

    # Load existing results (for --force check)
    output_path = Path(args.out)
    existing_results = {}
    if output_path.exists() and not args.force:
        with open(output_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        key = (
                            record.get("diff_id"),
                            record.get("model"),
                            record.get("skill") or record.get("model"),
                        )
                        # Skip records with judge_error (poisoned by scoring failure)
                        has_judge_error = any(
                            f.get("scores", {}).get("judge_error")
                            for f in record.get("findings", [])
                        )
                        if not has_judge_error:
                            existing_results[key] = record
                    except json.JSONDecodeError:
                        continue

    # Run eval
    if args.force and output_path.exists():
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.parallel:
        # Parallel execution (max 2 workers)
        # Note: _WallClockTimeout uses SIGALRM which is not thread-safe in Python.
        # Empirically, run_review.py's parallel mode works, but this is a caveat.
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for model, skill_model in pairs:
                futures.append(
                    executor.submit(
                        _run_pair,
                        model,
                        skill_model,
                        diff_records,
                        args.no_judge,
                        args.judge_model,
                        existing_results,
                        output_path,
                        args.force,
                    )
                )

            for future in as_completed(futures):
                label, findings_count, cell_judge_err = future.result()

        print()
        print("Eval complete: parallel run finished for all pairs")
    else:
        # Sequential execution (default)
        for model, skill_model in pairs:
            _run_pair(
                model,
                skill_model,
                diff_records,
                args.no_judge,
                args.judge_model,
                existing_results,
                output_path,
                args.force,
            )

        print()
        print(f"Eval complete: {len(pairs)} pairings processed")

    # Summary
    # Reload results for summary stats
    results = []
    if output_path.exists():
        with open(output_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    print("\nSummary by model:")
    by_model = {}
    for r in results:
        model = r.get("model", "unknown")
        if model not in by_model:
            by_model[model] = {"total": 0, "refused": 0, "findings": 0}
        by_model[model]["total"] += 1
        if r.get("refused"):
            by_model[model]["refused"] += 1
        by_model[model]["findings"] += len(r.get("findings", []))

    for model, stats in sorted(by_model.items()):
        print(
            f"  {model}: {stats['total']} diffs, {stats['refused']} refused, {stats['findings']} findings"
        )

    # Global summary (like --status output)
    print("\nGlobal summary:")
    _print_status_table(args.out, Path(args.eval), args.models, args.cross, args.skills)

    sys.exit(0)


if __name__ == "__main__":
    main()
