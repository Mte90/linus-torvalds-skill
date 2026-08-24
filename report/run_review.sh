#!/usr/bin/env bash
# Replicate the three-model Torvalds review of antirez/smallchat + baseline comparison.
#
# Produces, in report/:
#   With-skill reviews:
#     review-gpt-oss-120b.md
#     review-glm5.2.md
#     review-mistral.md
#   Baseline reviews (no skill) in report/baseline/:
#     baseline/review-baseline-gpt-oss-120b.md
#     baseline/review-baseline-glm5.2.md
#     baseline/review-baseline-mistral.md
#
# Crash-proof features:
#   - Skips reviews whose output already exists (use --force to override)
#   - Per-review timeout (40 min for GLM5.2, 15 min for others)
#   - One automatic retry per review on failure/timeout
#   - Each review is independent: one crash doesn't kill the others
#   - Logs are preserved (not deleted on exit) for post-mortem
#   - Exit 0 if >=5/6 reviews succeed
#
# Prerequisites:
#   - opencode agent CLI available as `opencode` on PATH
#   - smallchat cloned to /tmp/smallchat (this script does it if missing)
#   - skill files present at linus-torvalds-skill/SKILL.md, SKILL-GLM.md, SKILL-Mistral.md
#
# Environment variables:
#   CHUNKED_MODELS — comma-separated list of models to use chunked pipeline
#                    (e.g., "gpt-oss-120b,glm5.2"). Default: all models use chunked.

#
# Run from the repository root:
#   bash report/run_review.sh              # skip existing, run missing
#   bash report/run_review.sh --force      # regenerate all six
#   bash report/run_review.sh --clean-logs # remove .log files and exit
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="/tmp/smallchat"
REPORT_DIR="$ROOT/report"
SKILL_DIR="$ROOT/linus-torvalds-skill"
BASELINE_DIR="$REPORT_DIR/baseline"

CHUNKED_MODELS="${CHUNKED_MODELS:-}"
FORCE=0
CLEAN_LOGS=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --clean-logs) CLEAN_LOGS=1 ;;
  esac
done

if [ "$CLEAN_LOGS" -eq 1 ]; then
  rm -f "$REPORT_DIR"/review-*.log
  echo "Cleaned review logs."
  exit 0
fi

mkdir -p "$REPORT_DIR"
mkdir -p "$BASELINE_DIR"

# 1. Ensure the target codebase is present.
if [ ! -d "$TARGET" ]; then
  echo "Cloning antirez/smallchat to $TARGET..."
  git clone --depth 1 https://github.com/antirez/smallchat "$TARGET"
fi

# 2. Verify skill assets exist.
for f in \
  "$SKILL_DIR/SKILL.md" \
  "$SKILL_DIR/SKILL-GLM.md" \
  "$SKILL_DIR/SKILL-Mistral.md"; do
  if [ ! -f "$f" ]; then
    echo "Missing asset: $f" >&2
    exit 1
  fi
done

# 3. Shared review prompt body. Each model gets its own skill + output.
review_prompt() {
  local skill_file="$1"
  local out_file="$2"
  cat <<EOF
You are a code reviewer applying the Linus Torvalds reviewer skill to a real codebase.

Codebase to review: /tmp/smallchat/ — antirez/smallchat (minimal TCP chat server, ~706 LOC).
Source files: smallchat-server.c, smallchat-client.c, chatlib.c, chatlib.h, Makefile.

Skill file to apply: $skill_file — read it fully and apply its rules (triggers, precedence, definitions, anti-patterns).

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

Severity levels: CRITICAL | HIGH | MEDIUM | LOW
End with a Summary: verdict, findings by severity, whether the code passes.

Rules:
- Cover ALL source files.
- Each finding maps to a specific skill trigger.
- Precedence: correctness > performance > complexity > style > API stability.
- Be concrete: cite line numbers, name functions, quote code.
- Don't invent problems. If clean on a trigger, say so.
- English.

Read all source files first, then the skill, then write the report.
Write the final report to: $out_file
EOF
}

