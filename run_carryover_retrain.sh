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

echo "=== [0/4] Regenerating training data with 15 attack families (13 base + 2 new) ==="
rm -rf data/generated/stage5/combined
.venv/bin/python -m stage5.training.generate_training_data_reduced 2>&1 | tee "$LOG_DIR/00_data_gen.log"
commit "Generate training data with 15 attack families (device_fan_out, balance_drain_exit)"

echo "=== [1/4] Gen 3 curriculum retraining (now actually trains on attack rows) ==="
.venv/bin/python -m stage5.training.run_all_generations --stage gen3 2>&1 | tee "$LOG_DIR/d1_gen3.log"
commit "Fix curriculum retraining actually training on attack rows, not just testing on them"

echo "=== [2/4] Gen 4 curriculum retraining ==="
.venv/bin/python -m stage5.training.run_all_generations --stage gen4 2>&1 | tee "$LOG_DIR/d2_gen4.log"
commit "Run Gen 4 curriculum retraining with real attack exposure"

echo "=== [3/4] Gen 5 curriculum retraining ==="
.venv/bin/python -m stage5.training.run_all_generations --stage gen5 2>&1 | tee "$LOG_DIR/d3_gen5.log"
commit "Run Gen 5 curriculum retraining with real attack exposure, promote to live inference model"

echo "=== [4/4] Cross-generation evaluation ==="
.venv/bin/python -m stage5.validation.cross_generation_eval 2>&1 | tee "$LOG_DIR/d4_cross_gen_eval.log"
commit "Cross-generation evaluation on 15-family retrained model"

echo "=== ALL 15-FAMILY RETRAIN COMPLETE ==="
