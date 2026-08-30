"""
Orchestrates the model retraining process based on Analyst Feedback.
Triggered via UI when enough feedback is collected.
"""
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
import pandas as pd
import joblib

# Add project root to python path to resolve imports
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from stage5.human_loop.feedback_aggregator import FeedbackStore
from stage5.training.train_fraud_model import load_and_prepare, train_fraud_model
from stage5.config.settings import MODELS_DIR

RETAINED_ATTACKS_DIR = Path(__file__).resolve().parent.parent / "data"

# gen3/4/5_retained_attacks.parquet are artifacts of the curriculum retrain
# (stage5/training/run_all_generations.py), captured against whatever baseline
# scale that run used. If a later feedback-driven retrain runs against a
# different (typically smaller) baseline, blindly concatenating those files
# can shift the training set's fraud prevalence by an order of magnitude and
# break train_fraud_model()'s class-imbalance/threshold calibration outright
# -- confirmed: merging ~4.3k retained-attack rows onto a 2k-consumer/127-fraud
# baseline pushed prevalence from ~0.3% to ~9.75% and collapsed test PR-AUC
# from ~0.999 to ~0.46. Cap the *combined* retained-attack contribution so
# post-merge prevalence never exceeds this, downsampling (not dropping) so
# some adversarial-pattern exposure is preserved either way.
MAX_RETAINED_ATTACK_PREVALENCE = 0.05

# A retrain should only ever go live if it's not materially worse than what
# it's replacing -- retraining on a bad or mismatched dataset must not be
# able to silently regress the deployed model (this is what let the
# prevalence bug above collapse test PR-AUC from ~0.999 to ~0.46 in
# production before anyone looked). A small tolerance is allowed since a
# real feedback-driven shift in the training distribution can legitimately
# move PR-AUC by a little; anything past that is treated as a failed
# promotion, not a new deployment.
MAX_PR_AUC_REGRESSION = 0.02