# 4. Run a single with-skill review with timeout + retry.

# Source files to review
SOURCE_FILES=("smallchat-server.c" "smallchat-client.c" "chatlib.c" "chatlib.h" "Makefile")

# Run a single chunk review (one file) with timeout + retry.
run_chunk_review() {
  local model_label="$1"
  local skill_file="$2"
  local source_file="$3"
  local chunk_file="$4"
  local timeout_sec="$5"

  if [ -s "$chunk_file" ]; then
    echo "[$(date +%H:%M:%S)] $model_label chunk $(basename "$source_file") already exists ($(wc -w < "$chunk_file") words), skipping"
    return 0
  fi

  local prompt
  prompt=$(cat <<EOF
You are a code reviewer applying the Linus Torvalds reviewer skill.

Skill file: $skill_file — read it fully and apply its rules.

Review ONLY this file: $source_file from /tmp/smallchat/

For each finding use:
### [SEVERITY] Finding title
- **Type:** invariant-true | invariant-false | precedence | guideline
- **Trigger:** (the trigger from the skill that fired)
- **Location:** file:line
- **Issue:** what's wrong
- **Fix:** concrete action

Severity: CRITICAL | HIGH | MEDIUM | LOW
If clean, say "No findings." Don't invent problems.
English.
Read the skill and the source file, then write findings.
Write findings to: $chunk_file
EOF
)

  echo "[$(date +%H:%M:%S)] Starting $model_label chunk $(basename "$source_file") (timeout ${timeout_sec}s)"

  local attempt
  for attempt in 1 2; do
    if [ "$attempt" -gt 1 ]; then
      echo "[$(date +%H:%M:%S)] $model_label chunk $(basename "$source_file"): retrying (attempt 2)"
      rm -f "$chunk_file"
    fi

    local start_ts
    start_ts=$(date +%s)

    if timeout "${timeout_sec}" opencode run -m "regolo-ai/$model_label" "$prompt" > "$chunk_file.log" 2>&1; then
      if [ ! -s "$chunk_file" ] || [ "$(stat -c %Y "$chunk_file" 2>/dev/null || echo 0)" -lt "$start_ts" ]; then
        awk '/^---$/{found=1} found{print}' "$chunk_file.log" > "$chunk_file"
      fi

      if [ -s "$chunk_file" ]; then
        echo "[$(date +%H:%M:%S)] $model_label chunk $(basename "$source_file") done: $(wc -w < "$chunk_file") words"
        rm -f "$chunk_file.log"
        return 0
      fi
      echo "[$(date +%H:%M:%S)] $model_label chunk $(basename "$source_file"): opencode exited OK but output empty" >&2
    else
      local exit_code=$?
      if [ "$exit_code" -eq 124 ]; then
        echo "[$(date +%H:%M:%S)] $model_label chunk $(basename "$source_file") TIMED OUT after ${timeout_sec}s" >&2
      else
        echo "[$(date +%H:%M:%S)] $model_label chunk $(basename "$source_file") FAILED (exit $exit_code)" >&2
      fi
    fi
  done

  echo "[$(date +%H:%M:%S)] $model_label chunk $(basename "$source_file") FAILED after 2 attempts" >&2
  return 1
}

