#!/usr/bin/env bash
# Per-model decontaminated evaluation chain — resume-safe, self-driving.
# Runs each model sequentially: diagonal → baseline → cross, then rescore + stamp + reports.
set -euo pipefail
cd "$(dirname "$0")/.."
LOG="/tmp/eval_permodel_$(date +%s).log"
export PYTHONUNBUFFERED=1

MODELS="gpt-oss-120b mistral-small-4-119b glm5.2 qwen3.8-27b"

echo "=== Per-model chain started $(date) ===" | tee "$LOG"

for M in $MODELS; do
    echo "" | tee -a "$LOG"
    echo "=== Model: $M — diagonal (skill) ===" | tee -a "$LOG"
    python3 -B scripts/run_eval.py --models "$M" --repetitions 1 --parallel --judge-model glm5.2 2>&1 | tee -a "$LOG"

    echo "=== Model: $M — baseline ===" | tee -a "$LOG"
    python3 -B scripts/run_eval.py --models "$M" --baseline --repetitions 1 --parallel --judge-model glm5.2 2>&1 | tee -a "$LOG"

    echo "=== Model: $M — cross (all skills) ===" | tee -a "$LOG"
    python3 -B scripts/run_eval.py --cross --models "$M" --repetitions 1 --parallel --judge-model glm5.2 2>&1 | tee -a "$LOG"
done

echo "" | tee -a "$LOG"
echo "=== Stage 3: rescore-zeros ===" | tee -a "$LOG"
python3 -B scripts/run_eval.py --rescore-zeros --judge-model glm5.2 2>&1 | tee -a "$LOG"
python3 -B scripts/run_eval.py --rescore-zeros --cross --judge-model glm5.2 2>&1 | tee -a "$LOG"

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
