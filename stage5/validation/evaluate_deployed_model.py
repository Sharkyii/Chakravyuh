"""Evaluate whatever model/preprocessor currently sit in MODELS_DIR against the
primary held-out temporal test split, using the same metrics suite as
train_fraud_model.py's from-scratch training run.

run_all_generations.py's curriculum stages (gen3/4/5) promote their retrained
model/preprocessor into MODELS_DIR for live inference but never rewrite
model_metadata.json -- so model_metadata.json (and the live API's /api/metrics
panel, which reads it) kept showing the pre-curriculum baseline's numbers even
after a curriculum-hardened model (e.g. Gen 5) was deployed. Run this after
any promotion to MODELS_DIR to recompute+overwrite model_metadata.json's
test_metrics with the actually-deployed model's real accuracy.
"""
import sys
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage5.config.settings import MODELS_DIR, HELD_OUT_ATTACK_FAMILY, FIXED_FPR_TARGETS, ALL_FEATURES
from stage5.training.train_fraud_model import (
    load_and_prepare,
    compute_brier_score,
    precision_recall_at_fixed_fpr,
    pr_auc_score,
    bootstrap_ci_recall,
)


def _find_f1_optimal_threshold(y_val: np.ndarray, val_probs: np.ndarray) -> float:
    """Same sweep train_fraud_model() uses to pick selected_threshold, run here
    against the deployed model's own validation-split predictions -- a curriculum
    retrain can shift the probability distribution enough that a threshold
    picked for an earlier checkpoint (e.g. the pre-curriculum baseline) no
    longer sits where this checkpoint's F1 actually peaks.
    """
    best_threshold, best_f1 = 0.5, 0.0
    for th in np.arange(0.1, 0.95, 0.05):
        preds = (val_probs >= th).astype(int)
        f1 = f1_score(y_val, preds, zero_division=0)
        if f1 > best_f1:
            best_f1, best_threshold = f1, float(th)
    return best_threshold


