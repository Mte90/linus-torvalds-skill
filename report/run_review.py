#!/usr/bin/env python3
"""
Replicate the three-model Torvalds review of antirez/smallchat + baseline comparison.

Produces, in report/:
  With-skill reviews:
    review-gpt-oss-120b.md
    review-glm5.2.md
    review-mistral.md
  Baseline reviews (no skill) in report/baseline/:
    baseline/review-baseline-gpt-oss-120b.md
    baseline/review-baseline-glm5.2.md
    baseline/review-baseline-mistral.md

Crash-proof features:
  - Skips reviews whose output already exists (use --force to override)
  - Per-model checkpoint/resume with state tracking
  - Per-model timing metrics logged to metrics.jsonl
  - Per-review timeout (40 min for GLM5.2, 15 min for others)
  - One automatic retry per review on failure/timeout
  - Each review is independent: one crash doesn't kill the others
  - Logs are preserved (not deleted on exit) for post-mortem
  - Exit 0 if >=5/6 reviews succeed
  - Optional --parallel-models for concurrent execution (max 2 workers)
  - Optional --models filter for subset selection

Prerequisites:
  - Python 3 with stdlib urllib/json
  - smallchat cloned to /tmp/smallchat (this script does it if missing)
  - skill files present at linus-torvalds-skill/SKILL.md, SKILL-GLM.md, SKILL-Mistral.md

Environment variables:
  (none - all model settings now come from profiles.py)

Budget-gate chunking:
  Both with-skill and baseline arms call _should_chunk(prompt, profile).
  Over budget → chunked per-source-file review + merge; under → single call.

Run from the repository root:
  python3 report/run_review.py                    # skip existing, run missing
  python3 report/run_review.py --force            # regenerate all six
  python3 report/run_review.py --models glm5.2    # run only glm5.2
  python3 report/run_review.py --parallel-models  # run models in parallel (risk: OOM)
  python3 report/run_review.py --clean-logs       # remove .log files and exit
"""

import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

# Configuration
ROOT = Path(__file__).resolve().parent.parent
TARGET = Path("/tmp/smallchat")
REPORT_DIR = ROOT / "report"
SKILL_DIR = ROOT / "linus-torvalds-skill"
BASELINE_DIR = REPORT_DIR / "baseline"

# Source files to review
SOURCE_FILES = [
    "smallchat-server.c",
    "smallchat-client.c",
    "chatlib.c",
    "chatlib.h",
    "Makefile",
]

# Data-driven model configuration
MODELS = {
    "gpt-oss-120b": SKILL_DIR / "SKILL.md",
    "glm5.2": SKILL_DIR / "SKILL-GLM.md",
    "mistral-small-4-119b": SKILL_DIR / "SKILL-Mistral.md",
    "qwen3.8-27b": SKILL_DIR / "SKILL-Qwen.md",
}

# TIMEOUTS replaced by profile.review_timeout - removed hard-coded dict
DEFAULT_TIMEOUT = 900

# State file for per-model checkpoints
STATE_FILE = REPORT_DIR / ".review_state.json"


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run multi-model code review pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Parallelism note:
  --parallel-models runs models concurrently (max 2 workers). This can
  speed up runs but may cause OOM kills on machines with limited RAM.
  Default is sequential execution (safer for all machines).
""",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate all reviews (override skip-existing)",
    )
    parser.add_argument(
        "--clean-logs",
        action="store_true",
        help="Remove .log files and exit",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated subset of models to run (e.g., --models glm5.2 or --models gpt-oss-120b,mistral-small-4-119b). Default: all models.",
    )
    parser.add_argument(
        "--parallel-models",
        action="store_true",
        help="Run models in parallel (max 2 workers). WARNING: May cause OOM kills on machines with limited RAM. Default is sequential.",
    )
    return parser.parse_args()


def clean_logs():
    """Remove all review log files."""
    log_files = list(REPORT_DIR.glob("review-*.log"))
    for log_file in log_files:
        log_file.unlink()
    print("Cleaned review logs.")
    sys.exit(0)


def load_state() -> dict:
    """Load checkpoint state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict) -> None:
    """Save checkpoint state to disk."""
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except OSError:
        pass  # Silently ignore state write failures


def compute_file_hash(path: Path) -> str | None:
    """Compute SHA256 hash of a file. Returns None if file missing."""
    if not path.exists():
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def compute_input_hash(model: str, mode: str) -> str | None:
    """Compute SHA256 hash of inputs (skill + source files).

    Returns None if any input is missing.
    """
    if mode == "baseline":
        input_files = [TARGET / src for src in SOURCE_FILES]
    else:
        skill_file = MODELS.get(model)
        if not skill_file or not skill_file.exists():
            return None
        input_files = [skill_file] + [TARGET / src for src in SOURCE_FILES]

    h = hashlib.sha256()
    for inp in input_files:
        if not inp.exists():
            return None
        try:
            with open(inp, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except OSError:
            return None
    return h.hexdigest()


def _extract_input_hash_from_frontmatter(content: str) -> str | None:
    """Extract input_hash from YAML frontmatter. Returns None if not found."""
    if not content.lstrip().startswith("---"):
        return None
    stripped = content.lstrip()
    end = stripped.find("\n---", 3)
    if end == -1:
        return None
    frontmatter = stripped[3:end]
    match = re.search(r"^input_hash:\s*(\S+)", frontmatter, re.MULTILINE)
    return match.group(1) if match else None


def should_skip_model(model: str, mode: str, force: bool) -> tuple[bool, str]:
    """Check if a model/mode combination should be skipped.

    Skip if: output exists AND input_hash in frontmatter matches current input hash.
    Re-run if: any input changed (skill or source files).

    Returns (should_skip, reason).
    """
    if force:
        return False, "--force flag set"

    # Check if output file still exists
    if mode == "baseline":
        out_file = BASELINE_DIR / f"review-baseline-{model}.md"
    else:
        out_file = REPORT_DIR / f"review-{model}.md"

    if not out_file.exists():
        return False, "output file missing"

    # Check if output file has valid frontmatter with input_hash
    content = out_file.read_text()
    stored_input_hash = _extract_input_hash_from_frontmatter(content)
    if stored_input_hash is None:
        return False, "no input_hash in output frontmatter (legacy)"

    # Check if input hash matches (skill + source files)
    current_input_hash = compute_input_hash(model, mode)
    if current_input_hash is None:
        return False, "input file missing"

    if current_input_hash != stored_input_hash:
        return False, "input hash mismatch (skill or source changed)"

    return True, "checkpoint valid (input hash matches)"


def record_checkpoint(model: str, mode: str, out_file: Path, status: str) -> None:
    """Record a checkpoint for a model/mode combination."""
    state = load_state()
    key = f"{model}:{mode}"

    state[key] = {
        "timestamp": datetime.now(UTC).timestamp(),
        "output_hash": compute_file_hash(out_file) if out_file.exists() else None,
        "input_hash": compute_input_hash(model, mode),
        "status": status,
    }

    save_state(state)


def ensure_target_exists():
    """Clone smallchat if missing."""
    if not TARGET.exists():
        print(f"Cloning antirez/smallchat to {TARGET}...")
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/antirez/smallchat", str(TARGET)],
            check=True,
        )


