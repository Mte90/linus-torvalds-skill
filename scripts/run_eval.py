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
  python3 scripts/run_eval.py --baseline         # run baseline (no skill)
  python3 scripts/run_eval.py --repetitions 3    # run each diff 3 times
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
from torvalds_skill.matching import match_finding_to_bug  # noqa: E402
from torvalds_skill.profiles import get_profile  # noqa: E402

# Configuration
ROOT = Path(__file__).resolve().parent.parent
EVAL_INPUT = ROOT / "data" / "eval_diffs.jsonl"
EVAL_OUTPUT = ROOT / "data" / "eval_results.jsonl"
BENCHMARK_PATH = ROOT / "data" / "benchmark.jsonl"
SMALLCHAT_TARGET = Path("/tmp/smallchat")
SMALLCHAT_FILES = [
    "smallchat-server.c",
    "smallchat-client.c",
    "chatlib.c",
    "chatlib.h",
    "Makefile",
]

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


def build_diff_prompt(diff_record: dict, skill_text: str | None) -> str:
    """Build ground-truth-free diff review prompt.

    Args:
        diff_record: Record from eval_diffs.jsonl with id, diff, language, file, expected, bugs
        skill_text: Torvalds skill text to apply. If None, baseline mode (no skill block).

    Returns:
        Prompt string for LLM (contains no ground-truth bug information)
    """
    diff_id = diff_record.get("id", "unknown")
    diff_text = diff_record.get("diff", "")
    file_path = diff_record.get("file", "unknown")
    language = diff_record.get("language", "unknown")

    # Build prompt header
    prompt_parts = [
        "You are a code reviewer applying the Linus Torvalds reviewer skill to a code diff."
    ]
    prompt_parts.append("\nDo NOT use any tools. Everything you need is inlined below.")

    # Add skill block only if skill_text is provided
    if skill_text is not None:
        prompt_parts.append("\n== SKILL ==")
        prompt_parts.append(skill_text)

    # Add diff block
    prompt_parts.append("\n== DIFF ==")
    prompt_parts.append(f"File: {file_path}")
    prompt_parts.append(f"Language: {language}")
    prompt_parts.append(f"Diff ID: {diff_id}")
    prompt_parts.append(f"\n{diff_text}")

    return (
        "".join(prompt_parts)
        + """
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
    )


def match_finding_to_diff_bug(finding: dict, bugs: list[dict], diff_file: str = "") -> dict | None:
    """Match a finding to a ground-truth bug (same basename or alias, line ±5).

    Single implementation lives in torvalds_skill.matching, shared with the
    comparison report pipeline.
    """
    return match_finding_to_bug(finding, bugs, diff_file)


def _ensure_smallchat() -> None:
    """Clone antirez/smallchat to /tmp/smallchat if missing."""
    if SMALLCHAT_TARGET.exists():
        return
    import subprocess

    print(f"Cloning antirez/smallchat to {SMALLCHAT_TARGET}...")
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/antirez/smallchat",
            str(SMALLCHAT_TARGET),
        ],
        check=True,
        capture_output=True,
    )


def _read_smallchat_sources() -> str:
    """Read and concatenate all smallchat source files into a sources block."""
    parts = []
    for src in SMALLCHAT_FILES:
        path = SMALLCHAT_TARGET / src
        content = path.read_text() if path.exists() else f"(file not found: {src})"
        parts.append(f"== SOURCE: {src} ==\n{content}\n")
    return "\n".join(parts)


def build_codebase_prompt(skill_text: str | None) -> str:
    """Build a full-codebase review prompt (antirez/smallchat).

    Args:
        skill_text: Torvalds skill text to apply. If None, baseline mode (no skill block).

    Returns:
        Prompt string for LLM (contains no ground-truth bug information)
    """
    sources_block = _read_smallchat_sources()

    parts = [
        "You are a code reviewer applying the Linus Torvalds reviewer skill to a real codebase.",
        "\nDo NOT use any tools. Do NOT read any files. Everything you need is inlined below.",
    ]

    if skill_text is not None:
        parts.append("\n== SKILL ==")
        parts.append(skill_text)

    parts.append(f"\n{sources_block}")
    parts.append(
        """
## Task

Review the codebase above using the Torvalds skill. Find bugs, security issues, memory safety problems, and code quality issues.

## Format

For each finding use:
### [SEVERITY] Finding title
- **Type:** (the trigger from the skill that fired, or "unmatched" if none matches)
- **Trigger:** (the trigger from the skill that fired, or "unmatched" if none matches)
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action
- **Pass:** 1 | 2

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings
- Use `**Field:**` format (colon inside bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

## Two-Pass Review Rule

Pass 1 — Correctness and Memory Safety ONLY:
  - Report ONLY: crashes, corruption, OOB access, unchecked errors, resource leaks.
  - Severity: CRITICAL or HIGH only.
  - Label each finding: `Pass: 1`

Pass 2 — Style and Build Findings (capped):
  - Report ONLY for files that have ZERO Pass-1 findings.
  - Max 2 findings per file.
  - Severity: MEDIUM or LOW only.
  - Label each finding: `Pass: 2`

Merge rule: If a file has any Pass-1 findings, ALL Pass-2 findings for that file are dropped.

## Rules

- Cover ALL source files.
- Report every real bug you find. Map each finding to the closest matching skill trigger when one exists; if none matches, set Trigger: unmatched — do NOT suppress real bugs.
- Use the skill's severity calibration and precedence hierarchy.
- Precedence: correctness > performance > complexity > style > API stability.
- Be concrete: cite line numbers, name functions, quote code.
- Don't invent problems. If a file is genuinely clean, say "No findings."
- English.

Write your review to stdout.
"""
    )
    return "".join(parts)


def load_benchmark_bugs() -> list[dict]:
    """Load ground-truth bugs from data/benchmark.jsonl.

    Returns the bugs as synthetic diff-records so compute_cell_metrics can
    consume them unchanged: each bug becomes a record with id, file, bugs=[bug],
    expected='findings'.
    """
    bugs = []
    with open(BENCHMARK_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                bugs.append(json.loads(line))
    return bugs


def benchmark_to_diff_records(bugs: list[dict]) -> list[dict]:
    """Convert benchmark bugs into synthetic diff-records for compute_cell_metrics.

    Each bug becomes a record: {id, file, bugs:[bug], expected:'findings'}
    so the renderer's matching logic (match_finding_to_diff_bug) works unchanged.
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


def run_model_on_codebase(
    model: str,
    bugs: list[dict],
    no_judge: bool,
    judge_model: str | None = None,
    skill_model: str | None = None,
    baseline: bool = False,
) -> dict | None:
    """Run a single model on the full smallchat codebase.

    Produces one result record matching the diff-mode format so the renderer
    can consume it unchanged.
    """
    if baseline:
        skill_text = None
    else:
        skill_file = MODELS.get(skill_model or model)
        if not skill_file or not skill_file.exists():
            print(f"error: skill file not found: {skill_file}", file=sys.stderr)
            return None
        skill_text = skill_file.read_text()

    prompt = build_codebase_prompt(skill_text)
    profile = get_profile(model)
    timeout = getattr(profile, "review_timeout", 600)

    response = None
    for attempt in range(2):
        try:
            response = call_llm(model, prompt, timeout=timeout)
            if response.strip():
                break
            print(
                f"warning: empty response (attempt {attempt + 1}) for {model} on codebase",
                file=sys.stderr,
            )
            response = None
        except Exception as e:
            print(
                f"error: API call failed for {model} on codebase (attempt {attempt + 1}): {e}",
                file=sys.stderr,
            )
            response = None

    if response is None or not response.strip():
        return None

    # Parse findings using a synthetic diff_record for file context
    synthetic = {"diff": "", "file": "smallchat-server.c"}
    findings = parse_findings_from_review(response, synthetic)

    refused = check_refused(response, findings)

    # Score each finding against all benchmark bugs
    scores_list = []
    for finding in findings:
        bug = match_finding_to_diff_bug(finding, bugs, finding.get("file", ""))
        finding["scores"] = score_finding_with_judge(finding, bug, judge_model or model, no_judge)
        scores_list.append(finding["scores"])

    if scores_list:
        avg_scores = {
            k: sum(s.get(k, 0) for s in scores_list) / len(scores_list)
            for k in ("accuracy", "prioritization", "justification", "actionability")
        }
    else:
        avg_scores = {"accuracy": 0, "prioritization": 0, "justification": 0, "actionability": 0}

    result = {
        "diff_id": "SMALLCHAT",
        "model": model,
        "expected": "findings",
        "findings": findings,
        "scores": avg_scores,
        "refused": refused,
        "skill": skill_model if skill_model and not baseline else "none",
    }
    return result


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
    baseline: bool = False,
) -> dict:
    """Run a single model on a single diff record.

    Args:
        model: Model label used for the review call
        diff_record: Diff record from eval_diffs.jsonl
        no_judge: If True, skip judging (offline mode)
        judge_model: Model to use for judging (defaults to same as review model)
        skill_model: Whose skill to apply (defaults to model itself; set for cross runs)
        baseline: If True, run without skill text (skill="none")

    Returns:
        Result dict with: diff_id, model, expected, findings, scores, refused, skill, rep
    """
    # Baseline mode: no skill text
    if baseline:
        skill_text = None
    else:
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
    # Always include skill field ("none" for baseline, skill_model for others)
    result["skill"] = skill_model if skill_model and not baseline else "none"
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


def _stamp_judge_model(results_path: Path, judge_model: str | None) -> None:
    """Record which judge produced the scores, without re-judging anything.

    Records written before ``judge_model`` existed carry no proof of which model
    scored them, so a report can only assert the judge from how the run was
    invoked. Stamping closes that gap at zero API cost. It does NOT recompute
    scores: use ``--rescore-all`` when the scores themselves must be redone.

    Records already tagged with a different judge are left untouched and
    reported, so a wrong label can never be written silently.

    Run this only when no evaluation is writing to the same file.
    """
    if not judge_model:
        print(
            "error: --stamp-judge-model requires the judge name (e.g. --stamp-judge-model glm5.2)",
            file=sys.stderr,
        )
        sys.exit(2)

    results = []
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not results:
        print(f"No records found in {results_path}")
        return

    stamped = 0
    already = 0
    conflicts: list[str] = []
    for record in results:
        existing = record.get("judge_model")
        if existing is None:
            record["judge_model"] = judge_model
            stamped += 1
        elif existing == judge_model:
            already += 1
        else:
            conflicts.append(f"{record.get('model')}/{record.get('skill')}={existing}")

    tmp_path = results_path.with_suffix(".tmp")
    tmp_path.write_text("\n".join(json.dumps(r) for r in results) + "\n")
    tmp_path.replace(results_path)

    print(f"Stamped judge_model={judge_model} on {stamped} record(s) in {results_path}")
    print(f"  already tagged with this judge: {already}")
    if conflicts:
        print(f"  LEFT UNTOUCHED, tagged with a different judge: {len(conflicts)}")
        for entry in conflicts[:5]:
            print(f"    {entry}")


def _rescore_all(
    results_path: Path, diffs_path: Path, no_judge: bool, judge_model: str | None
) -> None:
    """Re-judge every finding in every record with a fixed judge model.

    Unlike ``_rescore_zeros``, this forces a full re-judgment of all records,
    not only those with zero scores or ``judge_error``. Use this to replace
    self-judged scores with a fixed external judge (e.g., ``glm5.2``) for
    cross-model fairness.

    Args:
        results_path: Path to eval results JSONL file
        diffs_path: Path to eval diffs JSONL file
        no_judge: If True, skip judging (offline mode)
        judge_model: Model to use for judging (required for fairness)
    """
    if no_judge:
        print("error: --rescore-all cannot be combined with --no-judge", file=sys.stderr)
        sys.exit(2)
    if not judge_model:
        print(
            "error: --rescore-all requires --judge-model (e.g., --judge-model glm5.2)",
            file=sys.stderr,
        )
        sys.exit(2)

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

    results = []
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not results:
        print("No records to rescore.")
        return

    print(f"Re-judging {len(results)} records with judge={judge_model} ...", flush=True)
    total_findings = sum(len(r.get("findings", [])) for r in results)

    progress_lock = Lock()
    progress_counter = {"done": 0, "errors": 0}

    def _rescore_one(record: dict) -> tuple[dict, int, int]:
        diff_id = record.get("diff_id")
        diff_record = diffs_by_id.get(diff_id, {})
        bugs = diff_record.get("bugs", [])
        findings = record.get("findings", [])
        err_count = 0

        for finding in findings:
            bug = match_finding_to_diff_bug(finding, bugs, diff_record.get("file", ""))
            finding["diff_text"] = diff_record.get("diff", "")
            new_scores = score_finding_with_judge(finding, bug, judge_model, no_judge=False)
            finding["scores"] = new_scores
            if new_scores.get("judge_error"):
                err_count += 1

            with progress_lock:
                progress_counter["done"] += 1
                if progress_counter["done"] % 25 == 0:
                    print(
                        f"  progress: {progress_counter['done']}/{total_findings} findings",
                        flush=True,
                    )

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
        record["judge_model"] = judge_model

        return record, len(findings), err_count

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_rescore_one, r): i for i, r in enumerate(results)}
        for future in as_completed(futures):
            idx = futures[future]
            rescored_record, _, err_count = future.result()
            results[idx] = rescored_record
            with progress_lock:
                progress_counter["errors"] += err_count

    findings_rescored = progress_counter["done"]
    still_failing = progress_counter["errors"]

    tmp_path = results_path.with_suffix(".tmp")
    tmp_path.write_text("\n".join(json.dumps(r) for r in results) + "\n")
    tmp_path.replace(results_path)

    print()
    print("Rescore-all complete:")
    print(f"  Records re-judged: {len(results)}")
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
    repetitions: int = 1,
    baseline: bool = False,
) -> tuple[str, int, int]:
    """Run all diffs for one (model, skill) pair.

    Args:
        model: Model label
        skill_model: Skill file to apply (or "none" for baseline)
        diff_records: List of diff records to process
        no_judge: If True, skip judging
        judge_model: Model to use for judging
        existing_results: Dict of already-computed results (keyed by (diff_id, model, skill, rep))
        output_path: Path to output JSONL file
        force: If True, regenerate all results
        repetitions: Number of times to run each diff (default 1)
        baseline: If True, run without skill text

    Returns:
        Tuple of (label, findings_count, judge_err_count)
    """
    label = model if model == skill_model else f"{model}←{skill_model}"
    if baseline:
        label = f"{model}←baseline"
    print(f"[{label}] processing {len(diff_records)} diffs × {repetitions} rep(s)...", flush=True)
    cell_start = time.time()
    cell_judge_err = 0
    findings_count = 0

    for idx, diff_record in enumerate(diff_records, 1):
        diff_id = diff_record.get("id", "unknown")

        # Run multiple repetitions
        for rep in range(repetitions):
            # Key includes rep for resume-safety (backward compatible: missing rep treated as 0)
            key = (diff_id, model, skill_model if skill_model else "none", rep)

            # Skip if already computed (unless force mode)
            if not force and key in existing_results:
                continue

            result = run_model_on_diff(
                model, diff_record, no_judge, judge_model, skill_model, baseline
            )
            if result:
                # Add rep field to result
                result["rep"] = rep

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
                    f"[{label}] {idx}/{len(diff_records)} rep={rep} diff_id={diff_id} findings={findings_count} "
                    f"refused={result.get('refused', False)} "
                    f"judge_err={cell_judge_err} elapsed={elapsed}s",
                    flush=True,
                )
            else:
                print(
                    f"[{label}] {idx}/{len(diff_records)} rep={rep} diff_id={diff_id} status=error elapsed={elapsed}s",
                    flush=True,
                )

    # Cell end summary
    elapsed_total = int(time.time() - cell_start)
    print(
        f"[{label}] complete: {len(diff_records)}/{len(diff_records)}, judge_err={cell_judge_err}, {elapsed_total}s",
        flush=True,
    )

    return label, findings_count, cell_judge_err