# Generate summary from all chunk findings.
run_summary_review() {
  local model_label="$1"
  local skill_file="$2"
  local chunk_dir="$3"
  local summary_file="$4"
  local timeout_sec="$5"

  if [ -s "$summary_file" ]; then
    echo "[$(date +%H:%M:%S)] $model_label summary already exists ($(wc -w < "$summary_file") words), skipping"
    return 0
  fi

  # Gather chunk contents
  local chunks_content=""
  for src in "${SOURCE_FILES[@]}"; do
    local chunk="$chunk_dir/${src}.md"
    if [ -f "$chunk" ]; then
      chunks_content+="\n--- Content of $src ---\n"
      chunks_content+="$(cat "$chunk")"
    fi
  done

  local prompt
  prompt=$(cat <<EOF
You are a code reviewer applying the Linus Torvalds reviewer skill.

Skill file: $skill_file — read it fully and apply its rules.

Below are the per-file findings from reviewing /tmp/smallchat/. Synthesize them into a cohesive summary.

$chunks_content

Produce a summary with:
1. YAML frontmatter (title, date, model, files_reviewed, findings_count, verdict)
2. Persona Narrative (2-3 paragraphs: how does the skill feel in practice?)
3. Technical Assessment (coverage, accuracy, severity calibration, precedence adherence)
4. Strengths (3-5 bullets)
5. Weaknesses (3-5 bullets)
6. Verdict (1-2 sentences: production-ready?)

English.
Write the summary to: $summary_file
EOF
)

  echo "[$(date +%H:%M:%S)] Starting $model_label summary (timeout ${timeout_sec}s)"

  local attempt
  for attempt in 1 2; do
    if [ "$attempt" -gt 1 ]; then
      echo "[$(date +%H:%M:%S)] $model_label summary: retrying (attempt 2)"
      rm -f "$summary_file"
    fi

    local start_ts
    start_ts=$(date +%s)

    if timeout "${timeout_sec}" opencode run -m "regolo-ai/$model_label" "$prompt" > "$summary_file.log" 2>&1; then
      if [ ! -s "$summary_file" ] || [ "$(stat -c %Y "$summary_file" 2>/dev/null || echo 0)" -lt "$start_ts" ]; then
        awk '/^---$/{found=1} found{print}' "$summary_file.log" > "$summary_file"
      fi

      if [ -s "$summary_file" ]; then
        echo "[$(date +%H:%M:%S)] $model_label summary done: $(wc -w < "$summary_file") words"
        rm -f "$summary_file.log"
        return 0
      fi
      echo "[$(date +%H:%M:%S)] $model_label summary: opencode exited OK but output empty" >&2
    else
      local exit_code=$?
      if [ "$exit_code" -eq 124 ]; then
        echo "[$(date +%H:%M:%S)] $model_label summary TIMED OUT after ${timeout_sec}s" >&2
      else
        echo "[$(date +%H:%M:%S)] $model_label summary FAILED (exit $exit_code)" >&2
      fi
    fi
  done

  echo "[$(date +%H:%M:%S)] $model_label summary FAILED after 2 attempts" >&2
  return 1
}