def verify_skill_assets():
    """Verify all skill files exist."""
    skill_files = [
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "SKILL-GLM.md",
        SKILL_DIR / "SKILL-Mistral.md",
        SKILL_DIR / "SKILL-Qwen.md",
    ]
    for skill_file in skill_files:
        if not skill_file.exists():
            print(f"Missing asset: {skill_file}", file=sys.stderr)
            sys.exit(1)


def read_source_file(source_file: str) -> str:
    """Read a source file from the target directory."""
    return (TARGET / source_file).read_text()


def _build_two_pass_rule() -> str:
    """Build the two-pass review rule text."""
    return """TWO-PASS REVIEW RULE (enforced strictly):

Pass 1 — Correctness and Memory Safety ONLY:
  - Report ONLY: crashes, corruption, OOB access, unchecked errors, resource leaks.
  - Severity: CRITICAL or HIGH only.
  - Label each finding: `Pass: 1`

Pass 2 — Style and Build Findings (capped):
  - Report ONLY for files that have ZERO Pass-1 findings.
  - Max 2 findings per file.
  - Severity: MEDIUM or LOW only.
  - Label each finding: `Pass: 2`

Precedence hierarchy (from skill): correctness > performance > complexity > style > API stability.
This rule enforces that precedence: Pass 1 (correctness) always takes priority over Pass 2 (style).

Merge rule: If a file has any Pass-1 findings, ALL Pass-2 findings for that file are dropped.
"""


def build_review_prompt(skill_file: Path, out_file: Path) -> str:
    """Build the with-skill review prompt."""
    skill_content = skill_file.read_text()
    sources_block = ""
    for src in SOURCE_FILES:
        sources_block += f"== SOURCE: {src} =={read_source_file(src)}\n\n"

    two_pass_rule = _build_two_pass_rule()

    return f"""You are a code reviewer applying the Linus Torvalds reviewer skill to a real codebase.

Do NOT use any tools. Do NOT read any files. Everything you need is inlined below.

== SKILL ==
{skill_content}

{sources_block}

## Persona Narrative (2-3 paragraphs)

Lead with: What does it feel like to interact with an AI using this skill? Does it capture Linus' voice? Is it too harsh, too soft, or about right? Give concrete examples of how the persona comes across.

Specifically:
- Quote specific lines from the skill file that capture (or miss) Linus' voice
- Compare the tone to real Linus quotes (directness, impatience with incompetence, passion for correctness)
- Assess whether the severity calibration feels authentic (does "CRITICAL" feel like something he'd call "garbage" or "horrible"?)
- Note any sections that feel generic vs. distinctly Linus

## Technical Assessment

Structured assessment of:
- Coverage: which triggers fired, which didn't, why
- Accuracy: are the findings legitimate or forced?
- Language-agnosticism: does the skill work for C code?
- Severity calibration: are CRITICAL/HIGH/MEDIUM/LOW assignments justified?
- Precedence adherence: correctness > performance > complexity > style > API stability

{two_pass_rule}

## Strengths

3-5 bullet points on what the skill gets right.

## Weaknesses

3-5 bullet points on gaps, misfires, or areas needing refinement.

## Verdict

1-2 sentences: would you use this in production?

Deliverable: a review report with YAML frontmatter, one section per source file, findings in this format:

### [SEVERITY] Finding title
- **Type:** invariant-true | invariant-false | precedence | guideline
- **Trigger:** (the trigger from the skill that fired)
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action
- **Pass:** 1 | 2

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings — not `####` or `##`
- Use `**Field:**` format (colon inside the bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

Severity levels: CRITICAL | HIGH | MEDIUM | LOW
End with a Summary: verdict, findings by severity, whether the code passes.

Rules:
- Cover ALL source files.
- Report every real bug you find. Map each finding to the closest matching skill trigger when one exists; if none matches, set Trigger: (unmatched) — do NOT suppress real bugs.
- Use the skill's severity calibration and precedence hierarchy to rank findings.
- Precedence: correctness > performance > complexity > style > API stability.
- Be concrete: cite line numbers, name functions, quote code.
- Don't invent problems. If a file is genuinely clean, say "No findings."
- English.

Write the final report to: {out_file}
"""