def _run_codebase_mode(args) -> None:
    """Run codebase-mode evaluation: one record per (model, skill) pair.

    Clones antirez/smallchat, builds full-codebase prompts, matches findings
    against data/benchmark.jsonl. Output goes to data/eval_results_codebase.jsonl
    unless --out is given.
    """
    _ensure_smallchat()
    bugs = load_benchmark_bugs()
    print(f"Loaded {len(bugs)} ground-truth bugs from {BENCHMARK_PATH}")

    # Determine output path
    if args.out is None:
        output_path = ROOT / "data" / "eval_results_codebase.jsonl"
    else:
        output_path = Path(args.out)

    # Determine models
    if args.models:
        models_to_run = [m.strip() for m in args.models.split(",")]
        missing = [m for m in models_to_run if m not in MODELS]
        if missing:
            print(f"error: unknown models: {', '.join(missing)}", file=sys.stderr)
            sys.exit(2)
    else:
        models_to_run = list(MODELS.keys())

    # Build pairs
    if args.baseline:
        pairs = [(m, "none") for m in models_to_run]
    elif args.cross:
        skills_filter = None
        if args.skills:
            skills_filter = [s.strip() for s in args.skills.split(",")]
        pairs = _cross_pairs(models_to_run, skills_filter)
    else:
        pairs = [(m, m) for m in models_to_run]

    print(f"Codebase mode: {len(pairs)} pairings × {args.repetitions} rep(s)")
    print(f"  Output: {output_path}")
    print(f"  Judge: {args.judge_model or 'self (per-model)'}")
    print()

    # Load existing results for resume (key: model, skill, rep)
    existing = {}
    if output_path.exists() and not args.force:
        with open(output_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    key = (rec.get("model"), rec.get("skill", "none"), rec.get("rep", 0))
                    has_err = any(
                        f.get("scores", {}).get("judge_error") for f in rec.get("findings", [])
                    )
                    if not has_err:
                        existing[key] = rec
                except json.JSONDecodeError:
                    continue

    if args.force and output_path.exists():
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for model, skill_model in pairs:
        for rep in range(args.repetitions):
            key = (model, skill_model if skill_model else "none", rep)
            if key in existing:
                print(f"[{model}←{skill_model}] rep={rep} skipped (already done)")
                continue

            baseline = args.baseline or skill_model == "none"
            result = run_model_on_codebase(
                model=model,
                bugs=bugs,
                no_judge=args.no_judge,
                judge_model=args.judge_model,
                skill_model=skill_model if not baseline else None,
                baseline=baseline,
            )
            if result is None:
                print(f"[{model}←{skill_model}] rep={rep} status=error")
                continue

            result["rep"] = rep
            with open(output_path, "a") as f:
                f.write(json.dumps(result) + "\n")
                f.flush()

            n_findings = len(result.get("findings", []))
            n_err = sum(
                1 for f in result.get("findings", []) if f.get("scores", {}).get("judge_error")
            )
            print(
                f"[{model}←{skill_model}] rep={rep} findings={n_findings} "
                f"refused={result.get('refused', False)} judge_err={n_err}"
            )

    print()
    print(f"Codebase eval complete: {len(pairs)} pairings")


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
  python3 scripts/run_eval.py --baseline         # run baseline (no skill text)
  python3 scripts/run_eval.py --repetitions 3    # run each diff 3 times
  python3 scripts/run_eval.py --cross            # run off-diagonal skill×model pairs
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
        default=None,
        help=(
            "Path to output results JSONL file. Default: "
            "data/eval_results.jsonl (diagonal) or "
            "data/eval_results_cross.jsonl (--cross)."
        ),
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
        "--stamp-judge-model",
        type=str,
        default=None,
        metavar="MODEL",
        help=(
            "Record MODEL as the judge on records that lack a judge_model field, "
            "without re-judging. Use when scores came from --judge-model at "
            "generation time but the field did not exist yet."
        ),
    )
    parser.add_argument(
        "--rescore-all",
        action="store_true",
        help=(
            "Re-judge ALL findings with a fixed judge model (requires --judge-model). "
            "Use to replace self-judged scores with an external judge for cross-model fairness."
        ),
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run (model, skill) pairs in parallel with max 2 workers (default: sequential).",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Number of times to run each diff (default: 1). Each repetition gets a separate record with 'rep' field (0-based).",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Run baseline mode: model runs WITHOUT any skill text (skill='none'). Composes with --repetitions.",
    )
    parser.add_argument(
        "--codebase",
        action="store_true",
        help=(
            "Codebase mode: clone antirez/smallchat, review full source files "
            "(not synthetic diffs), match against data/benchmark.jsonl. "
            "Produces one record per (model, skill) pair instead of per-diff."
        ),
    )
    args = parser.parse_args()

    # --codebase mode: full-codebase review, one record per pair
    # Dispatch before the --cross output-path resolution so codebase mode
    # writes to eval_results_codebase.jsonl, not the diff-based cross file.
    if args.codebase:
        _run_codebase_mode(args)
        sys.exit(0)

    # Resolve default output path based on --cross flag
    if args.out is None:
        if args.cross:
            args.out = str(ROOT / "data" / "eval_results_cross.jsonl")
        else:
            args.out = str(EVAL_OUTPUT)

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

    # --stamp-judge-model: tag records, no API calls
    if args.stamp_judge_model:
        _stamp_judge_model(Path(args.out), args.stamp_judge_model)
        sys.exit(0)

    # --rescore-all: re-judge every record with a fixed external judge
    if args.rescore_all:
        _rescore_all(Path(args.out), Path(args.eval), args.no_judge, args.judge_model)
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

    # Build pairs based on mode
    if args.baseline:
        # Baseline mode: each model runs without skill (skill="none")
        pairs = [(m, "none") for m in models_to_run]
        # --cross doesn't apply to baseline (baseline is its own mode)
    elif args.cross:
        pairs = _cross_pairs(models_to_run, skills_filter)
    else:
        pairs = [(m, m) for m in models_to_run]

    print(
        f"Running eval: {len(diff_records)} diffs × {len(pairs)} pairings × {args.repetitions} rep(s)"
    )
    print(f"  Input: {args.eval}")
    print(f"  Output: {args.out}")
    if args.baseline:
        print("  Mode: baseline (no skill text)")
    elif args.cross:
        print(f"  Pairings (model←skill): {', '.join(f'{m}←{s}' for m, s in pairs)}")
    else:
        print(f"  Pairings (model←skill): {', '.join(f'{m}←{s}' for m, s in pairs)}")
    print(f"  Judge: {args.judge_model or 'self (per-model)'}")
    print(f"  Judge mode: {'disabled' if args.no_judge else 'enabled'}")
    print(f"  Parallel: {args.parallel} ({'max 2 workers' if args.parallel else 'sequential'})")
    print(f"  Repetitions: {args.repetitions}")
    print()

    # Load existing results (for --force check)
    # Key format: (diff_id, model, skill, rep) - backward compatible: missing rep treated as 0
    output_path = Path(args.out)
    existing_results = {}
    if output_path.exists() and not args.force:
        with open(output_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        diff_id = record.get("diff_id")
                        model = record.get("model")
                        skill = record.get("skill") or record.get("model")
                        rep = record.get("rep", 0)  # Backward compatible: missing rep = 0
                        key = (diff_id, model, skill, rep)
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
                        args.repetitions,
                        args.baseline,
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
                args.repetitions,
                args.baseline,
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
