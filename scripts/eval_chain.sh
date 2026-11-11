#!/usr/bin/env bash
# Full decontaminated evaluation chain — resume-safe, self-driving.
# Stages: diagonal → baseline → cross → stamp-judge → regenerate reports
set -euo pipefail

cd "$(dirname "$0")/.."
LOG="/tmp/eval_chain_$(date +%s).log"
export PYTHONUNBUFFERED=1

echo "=== Chain started $(date) ===" | tee "$LOG"

# Stage 1a: diagonal (model with own skill)
echo "=== Stage 1a: diagonal skill arm ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --repetitions 1 --codebase --judge-model glm5.2 2>&1 | tee -a "$LOG"

# Stage 1b: baseline (model without skill)
echo "=== Stage 1b: baseline arm ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --baseline --repetitions 1 --codebase --judge-model glm5.2 2>&1 | tee -a "$LOG"

# Stage 2: cross (off-diagonal model×skill pairs)
echo "=== Stage 2: cross arm ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --cross --repetitions 1 --codebase --judge-model glm5.2 2>&1 | tee -a "$LOG"

# Stage 3: stamp judge model
echo "=== Stage 3: stamp judge model ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --stamp-judge-model glm5.2 2>&1 | tee -a "$LOG"
python3 -B scripts/run_eval.py --stamp-judge-model glm5.2 --cross 2>&1 | tee -a "$LOG"

# Guard: verify record count before publishing (codebase mode: 4 models x 5 skills = 20)
TOTAL=$(wc -l < data/eval_results_codebase.jsonl 2>/dev/null || echo 0)
echo "=== Guard: codebase records=$TOTAL ===" | tee -a "$LOG"
if [ "$TOTAL" -lt 20 ]; then
    echo "GUARD FAILED: incomplete data (total=$TOTAL<20). Reports NOT regenerated." | tee -a "$LOG"
    exit 1
fi

# Stage 5: regenerate reports
echo "=== Stage 5: regenerate reports ===" | tee -a "$LOG"
python3 -B scripts/render_cross.py --codebase --eval-provenance decontaminated 2>&1 | tee -a "$LOG"
python3 -B -c "
import sys; sys.path.insert(0, 'report')
from build_comparison import generate_markdown
from pathlib import Path
md = generate_markdown(eval_provenance='decontaminated')
Path('report/comparison.md').write_text(md)
print('comparison.md written:', len(md), 'chars')
" 2>&1 | tee -a "$LOG"

echo "=== PIPELINE COMPLETE $(date) ===" | tee -a "$LOG"