def build_chunk_prompt(skill_file: Path, source_file: str, chunk_file: Path) -> str:
    """Build the chunk review prompt (single file)."""
    skill_content = skill_file.read_text()
    source_content = read_source_file(source_file)
    two_pass_rule = _build_two_pass_rule()

    return f"""You are a code reviewer applying the Linus Torvalds reviewer skill.

Do NOT use any tools. Do NOT read any files. Everything you need is inlined below.

== SKILL ==
{skill_content}

== SOURCE: {source_file} ==
{source_content}

{two_pass_rule}

Review the source above using the skill rules. For each finding use:
### [SEVERITY] Finding title
- **Type:** invariant-true | invariant-false | precedence | guideline
- **Trigger:** (the trigger from the skill that fired)
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action
- **Pass:** 1 | 2

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings — not `####` or `##`
- Use `**Field:**` format (colon inside the bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

Severity: CRITICAL | HIGH | MEDIUM | LOW
Report every real bug you find. Map each finding to the closest matching skill trigger when one exists; if none matches, set Trigger: (unmatched) — do NOT suppress real bugs.
If a file is genuinely clean, say "No findings." Don't invent problems.
Write findings to: {chunk_file}
"""


def build_baseline_prompt(out_file: Path) -> str:
    """Build the baseline (no-skill) review prompt.

    NOTE: Two-pass rule and Pass caps are added here for validation symmetry with
    the with-skill prompt. Budget-gate chunking (_should_chunk) applies to both
    arms identically. The remaining asymmetry (Persona Narrative, meta-task) is
    documented here and will be addressed in a later task if needed.
    """
    sources_block = ""
    for src in SOURCE_FILES:
        sources_block += f"== SOURCE: {src} =={read_source_file(src)}\n\n"

    two_pass_rule = _build_two_pass_rule()

    return f"""You are a code reviewer. Review the codebase below — antirez/smallchat (minimal TCP chat server, ~706 LOC).

Do NOT use any tools. Do NOT read any files. Everything you need is inlined below.

{sources_block}

{two_pass_rule}

Conduct a thorough code review finding:
- Bugs and logic errors
- Security vulnerabilities (buffer overflows, use-after-free, injection, etc.)
- Memory leaks and resource management issues
- Race conditions and concurrency problems
- Performance issues
- Code quality and maintainability concerns

Deliverable: a review report with YAML frontmatter, one section per source file, findings in this format:

### [SEVERITY] Finding title
- **Type:** bug | security | memory | concurrency | performance | code-quality
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action
- **Pass:** 1 | 2

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings — not `####` or `##`
- Use `**Field:**` format (colon inside the bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

Severity levels: CRITICAL | HIGH | MEDIUM | LOW

End with a Summary: overall assessment, findings by severity, whether the code is production-ready.

Rules:
- Cover ALL source files.
- Be concrete: cite line numbers, name functions, quote code.
- Don't invent problems. If clean in an area, say so.
- Use your own judgment and expertise — no external skill file to follow.
- English.

Write the final report to: {out_file}
"""


def run_llm_call(
    model_label: str, prompt_file: Path, out_file: Path, timeout_sec: int
) -> tuple[int, str]:
    """Run the LLM review subprocess. Returns (exit_code, output)."""
    try:
        result = subprocess.run(
            [
                "python3",
                "report/llm_review.py",
                "--model",
                model_label,
                "--prompt-file",
                str(prompt_file),
                "--out",
                str(out_file),
                "--timeout",
                str(timeout_sec),
            ],
            timeout=timeout_sec,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and result.stderr:
            print(f"  [{model_label}] stderr: {result.stderr[:300]}", file=sys.stderr)
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired:
        return 124, "Timeout expired"


def log_metrics(
    model: str,
    review_type: str,
    out_file: Path,
    duration_sec: int,
    exit_code: int,
    chunk: str | None = None,
    chunked: bool = False,
):
    """Log metrics to metrics.jsonl (legacy format for compatibility)."""
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    word_count = 0
    findings_count = 0

    if out_file.exists() and out_file.stat().st_size > 0:
        word_count = len(out_file.read_text().split())
        import re

        findings_count = len(
            re.findall(
                r"^#{2,4}\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]", out_file.read_text(), re.MULTILINE
            )
        )

    metrics = {
        "ts": ts,
        "model": model,
        "type": review_type,
        "chunk": chunk,
        "duration_sec": duration_sec,
        "exit_code": exit_code,
        "word_count": word_count,
        "raw_findings_count": findings_count,
        "chunked": chunked,
    }

    metrics_file = REPORT_DIR / "metrics.jsonl"
    try:
        with open(metrics_file, "a") as f:
            f.write(json.dumps(metrics) + "\n")
    except OSError as e:
        print(f"WARNING: Failed to write metrics: {e}", file=sys.stderr)


def log_model_metrics(
    model: str, mode: str, started_iso: str, elapsed_s: float, status: str, out_file: Path
) -> None:
    """Log per-model timing to metrics.jsonl (new schema: model, mode, started_iso, elapsed_s, status, out_file.

    Never crashes if write fails - warns to stderr instead.
    """
    metrics = {
        "model": model,
        "mode": mode,
        "started_iso": started_iso,
        "elapsed_s": elapsed_s,
        "status": status,
        "out_file": str(out_file),
    }

    metrics_file = REPORT_DIR / "metrics.jsonl"
    try:
        with open(metrics_file, "a") as f:
            f.write(json.dumps(metrics) + "\n")
    except OSError as e:
        print(f"WARNING: Failed to write model metrics: {e}", file=sys.stderr)


def run_chunk_review(
    model_label: str,
    skill_file: Path,
    source_file: str,
    chunk_file: Path,
    timeout_sec: int,
    force: bool,
) -> bool:
    """Run a single chunk review with timeout + retry. Returns True on success."""
    if not force and chunk_file.exists() and chunk_file.stat().st_size > 0:
        word_count = len(chunk_file.read_text().split())
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] [skip] {model_label} chunk {source_file} already exists ({word_count} words)"
        )
        return True

    chunk_dir = chunk_file.parent
    chunk_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, 4):
        if attempt > 1:
            backoff_multiplier = 2 ** (attempt - 1)
            jitter = random.randint(0, 30)
            retry_timeout = int(timeout_sec * backoff_multiplier + jitter)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file}: retrying (attempt {attempt}, timeout {retry_timeout}s)"
            )
            chunk_file.unlink(missing_ok=True)
        else:
            retry_timeout = timeout_sec

        prompt = build_chunk_prompt(skill_file, source_file, chunk_file)
        prompt_file = chunk_dir / f"{source_file}.prompt"
        prompt_file.write_text(prompt)

        start_ts = datetime.now()
        exit_code, _ = run_llm_call(model_label, prompt_file, chunk_file, retry_timeout)
        (datetime.now() - start_ts).total_seconds()

        prompt_file.unlink(missing_ok=True)

        if exit_code == 0 and chunk_file.exists() and chunk_file.stat().st_size > 0:
            word_count = len(chunk_file.read_text().split())
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} done: {word_count} words"
            )
            return True

        if exit_code == 124:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} TIMED OUT after {retry_timeout}s",
                file=sys.stderr,
            )
        else:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} FAILED (exit {exit_code})",
                file=sys.stderr,
            )

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} FAILED after 3 attempts",
        file=sys.stderr,
    )
    return False


