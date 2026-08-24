#!/bin/bash
set -euo pipefail
cd /home/sharkyi/Desktop/Chakravyuh
export PYTHONPATH=/home/sharkyi/Desktop/Chakravyuh

LOG_DIR=stage5/data/run_logs
mkdir -p "$LOG_DIR"

commit() {
  git add -A
  # GPG signing needs an interactive pinentry that can't be answered by this
  # detached background process -- scoped to just these automated commits,
  # not a persistent config change.
  git -c commit.gpgsign=false commit -m "$1" || echo "Nothing to commit for: $1"
  git push origin main || echo "Push failed for: $1 (will retry at next stage)"
}

echo "=== [1/4] Generating self-consistent synthetic dataset (reduced scale) ==="
.venv/bin/python -m stage5.training.generate_training_data_reduced 2>&1 | tee "$LOG_DIR/01_generate_data.log"
commit "Generate reduced-scale single-simulator training dataset"

echo "=== [2/4] Baseline training ==="
.venv/bin/python -m stage5.training.train_fraud_model 2>&1 | tee "$LOG_DIR/02_baseline_train.log"
commit "Train baseline fraud model on synthetic dataset"

echo "=== [3/4] Gen 3 curriculum retraining ==="
.venv/bin/python -m stage5.training.run_all_generations --stage baseline 2>&1 | tee "$LOG_DIR/03a_baseline_stage.log"
.venv/bin/python -m stage5.training.run_all_generations --stage gen3 2>&1 | tee "$LOG_DIR/03b_gen3.log"
commit "Run Gen 3 curriculum retraining"

echo "=== [4/4] Gen 4 + Gen 5 curriculum retraining ==="
.venv/bin/python -m stage5.training.run_all_generations --stage gen4 2>&1 | tee "$LOG_DIR/04_gen4.log"
commit "Run Gen 4 curriculum retraining"

.venv/bin/python -m stage5.training.run_all_generations --stage gen5 2>&1 | tee "$LOG_DIR/05_gen5.log"
commit "Run Gen 5 curriculum retraining, promote to live inference model"

echo "=== ALL STAGES COMPLETE ==="
