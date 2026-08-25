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
  - Per-review timeout (40 min for GLM5.2, 15 min for others)
  - One automatic retry per review on failure/timeout
  - Each review is independent: one crash doesn't kill the others
  - Logs are preserved (not deleted on exit) for post-mortem
  - Exit 0 if >=5/6 reviews succeed

Prerequisites:
  - Python 3 with stdlib urllib/json
  - smallchat cloned to /tmp/smallchat (this script does it if missing)
  - skill files present at linus-torvalds-skill/SKILL.md, SKILL-GLM.md, SKILL-Mistral.md

Environment variables:
  CHUNKED_MODELS — comma-separated list of models to use chunked pipeline
                   (e.g., "gpt-oss-120b,glm5.2"). Default: all models use chunked.

Run from the repository root:
  python3 report/run_review.py              # skip existing, run missing
  python3 report/run_review.py --force      # regenerate all six
  python3 report/run_review.py --clean-logs # remove .log files and exit
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
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
}

TIMEOUTS = {
    "glm5.2": 2400,  # GLM5.2 needs longer timeout (reasoning model)
}
DEFAULT_TIMEOUT = 900


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run multi-model code review pipeline"
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
    return parser.parse_args()


def clean_logs():
    """Remove all review log files."""
    log_files = list(REPORT_DIR.glob("review-*.log"))
    for log_file in log_files:
        log_file.unlink()
    print("Cleaned review logs.")
    sys.exit(0)


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
    ]
    for skill_file in skill_files:
        if not skill_file.exists():
            print(f"Missing asset: {skill_file}", file=sys.stderr)
            sys.exit(1)


def read_source_file(source_file: str) -> str:
    """Read a source file from the target directory."""
    return (TARGET / source_file).read_text()