def _clean_chunk_content(text: str) -> str:
    """Strip per-chunk YAML frontmatter and leaked prompt templates.

    Chunks sometimes echo the prompt's format instructions (e.g. a literal
    '### [SEVERITY] Finding title' heading) or carry their own frontmatter;
    both pollute the merged document.
    """
    import re

    # Strip YAML frontmatter if present
    if text.lstrip().startswith("---"):
        stripped = text.lstrip()
        end = stripped.find("\n---", 3)
        if end != -1:
            text = stripped[end + 4 :]

    # Drop literal prompt-template headings like '### [SEVERITY] Finding title'
    text = re.sub(r"^#{3,4}\s+\[SEVERITY\]\s+Finding title\s*$", "", text, flags=re.MULTILINE)
    return text.strip("\n")


def _parse_findings_from_chunk(content: str) -> list[dict]:
    """Parse findings from chunk content. Returns list of finding dicts.

    Each finding dict has keys: 'severity', 'pass_num', 'location', 'raw_block'
    """
    import re

    findings = []
    # Match severity headings: ### [SEVERITY] or ### SEVERITY
    heading_re = re.compile(r"^#{3,4}\s+\[?(CRITICAL|HIGH|MEDIUM|LOW)\]?(?:\s|$)", re.MULTILINE)
    # Match Pass field (with or without bold markers)
    pass_re = re.compile(r"^\s*-?\s*\*\*Pass:\*\*\s*(\d+)", re.MULTILINE)
    # Match Location field (with or without bold markers)
    location_re = re.compile(
        r"^\s*-?\s*(?:\*\*)?Location(?:\*\*)?:\s*(?:\*\*)?\s*(.+)", re.MULTILINE
    )

    # Split content into finding blocks (each starts with ### heading)
    blocks = re.split(
        r"^(?=#{3,4}\s+\[?(?:CRITICAL|HIGH|MEDIUM|LOW)\]?(?:\s|$))", content, flags=re.MULTILINE
    )

    for block in blocks:
        if not block.strip():
            continue
        heading_match = heading_re.search(block)
        if not heading_match:
            continue

        severity = heading_match.group(1)
        pass_match = pass_re.search(block)
        pass_num = int(pass_match.group(1)) if pass_match else 1  # Default to Pass 1

        location_match = location_re.search(block)
        location = location_match.group(1).strip() if location_match else "unknown"

        findings.append(
            {
                "severity": severity,
                "pass_num": pass_num,
                "location": location,
                "raw_block": block.strip(),
            }
        )

    return findings


def _filter_findings_by_pass(findings: list[dict], file_has_pass1: dict[str, bool]) -> list[dict]:
    """Filter findings based on two-pass rule.

    Args:
        findings: List of finding dicts with 'pass_num', 'location', 'raw_block'
        file_has_pass1: Dict mapping filename -> True if file has Pass-1 findings

    Returns:
        Filtered list of findings
    """
    # Group findings by file
    findings_by_file: dict[str, list[dict]] = {}
    for finding in findings:
        location = finding["location"]
        # Extract filename from location (format: file:line)
        filename = location.split(":")[0] if ":" in location else location
        if filename not in findings_by_file:
            findings_by_file[filename] = []
        findings_by_file[filename].append(finding)

    # Apply filtering rules
    filtered = []
    for filename, file_findings in findings_by_file.items():
        has_pass1 = file_has_pass1.get(filename, False)

        if has_pass1:
            # Drop all Pass-2 findings for this file
            filtered.extend([f for f in file_findings if f["pass_num"] == 1])
        else:
            # Cap Pass-2 findings at 2 per file
            pass1_findings = [f for f in file_findings if f["pass_num"] == 1]
            pass2_findings = [f for f in file_findings if f["pass_num"] == 2]

            filtered.extend(pass1_findings)
            filtered.extend(pass2_findings[:2])  # Cap at 2

    return filtered


