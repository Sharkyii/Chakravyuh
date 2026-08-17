import os
import sys
import json
from datetime import datetime
import joblib
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
from stage5.config.settings import (
    STAGE5_DATA_DIR,
    MODELS_DIR,
    CATEGORICAL_FEATURES,
    NUMERICAL_FEATURES,
    BOOLEAN_FEATURES,
    BEHAVIORAL_FEATURES,
    GRAPH_FEATURES,
    ALL_FEATURES
)
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

def main():
    print("=== Training Stage 5 Primary Fraud Model ===")
    
    # 1. Load data
    combined_dir = STAGE5_DATA_DIR / "combined"
    if not combined_dir.exists():
        print(f"Error: Combined dataset not found at {combined_dir}. Please run generate_training_data.py first.")
        sys.exit(1)
        
    print("Loading combined dataset...")
    dataset = load_dataset(combined_dir)
    
    # 2. Build feature DataFrame
    from stage5.features.feature_engineering import build_features
    df = build_features(dataset)
    
    # 3. Scenario-level split to prevent leakage
    print("Splitting dataset into train/validation/test splits...")
    
    # Extract unique scenario IDs
    unique_scenarios = sorted(df[df["campaign_id"].notna()]["campaign_id"].unique())
    np.random.seed(42)
    np.random.shuffle(unique_scenarios)
    
    n_scen = len(unique_scenarios)
    n_train_scen = int(n_scen * 0.70)
    n_val_scen = int(n_scen * 0.15)
    
    train_scenarios = set(unique_scenarios[:n_train_scen])
    val_scenarios = set(unique_scenarios[n_train_scen:n_train_scen + n_val_scen])
    test_scenarios = set(unique_scenarios[n_train_scen + n_val_scen:])
    
    # Split baseline (non-scenario) transactions by payer to avoid user-level leakage
    baseline_mask = df["campaign_id"].isna()
    unique_payers = sorted(df[baseline_mask]["payer_id"].unique())
    np.random.shuffle(unique_payers)
    
    n_pay = len(unique_payers)
    n_train_pay = int(n_pay * 0.70)
    n_val_pay = int(n_pay * 0.15)
    
    train_payers = set(unique_payers[:n_train_pay])
    val_payers = set(unique_payers[n_train_pay:n_train_pay + n_val_pay])
    test_payers = set(unique_payers[n_train_pay + n_val_pay:])
    
    def get_split(row):
        scen = row["campaign_id"]
        if pd.notna(scen) and scen:
            if scen in train_scenarios:
                return "train"
            elif scen in val_scenarios:
                return "val"
            else:
                return "test"
        else:
            pay = row["payer_id"]
            if pay in train_payers:
                return "train"
            elif pay in val_payers:
                return "val"
            else:
                return "test"
                
    df["split"] = df.apply(get_split, axis=1)
    
    train_df = df[df["split"] == "train"].copy()
    val_df = df[df["split"] == "val"].copy()
    test_df = df[df["split"] == "test"].copy()
    
    print(f"Train size: {len(train_df)} transactions (Fraud count: {train_df['is_fraud'].sum()})")
    print(f"Val size: {len(val_df)} transactions (Fraud count: {val_df['is_fraud'].sum()})")
    print(f"Test size: {len(test_df)} transactions (Fraud count: {test_df['is_fraud'].sum()})")
    
    # 4. Prepare X and y
    X_train = train_df[ALL_FEATURES]
    y_train = train_df["is_fraud"].astype(int)
    
    X_val = val_df[ALL_FEATURES]
    y_val = val_df["is_fraud"].astype(int)
    
    X_test = test_df[ALL_FEATURES]
    y_test = test_df["is_fraud"].astype(int)
    
    # 5. Fit Preprocessing Pipeline
    print("Fitting preprocessing pipeline...")
    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])
    
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])
    
    preprocessor = ColumnTransformer(transformers=[
        ("cat", cat_pipeline, CATEGORICAL_FEATURES),
        ("num", num_pipeline, NUMERICAL_FEATURES + BOOLEAN_FEATURES + BEHAVIORAL_FEATURES + GRAPH_FEATURES)
    ])
    
    X_train_proc = preprocessor.fit_transform(X_train)
    X_val_proc = preprocessor.transform(X_val)
    X_test_proc = preprocessor.transform(X_test)
    
    # 6. Train Models
    # Model 1: Logistic Regression
    print("Training Model 1: Logistic Regression...")
    lr = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    lr.fit(X_train_proc, y_train)
    lr_val_preds = lr.predict_proba(X_val_proc)[:, 1]
    
    # Model 2: Random Forest
    print("Training Model 2: Random Forest...")
    rf = RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1)
    rf.fit(X_train_proc, y_train)
    rf_val_preds = rf.predict_proba(X_val_proc)[:, 1]
    
    # Model 3: XGBoost (Primary Candidate)
    print("Training Model 3: XGBoost...")
    # Calculate scale_pos_weight
    neg_count = len(y_train) - sum(y_train)
    pos_count = sum(y_train)
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0
    print(f"XGBoost scale_pos_weight calculated: {scale_pos_weight:.2f}")
    
    xgb = XGBClassifier(
        n_estimators=150,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
        eval_metric="logloss"
    )
    xgb.fit(X_train_proc, y_train)
    xgb_val_preds = xgb.predict_proba(X_val_proc)[:, 1]
    
    # Compare validation performance (PR-AUC)
    def pr_auc(y_true, y_prob):
        p, r, _ = precision_recall_curve(y_true, y_prob)
        return auc(r, p)
        
    lr_pr = pr_auc(y_val, lr_val_preds)
    rf_pr = pr_auc(y_val, rf_val_preds)
    xgb_pr = pr_auc(y_val, xgb_val_preds)
    
    print(f"Validation PR-AUC -> Logistic Regression: {lr_pr:.4f}, Random Forest: {rf_pr:.4f}, XGBoost: {xgb_pr:.4f}")
    
    # Select XGBoost as the final model
    final_model = xgb
    final_val_preds = xgb_val_preds
    
    # 7. Threshold Tuning on Validation Set
    print("Tuning decision threshold on validation set...")
    thresholds = np.arange(0.1, 0.95, 0.05)
    best_threshold = 0.5
    best_f1 = 0.0
    tuning_table = []
    
    for th in thresholds:
        preds = (final_val_preds >= th).astype(int)
        prec = precision_score(y_val, preds, zero_division=0)
        rec = recall_score(y_val, preds, zero_division=0)
        f1 = f1_score(y_val, preds, zero_division=0)
        
        # FPR calculation
        tn = sum((y_val == 0) & (preds == 0))
        fp = sum((y_val == 0) & (preds == 1))
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        # Alerts per 1000
        alerts_per_1000 = (preds.sum() / len(preds)) * 1000
        
        tuning_table.append({
            "threshold": float(th),
            "precision": float(prec),
            "recall": float(rec),
            "f1": float(f1),
            "fpr": float(fpr),
            "alerts_per_1000": float(alerts_per_1000)
        })
        
        # Optimize for F1 score
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = th
            
    print(f"Optimal threshold selected: {best_threshold:.2f} (Val F1: {best_f1:.4f})")
    
    # 8. Unbiased Evaluation on Untouched Test Set
    print("Running final evaluation on untouched Test Set...")
    final_test_probs = final_model.predict_proba(X_test_proc)[:, 1]
    test_preds = (final_test_probs >= best_threshold).astype(int)
    
    test_prec = precision_score(y_test, test_preds, zero_division=0)
    test_rec = recall_score(y_test, test_preds, zero_division=0)
    test_f1 = f1_score(y_test, test_preds, zero_division=0)
    test_pr_auc = pr_auc(y_test, final_test_probs)
    test_roc_auc = roc_auc_score(y_test, final_test_probs)
    
    tn = sum((y_test == 0) & (test_preds == 0))
    fp = sum((y_test == 0) & (test_preds == 1))
    test_fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    test_alerts = (test_preds.sum() / len(test_preds)) * 1000
    
    print("\n--- Final Test Set Metrics ---")
    print(f"PR-AUC:    {test_pr_auc:.4f}")
    print(f"ROC-AUC:   {test_roc_auc:.4f}")
    print(f"Precision: {test_prec:.4f}")
    print(f"Recall:    {test_rec:.4f}")
    print(f"F1 Score:  {test_f1:.4f}")
    print(f"FPR:       {test_fpr:.4f}")
    print(f"Alerts per 1,000 transactions: {test_alerts:.2f}")
    
    # 9. Save Model Artifacts
    print(f"Saving final model artifacts to {MODELS_DIR}...")
    joblib.dump(final_model, MODELS_DIR / "fraud_model.pkl")
    joblib.dump(preprocessor, MODELS_DIR / "preprocessor.pkl")
    
    # Save feature schema
    feature_schema = {
        "features": ALL_FEATURES,
        "categorical": CATEGORICAL_FEATURES,
        "numerical": NUMERICAL_FEATURES,
        "boolean": BOOLEAN_FEATURES
    }
    with open(MODELS_DIR / "feature_schema.json", "w", encoding="utf-8") as f:
        json.dump(feature_schema, f, indent=2)
        
    # Save model metadata
    metadata = {
        "model_name": "Stage 5 Primary Fraud XGBoost",
        "model_version": "stage5_xgb_v1",
        "trained_timestamp": datetime.now().isoformat(),
        "random_seed": 42,
        "selected_threshold": float(best_threshold),
        "validation_metrics": {
            "best_f1": float(best_f1),
            "lr_pr_auc": float(lr_pr),
            "rf_pr_auc": float(rf_pr),
            "xgb_pr_auc": float(xgb_pr),
            "threshold_tuning_table": tuning_table
        },
        "test_metrics": {
            "pr_auc": float(test_pr_auc),
            "roc_auc": float(test_roc_auc),
            "precision": float(test_prec),
            "recall": float(test_rec),
            "f1": float(test_f1),
            "fpr": float(test_fpr),
            "alerts_per_1000": float(test_alerts)
        }
    }
    with open(MODELS_DIR / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    print("=== Model training and saving complete! ===")

if __name__ == "__main__":
    main()
