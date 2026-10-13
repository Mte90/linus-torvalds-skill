#!/usr/bin/env bash
# Full decontaminated evaluation chain — resume-safe, self-driving.
# Stages: diagonal → baseline → cross → rescore-zeros → stamp-judge → regenerate reports
set -euo pipefail

cd "$(dirname "$0")/.."
LOG="/tmp/eval_chain_$(date +%s).log"
export PYTHONUNBUFFERED=1

echo "=== Chain started $(date) ===" | tee "$LOG"

# Stage 1a: diagonal (model with own skill)
echo "=== Stage 1a: diagonal skill arm ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --repetitions 1 --parallel --judge-model glm5.2 2>&1 | tee -a "$LOG"

# Stage 1b: baseline (model without skill)
echo "=== Stage 1b: baseline arm ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --baseline --repetitions 1 --parallel --judge-model glm5.2 2>&1 | tee -a "$LOG"

# Stage 2: cross (off-diagonal model×skill pairs)
echo "=== Stage 2: cross arm ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --cross --repetitions 1 --parallel --judge-model glm5.2 2>&1 | tee -a "$LOG"

# Stage 3: rescore zeros (fix judge failures)
echo "=== Stage 3: rescore-zeros ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --rescore-zeros --judge-model glm5.2 2>&1 | tee -a "$LOG"
python3 -B scripts/run_eval.py --rescore-zeros --cross --judge-model glm5.2 2>&1 | tee -a "$LOG"

# Stage 4: stamp judge model
echo "=== Stage 4: stamp judge model ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --stamp-judge-model glm5.2 2>&1 | tee -a "$LOG"
python3 -B scripts/run_eval.py --stamp-judge-model glm5.2 --cross 2>&1 | tee -a "$LOG"

# Guard: verify record counts before publishing
DIAG=$(wc -l < data/eval_results.jsonl)
CROSS=$(wc -l < data/eval_results_cross.jsonl 2>/dev/null || echo 0)
echo "=== Guard: diagonal=$DIAG cross=$CROSS ===" | tee -a "$LOG"
if [ "$DIAG" -lt 360 ] || [ "$CROSS" -lt 540 ]; then
    echo "GUARD FAILED: incomplete data (diag=$DIAG<360 or cross=$CROSS<540). Reports NOT regenerated." | tee -a "$LOG"
    exit 1
fi

# Stage 5: regenerate reports
echo "=== Stage 5: regenerate reports ===" | tee -a "$LOG"
python3 -B scripts/render_cross.py --eval-provenance decontaminated 2>&1 | tee -a "$LOG"
python3 -B -c "
import sys; sys.path.insert(0, 'report')
from build_comparison import generate_markdown
from pathlib import Path
md = generate_markdown(eval_provenance='decontaminated')
Path('report/comparison.md').write_text(md)
print('comparison.md written:', len(md), 'chars')
" 2>&1 | tee -a "$LOG"

echo "=== PIPELINE COMPLETE $(date) ===" | tee -a "$LOG"