def merge_chunks(
    model_label: str, chunk_dir: Path, final_file: Path, input_hash: str | None = None
) -> bool:
    """Merge chunks mechanically into final review file. Returns True on success.

    Applies two-pass filtering: drops Pass-2 findings for files with Pass-1 findings,
    caps Pass-2 at 2 per file.
    """

    # First pass: collect all findings and track which files have Pass-1
    all_findings: list[dict] = []
    file_has_pass1: dict[str, bool] = {}
    files_reviewed = 0
    cleaned_chunks: dict[str, str] = {}

    for src in SOURCE_FILES:
        chunk = chunk_dir / f"{src}.md"
        if chunk.exists() and chunk.stat().st_size > 0:
            files_reviewed += 1
            content = _clean_chunk_content(chunk.read_text())
            cleaned_chunks[src] = content

            # Parse findings from this chunk
            findings = _parse_findings_from_chunk(content)
            all_findings.extend(findings)

            # Track if this file has Pass-1 findings
            for f in findings:
                if f["pass_num"] == 1:
                    file_has_pass1[src] = True

    # Apply two-pass filtering
    filtered_findings = _filter_findings_by_pass(all_findings, file_has_pass1)

    # Count findings by severity from filtered results
    total_findings = len(filtered_findings)
    severity_totals = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in filtered_findings:
        severity_totals[f["severity"]] += 1

    # Build frontmatter
    verdict = "passes review" if total_findings == 0 else "needs review"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")

    severity_summary = ", ".join(f"{sev}: {n}" for sev, n in severity_totals.items())

    # Build frontmatter
    output_lines = [
        "---",
        f"title: Review of SmallChat by {model_label}",
        f"date: {timestamp}",
        f"model: {model_label}",
        f"files_reviewed: {files_reviewed}",
        f"findings_count: {total_findings}",
        f"verdict: {verdict}",
    ]
    if input_hash:
        output_lines.append(f"input_hash: {input_hash}")
    output_lines.extend(
        [
            "---",
            "",
            "## Review Summary",
            "",
            f"**Model:** {model_label}",
            f"**Files reviewed:** {files_reviewed}",
            f"**Total findings:** {total_findings}",
            f"**Findings by severity:** {severity_summary}",
            "",
            "## Findings",
            "",
        ]
    )

    # Rebuild findings section from filtered findings, grouped by file
    findings_by_file: dict[str, list[str]] = {}
    for f in filtered_findings:
        location = f["location"]
        filename = location.split(":")[0] if ":" in location else location
        if filename not in findings_by_file:
            findings_by_file[filename] = []
        findings_by_file[filename].append(f["raw_block"])

    for src in SOURCE_FILES:
        if src in cleaned_chunks:
            output_lines.append(f"### {src}")
            output_lines.append("")
            if src in findings_by_file:
                output_lines.append("\n\n".join(findings_by_file[src]))
            else:
                output_lines.append("No findings.")
            output_lines.append("")

    final_file.write_text("\n".join(output_lines))

    if final_file.stat().st_size > 0:
        word_count = len(final_file.read_text().split())
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Merge complete: {word_count} words in {final_file.name}"
        )
        shutil.rmtree(chunk_dir)
        return True
    else:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Merge failed: output empty", file=sys.stderr
        )
        return False


def _should_chunk(prompt: str, profile) -> bool:
    """Budget gate: return True if prompt exceeds profile.prompt_budget_chars.

    Pure function for testing. Both arms call this to decide chunked vs single.
    """
    return len(prompt) > profile.prompt_budget_chars


def run_review_chunked(
    model_label: str,
    skill_file: Path,
    out_file: Path,
    force: bool,
) -> bool:
    """Run chunked review pipeline (per-source-file chunks + merge). Returns True on success."""
    started_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_ts = datetime.now()

    # Check checkpoint
    skip, reason = should_skip_model(model_label, "with-skill", force)
    if skip:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [skip] {model_label} with-skill: {reason}")
        elapsed = (datetime.now() - start_ts).total_seconds()
        log_model_metrics(model_label, "with-skill", started_iso, elapsed, "skip", out_file)
        record_checkpoint(model_label, "with-skill", out_file, "skip")
        return True

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [run] {model_label} with-skill (chunked)")

    # Handle interrupted merge: final file exists but chunks dir also exists
    chunk_dir = REPORT_DIR / "chunks" / model_label
    if not force and out_file.exists() and out_file.stat().st_size > 0 and chunk_dir.exists():
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: stale chunks dir found, cleaning up"
        )
        shutil.rmtree(chunk_dir)
        return True

    chunk_dir.mkdir(parents=True, exist_ok=True)

    # Timeout: use profile.review_timeout
    from torvalds_skill.profiles import get_profile

    profile = get_profile(model_label)
    chunk_timeout = profile.review_timeout

    # Check if chunks dir exists (resume from interrupted run)
    if chunk_dir.exists() and any(chunk_dir.iterdir()):
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: resuming from existing chunks dir"
        )

    # Process each source file chunk
    failed_chunks = 0
    for src in SOURCE_FILES:
        chunk_file = chunk_dir / f"{src}.md"

        # Skip if chunk already exists and non-empty
        if chunk_file.exists() and chunk_file.stat().st_size > 0:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {src} already done, skipping"
            )
            continue

        if not run_chunk_review(model_label, skill_file, src, chunk_file, chunk_timeout, force):
            failed_chunks += 1

    if failed_chunks > 0:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: {failed_chunks} chunk(s) failed, keeping chunks for retry",
            file=sys.stderr,
        )
        return False

    # Merge chunks into final output (mechanical merge, no LLM call)
    input_hash = compute_input_hash(model_label, "with-skill")
    if not merge_chunks(model_label, chunk_dir, out_file, input_hash):
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: merge failed, keeping chunks for manual recovery",
            file=sys.stderr,
        )
        return False

    elapsed = (datetime.now() - start_ts).total_seconds()
    log_model_metrics(model_label, "with-skill", started_iso, elapsed, "ok", out_file)
    record_checkpoint(model_label, "with-skill", out_file, "ok")
    return True