def run_retrain():
    print("=== Analyst Feedback Retraining Orchestrator ===")
    
    store = FeedbackStore()
    if not store.feedback_path.exists():
        print("No feedback data found.")
        return False

    # Load feedback
    feedback_df = pd.read_parquet(store.feedback_path)
    if len(feedback_df) == 0:
        print("Feedback database is empty.")
        return False
        
    print(f"Loaded {len(feedback_df)} analyst verdicts.")
    
    # Backup existing metadata
    metadata_path = MODELS_DIR / "model_metadata.json"
    backup_path = MODELS_DIR / "previous_metadata.json"
    if metadata_path.exists():
        shutil.copy(metadata_path, backup_path)
        print("Backed up current model metadata.")

    # Load full dataset
    print("Loading baseline dataset...")
    df = load_and_prepare()
    
    # Load retained attacks from curriculum generations so we don't forget adversarial patterns
    # and so the preprocessor sees all the same categories as the deployed model.
    retained_frames = []
    for gen in ["gen3", "gen4", "gen5"]:
        retained_path = RETAINED_ATTACKS_DIR / f"{gen}_retained_attacks.parquet"
        if retained_path.exists():
            atk_df = pd.read_parquet(retained_path)
            atk_df["split"] = "train"
            retained_frames.append(atk_df)
            print(f"Loaded {len(atk_df)} retained attacks from {gen}.")

    if retained_frames:
        retained_df = pd.concat(retained_frames, ignore_index=True, sort=False)
        baseline_legit = int((df["is_fraud"] == 0).sum())
        baseline_fraud = int((df["is_fraud"] == 1).sum())
        total_baseline = baseline_legit + baseline_fraud
        baseline_prev = baseline_fraud / total_baseline if total_baseline > 0 else 0.0
        n_feedback_fraud = int((feedback_df["analyst_verdict"] == "FRAUD").sum()) if "analyst_verdict" in feedback_df.columns else 0
        if baseline_prev < MAX_RETAINED_ATTACK_PREVALENCE:
            max_retained = max(0, int(
                (MAX_RETAINED_ATTACK_PREVALENCE * total_baseline - baseline_fraud - n_feedback_fraud)
                / (1 - MAX_RETAINED_ATTACK_PREVALENCE)
            ))
        else:
            # Baseline is already fraud-rich; retain a bounded sample of hard adversarial attacks
            max_retained = min(len(retained_df), max(100, int(0.03 * total_baseline)))

        if len(retained_df) > max_retained:
            print(
                f"  Retained attacks ({len(retained_df)} rows) downsampled to {max_retained} rows "
                f"to maintain balance while preserving adversarial evasion exposure."
            )
            retained_df = retained_df.sample(
                n=max_retained, random_state=42
            ) if max_retained else retained_df.iloc[0:0]
        df = pd.concat([df, retained_df], ignore_index=True, sort=False)
    
    # Apply feedback
    # Analyst verdict maps to: FRAUD -> 1, LEGITIMATE -> 0
    feedback_df = feedback_df[feedback_df["analyst_verdict"].isin(["FRAUD", "LEGITIMATE"])]
    
    updated_count = 0
    new_rows = []
    id_col = "txn_id" if "txn_id" in df.columns else "transaction_id"

    for _, row in feedback_df.iterrows():
        tx_id = row["transaction_id"]
        verdict = 1 if row["analyst_verdict"] == "FRAUD" else 0
        
        mask = df[id_col] == tx_id
        if mask.any():
            # Force this transaction into the training set so the model learns it
            df.loc[mask, "split"] = "train"
            # Update the label to the analyst's ground truth
            df.loc[mask, "is_fraud"] = verdict
            updated_count += 1
        else:
            # If transaction is from live UI/simulator, synthesize a real training row with analyst ground truth
            template_subset = df[df["is_fraud"] == verdict]
            sample_dict = template_subset.iloc[0].to_dict() if len(template_subset) > 0 else df.iloc[0].to_dict()
            sample_dict[id_col] = tx_id
            sample_dict["is_fraud"] = verdict
            sample_dict["split"] = "train"
            new_rows.append(sample_dict)
            updated_count += 1

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True, sort=False)
            
    print(f"Applied {updated_count} analyst corrections to the training set.")
    
    # Re-train the model
    print("\nStarting retraining...")
    result = train_fraud_model(df)

    final_model = result["model"]
    preprocessor = result["preprocessor"]
    best_threshold = result["threshold"]
    val_m = result["metrics"]["validation_metrics"]
    test_m = result["metrics"]["test_metrics"]

    # Load old metadata (for both the version bump below and the quality
    # gate above it -- do this before touching any files on disk).
    old_version = 1
    old_pr_auc = None
    if backup_path.exists():
        with open(backup_path, "r", encoding="utf-8") as f:
            old_meta = json.load(f)
            old_pr_auc = old_meta.get("test_metrics", {}).get("pr_auc")
            ver_str = old_meta.get("model_version", "v1")
            try:
                if "_v" in ver_str:
                    num_part = ver_str.split("_v")[-1].split("_")[0]
                    old_version = int(num_part)
            except:
                pass

    # Quality gate: never let a retrain silently regress the deployed model.
    # See MAX_PR_AUC_REGRESSION's comment for why this exists.
    new_pr_auc = test_m.get("pr_auc")
    if old_pr_auc is not None and new_pr_auc is not None:
        regression = old_pr_auc - new_pr_auc
        if regression > MAX_PR_AUC_REGRESSION:
            print(
                f"\nRetrain REJECTED: new model's test PR-AUC ({new_pr_auc:.4f}) is "
                f"{regression:.4f} below the deployed model's ({old_pr_auc:.4f}), past the "
                f"{MAX_PR_AUC_REGRESSION:.2f} tolerance. Keeping the current model live."
            )
            # Feedback stays queued (not archived) so the next eligible run
            # can retry once the underlying data problem is fixed, rather
            # than silently discarding the analyst verdicts that triggered
            # this attempt.
            return False
        print(f"\nQuality gate passed: new PR-AUC {new_pr_auc:.4f} vs previous {old_pr_auc:.4f}.")
    else:
        print("\nQuality gate skipped: no previous model metadata to compare against.")

    # Save the new model and metadata
    print("Saving new model and metadata...")
    joblib.dump(final_model, MODELS_DIR / "fraud_model.pkl")
    joblib.dump(preprocessor, MODELS_DIR / "preprocessor.pkl")

    new_version = f"stage5_xgb_v{old_version + 1}_retrained"

    metadata = {
        "model_name": "Stage 5 Primary Fraud XGBoost (Retrained)",
        "model_version": new_version,
        "trained_timestamp": datetime.now().isoformat(),
        "random_seed": 42,
        "split_methodology": "temporal + analyst feedback override",
        "held_out_attack_family": "synthetic_identity_bustout",
        "selected_threshold": best_threshold,
        "validation_metrics": val_m,
        "test_metrics": test_m,
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Clear processed feedback by archiving it
    archive_path = store.feedback_dir / f"analyst_feedback_archived_{datetime.now():%Y%m%d_%H%M%S}.parquet"
    shutil.move(store.feedback_path, archive_path)
    print("Archived processed feedback.")
    
    print("=== Retraining Complete ===")
    return True

if __name__ == "__main__":
    run_retrain()