# Merge chunks + summary into final review file.
merge_chunks() {
  local model_label="$1"
  local chunk_dir="$2"
  local final_file="$3"

  local summary="$chunk_dir/_summary.md"
  if [ ! -s "$summary" ]; then
    echo "[$(date +%H:%M:%S)] Merge failed: summary missing or empty" >&2
    return 1
  fi

  # Extract frontmatter and narrative sections from summary (up to ## Findings or end)
  local in_findings=0
  local summary_body=""
  while IFS= read -r line; do
    if [[ "$line" =~ ^##\ Findings ]]; then
      in_findings=1
      continue
    fi
    if [ "$in_findings" -eq 0 ]; then
      summary_body+="$line\n"
    fi
  done < "$summary"

  # Write final file: summary body + findings section
  {
    printf '%s' "$summary_body"
    printf '\n## Findings\n\n'
    for src in "${SOURCE_FILES[@]}"; do
      local chunk="$chunk_dir/${src}.md"
      if [ -f "$chunk" ] && [ -s "$chunk" ]; then
        printf '### %s\n\n' "$src"
        cat "$chunk"
        printf '\n'
      fi
    done
  } > "$final_file"

  if [ -s "$final_file" ]; then
    echo "[$(date +%H:%M:%S)] Merge complete: $(wc -w < "$final_file") words in $(basename "$final_file")"
    rm -rf "$chunk_dir"
    return 0
  else
    echo "[$(date +%H:%M:%S)] Merge failed: output empty" >&2
    return 1
  fi
}

# Run a single with-skill review with chunked pipeline + resume support.
run_review_chunked() {
  local model_label="$1"
  local skill_file="$2"
  local out_file="$3"

  # Skip if final output already exists (unless --force).
  if [ "$FORCE" -eq 0 ] && [ -s "$out_file" ]; then
    echo "[$(date +%H:%M:%S)] $model_label review already exists ($(wc -w < "$out_file") words), skipping"
    return 0
  fi

  # Handle interrupted merge: final file exists but chunks dir also exists
  if [ "$FORCE" -eq 0 ] && [ -s "$out_file" ] && [ -d "$REPORT_DIR/chunks/$model_label" ]; then
    echo "[$(date +%H:%M:%S)] $model_label: stale chunks dir found, cleaning up"
    rm -rf "$REPORT_DIR/chunks/$model_label"
    return 0
  fi

  local chunk_dir="$REPORT_DIR/chunks/$model_label"
  mkdir -p "$chunk_dir"

  # Timeout per chunk: 2400s for GLM5.2 (8K-word skill + reasoning latency), 600s for others
  local chunk_timeout=600
  if [ "$model_label" = "glm5.2" ]; then
    chunk_timeout=2400
  fi

  # Check if chunks dir exists (resume from interrupted run)
  if [ -d "$chunk_dir" ]; then
    echo "[$(date +%H:%M:%S)] $model_label: resuming from existing chunks dir"
  fi

  # Process each source file chunk
  local failed_chunks=0
  for src in "${SOURCE_FILES[@]}"; do
    local chunk_file="$chunk_dir/${src}.md"

    # Skip if chunk already exists and non-empty
    if [ -s "$chunk_file" ]; then
      echo "[$(date +%H:%M:%S)] $model_label chunk $(basename "$src") already done, skipping"
      continue
    fi

    if ! run_chunk_review "$model_label" "$skill_file" "$src" "$chunk_file" "$chunk_timeout"; then
      failed_chunks=$((failed_chunks+1))
    fi
  done

  if [ "$failed_chunks" -gt 0 ]; then
    echo "[$(date +%H:%M:%S)] $model_label: $failed_chunks chunk(s) failed, keeping chunks for retry"
    return 1
  fi

  # Generate summary
  local summary_file="$chunk_dir/_summary.md"
  if ! run_summary_review "$model_label" "$skill_file" "$chunk_dir" "$summary_file" "$chunk_timeout"; then
    echo "[$(date +%H:%M:%S)] $model_label: summary failed, keeping chunks for retry"
    return 1
  fi

  # Merge chunks into final output
  if ! merge_chunks "$model_label" "$chunk_dir" "$out_file"; then
    echo "[$(date +%H:%M:%S)] $model_label: merge failed, keeping chunks for manual recovery"
    return 1
  fi

  return 0
}

run_review() {
  local model_label="$1"
  local skill_file="$2"
  local out_file="$3"

  # Skip if already done (unless --force).
  if [ "$FORCE" -eq 0 ] && [ -s "$out_file" ]; then
    echo "[$(date +%H:%M:%S)] $model_label review already exists ($(wc -w < "$out_file") words), skipping"
    return 0
  fi

  local prompt
  prompt="$(review_prompt "$skill_file" "$out_file")"

  # Timeout: 40 min for GLM5.2 (long reasoning latency), 15 min for others.
  local timeout_sec=900
  if [ "$model_label" = "glm5.2" ]; then
    timeout_sec=2400
  fi

  echo "[$(date +%H:%M:%S)] Starting $model_label review -> $(basename "$out_file") (timeout ${timeout_sec}s)"

  local start_ts
  start_ts=$(date +%s)

  local attempt
  local exit_code=0
  for attempt in 1 2; do
    if [ "$attempt" -gt 1 ]; then
      echo "[$(date +%H:%M:%S)] $model_label review: retrying (attempt 2)"
      rm -f "$out_file"
    fi

    if timeout "${timeout_sec}" opencode run -m "regolo-ai/$model_label" "$prompt" > "$REPORT_DIR/review-$model_label.log" 2>&1; then
      # Extract report from log if agent didn't write the file itself.
      if [ ! -s "$out_file" ] || [ "$(stat -c %Y "$out_file" 2>/dev/null || echo 0)" -lt "$start_ts" ]; then
        awk '/^---$/{found=1} found{print}' "$REPORT_DIR/review-$model_label.log" > "$out_file"
      fi

      if [ -s "$out_file" ]; then
        local end_ts
        end_ts=$(date +%s)
        local duration=$((end_ts - start_ts))
        echo "[$(date +%H:%M:%S)] $model_label review done: $(wc -w < "$out_file") words"
        log_metrics "$model_label" "with-skill" "$out_file" "$duration" 0 "" "false"
        return 0
      fi
      echo "[$(date +%H:%M:%S)] $model_label review: opencode exited OK but output empty" >&2
      exit_code=1
    else
      exit_code=$?
      if [ "$exit_code" -eq 124 ]; then
        echo "[$(date +%H:%M:%S)] $model_label review TIMED OUT after ${timeout_sec}s" >&2
      else
        echo "[$(date +%H:%M:%S)] $model_label review FAILED (exit $exit_code)" >&2
      fi
    fi
  done

  local end_ts
  end_ts=$(date +%s)
  local duration=$((end_ts - start_ts))
  log_metrics "$model_label" "with-skill" "$out_file" "$duration" "$exit_code" "" "false"
  echo "[$(date +%H:%M:%S)] $model_label review FAILED after 2 attempts" >&2
  return 1
}

# Baseline review prompt (no skill). Neutral code reviewer.
baseline_prompt() {
  local out_file="$1"
  cat <<EOF
You are a code reviewer. Review the codebase at /tmp/smallchat/ — antirez/smallchat (minimal TCP chat server, ~706 LOC).

Source files: smallchat-server.c, smallchat-client.c, chatlib.c, chatlib.h, Makefile.

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

Severity levels: CRITICAL | HIGH | MEDIUM | LOW

End with a Summary: overall assessment, findings by severity, whether the code is production-ready.

Rules:
- Cover ALL source files.
- Be concrete: cite line numbers, name functions, quote code.
- Don't invent problems. If clean in an area, say so.
- Use your own judgment and expertise — no external skill file to follow.
- English.

Read all source files carefully, then write the report.
Write the final report to: $out_file
EOF
}

# Run a single baseline review with timeout + retry.
run_baseline_review() {
  local model_label="$1"
  local out_file="$2"

  # Skip if already done (unless --force).
  if [ "$FORCE" -eq 0 ] && [ -s "$out_file" ]; then
    echo "[$(date +%H:%M:%S)] baseline $model_label review already exists ($(wc -w < "$out_file") words), skipping"
    return 0
  fi

  local prompt
  prompt="$(baseline_prompt "$out_file")"

  # Timeout: 40 min for GLM5.2, 15 min for others.
  local timeout_sec=900
  if [ "$model_label" = "glm5.2" ]; then
    timeout_sec=2400
  fi

  echo "[$(date +%H:%M:%S)] Starting baseline $model_label review -> $(basename "$out_file") (timeout ${timeout_sec}s)"

  local start_ts
  start_ts=$(date +%s)

  local attempt
  local exit_code=0
  for attempt in 1 2; do
    if [ "$attempt" -gt 1 ]; then
      echo "[$(date +%H:%M:%S)] baseline $model_label review: retrying (attempt 2)"
      rm -f "$out_file"
    fi

    if timeout "${timeout_sec}" opencode run -m "regolo-ai/$model_label" "$prompt" > "$BASELINE_DIR/review-baseline-$model_label.log" 2>&1; then
      # Extract report from log if agent didn't write the file.
      if [ ! -s "$out_file" ] || [ "$(stat -c %Y "$out_file" 2>/dev/null || echo 0)" -lt "$start_ts" ]; then
        awk '/^---$/{found=1} found{print}' "$BASELINE_DIR/review-baseline-$model_label.log" > "$out_file"
      fi

      if [ -s "$out_file" ]; then
        local end_ts
        end_ts=$(date +%s)
        local duration=$((end_ts - start_ts))
        echo "[$(date +%H:%M:%S)] baseline $model_label review done: $(wc -w < "$out_file") words"
        log_metrics "$model_label" "baseline" "$out_file" "$duration" 0 "" "false"
        return 0
      fi
      echo "[$(date +%H:%M:%S)] baseline $model_label review: opencode exited OK but output empty" >&2
      exit_code=1
    else
      exit_code=$?
      if [ "$exit_code" -eq 124 ]; then
        echo "[$(date +%H:%M:%S)] baseline $model_label review TIMED OUT after ${timeout_sec}s" >&2
      else
        echo "[$(date +%H:%M:%S)] baseline $model_label review FAILED (exit $exit_code)" >&2
      fi
    fi
  done

  local end_ts
  end_ts=$(date +%s)
  local duration=$((end_ts - start_ts))
  log_metrics "$model_label" "baseline" "$out_file" "$duration" "$exit_code" "" "false"
  echo "[$(date +%H:%M:%S)] baseline $model_label review FAILED after 2 attempts" >&2
  return 1
}

export -f review_prompt run_review baseline_prompt run_baseline_review run_chunk_review run_summary_review merge_chunks run_review_chunked

# Validate review format after generation
validate_review_format() {
  local file="$1"
  local model="$2"
  if [ ! -s "$file" ]; then
    echo "[$(date +%H:%M:%S)] $model: review file empty" >&2
    return 1
  fi
  if ! grep -qE '^#{2,4}\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]' "$file"; then
    if ! grep -qi "no findings" "$file"; then
      echo "[$(date +%H:%M:%S)] $model: no valid severity headings found" >&2
      return 1
    fi
  fi
  return 0
}

# Log metrics to metrics.jsonl after each review
log_metrics() {
  local model="$1"
  local review_type="$2"
  local out_file="$3"
  local duration_sec="$4"
  local exit_code="$5"
  local chunk="$6"
  local chunked="$7"

  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local word_count=0
  local findings_count=0

  if [ -s "$out_file" ]; then
    word_count=$(wc -w < "$out_file")
    findings_count=$(grep -cE '^#{2,4}\s+\[(CRITICAL|HIGH|MEDIUM|LOW)\]' "$out_file" || true)
  fi

  local chunk_json="null"
  if [ -n "$chunk" ]; then
    chunk_json="\"$chunk\""
  fi

  printf '{"ts":"%s","model":"%s","type":"%s","chunk":%s,"duration_sec":%d,"exit_code":%d,"word_count":%d,"findings_count":%d,"chunked":%s}\n' \
    "$ts" "$model" "$review_type" "$chunk_json" "$duration_sec" "$exit_code" "$word_count" "$findings_count" "$chunked" >> "$REPORT_DIR/metrics.jsonl"
}

# 5. Dispatch all six reviews concurrently (3 with-skill + 3 baseline).
echo "Dispatching six parallel reviews (3 with-skill, 3 baseline)..."
echo "  Force mode: $FORCE (0=skip existing, 1=regenerate all)"
echo ""

# With-skill reviews — use chunked if model is in CHUNKED_MODELS
if [[ ",${CHUNKED_MODELS}," == *",gpt-oss-120b,"* ]]; then
  run_review_chunked "gpt-oss-120b" "$SKILL_DIR/SKILL.md" "$REPORT_DIR/review-gpt-oss-120b.md" &
else
  run_review "gpt-oss-120b" "$SKILL_DIR/SKILL.md" "$REPORT_DIR/review-gpt-oss-120b.md" &
fi
PID_GPT=$!
if [[ ",${CHUNKED_MODELS}," == *",glm5.2,"* ]]; then
  run_review_chunked "glm5.2" "$SKILL_DIR/SKILL-GLM.md" "$REPORT_DIR/review-glm5.2.md" &
else
  run_review "glm5.2" "$SKILL_DIR/SKILL-GLM.md" "$REPORT_DIR/review-glm5.2.md" &
fi
PID_GLM=$!
if [[ ",${CHUNKED_MODELS}," == *",mistral-small-4-119b,"* ]]; then
  run_review_chunked "mistral-small-4-119b" "$SKILL_DIR/SKILL-Mistral.md" "$REPORT_DIR/review-mistral.md" &
else
  run_review "mistral-small-4-119b" "$SKILL_DIR/SKILL-Mistral.md" "$REPORT_DIR/review-mistral.md" &
fi
PID_MIS=$!
# Baseline reviews (no skill)
run_baseline_review "gpt-oss-120b" "$BASELINE_DIR/review-baseline-gpt-oss-120b.md" &
PID_GPT_BASE=$!
run_baseline_review "glm5.2" "$BASELINE_DIR/review-baseline-glm5.2.md" &
PID_GLM_BASE=$!
run_baseline_review "mistral-small-4-119b" "$BASELINE_DIR/review-baseline-mistral.md" &
PID_MIS_BASE=$!

# 6. Wait for all six. Collect failures independently.
FAILURES=0
wait "$PID_GPT"     || { echo "gpt-oss-120b with-skill FAILED"; FAILURES=$((FAILURES+1)); }
wait "$PID_GLM"     || { echo "glm5.2 with-skill FAILED";       FAILURES=$((FAILURES+1)); }
wait "$PID_MIS"     || { echo "mistral with-skill FAILED";      FAILURES=$((FAILURES+1)); }
wait "$PID_GPT_BASE" || { echo "gpt-oss-120b baseline FAILED";  FAILURES=$((FAILURES+1)); }
wait "$PID_GLM_BASE" || { echo "glm5.2 baseline FAILED";       FAILURES=$((FAILURES+1)); }
wait "$PID_MIS_BASE" || { echo "mistral baseline FAILED";      FAILURES=$((FAILURES+1)); }

echo ""
echo "Reviews complete. Failures: $FAILURES/6"
echo ""
echo "With-skill reviews:"
for f in "$REPORT_DIR"/review-{gpt-oss-120b,glm5.2,mistral}.md; do
  if [ -f "$f" ] && [ -s "$f" ]; then
    printf '  %-40s %s words\n' "$(basename "$f")" "$(wc -w < "$f")"
  else
    printf '  %-40s MISSING\n' "$(basename "$f")"
  fi
done
echo "Baseline reviews (no skill):"
for f in "$BASELINE_DIR"/review-baseline-{gpt-oss-120b,glm5.2,mistral}.md; do
  if [ -f "$f" ] && [ -s "$f" ]; then
    printf '  %-40s %s words\n' "$(basename "$f")" "$(wc -w < "$f")"
  else
    printf '  %-40s MISSING\n' "$(basename "$f")"
  fi
done

echo ""
if [ "$FAILURES" -le 1 ]; then
  echo "Success: $((6-FAILURES))/6 reviews produced."

  # Generate the comparison report from the six reviews.
  echo ""
  echo "[$(date +%H:%M:%S)] Generating comparison report..."
  if python3 report/build_comparison.py; then
    echo "[$(date +%H:%M:%S)] Comparison written to report/comparison.md"
  else
    echo "[$(date +%H:%M:%S)] WARNING: comparison generation failed" >&2
  fi

  # Baseline reviews are preserved in report/baseline/ for future runs.
  # build_comparison.py tolerates their absence (shows "N/A" for baseline stats).

  echo ""
  echo "Done. Final artifacts:"
  echo "  report/comparison.md"
  echo "  report/review-gpt-oss-120b.md"
  echo "  report/review-glm5.2.md"
  echo "  report/review-mistral.md"
  exit 0
else
  echo "WARNING: $FAILURES reviews failed. Check .log files in report/ for details." >&2
  echo "Re-run the script to retry only the missing reviews (existing outputs are skipped)." >&2
  exit 1
fi