def run_review(model_label: str, skill_file: Path, out_file: Path, force: bool) -> bool:
    """Run with-skill or baseline review. Budget gate decides chunked vs single.

    Both arms call _should_chunk(prompt, profile). Over budget → chunked; under → single.
    """
    started_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_ts = datetime.now()

    # Check checkpoint
    skip, reason = should_skip_model(model_label, "with-skill", force)
    if skip:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [skip] {model_label} with-skill: {reason}")
        elapsed = (datetime.now() - start_ts).total_seconds()
        log_model_metrics(model_label, "with-skill", started_iso, elapsed, "skip", out_file)
        record_checkpoint(model_label, "with-skill", out_file, "skip")
        return True

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [run] {model_label} with-skill")

    prompt = build_review_prompt(skill_file, out_file)

    # Budget gate: decide chunked vs single
    from torvalds_skill.profiles import get_profile

    profile = get_profile(model_label)
    if _should_chunk(prompt, profile):
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: prompt {len(prompt)} > budget {profile.prompt_budget_chars}, using chunked pipeline"
        )
        return run_review_chunked(model_label, skill_file, out_file, force)

    timeout_sec = profile.review_timeout

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] Starting {model_label} review -> {out_file.name} (timeout {timeout_sec}s)"
    )

    for attempt in range(1, 4):
        if attempt > 1:
            backoff_multiplier = 2 ** (attempt - 1)
            jitter = random.randint(0, 30)
            retry_timeout = int(timeout_sec * backoff_multiplier + jitter)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review: retrying (attempt {attempt}, timeout {retry_timeout}s)"
            )
            out_file.unlink(missing_ok=True)
        else:
            retry_timeout = timeout_sec

        prompt_file = REPORT_DIR / f"review-{model_label}.prompt"
        prompt_file.write_text(prompt)

        exit_code, _ = run_llm_call(model_label, prompt_file, out_file, retry_timeout)
        prompt_file.unlink(missing_ok=True)

        if exit_code == 0 and out_file.exists() and out_file.stat().st_size > 0:
            duration = int((datetime.now() - start_ts).total_seconds())
            word_count = len(out_file.read_text().split())
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review done: {word_count} words"
            )
            log_metrics(model_label, "with-skill", out_file, duration, 0, chunk=None, chunked=False)
            elapsed = (datetime.now() - start_ts).total_seconds()
            log_model_metrics(model_label, "with-skill", started_iso, elapsed, "ok", out_file)
            record_checkpoint(model_label, "with-skill", out_file, "ok")
            return True

        if exit_code == 124:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review TIMED OUT after {retry_timeout}s",
                file=sys.stderr,
            )
        else:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review FAILED (exit {exit_code})",
                file=sys.stderr,
            )

    duration = int((datetime.now() - start_ts).total_seconds())
    log_metrics(model_label, "with-skill", out_file, duration, exit_code, chunk=None, chunked=False)
    elapsed = (datetime.now() - start_ts).total_seconds()
    log_model_metrics(model_label, "with-skill", started_iso, elapsed, "fail", out_file)
    record_checkpoint(model_label, "with-skill", out_file, "fail")
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review FAILED after 3 attempts",
        file=sys.stderr,
    )
    return False


def run_baseline_review(model_label: str, out_file: Path, force: bool) -> bool:
    """Run baseline review. Budget gate decides chunked vs single (symmetric with with-skill).

    Both arms call _should_chunk(prompt, profile). Over budget → chunked; under → single.
    """
    started_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_ts = datetime.now()

    # Check checkpoint
    skip, reason = should_skip_model(model_label, "baseline", force)
    if skip:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [skip] {model_label} baseline: {reason}")
        elapsed = (datetime.now() - start_ts).total_seconds()
        log_model_metrics(model_label, "baseline", started_iso, elapsed, "skip", out_file)
        record_checkpoint(model_label, "baseline", out_file, "skip")
        return True

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [run] {model_label} baseline")

    prompt = build_baseline_prompt(out_file)

    # Budget gate: decide chunked vs single (symmetric with with-skill arm)
    from torvalds_skill.profiles import get_profile

    profile = get_profile(model_label)
    if _should_chunk(prompt, profile):
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label}: prompt {len(prompt)} > budget {profile.prompt_budget_chars}, using chunked pipeline"
        )
        # Baseline chunked path: create a variant without skill_file parameter
        return run_baseline_review_chunked(model_label, out_file, force)

    timeout_sec = profile.review_timeout

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] Starting baseline {model_label} review -> {out_file.name} (timeout {timeout_sec}s)"
    )

    for attempt in range(1, 4):
        if attempt > 1:
            backoff_multiplier = 2 ** (attempt - 1)
            jitter = random.randint(0, 30)
            retry_timeout = int(timeout_sec * backoff_multiplier + jitter)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review: retrying (attempt {attempt}, timeout {retry_timeout}s)"
            )
            out_file.unlink(missing_ok=True)
        else:
            retry_timeout = timeout_sec

        prompt_file = BASELINE_DIR / f"review-baseline-{model_label}.prompt"
        prompt_file.write_text(prompt)

        exit_code, _ = run_llm_call(model_label, prompt_file, out_file, retry_timeout)
        prompt_file.unlink(missing_ok=True)

        if exit_code == 0 and out_file.exists() and out_file.stat().st_size > 0:
            duration = int((datetime.now() - start_ts).total_seconds())
            word_count = len(out_file.read_text().split())
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review done: {word_count} words"
            )
            log_metrics(model_label, "baseline", out_file, duration, 0, chunk=None, chunked=False)
            elapsed = (datetime.now() - start_ts).total_seconds()
            log_model_metrics(model_label, "baseline", started_iso, elapsed, "ok", out_file)
            record_checkpoint(model_label, "baseline", out_file, "ok")
            return True

        if exit_code == 124:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review TIMED OUT after {retry_timeout}s",
                file=sys.stderr,
            )
        else:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review FAILED (exit {exit_code})",
                file=sys.stderr,
            )

    duration = int((datetime.now() - start_ts).total_seconds())
    log_metrics(model_label, "baseline", out_file, duration, exit_code, chunk=None, chunked=False)
    elapsed = (datetime.now() - start_ts).total_seconds()
    log_model_metrics(model_label, "baseline", started_iso, elapsed, "fail", out_file)
    record_checkpoint(model_label, "baseline", out_file, "fail")
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review FAILED after 3 attempts",
        file=sys.stderr,
    )
    return False