def evaluate_deployed_model(held_out_attack_family: str = HELD_OUT_ATTACK_FAMILY) -> dict:
    print("Loading dataset + assigning temporal splits...")
    df = load_and_prepare(held_out_attack_family=held_out_attack_family)
    val_df = df[df["split"] == "validation"].copy()
    test_df = df[df["split"] == "test"].copy()
    y_val = val_df["is_fraud"].astype(int)
    y_test = test_df["is_fraud"].astype(int)

    print(f"Loading deployed model/preprocessor from {MODELS_DIR}...")
    model = joblib.load(MODELS_DIR / "fraud_model.pkl")
    preprocessor = joblib.load(MODELS_DIR / "preprocessor.pkl")

    X_val = val_df.reindex(columns=list(val_df.columns) + [c for c in ALL_FEATURES if c not in val_df.columns])
    X_test = test_df.reindex(columns=list(test_df.columns) + [c for c in ALL_FEATURES if c not in test_df.columns])
    val_probs = model.predict_proba(preprocessor.transform(X_val[ALL_FEATURES]))[:, 1]
    probs = model.predict_proba(preprocessor.transform(X_test[ALL_FEATURES]))[:, 1]

    selected_threshold = _find_f1_optimal_threshold(y_val.to_numpy(), val_probs)
    y_test_arr = y_test.to_numpy()
    pr_auc = pr_auc_score(y_test_arr, probs)
    roc_auc = roc_auc_score(y_test_arr, probs) if y_test.nunique() > 1 else float("nan")
    brier = compute_brier_score(y_test_arr, probs)

    fixed_fpr_metrics = [precision_recall_at_fixed_fpr(y_test_arr, probs, t) for t in FIXED_FPR_TARGETS]

    held_out_generalisation = []
    if "attack_id" in test_df.columns and held_out_attack_family is not None:
        held_out_test_mask = (test_df["attack_id"] == held_out_attack_family).to_numpy()
        held_out_fraud_mask = held_out_test_mask & (y_test_arr == 1)
        held_out_fraud_total = int(held_out_fraud_mask.sum())
        for m in fixed_fpr_metrics:
            preds_at_threshold = (probs >= m["threshold"]).astype(int)
            caught = int(preds_at_threshold[held_out_fraud_mask].sum()) if held_out_fraud_total else 0
            held_out_recall = (caught / held_out_fraud_total) if held_out_fraud_total else None
            boot_ci = bootstrap_ci_recall(
                y_test_arr[held_out_fraud_mask], probs[held_out_fraud_mask],
                m["threshold"], n_resamples=100, ci=0.95
            ) if held_out_fraud_total else {"ci_lower": None, "ci_upper": None, "point_estimate": None, "n_samples": 0}
            held_out_generalisation.append({
                "target_fpr": m["target_fpr"], "threshold": m["threshold"],
                "held_out_fraud_total": held_out_fraud_total, "held_out_fraud_caught": caught,
                "held_out_recall": held_out_recall,
                "held_out_recall_95ci": {
                    "point": boot_ci["point_estimate"], "lower": boot_ci["ci_lower"], "upper": boot_ci["ci_upper"],
                },
            })

    preds_sel = (probs >= selected_threshold).astype(int)
    tn = int(((y_test_arr == 0) & (preds_sel == 0)).sum())
    fp = int(((y_test_arr == 0) & (preds_sel == 1)).sum())
    fpr_sel = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    test_metrics = {
        "pr_auc": float(pr_auc),
        "roc_auc_secondary": float(roc_auc),
        "brier_score": brier,
        "fixed_fpr_operating_points": fixed_fpr_metrics,
        "held_out_family_generalisation": held_out_generalisation,
        "f1_optimal_threshold_metrics": {
            "precision": float(precision_score(y_test_arr, preds_sel, zero_division=0)),
            "recall": float(recall_score(y_test_arr, preds_sel, zero_division=0)),
            "f1": float(f1_score(y_test_arr, preds_sel, zero_division=0)),
            "fpr": float(fpr_sel),
            "alerts_per_1000": float((preds_sel.sum() / len(preds_sel)) * 1000),
        },
    }
    return {
        "test_metrics": test_metrics,
        "test_size": len(test_df),
        "fraud_count_test": int(y_test.sum()),
        "selected_threshold": selected_threshold,
    }


def main():
    result = evaluate_deployed_model()
    metadata_path = MODELS_DIR / "model_metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    metadata["test_metrics"] = result["test_metrics"]
    metadata["selected_threshold"] = result["selected_threshold"]
    metadata["evaluated_timestamp"] = datetime.now().isoformat()
    metadata["evaluation_note"] = (
        "test_metrics recomputed directly against the model/preprocessor actually "
        "deployed in MODELS_DIR (post-curriculum), not the pre-curriculum baseline "
        "that train_fraud_model.main() originally wrote here."
    )
    metadata_path.write_text(json.dumps(metadata, indent=2))

    tm = result["test_metrics"]
    print(f"\nTest size: {result['test_size']} (fraud: {result['fraud_count_test']})")
    print(f"Selected (F1-optimal) threshold: {result['selected_threshold']:.4f}")
    print(f"PR-AUC: {tm['pr_auc']:.4f}  ROC-AUC: {tm['roc_auc_secondary']:.4f}  Brier: {tm['brier_score']:.6f}")
    for m in tm["fixed_fpr_operating_points"]:
        print(f"  @ {m['target_fpr']*100:.2f}% FPR: threshold={m['threshold']:.4f} "
              f"precision={m['precision']:.3f} recall={m['recall']:.3f}")
    for g in tm["held_out_family_generalisation"]:
        print(f"  held-out family recall @ {g['target_fpr']*100:.2f}% FPR: {g['held_out_recall']}")
    print(f"\nUpdated {metadata_path}")


if __name__ == "__main__":
    main()
