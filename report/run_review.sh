#!/usr/bin/env bash
# Replicate the three-model Torvalds review of antirez/smallchat + baseline comparison.
#
# Produces, in report/:
#   With-skill reviews:
#     review-gpt-oss-120b.md
#     review-glm5.2.md
#     review-mistral.md
#   Baseline reviews (no skill/soul):
#     review-baseline-gpt-oss-120b.md
#     review-baseline-glm5.2.md
#     review-baseline-mistral.md
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
#   - soul files present at soul/soul.md, soul-glm.md, soul-mistral.md
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
SOUL_DIR="$ROOT/soul"

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

# 1. Ensure the target codebase is present.
if [ ! -d "$TARGET" ]; then
  echo "Cloning antirez/smallchat to $TARGET..."
  git clone --depth 1 https://github.com/antirez/smallchat "$TARGET"
fi

# 2. Verify skill + soul assets exist.
for f in \
  "$SKILL_DIR/SKILL.md" \
  "$SKILL_DIR/SKILL-GLM.md" \
  "$SKILL_DIR/SKILL-Mistral.md" \
  "$SOUL_DIR/soul.md" \
  "$SOUL_DIR/soul-glm.md" \
  "$SOUL_DIR/soul-mistral.md"; do
  if [ ! -f "$f" ]; then
    echo "Missing asset: $f" >&2
    exit 1
  fi
done

# 3. Shared review prompt body. Each model gets its own skill + soul + output.
review_prompt() {
  local skill_file="$1"
  local soul_file="$2"
  local out_file="$3"
  cat <<EOF
You are a code reviewer applying the Linus Torvalds reviewer skill to a real codebase.

Codebase to review: /tmp/smallchat/ — antirez/smallchat (minimal TCP chat server, ~706 LOC).
Source files: smallchat-server.c, smallchat-client.c, chatlib.c, chatlib.h, Makefile.

Skill file to apply: $skill_file — read it fully and apply its rules (triggers, precedence, definitions, anti-patterns).
Soul file for tone: $soul_file — adopt this voice. Profanity is permitted for dangerous/negligent defects; replicate faithfully.

## Persona Narrative (2-3 paragraphs)

Lead with: What does it feel like to interact with an AI using this skill/soul? Does it capture Linus' voice? Is it too harsh, too soft, or about right? Give concrete examples of how the persona comes across.

Specifically:
- Quote specific lines from the skill/soul file that capture (or miss) Linus' voice
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

3-5 bullet points on what the skill/soul gets right.

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
- English. Torvalds' voice from the soul.

Read all source files first, then the skill, then the soul, then write the report.
Write the final report to: $out_file
EOF
}

# 4. Run a single with-skill review with timeout + retry.
run_review() {
  local model_label="$1"
  local skill_file="$2"
  local soul_file="$3"
  local out_file="$4"

  # Skip if already done (unless --force).
  if [ "$FORCE" -eq 0 ] && [ -s "$out_file" ]; then
    echo "[$(date +%H:%M:%S)] $model_label review already exists ($(wc -w < "$out_file") words), skipping"
    return 0
  fi

  local prompt
  prompt="$(review_prompt "$skill_file" "$soul_file" "$out_file")"

  # Timeout: 40 min for GLM5.2 (long reasoning latency), 15 min for others.
  local timeout_sec=900
  if [ "$model_label" = "glm5.2" ]; then
    timeout_sec=2400
  fi

  echo "[$(date +%H:%M:%S)] Starting $model_label review -> $(basename "$out_file") (timeout ${timeout_sec}s)"

  local attempt
  for attempt in 1 2; do
    if [ "$attempt" -gt 1 ]; then
      echo "[$(date +%H:%M:%S)] $model_label review: retrying (attempt 2)"
      rm -f "$out_file"
    fi

    local start_ts
    start_ts=$(date +%s)

    if timeout "${timeout_sec}" opencode run -m "regolo-ai/$model_label" "$prompt" > "$REPORT_DIR/review-$model_label.log" 2>&1; then
      # Extract report from log if agent didn't write the file itself.
      if [ ! -s "$out_file" ] || [ "$(stat -c %Y "$out_file" 2>/dev/null || echo 0)" -lt "$start_ts" ]; then
        awk '/^---$/{found=1} found{print}' "$REPORT_DIR/review-$model_label.log" > "$out_file"
      fi

      if [ -s "$out_file" ]; then
        echo "[$(date +%H:%M:%S)] $model_label review done: $(wc -w < "$out_file") words"
        return 0
      fi
      echo "[$(date +%H:%M:%S)] $model_label review: opencode exited OK but output empty" >&2
    else
      local exit_code=$?
      if [ "$exit_code" -eq 124 ]; then
        echo "[$(date +%H:%M:%S)] $model_label review TIMED OUT after ${timeout_sec}s" >&2
      else
        echo "[$(date +%H:%M:%S)] $model_label review FAILED (exit $exit_code)" >&2
      fi
    fi
  done

  echo "[$(date +%H:%M:%S)] $model_label review FAILED after 2 attempts" >&2
  return 1
}

