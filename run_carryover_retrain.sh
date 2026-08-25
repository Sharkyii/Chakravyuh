#!/bin/bash
set -euo pipefail
cd /home/sharkyi/Desktop/Chakravyuh
export PYTHONPATH=/home/sharkyi/Desktop/Chakravyuh

LOG_DIR=stage5/data/run_logs
mkdir -p "$LOG_DIR"

commit() {
  git add -A
  git -c commit.gpgsign=false commit -m "$1" || echo "Nothing to commit for: $1"
  git push origin main || echo "Push failed for: $1 (will retry at next stage)"
}

echo "=== [1/3] Gen 3 curriculum retraining (with attack carryover fix) ==="
.venv/bin/python -m stage5.training.run_all_generations --stage gen3 2>&1 | tee "$LOG_DIR/c1_gen3.log"
commit "Fix catastrophic forgetting: carry forward prior generations' attacks in curriculum retraining"

echo "=== [2/3] Gen 4 curriculum retraining ==="
.venv/bin/python -m stage5.training.run_all_generations --stage gen4 2>&1 | tee "$LOG_DIR/c2_gen4.log"
commit "Run Gen 4 curriculum retraining with attack carryover"

echo "=== [3/3] Gen 5 curriculum retraining ==="
.venv/bin/python -m stage5.training.run_all_generations --stage gen5 2>&1 | tee "$LOG_DIR/c3_gen5.log"
commit "Run Gen 5 curriculum retraining with attack carryover, promote to live inference model"

echo "=== ALL CARRYOVER STAGES COMPLETE ==="
