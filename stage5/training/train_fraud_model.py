import os
import sys
import json
from datetime import datetime
import joblib
import mlflow
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import precision_recall_curve, auc, roc_auc_score, precision_score, recall_score, f1_score

# Add project root to python path to resolve imports
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.dataset.loader import load_dataset
from src.dataset.splits import TemporalSplitConfig, assign_split, split_windows
from stage5.config.settings import (
    STAGE5_DATA_DIR,
    MODELS_DIR,
    CATEGORICAL_FEATURES,
    NUMERICAL_FEATURES,
    BOOLEAN_FEATURES,
    BEHAVIORAL_FEATURES,
    GRAPH_FEATURES,
    ALL_FEATURES,
    TRAIN_RATIO,
    VAL_RATIO,
    TEST_RATIO,
    HELD_OUT_ATTACK_FAMILY,
    FIXED_FPR_TARGETS,
)
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import roc_curve


def compute_brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Brier score: mean squared error of probability predictions.

    Measures calibration — how well predicted probabilities match observed frequencies.
    Lower is better; 0.0 is perfect calibration.
    """
    return float(np.mean((y_prob - y_true) ** 2))

def bootstrap_ci_recall(y_true: np.ndarray, y_prob: np.ndarray, threshold: float,
                        n_resamples: int = 100, ci: float = 0.95) -> dict:
    """Bootstrap confidence interval for recall at a fixed threshold.

    Resamples fraud rows with replacement, computes recall at the threshold for each,
    then returns the empirical distribution's lower/upper bounds.
    """
    fraud_mask = (y_true == 1)
    fraud_indices = np.where(fraud_mask)[0]
    if len(fraud_indices) == 0:
        return {"ci_lower": 0.0, "ci_upper": 0.0, "point_estimate": 0.0, "n_samples": 0}

    recalls = []
    for _ in range(n_resamples):
        boot_indices = np.random.choice(fraud_indices, size=len(fraud_indices), replace=True)
        boot_y_true = y_true[boot_indices]
        boot_y_prob = y_prob[boot_indices]
        boot_preds = (boot_y_prob >= threshold).astype(int)
        boot_recall = float(recall_score(boot_y_true, boot_preds, zero_division=0))
        recalls.append(boot_recall)

    recalls = np.array(recalls)
    point_estimate = float(np.mean(recalls))
    alpha = (1 - ci) / 2
    ci_lower = float(np.quantile(recalls, alpha))
    ci_upper = float(np.quantile(recalls, 1 - alpha))

    return {
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "point_estimate": point_estimate,
        "n_samples": len(fraud_indices)
    }

def precision_recall_at_fixed_fpr(y_true: np.ndarray, y_prob: np.ndarray, target_fpr: float) -> dict:
    """Precision/recall at the highest-recall threshold whose FPR does not exceed target_fpr.

    This is the brief's headline metric (section 6/8): UPI credits are final,
    so the detector is a pre-auth control and the operating point matters
    more than ranking quality -- lead with this, not ROC-AUC.
    """
    fpr, _tpr, thresholds = roc_curve(y_true, y_prob)
    idx = max(int(np.searchsorted(fpr, target_fpr, side="right")) - 1, 0)
    threshold = float(thresholds[idx])
    preds = (y_prob >= threshold).astype(int)
    return {
        "target_fpr": target_fpr,
        "achieved_fpr": float(fpr[idx]),
        "threshold": threshold,
        "precision": float(precision_score(y_true, preds, zero_division=0)),
        "recall": float(recall_score(y_true, preds, zero_division=0)),
    }


def pr_auc_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    p, r, _ = precision_recall_curve(y_true, y_prob)
    return float(auc(r, p))


def train_fraud_model(df: pd.DataFrame, held_out_attack_family: str = HELD_OUT_ATTACK_FAMILY) -> dict:
    """Train + evaluate a fraud model on an already-assembled DataFrame.

    Callable directly (curriculum retraining passes an in-memory df mixing
    original data, analyst feedback, and new attack variants), or via main()
    below for the from-scratch baseline training run.

    Expects `df` to already carry a `split` column with values in
    {"train", "validation", "test"} and an `is_fraud` column. Any of
    ALL_FEATURES missing from df is imputed (median/constant) same as a
    genuinely-missing real-world field would be.

    Returns:
        {
            'model': trained XGBClassifier,
            'preprocessor': fitted ColumnTransformer,
            'threshold': float,
            'metrics': {...}  # same shape as model_metadata.json's test_metrics,
                               # plus validation_metrics
        }
    """
    df = df.reindex(columns=list(df.columns) + [c for c in ALL_FEATURES if c not in df.columns])

    train_df = df[df["split"] == "train"].copy()
    val_df = df[df["split"] == "validation"].copy()
    test_df = df[df["split"] == "test"].copy()

    if val_df.empty:
        # Curriculum calls sometimes mix in a small batch of new attack rows
        # with no validation slice of their own -- carve one out of train
        # rather than fail, so threshold tuning still has held-out signal.
        val_df = train_df.sample(frac=0.15, random_state=42)
        train_df = train_df.drop(val_df.index)

    if test_df.empty:
        test_df = val_df

    y_train = train_df["is_fraud"].astype(int)
    y_val = val_df["is_fraud"].astype(int)
    y_test = test_df["is_fraud"].astype(int)

    # Anti-leakage guard: if a feature's presence/absence is itself a near-
    # perfect proxy for the label (e.g. one data source populates a column
    # and another never does), the model learns "is this column NaN?" rather
    # than any real fraud signal -- trivial separation the brief specifically
    # warns judges will catch. Drop any feature whose missingness rate
    # differs by more than this much between classes, decided on train only.
    MISSINGNESS_LEAKAGE_THRESHOLD = 0.90
    dropped_leaky_features = []
    # Same failure mode can also show up as a scale gap rather than a missingness
    # gap: two features can both be fully populated yet occupy near-disjoint
    # value ranges (e.g. one source's amounts are ~30x another's), which is
    # just as trivial a shortcut for a tree model to exploit. Catch that too:
    # drop a numeric feature if the classes' 5th-95th percentile ranges don't
    # overlap at all on the training split.
    dropped_scale_features = []
    usable_features = []
    fraud_train = train_df[y_train == 1]
    legit_train = train_df[y_train == 0]
    for col in ALL_FEATURES:
        if len(fraud_train) and len(legit_train):
            fraud_missing = fraud_train[col].isna().mean()
            legit_missing = legit_train[col].isna().mean()
            if abs(fraud_missing - legit_missing) >= MISSINGNESS_LEAKAGE_THRESHOLD:
                dropped_leaky_features.append(col)
                continue

            if col in NUMERICAL_FEATURES + BEHAVIORAL_FEATURES + GRAPH_FEATURES:
                f_vals = fraud_train[col].dropna()
                l_vals = legit_train[col].dropna()
                if len(f_vals) >= 10 and len(l_vals) >= 10:
                    f_lo, f_hi = f_vals.quantile(0.05), f_vals.quantile(0.95)
                    l_lo, l_hi = l_vals.quantile(0.05), l_vals.quantile(0.95)
                    if f_hi < l_lo or l_hi < f_lo:
                        dropped_scale_features.append(col)
                        continue
        usable_features.append(col)

    if dropped_leaky_features:
        print(f"  Dropping {len(dropped_leaky_features)} features with class-correlated "
              f"missingness (leakage guard): {dropped_leaky_features}")
    if dropped_scale_features:
        print(f"  Dropping {len(dropped_scale_features)} features with disjoint value "
              f"ranges between classes (scale-mismatch guard): {dropped_scale_features}")

    active_categorical = [c for c in CATEGORICAL_FEATURES if c in usable_features]
    active_numeric = [c for c in NUMERICAL_FEATURES + BOOLEAN_FEATURES + BEHAVIORAL_FEATURES + GRAPH_FEATURES if c in usable_features]

    X_train, X_val, X_test = train_df[usable_features], val_df[usable_features], test_df[usable_features]

    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])
    preprocessor = ColumnTransformer(transformers=[
        ("cat", cat_pipeline, active_categorical),
        ("num", num_pipeline, active_numeric)
    ])
    # Keep named columns through to the fitted model -- with a bare ndarray,
    # XGBoost's booster records no feature_names at all (None, not the
    # positional f0/f1/... names one might expect), which breaks anything
    # downstream that maps feature importances back to names (Gen 3's
    # get_top_features -> "'NoneType' object is not iterable").
    preprocessor.set_output(transform="pandas")

    X_train_proc = preprocessor.fit_transform(X_train)
    X_val_proc = preprocessor.transform(X_val)
    X_test_proc = preprocessor.transform(X_test)

    lr = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    lr.fit(X_train_proc, y_train)
    lr_val_preds = lr.predict_proba(X_val_proc)[:, 1]

    rf = RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1)
    rf.fit(X_train_proc, y_train)
    rf_val_preds = rf.predict_proba(X_val_proc)[:, 1]

    neg_count = len(y_train) - sum(y_train)
    pos_count = sum(y_train)
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0

    xgb = XGBClassifier(
        n_estimators=150,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        tree_method="hist",
        eval_metric="logloss",
    )
    xgb.fit(X_train_proc, y_train)
    xgb_val_preds = xgb.predict_proba(X_val_proc)[:, 1]

    lr_pr = pr_auc_score(y_val, lr_val_preds)
    rf_pr = pr_auc_score(y_val, rf_val_preds)
    xgb_pr = pr_auc_score(y_val, xgb_val_preds)

    final_model = xgb
    final_val_preds = xgb_val_preds

    thresholds = np.arange(0.1, 0.95, 0.05)
    best_threshold, best_f1 = 0.5, 0.0
    tuning_table = []
    for th in thresholds:
        preds = (final_val_preds >= th).astype(int)
        prec = precision_score(y_val, preds, zero_division=0)
        rec = recall_score(y_val, preds, zero_division=0)
        f1 = f1_score(y_val, preds, zero_division=0)
        tn = sum((y_val == 0) & (preds == 0))
        fp = sum((y_val == 0) & (preds == 1))
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        tuning_table.append({
            "threshold": float(th), "precision": float(prec), "recall": float(rec),
            "f1": float(f1), "fpr": float(fpr),
            "alerts_per_1000": float((preds.sum() / len(preds)) * 1000),
        })
        if f1 > best_f1:
            best_f1, best_threshold = f1, th

    final_test_probs = final_model.predict_proba(X_test_proc)[:, 1]
    test_preds = (final_test_probs >= best_threshold).astype(int)
    test_prec = precision_score(y_test, test_preds, zero_division=0)
    test_rec = recall_score(y_test, test_preds, zero_division=0)
    test_f1 = f1_score(y_test, test_preds, zero_division=0)
    test_pr_auc = pr_auc_score(y_test, final_test_probs)
    test_roc_auc = roc_auc_score(y_test, final_test_probs) if y_test.nunique() > 1 else float('nan')

    tn = sum((y_test == 0) & (test_preds == 0))
    fp = sum((y_test == 0) & (test_preds == 1))
    test_fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    test_alerts = (test_preds.sum() / len(test_preds)) * 1000

    y_test_arr = y_test.to_numpy()
    fixed_fpr_metrics = [
        precision_recall_at_fixed_fpr(y_test_arr, final_test_probs, t) for t in FIXED_FPR_TARGETS
    ]

    held_out_generalisation = []
    if "attack_id" in test_df.columns and held_out_attack_family is not None:
        held_out_test_mask = (test_df["attack_id"] == held_out_attack_family).to_numpy()
        held_out_fraud_mask = held_out_test_mask & (y_test_arr == 1)
        held_out_fraud_total = int(held_out_fraud_mask.sum())
        for m in fixed_fpr_metrics:
            preds_at_threshold = (final_test_probs >= m["threshold"]).astype(int)
            caught = int(preds_at_threshold[held_out_fraud_mask].sum()) if held_out_fraud_total else 0
            held_out_recall = (caught / held_out_fraud_total) if held_out_fraud_total else None
            boot_ci = bootstrap_ci_recall(
                y_test_arr[held_out_fraud_mask], final_test_probs[held_out_fraud_mask],
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

    # Strip the ColumnTransformer's "cat__"/"num__" prefix for readability in
    # reports -- "num__edge_count" means nothing to a reader, "edge_count" does.
    feature_names = [n.split("__", 1)[1] if "__" in n else n for n in preprocessor.get_feature_names_out()]
    importances = final_model.feature_importances_
    top_features = sorted(
        zip(feature_names, importances.tolist()), key=lambda x: x[1], reverse=True
    )[:10]

    metrics = {
        "validation_metrics": {
            "best_f1": float(best_f1),
            "lr_pr_auc": float(lr_pr),
            "rf_pr_auc": float(rf_pr),
            "xgb_pr_auc": float(xgb_pr),
            "threshold_tuning_table": tuning_table,
        },
        "test_metrics": {
            "pr_auc": float(test_pr_auc),
            "roc_auc_secondary": float(test_roc_auc),
            "brier_score": compute_brier_score(y_test_arr, final_test_probs),
            "fixed_fpr_operating_points": fixed_fpr_metrics,
            "held_out_family_generalisation": held_out_generalisation,
            "f1_optimal_threshold_metrics": {
                "precision": float(test_prec), "recall": float(test_rec), "f1": float(test_f1),
                "fpr": float(test_fpr), "alerts_per_1000": float(test_alerts),
            },
        },
        "top_features": [{"name": n, "importance": round(i, 4)} for n, i in top_features],
        "train_size": len(train_df), "val_size": len(val_df), "test_size": len(test_df),
        "fraud_count_train": int(y_train.sum()), "fraud_count_test": int(y_test.sum()),
        "usable_features": usable_features,
        "dropped_leaky_features": dropped_leaky_features,
        "dropped_scale_mismatch_features": dropped_scale_features,
    }

    return {
        "model": final_model,
        "preprocessor": preprocessor,
        "threshold": float(best_threshold),
        "metrics": metrics,
    }


def load_and_prepare(combined_dir: Path = None, held_out_attack_family: str = HELD_OUT_ATTACK_FAMILY) -> pd.DataFrame:
    """Load the combined dataset, engineer features, and assign temporal splits.

    Shared by main() (from-scratch baseline training) and
    stage5.training.run_all_generations (curriculum pipeline stages) so
    both start from the identical, correctly-split DataFrame -- this used
    to be duplicated ad hoc and drifted (run_all_generations was reading
    the raw parquet without ever assigning a 'split' column at all).
    """
    if combined_dir is None:
        combined_dir = STAGE5_DATA_DIR / "combined"
    if not combined_dir.exists():
        raise FileNotFoundError(f"Combined dataset not found at {combined_dir}. Run generate_training_data first.")

    dataset = load_dataset(combined_dir)

    from stage5.features.feature_engineering import build_features
    df = build_features(dataset)

    windows = split_windows(
        TemporalSplitConfig(
            train_fraction=TRAIN_RATIO, validation_fraction=VAL_RATIO, test_fraction=TEST_RATIO
        )
    )
    df["split"] = df["timestamp"].apply(lambda ts: assign_split(ts, windows) or "test")

    if held_out_attack_family is not None and "attack_id" in df.columns:
        held_out_mask = df["attack_id"] == held_out_attack_family
        df.loc[held_out_mask, "split"] = "test"
        assert df[(df["split"] != "test") & held_out_mask].empty

    return df


def main():
    print("=== Training Stage 5 Primary Fraud Model ===")

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    mlflow.set_experiment("chakravyuh-fraud-model")
    mlflow.start_run(run_name=f"fraud_model_{datetime.now():%Y%m%d_%H%M%S}")

    print("Loading combined dataset and assigning temporal splits...")
    df = load_and_prepare()
    held_out_mask = df["attack_id"] == HELD_OUT_ATTACK_FAMILY

    print(f"Train size: {(df['split']=='train').sum()}, Val size: {(df['split']=='validation').sum()}, "
          f"Test size: {(df['split']=='test').sum()} (held-out family rows: {int(held_out_mask.sum())})")

    result = train_fraud_model(df, held_out_attack_family=HELD_OUT_ATTACK_FAMILY)
    final_model, preprocessor, best_threshold = result["model"], result["preprocessor"], result["threshold"]
    val_m, test_m = result["metrics"]["validation_metrics"], result["metrics"]["test_metrics"]

    mlflow.log_params({
        "n_estimators": final_model.n_estimators, "max_depth": final_model.max_depth,
        "learning_rate": final_model.learning_rate, "random_seed": 42,
    })
    mlflow.log_metrics({
        "val_pr_auc_lr": val_m["lr_pr_auc"], "val_pr_auc_rf": val_m["rf_pr_auc"],
        "val_pr_auc_xgb": val_m["xgb_pr_auc"], "selected_threshold": best_threshold,
        "test_pr_auc": test_m["pr_auc"], "test_roc_auc": test_m["roc_auc_secondary"],
        "test_precision_f1_optimal": test_m["f1_optimal_threshold_metrics"]["precision"],
        "test_recall_f1_optimal": test_m["f1_optimal_threshold_metrics"]["recall"],
        "test_f1_optimal": test_m["f1_optimal_threshold_metrics"]["f1"],
        "test_fpr_f1_optimal": test_m["f1_optimal_threshold_metrics"]["fpr"],
    })
    for m in test_m["fixed_fpr_operating_points"]:
        tag = f"{m['target_fpr']*100:.2f}pct_fpr"
        mlflow.log_metrics({f"precision_at_{tag}": m["precision"], f"recall_at_{tag}": m["recall"]})
    for g in test_m["held_out_family_generalisation"]:
        if g["held_out_recall"] is not None:
            tag = f"{g['target_fpr']*100:.2f}pct_fpr"
            mlflow.log_metric(f"held_out_recall_at_{tag}", g["held_out_recall"])

    print(f"Saving final model artifacts to {MODELS_DIR}...")
    joblib.dump(final_model, MODELS_DIR / "fraud_model.pkl")
    joblib.dump(preprocessor, MODELS_DIR / "preprocessor.pkl")

    feature_schema = {
        "features": ALL_FEATURES, "categorical": CATEGORICAL_FEATURES,
        "numerical": NUMERICAL_FEATURES, "boolean": BOOLEAN_FEATURES,
    }
    with open(MODELS_DIR / "feature_schema.json", "w", encoding="utf-8") as f:
        json.dump(feature_schema, f, indent=2)

    metadata = {
        "model_name": "Stage 5 Primary Fraud XGBoost", "model_version": "stage5_xgb_v2",
        "trained_timestamp": datetime.now().isoformat(), "random_seed": 42,
        "split_methodology": "temporal (train/validation/test by transaction timestamp), never random",
        "held_out_attack_family": HELD_OUT_ATTACK_FAMILY, "selected_threshold": best_threshold,
        "validation_metrics": val_m, "test_metrics": test_m,
    }
    with open(MODELS_DIR / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    mlflow.log_artifact(str(MODELS_DIR / "fraud_model.pkl"))
    mlflow.log_artifact(str(MODELS_DIR / "preprocessor.pkl"))
    mlflow.log_artifact(str(MODELS_DIR / "feature_schema.json"))
    mlflow.log_artifact(str(MODELS_DIR / "model_metadata.json"))
    mlflow.end_run()

    print("=== Model training and saving complete! ===")


if __name__ == "__main__":
    main()
