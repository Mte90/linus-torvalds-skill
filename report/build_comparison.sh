#!/usr/bin/env bash
# Build report/comparison.md from the three review files.
#
# This is a scaffold: the synthesis is qualitative and was written by hand from
# the three reports. This script regenerates the headline numbers table so the
# comparison stays in sync with the review files.
#
# Run from the repository root:
#   bash report/build_comparison.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORT_DIR="$ROOT/report"

count_severity() {
  local file="$1"
  local sev="$2"
  grep -cE "^### \[?$sev\]|^### $sev —" "$file" 2>/dev/null || echo 0
}

count_total() {
  grep -cE "^### \[(CRITICAL|HIGH|MEDIUM|LOW)\]|^### (CRITICAL|HIGH|MEDIUM|LOW) —" "$1" 2>/dev/null || echo 0
}

word_count() {
  wc -w < "$1" | tr -d ' '
}

GPT="$REPORT_DIR/review-gpt-oss-120b.md"
GLM="$REPORT_DIR/review-glm5.2.md"
MIS="$REPORT_DIR/review-mistral.md"

for f in "$GPT" "$GLM" "$MIS"; do
  [ -f "$f" ] || { echo "Missing: $f" >&2; exit 1; }
done

cat <<EOF
# Headline numbers (regenerated $(date -u +%Y-%m-%dT%H:%M:%SZ))

| Metric | gpt-oss-120b | glm5.2 | mistral-small-4-119b |
|--------|-------------|--------|----------------------|
| Findings (total) | $(count_total "$GPT") | $(count_total "$GLM") | $(count_total "$MIS") |
| CRITICAL | $(count_severity "$GPT" CRITICAL) | $(count_severity "$GLM" CRITICAL) | $(count_severity "$MIS" CRITICAL) |
| HIGH | $(count_severity "$GPT" HIGH) | $(count_severity "$GLM" HIGH) | $(count_severity "$MIS" HIGH) |
| MEDIUM | $(count_severity "$GPT" MEDIUM) | $(count_severity "$GLM" MEDIUM) | $(count_severity "$MIS" MEDIUM) |
| LOW | $(count_severity "$GPT" LOW) | $(count_severity "$GLM" LOW) | $(count_severity "$MIS" LOW) |
| Report words | $(word_count "$GPT") | $(word_count "$GLM") | $(word_count "$MIS") |

The qualitative synthesis (consensus findings, divergences, skill observations)
lives in the hand-written portion of comparison.md above this table.
EOF