def run_baseline_review_chunked(
    model_label: str,
    out_file: Path,
    force: bool,
) -> bool:
    """Run chunked baseline review pipeline (per-source-file chunks + merge). Returns True on success."""
    started_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_ts = datetime.now()

    # Check checkpoint
    skip, reason = should_skip_model(model_label, "baseline", force)
    if skip:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [skip] {model_label} baseline: {reason}")
        elapsed = (datetime.now() - start_ts).total_seconds()
        log_model_metrics(model_label, "baseline", started_iso, elapsed, "skip", out_file)
        record_checkpoint(model_label, "baseline", out_file, "skip")
        return True

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [run] {model_label} baseline (chunked)")

    # Handle interrupted merge: final file exists but chunks dir also exists
    chunk_dir = BASELINE_DIR / "chunks" / model_label
    if not force and out_file.exists() and out_file.stat().st_size > 0 and chunk_dir.exists():
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: stale chunks dir found, cleaning up"
        )
        shutil.rmtree(chunk_dir)
        return True

    chunk_dir.mkdir(parents=True, exist_ok=True)

    # Timeout: use profile.review_timeout
    from torvalds_skill.profiles import get_profile

    profile = get_profile(model_label)
    chunk_timeout = profile.review_timeout

    # Check if chunks dir exists (resume from interrupted run)
    if chunk_dir.exists() and any(chunk_dir.iterdir()):
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: resuming from existing chunks dir"
        )

    # Process each source file chunk
    failed_chunks = 0
    for src in SOURCE_FILES:
        chunk_file = chunk_dir / f"{src}.md"

        # Skip if chunk already exists and non-empty
        if chunk_file.exists() and chunk_file.stat().st_size > 0:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} baseline chunk {src} already done, skipping"
            )
            continue

        if not run_baseline_chunk_review(model_label, src, chunk_file, chunk_timeout, force):
            failed_chunks += 1

    if failed_chunks > 0:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: {failed_chunks} chunk(s) failed, keeping chunks for retry",
            file=sys.stderr,
        )
        return False

    # Merge chunks into final output (mechanical merge, no LLM call)
    input_hash = compute_input_hash(model_label, "baseline")
    if not merge_chunks(model_label, chunk_dir, out_file, input_hash):
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: merge failed, keeping chunks for manual recovery",
            file=sys.stderr,
        )
        return False

    elapsed = (datetime.now() - start_ts).total_seconds()
    log_model_metrics(model_label, "baseline", started_iso, elapsed, "ok", out_file)
    record_checkpoint(model_label, "baseline", out_file, "ok")
    return True


def run_baseline_chunk_review(
    model_label: str,
    source_file: str,
    chunk_file: Path,
    timeout_sec: int,
    force: bool,
) -> bool:
    """Run a single baseline chunk review with timeout + retry. Returns True on success."""
    if not force and chunk_file.exists() and chunk_file.stat().st_size > 0:
        word_count = len(chunk_file.read_text().split())
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] [skip] {model_label} baseline chunk {source_file} already exists ({word_count} words)"
        )
        return True

    chunk_dir = chunk_file.parent
    chunk_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, 4):
        if attempt > 1:
            backoff_multiplier = 2 ** (attempt - 1)
            jitter = random.randint(0, 30)
            retry_timeout = int(timeout_sec * backoff_multiplier + jitter)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} baseline chunk {source_file}: retrying (attempt {attempt}, timeout {retry_timeout}s)"
            )
            chunk_file.unlink(missing_ok=True)
        else:
            retry_timeout = timeout_sec

        prompt = build_baseline_chunk_prompt(source_file, chunk_file)
        prompt_file = chunk_dir / f"{source_file}.prompt"
        prompt_file.write_text(prompt)

        start_ts = datetime.now()
        exit_code, _ = run_llm_call(model_label, prompt_file, chunk_file, retry_timeout)
        (datetime.now() - start_ts).total_seconds()

        prompt_file.unlink(missing_ok=True)

        if exit_code == 0 and chunk_file.exists() and chunk_file.stat().st_size > 0:
            word_count = len(chunk_file.read_text().split())
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} baseline chunk {source_file} done: {word_count} words"
            )
            return True

        if exit_code == 124:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} baseline chunk {source_file} TIMED OUT after {retry_timeout}s",
                file=sys.stderr,
            )
        else:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} baseline chunk {source_file} FAILED (exit {exit_code})",
                file=sys.stderr,
            )

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} baseline chunk {source_file} FAILED after 3 attempts",
        file=sys.stderr,
    )
    return False


def build_baseline_chunk_prompt(source_file: str, chunk_file: Path) -> str:
    """Build the baseline chunk review prompt (single file, no skill)."""
    source_content = read_source_file(source_file)
    two_pass_rule = _build_two_pass_rule()

    return f"""You are a code reviewer. Review the code below — antirez/smallchat (minimal TCP chat server, ~706 LOC).

Do NOT use any tools. Do NOT read any files. Everything you need is inlined below.

== SOURCE: {source_file} ==
{source_content}

{two_pass_rule}

Review the source above finding:
- Bugs and logic errors
- Security vulnerabilities (buffer overflows, use-after-free, injection, etc.)
- Memory leaks and resource management issues
- Race conditions and concurrency problems
- Performance issues
- Code quality and maintainability concerns

For each finding use:
### [SEVERITY] Finding title
- **Type:** bug | security | memory | concurrency | performance | code-quality
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action
- **Pass:** 1 | 2

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings — not `####` or `##`
- Use `**Field:**` format (colon inside the bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

Severity: CRITICAL | HIGH | MEDIUM | LOW
Report every real bug you find. If a file is genuinely clean, say "No findings." Don't invent problems.
Write findings to: {chunk_file}
"""