def build_review_prompt(skill_file: Path, out_file: Path) -> str:
    """Build the with-skill review prompt."""
    skill_content = skill_file.read_text()
    sources_block = ""
    for src in SOURCE_FILES:
        sources_block += f"== SOURCE: {src} =={read_source_file(src)}\n\n"

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

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings — not `####` or `##`
- Use `**Field:**` format (colon inside the bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

Severity levels: CRITICAL | HIGH | MEDIUM | LOW
End with a Summary: verdict, findings by severity, whether the code passes.

Rules:
- Cover ALL source files.
- Each finding maps to a specific skill trigger.
- Precedence: correctness > performance > complexity > style > API stability.
- Be concrete: cite line numbers, name functions, quote code.
- Don't invent problems. If clean on a trigger, say so.
- English.

Write the final report to: {out_file}
"""


def build_chunk_prompt(skill_file: Path, source_file: str, chunk_file: Path) -> str:
    """Build the chunk review prompt (single file)."""
    skill_content = skill_file.read_text()
    source_content = read_source_file(source_file)

    return f"""You are a code reviewer applying the Linus Torvalds reviewer skill.

Do NOT use any tools. Do NOT read any files. Everything you need is inlined below.

== SKILL ==
{skill_content}

== SOURCE: {source_file} ==
{source_content}

Review the source above using the skill rules. For each finding use:
### [SEVERITY] Finding title
- **Type:** invariant-true | invariant-false | precedence | guideline
- **Trigger:** (the trigger from the skill that fired)
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action

**Format rules:**
- Use exactly `###` (three hash marks) for severity headings — not `####` or `##`
- Use `**Field:**` format (colon inside the bold markers) for all fields
- Severity values are: CRITICAL, HIGH, MEDIUM, LOW (uppercase only)

Severity: CRITICAL | HIGH | MEDIUM | LOW
If clean, say "No findings." Don't invent problems.
Write findings to: {chunk_file}
"""


def build_baseline_prompt(out_file: Path) -> str:
    """Build the baseline (no-skill) review prompt."""
    sources_block = ""
    for src in SOURCE_FILES:
        sources_block += f"== SOURCE: {src} =={read_source_file(src)}\n\n"

    return f"""You are a code reviewer. Review the codebase below — antirez/smallchat (minimal TCP chat server, ~706 LOC).

Do NOT use any tools. Do NOT read any files. Everything you need is inlined below.

{sources_block}

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


def run_llm_call(model_label: str, prompt_file: Path, out_file: Path, timeout_sec: int) -> tuple[int, str]:
    """Run the LLM review subprocess. Returns (exit_code, output)."""
    try:
        result = subprocess.run(
            ["python3", "report/llm_review.py", "--model", model_label,
             "--prompt-file", str(prompt_file), "--out", str(out_file),
             "--timeout", str(timeout_sec)],
            timeout=timeout_sec,
            capture_output=True,
            text=True,
        )
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
    """Log metrics to metrics.jsonl."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    word_count = 0
    findings_count = 0

    if out_file.exists() and out_file.stat().st_size > 0:
        word_count = len(out_file.read_text().split())
        import re
        findings_count = len(re.findall(r'^#{2,4}\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]', out_file.read_text(), re.MULTILINE))

    metrics = {
        "ts": ts,
        "model": model,
        "type": review_type,
        "chunk": chunk,
        "duration_sec": duration_sec,
        "exit_code": exit_code,
        "word_count": word_count,
        "findings_count": findings_count,
        "chunked": chunked,
    }

    metrics_file = REPORT_DIR / "metrics.jsonl"
    with open(metrics_file, "a") as f:
        f.write(json.dumps(metrics) + "\n")


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
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} already exists ({word_count} words), skipping")
        return True

    chunk_dir = chunk_file.parent
    chunk_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, 4):
        if attempt > 1:
            backoff_multiplier = 2 ** (attempt - 1)
            jitter = random.randint(0, 30)
            retry_timeout = int(timeout_sec * backoff_multiplier + jitter)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file}: retrying (attempt {attempt}, timeout {retry_timeout}s)")
            chunk_file.unlink(missing_ok=True)
        else:
            retry_timeout = timeout_sec

        prompt = build_chunk_prompt(skill_file, source_file, chunk_file)
        prompt_file = chunk_dir / f"{source_file}.prompt"
        prompt_file.write_text(prompt)

        start_ts = datetime.now()
        exit_code, _ = run_llm_call(model_label, prompt_file, chunk_file, retry_timeout)
        duration = (datetime.now() - start_ts).total_seconds()

        prompt_file.unlink(missing_ok=True)

        if exit_code == 0 and chunk_file.exists() and chunk_file.stat().st_size > 0:
            word_count = len(chunk_file.read_text().split())
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} done: {word_count} words")
            return True

        if exit_code == 124:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} TIMED OUT after {retry_timeout}s", file=sys.stderr)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} FAILED (exit {exit_code})", file=sys.stderr)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {source_file} FAILED after 3 attempts", file=sys.stderr)
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
            text = stripped[end + 4:]

    # Drop literal prompt-template headings like '### [SEVERITY] Finding title'
    text = re.sub(r"^#{3,4}\s+\[SEVERITY\]\s+Finding title\s*$", "", text, flags=re.MULTILINE)
    return text.strip("\n")


def merge_chunks(model_label: str, chunk_dir: Path, final_file: Path) -> bool:
    """Merge chunks mechanically into final review file. Returns True on success."""
    total_findings = 0
    files_reviewed = 0
    severity_totals = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    import re
    # Tolerant heading match: 3-4 hashes, brackets optional.
    # Models emit both '### [CRITICAL] Title' and '### CRITICAL Title'.
    sev_re = re.compile(r"^#{3,4}\s+\[?(CRITICAL|HIGH|MEDIUM|LOW)\]?(?:\s|$)", re.MULTILINE)

    cleaned_chunks = {}
    for src in SOURCE_FILES:
        chunk = chunk_dir / f"{src}.md"
        if chunk.exists() and chunk.stat().st_size > 0:
            files_reviewed += 1
            content = _clean_chunk_content(chunk.read_text())
            cleaned_chunks[src] = content
            for sev in sev_re.findall(content):
                total_findings += 1
                severity_totals[sev] += 1

    verdict = "passes review" if total_findings == 0 else "needs review"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

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

    # Concatenate all chunk findings
    for src in SOURCE_FILES:
        if src in cleaned_chunks:
            output_lines.append(f"### {src}")
            output_lines.append("")
            output_lines.append(cleaned_chunks[src])
            output_lines.append("")

    final_file.write_text("\n".join(output_lines))

    if final_file.stat().st_size > 0:
        word_count = len(final_file.read_text().split())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Merge complete: {word_count} words in {final_file.name}")
        shutil.rmtree(chunk_dir)
        return True
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Merge failed: output empty", file=sys.stderr)
        return False


def run_review_chunked(
    model_label: str,
    skill_file: Path,
    out_file: Path,
    force: bool,
) -> bool:
    """Run chunked review pipeline. Returns True on success."""
    # Skip if final output already exists (unless --force).
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        word_count = len(out_file.read_text().split())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review already exists ({word_count} words), skipping")
        return True

    # Handle interrupted merge: final file exists but chunks dir also exists
    chunk_dir = REPORT_DIR / "chunks" / model_label
    if not force and out_file.exists() and out_file.stat().st_size > 0 and chunk_dir.exists():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: stale chunks dir found, cleaning up")
        shutil.rmtree(chunk_dir)
        return True

    chunk_dir.mkdir(parents=True, exist_ok=True)

    # Timeout: use per-model override from TIMEOUTS dict, or fall back to default
    chunk_timeout = TIMEOUTS.get(model_label, DEFAULT_TIMEOUT)

    # Check if chunks dir exists (resume from interrupted run)
    if chunk_dir.exists() and any(chunk_dir.iterdir()):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: resuming from existing chunks dir")

    # Process each source file chunk
    failed_chunks = 0
    for src in SOURCE_FILES:
        chunk_file = chunk_dir / f"{src}.md"

        # Skip if chunk already exists and non-empty
        if chunk_file.exists() and chunk_file.stat().st_size > 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} chunk {src} already done, skipping")
            continue

        if not run_chunk_review(model_label, skill_file, src, chunk_file, chunk_timeout, force):
            failed_chunks += 1

    if failed_chunks > 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: {failed_chunks} chunk(s) failed, keeping chunks for retry", file=sys.stderr)
        return False

    # Merge chunks into final output (mechanical merge, no LLM call)
    if not merge_chunks(model_label, chunk_dir, out_file):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label}: merge failed, keeping chunks for manual recovery", file=sys.stderr)
        return False

    return True


def run_review(model_label: str, skill_file: Path, out_file: Path, force: bool) -> bool:
    """Run a single with-skill review with timeout + retry. Returns True on success."""
    # Skip if already done (unless --force).
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        word_count = len(out_file.read_text().split())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review already exists ({word_count} words), skipping")
        return True

    prompt = build_review_prompt(skill_file, out_file)
    timeout_sec = TIMEOUTS.get(model_label, DEFAULT_TIMEOUT)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting {model_label} review -> {out_file.name} (timeout {timeout_sec}s)")

    start_ts = datetime.now()

    for attempt in range(1, 4):
        if attempt > 1:
            backoff_multiplier = 2 ** (attempt - 1)
            jitter = random.randint(0, 30)
            retry_timeout = int(timeout_sec * backoff_multiplier + jitter)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review: retrying (attempt {attempt}, timeout {retry_timeout}s)")
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review done: {word_count} words")
            log_metrics(model_label, "with-skill", out_file, duration, 0, chunk=None, chunked=False)
            return True

        if exit_code == 124:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review TIMED OUT after {retry_timeout}s", file=sys.stderr)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review FAILED (exit {exit_code})", file=sys.stderr)

    duration = int((datetime.now() - start_ts).total_seconds())
    log_metrics(model_label, "with-skill", out_file, duration, exit_code, chunk=None, chunked=False)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {model_label} review FAILED after 3 attempts", file=sys.stderr)
    return False


def run_baseline_review(model_label: str, out_file: Path, force: bool) -> bool:
    """Run a single baseline review with timeout + retry. Returns True on success."""
    # Skip if already done (unless --force).
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        word_count = len(out_file.read_text().split())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review already exists ({word_count} words), skipping")
        return True

    prompt = build_baseline_prompt(out_file)
    timeout_sec = TIMEOUTS.get(model_label, DEFAULT_TIMEOUT)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting baseline {model_label} review -> {out_file.name} (timeout {timeout_sec}s)")

    start_ts = datetime.now()

    for attempt in range(1, 4):
        if attempt > 1:
            backoff_multiplier = 2 ** (attempt - 1)
            jitter = random.randint(0, 30)
            retry_timeout = int(timeout_sec * backoff_multiplier + jitter)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review: retrying (attempt {attempt}, timeout {retry_timeout}s)")
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review done: {word_count} words")
            log_metrics(model_label, "baseline", out_file, duration, 0, chunk=None, chunked=False)
            return True

        if exit_code == 124:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review TIMED OUT after {retry_timeout}s", file=sys.stderr)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review FAILED (exit {exit_code})", file=sys.stderr)

    duration = int((datetime.now() - start_ts).total_seconds())
    log_metrics(model_label, "baseline", out_file, duration, exit_code, chunk=None, chunked=False)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] baseline {model_label} review FAILED after 3 attempts", file=sys.stderr)
    return False


def validate_review_format(file: Path, model: str) -> bool:
    """Validate review format after generation. Returns True if valid."""
    import re

    if not file.exists() or file.stat().st_size == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {model}: review file empty", file=sys.stderr)
        return False

    content = file.read_text()
    if not re.search(r'^#{2,4}\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]', content, re.MULTILINE):
        if "no findings" not in content.lower():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {model}: no valid severity headings found", file=sys.stderr)
            return False
    return True


def dispatch_reviews(force: bool, chunked_models: set[str]) -> tuple[int, int]:
    """Dispatch all reviews concurrently. Returns (successes, failures)."""
    print("Dispatching parallel reviews (data-driven model configuration)...")
    print(f"  Force mode: {int(force)} ({'regenerate all' if force else 'skip existing'})")
    print(f"  Models: {', '.join(MODELS.keys())}")
    print(f"  Chunked models: {', '.join(chunked_models) if chunked_models else 'none'}")
    print()

    successes = 0
    failures = 0

    with ThreadPoolExecutor(max_workers=len(MODELS) * 2) as executor:
        futures = []

        # Dispatch with-skill reviews
        for model_label, skill_file in MODELS.items():
            out_file = REPORT_DIR / f"review-{model_label}.md"

            if model_label in chunked_models:
                futures.append(executor.submit(run_review_chunked, model_label, skill_file, out_file, force))
            else:
                futures.append(executor.submit(run_review, model_label, skill_file, out_file, force))

        # Dispatch baseline reviews
        for model_label in MODELS:
            out_file = BASELINE_DIR / f"review-baseline-{model_label}.md"
            futures.append(executor.submit(run_baseline_review, model_label, out_file, force))

        # Wait for all reviews
        for future in as_completed(futures):
            if future.result():
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
        print(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: comparison generation failed", file=sys.stderr)
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

    # Get chunked models from environment
    chunked_models_str = os.environ.get("CHUNKED_MODELS", "")
    chunked_models = set(m.strip() for m in chunked_models_str.split(",") if m.strip())

    # Dispatch all reviews concurrently
    successes, failures = dispatch_reviews(args.force, chunked_models)

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
        print(f"\nWARNING: {failures} reviews failed. Check .log files in report/ for details.", file=sys.stderr)
        print("Re-run the script to retry only the missing reviews (existing outputs are skipped).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()