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
    data_dir = Path(__file__).resolve().parent.parent / "data"
    for gen in ["gen3", "gen4", "gen5"]:
        retained_path = data_dir / f"{gen}_retained_attacks.parquet"
        if retained_path.exists():
            atk_df = pd.read_parquet(retained_path)
            # Retained attacks should be part of the training set
            atk_df["split"] = "train"
            df = pd.concat([df, atk_df], ignore_index=True)
            print(f"Loaded {len(atk_df)} retained attacks from {gen}.")
    
    # Apply feedback
    # Analyst verdict maps to: FRAUD -> 1, LEGITIMATE -> 0
    feedback_df = feedback_df[feedback_df["analyst_verdict"].isin(["FRAUD", "LEGITIMATE"])]
    
    updated_count = 0
    for _, row in feedback_df.iterrows():
        tx_id = row["transaction_id"]
        verdict = 1 if row["analyst_verdict"] == "FRAUD" else 0
        
        id_col = "txn_id" if "txn_id" in df.columns else "transaction_id"
        mask = df[id_col] == tx_id
        if mask.any():
            # Force this transaction into the training set so the model learns it
            df.loc[mask, "split"] = "train"
            # Update the label to the analyst's ground truth
            df.loc[mask, "is_fraud"] = verdict
            updated_count += 1
            
    print(f"Applied {updated_count} analyst corrections to the training set.")
    
    # Re-train the model
    print("\nStarting retraining...")
    result = train_fraud_model(df)
    
    final_model = result["model"]
    preprocessor = result["preprocessor"]
    best_threshold = result["threshold"]
    val_m = result["metrics"]["validation_metrics"]
    test_m = result["metrics"]["test_metrics"]
    
    # Save the new model and metadata
    print("\nSaving new model and metadata...")
    joblib.dump(final_model, MODELS_DIR / "fraud_model.pkl")
    joblib.dump(preprocessor, MODELS_DIR / "preprocessor.pkl")
    
    # Load old metadata to increment version
    old_version = 1
    if backup_path.exists():
        with open(backup_path, "r", encoding="utf-8") as f:
            old_meta = json.load(f)
            ver_str = old_meta.get("model_version", "v1")
            try:
                if "_v" in ver_str:
                    num_part = ver_str.split("_v")[-1].split("_")[0]
                    old_version = int(num_part)
            except:
                pass

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