def validate_review_format(file: Path, model: str) -> bool:
    """Validate review format after generation. Returns True if valid."""
    import re

    if not file.exists() or file.stat().st_size == 0:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {model}: review file empty", file=sys.stderr
        )
        return False

    content = file.read_text()
    if not re.search(r"^#{2,4}\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]", content, re.MULTILINE):
        if "no findings" not in content.lower():
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {model}: no valid severity headings found",
                file=sys.stderr,
            )
            return False
    return True


def dispatch_reviews(
    force: bool, models_filter: set[str] | None, parallel: bool
) -> tuple[int, int]:
    """Dispatch all reviews. Returns (successes, failures).

    Args:
        force: Regenerate all reviews
        models_filter: Optional subset of models to run (None = all)
        parallel: Run models in parallel (max 2 workers)
    """
    # Determine which models to run
    models_to_run = models_filter if models_filter is not None else set(MODELS.keys())

    print("Dispatching reviews (profile-based configuration)...")
    print(f"  Force mode: {int(force)} ({'regenerate all' if force else 'skip existing'})")
    print(f"  Models: {', '.join(sorted(models_to_run))}")
    print(f"  Parallel: {parallel} ({'max 2 workers' if parallel else 'sequential'})")
    print("  Budget-gate chunking: _should_chunk(prompt, profile) on both arms")
    print()

    successes = 0
    failures = 0

    # Build list of (model, mode, runner) tuples
    # Both arms use the same runner; _should_chunk decides chunked vs single
    reviews_to_run = []
    for model_label in models_to_run:
        skill_file = MODELS[model_label]

        # With-skill review - runner uses budget gate to decide chunked vs single
        out_file = REPORT_DIR / f"review-{model_label}.md"
        reviews_to_run.append((model_label, "with-skill", run_review, skill_file, out_file))

        # Baseline review
        baseline_out = BASELINE_DIR / f"review-baseline-{model_label}.md"
        reviews_to_run.append((model_label, "baseline", run_baseline_review, None, baseline_out))

    if parallel:
        # Parallel execution (max 2 workers)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for model_label, _mode, runner, skill_file, out_file in reviews_to_run:
                if skill_file is not None:
                    futures.append(
                        executor.submit(runner, model_label, skill_file, out_file, force)
                    )
                else:
                    futures.append(executor.submit(runner, model_label, out_file, force))

            for future in as_completed(futures):
                if future.result():
                    successes += 1
                else:
                    failures += 1
    else:
        # Sequential execution (default, safer)
        for model_label, _mode, runner, skill_file, out_file in reviews_to_run:
            if skill_file is not None:
                result = runner(model_label, skill_file, out_file, force)
            else:
                result = runner(model_label, out_file, force)

            if result:
                successes += 1
            else:
                failures += 1

    return successes, failures


def print_summary(successes: int, failures: int):
    """Print review summary."""
    total_reviews = successes + failures

    print()
    print(f"Reviews complete. Failures: {failures}/{total_reviews}")
    print()

    print("With-skill reviews:")
    for model_label in MODELS:
        f = REPORT_DIR / f"review-{model_label}.md"
        if f.exists() and f.stat().st_size > 0:
            word_count = len(f.read_text().split())
            print(f"  {f.name:<40} {word_count} words")
        else:
            print(f"  {f.name:<40} MISSING")

    print("Baseline reviews (no skill):")
    for model_label in MODELS:
        f = BASELINE_DIR / f"review-baseline-{model_label}.md"
        if f.exists() and f.stat().st_size > 0:
            word_count = len(f.read_text().split())
            print(f"  {f.name:<40} {word_count} words")
        else:
            print(f"  {f.name:<40} MISSING")


def generate_comparison_report():
    """Generate comparison report via build_comparison.py."""
    print()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating comparison report...")
    result = subprocess.run(
        ["python3", "report/build_comparison.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Comparison written to report/comparison.md")
    else:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: comparison generation failed",
            file=sys.stderr,
        )
        if result.stderr:
            print(result.stderr, file=sys.stderr)


def main():
    """Main entry point."""
    args = parse_args()

    # Handle --clean-logs
    if args.clean_logs:
        clean_logs()

    # Ensure directories exist
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    # Ensure target codebase is present
    ensure_target_exists()

    # Verify skill assets exist
    verify_skill_assets()

    # Parse --models filter
    models_filter = None
    if args.models:
        models_filter = set(m.strip() for m in args.models.split(",") if m.strip())
        # Validate model names
        invalid = models_filter - set(MODELS.keys())
        if invalid:
            valid_list = ", ".join(sorted(MODELS.keys()))
            print(
                f"ERROR: Invalid model(s): {', '.join(sorted(invalid))}",
                file=sys.stderr,
            )
            print(f"Valid models: {valid_list}", file=sys.stderr)
            sys.exit(2)

    # Dispatch all reviews
    successes, failures = dispatch_reviews(args.force, models_filter, args.parallel_models)

    # Print summary
    print_summary(successes, failures)

    # Determine exit code
    if failures <= 1:
        print(f"\nSuccess: {successes}/{successes + failures} reviews produced.")

        # Generate the comparison report
        generate_comparison_report()

        print()
        print("Done. Final artifacts:")
        print("  report/comparison.md")
        for model_label in MODELS:
            print(f"  report/review-{model_label}.md")
        sys.exit(0)
    else:
        print(
            f"\nWARNING: {failures} reviews failed. Check .log files in report/ for details.",
            file=sys.stderr,
        )
        print(
            "Re-run the script to retry only the missing reviews (existing outputs are skipped).",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