# Baseline review prompt (no skill/soul). Neutral code reviewer.
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

  local attempt
  for attempt in 1 2; do
    if [ "$attempt" -gt 1 ]; then
      echo "[$(date +%H:%M:%S)] baseline $model_label review: retrying (attempt 2)"
      rm -f "$out_file"
    fi

    local start_ts
    start_ts=$(date +%s)

    if timeout "${timeout_sec}" opencode run -m "regolo-ai/$model_label" "$prompt" > "$REPORT_DIR/review-baseline-$model_label.log" 2>&1; then
      # Extract report from log if agent didn't write the file.
      if [ ! -s "$out_file" ] || [ "$(stat -c %Y "$out_file" 2>/dev/null || echo 0)" -lt "$start_ts" ]; then
        awk '/^---$/{found=1} found{print}' "$REPORT_DIR/review-baseline-$model_label.log" > "$out_file"
      fi

      if [ -s "$out_file" ]; then
        echo "[$(date +%H:%M:%S)] baseline $model_label review done: $(wc -w < "$out_file") words"
        return 0
      fi
      echo "[$(date +%H:%M:%S)] baseline $model_label review: opencode exited OK but output empty" >&2
    else
      local exit_code=$?
      if [ "$exit_code" -eq 124 ]; then
        echo "[$(date +%H:%M:%S)] baseline $model_label review TIMED OUT after ${timeout_sec}s" >&2
      else
        echo "[$(date +%H:%M:%S)] baseline $model_label review FAILED (exit $exit_code)" >&2
      fi
    fi
  done

  echo "[$(date +%H:%M:%S)] baseline $model_label review FAILED after 2 attempts" >&2
  return 1
}

export -f review_prompt run_review baseline_prompt run_baseline_review

# 5. Dispatch all six reviews concurrently (3 with-skill + 3 baseline).
echo "Dispatching six parallel reviews (3 with-skill, 3 baseline)..."
echo "  Force mode: $FORCE (0=skip existing, 1=regenerate all)"
echo ""

# With-skill reviews
run_review "gpt-oss-120b" "$SKILL_DIR/SKILL.md" "$SOUL_DIR/soul.md" "$REPORT_DIR/review-gpt-oss-120b.md" &
PID_GPT=$!
run_review "glm5.2" "$SKILL_DIR/SKILL-GLM.md" "$SOUL_DIR/soul-glm.md" "$REPORT_DIR/review-glm5.2.md" &
PID_GLM=$!
run_review "mistral-small-4-119b" "$SKILL_DIR/SKILL-Mistral.md" "$SOUL_DIR/soul-mistral.md" "$REPORT_DIR/review-mistral.md" &
PID_MIS=$!
# Baseline reviews (no skill/soul)
run_baseline_review "gpt-oss-120b" "$REPORT_DIR/review-baseline-gpt-oss-120b.md" &
PID_GPT_BASE=$!
run_baseline_review "glm5.2" "$REPORT_DIR/review-baseline-glm5.2.md" &
PID_GLM_BASE=$!
run_baseline_review "mistral-small-4-119b" "$REPORT_DIR/review-baseline-mistral.md" &
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
echo "Baseline reviews (no skill/soul):"
for f in "$REPORT_DIR"/review-baseline-{gpt-oss-120b,glm5.2,mistral}.md; do
  if [ -f "$f" ] && [ -s "$f" ]; then
    printf '  %-40s %s words\n' "$(basename "$f")" "$(wc -w < "$f")"
  else
    printf '  %-40s MISSING\n' "$(basename "$f")"
  fi
done

echo ""
if [ "$FAILURES" -le 1 ]; then
  echo "Success: $((6-FAILURES))/6 reviews produced."
  echo "Next: generate the comparison with report/build_comparison.sh"
  exit 0
else
  echo "WARNING: $FAILURES reviews failed. Check .log files in report/ for details." >&2
  echo "Re-run the script to retry only the missing reviews (existing outputs are skipped)." >&2
  exit 1
fi
