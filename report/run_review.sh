#!/usr/bin/env bash
# Replicate the three-model Torvalds review of antirez/smallchat.
#
# Produces, in report/:
#   review-gpt-oss-120b.md
#   review-glm5.2.md
#   review-mistral.md
#
# Prerequisites:
#   - opencode agent CLI available as `opencode` on PATH
#   - smallchat cloned to /tmp/smallchat (this script does it if missing)
#   - skill files present at linus-torvalds-skill/SKILL.md, SKILL-GLM.md, SKILL-Mistral.md
#   - soul files present at soul/soul.md, soul-glm.md, soul-mistral.md
#
# Run from the repository root:
#   bash report/run_review.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="/tmp/smallchat"
REPORT_DIR="$ROOT/report"
SKILL_DIR="$ROOT/linus-torvalds-skill"
SOUL_DIR="$ROOT/soul"

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
  cat <<EOF
You are a code reviewer applying the Linus Torvalds reviewer skill to a real codebase.

Codebase to review: /tmp/smallchat/ — antirez/smallchat (minimal TCP chat server, ~706 LOC).
Source files: smallchat-server.c, smallchat-client.c, chatlib.c, chatlib.h, Makefile.

Skill file to apply: $skill_file — read it fully and apply its rules (triggers, precedence, definitions, anti-patterns).
Soul file for tone: $soul_file — adopt this voice. Profanity is permitted for dangerous/negligent defects; replicate faithfully.

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
EOF
}

# 4. Run the three reviews in parallel via opencode agents.
run_review() {
  local model_label="$1"
  local skill_file="$2"
  local soul_file="$3"
  local out_file="$4"
  local prompt

  prompt="$(review_prompt "$skill_file" "$soul_file")

Write the report to: $out_file"

  echo "[$(date +%H:%M:%S)] Starting $model_label review -> $(basename "$out_file")"
  opencode run --prompt "$prompt" >/dev/null 2>&1 || {
    echo "[$(date +%H:%M:%S)] $model_label review FAILED" >&2
    return 1
  }
  echo "[$(date +%H:%M:%S)] $model_label review done: $(wc -w < "$out_file" 2>/dev/null || echo '?') words"
}

export -f review_prompt run_review

# 5. Dispatch all three concurrently.
echo "Dispatching three parallel reviews..."
run_review "gpt-oss-120b" "$SKILL_DIR/SKILL.md" "$SOUL_DIR/soul.md" "$REPORT_DIR/review-gpt-oss-120b.md" &
PID_GPT=$!
run_review "glm5.2" "$SKILL_DIR/SKILL-GLM.md" "$SOUL_DIR/soul-glm.md" "$REPORT_DIR/review-glm5.2.md" &
PID_GLM=$!
run_review "mistral-small-4-119b" "$SKILL_DIR/SKILL-Mistral.md" "$SOUL_DIR/soul-mistral.md" "$REPORT_DIR/review-mistral.md" &
PID_MIS=$!

# 6. Wait for all three.
FAIL=0
wait "$PID_GPT" || FAIL=1
wait "$PID_GLM" || FAIL=1
wait "$PID_MIS" || FAIL=1

if [ "$FAIL" -ne 0 ]; then
  echo "One or more reviews failed. See output above." >&2
  exit 1
fi

echo ""
echo "All reviews complete:"
for f in "$REPORT_DIR"/review-*.md; do
  printf '  %-40s %s words\n' "$(basename "$f")" "$(wc -w < "$f")"
done
echo ""
echo "Next: generate the comparison with report/build_comparison.sh"
