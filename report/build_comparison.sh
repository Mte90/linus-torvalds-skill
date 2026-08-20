#!/usr/bin/env bash
# Build report/comparison.md from the review files (with-skill and baseline).
#
# This script extracts metrics from 6 review files:
# - 3 with-skill reviews: review-{model}.md
# - 3 baseline reviews: review-baseline-{model}.md
#
# Run from the repository root:
#   bash report/build_comparison.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORT_DIR="$ROOT/report"

count_severity() {
  local file="$1"
  local sev="$2"
  local n
  n=$(grep -cE "^#+ \[?${sev}\]?[ ]" "$file" 2>/dev/null || true)
  echo "${n:-0}"
}

count_total() {
  local n
  n=$(grep -cE "^#+ \[?(CRITICAL|HIGH|MEDIUM|LOW)\]?[ ]" "$1" 2>/dev/null || true)
  echo "${n:-0}"
}

word_count() {
  wc -w < "$1" | tr -d ' '
}

# With-skill review files
GPT="$REPORT_DIR/review-gpt-oss-120b.md"
GLM="$REPORT_DIR/review-glm5.2.md"
MIS="$REPORT_DIR/review-mistral.md"

# Baseline (no-skill) review files
GPT_BASE="$REPORT_DIR/review-baseline-gpt-oss-120b.md"
GLM_BASE="$REPORT_DIR/review-baseline-glm5.2.md"
MIS_BASE="$REPORT_DIR/review-baseline-mistral.md"

# Remove any leftover per-review log files before emitting the table.
rm -f "$REPORT_DIR"/review-*.log

# Helper: extract metrics from a file, return "N/A" if missing
get_metrics() {
  local file="$1"
  if [ -f "$file" ]; then
    local words findings critical high medium low
    words=$(word_count "$file")
    findings=$(count_total "$file")
    critical=$(count_severity "$file" CRITICAL)
    high=$(count_severity "$file" HIGH)
    medium=$(count_severity "$file" MEDIUM)
    low=$(count_severity "$file" LOW)
    echo "$words $findings $critical $high $medium $low"
  else
    echo "N/A N/A N/A N/A N/A N/A"
  fi
}

# Extract metrics for all 6 files
read -r GPT_WORDS GPT_FIND GPT_CRIT GPT_HIGH GPT_MED GPT_LOW <<< "$(get_metrics "$GPT")"
read -r GPT_B_WORDS GPT_B_FIND GPT_B_CRIT GPT_B_HIGH GPT_B_MED GPT_B_LOW <<< "$(get_metrics "$GPT_BASE")"
read -r GLM_WORDS GLM_FIND GLM_CRIT GLM_HIGH GLM_MED GLM_LOW <<< "$(get_metrics "$GLM")"
read -r GLM_B_WORDS GLM_B_FIND GLM_B_CRIT GLM_B_HIGH GLM_B_MED GLM_B_LOW <<< "$(get_metrics "$GLM_BASE")"
read -r MIS_WORDS MIS_FIND MIS_CRIT MIS_HIGH MIS_MED MIS_LOW <<< "$(get_metrics "$MIS")"
read -r MIS_B_WORDS MIS_B_FIND MIS_B_CRIT MIS_B_HIGH MIS_B_MED MIS_B_LOW <<< "$(get_metrics "$MIS_BASE")"

# Calculate deltas (with-skill minus baseline)
calc_delta() {
  local skill_val="$1" baseline_val="$2"
  if [ "$skill_val" = "N/A" ] || [ "$baseline_val" = "N/A" ]; then
    echo "—"
  else
    local delta=$((skill_val - baseline_val))
    if [ $delta -gt 0 ]; then
      echo "+$delta"
    elif [ $delta -lt 0 ]; then
      echo "$delta"
    else
      echo "0"
    fi
  fi
}

GPT_DELTA=$(calc_delta "$GPT_FIND" "$GPT_B_FIND")
GLM_DELTA=$(calc_delta "$GLM_FIND" "$GLM_B_FIND")
MIS_DELTA=$(calc_delta "$MIS_FIND" "$MIS_B_FIND")

cat <<EOF
# Review Comparison: With-Skill vs Baseline

Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

## Detailed Metrics by Model

| Model | Mode | Words | Findings | CRITICAL | HIGH | MEDIUM | LOW |
|-------|------|-------|----------|----------|------|--------|-----|
| gpt-oss-120b | with-skill | $GPT_WORDS | $GPT_FIND | $GPT_CRIT | $GPT_HIGH | $GPT_MED | $GPT_LOW |
| gpt-oss-120b | baseline | $GPT_B_WORDS | $GPT_B_FIND | $GPT_B_CRIT | $GPT_B_HIGH | $GPT_B_MED | $GPT_B_LOW |
| glm5.2 | with-skill | $GLM_WORDS | $GLM_FIND | $GLM_CRIT | $GLM_HIGH | $GLM_MED | $GLM_LOW |
| glm5.2 | baseline | $GLM_B_WORDS | $GLM_B_FIND | $GLM_B_CRIT | $GLM_B_HIGH | $GLM_B_MED | $GLM_B_LOW |
| mistral-small-4-119b | with-skill | $MIS_WORDS | $MIS_FIND | $MIS_CRIT | $MIS_HIGH | $MIS_MED | $MIS_LOW |
| mistral-small-4-119b | baseline | $MIS_B_WORDS | $MIS_B_FIND | $MIS_B_CRIT | $MIS_B_HIGH | $MIS_B_MED | $MIS_B_LOW |

## Skill Impact: Finding Delta

| Model | Baseline Findings | With-Skill Findings | Δ (skill benefit) |
|-------|-------------------|---------------------|-------------------|
| gpt-oss-120b | $GPT_B_FIND | $GPT_FIND | $GPT_DELTA |
| glm5.2 | $GLM_B_FIND | $GLM_FIND | $GLM_DELTA |
| mistral-small-4-119b | $MIS_B_FIND | $MIS_FIND | $MIS_DELTA |

## Synthesis

The skill's impact varies by model. The delta column shows how many additional findings
the with-skill review produced compared to baseline. Positive deltas indicate the skill
helped the model identify more issues.

Among the three models, the one with the highest finding count demonstrates the skill's
maximum benefit. Check the delta column to see which model gains the most from the skill.

The qualitative synthesis (consensus findings, divergences, skill observations)
lives in the hand-written portion of comparison.md above this table.
EOF