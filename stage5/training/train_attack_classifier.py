import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

# Add project root to python path to resolve imports
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.dataset.loader import load_dataset
from stage5.config.settings import STAGE5_DATA_DIR, MODELS_DIR, ALL_FEATURES

def main():
    print("=== Training Stage 5 Attack Family Classifier ===")
    
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
    
    # 3. Filter only fraudulent transactions for attack classification
    fraud_df = df[df["is_fraud"] == True].copy()
    if len(fraud_df) == 0:
        print("Error: No fraudulent transactions found to train the attack classifier!")
        sys.exit(1)
        
    print(f"Found {len(fraud_df)} fraudulent transactions for training.")
    
    # Sort/identify all unique attack families present
    attack_ids = sorted(fraud_df["attack_id"].unique())
    attack_to_idx = {name: idx for idx, name in enumerate(attack_ids)}
    idx_to_attack = {idx: name for idx, name in enumerate(attack_ids)}
    print(f"Attack classes to learn: {attack_ids}")
    
    fraud_df["attack_label"] = fraud_df["attack_id"].map(attack_to_idx)
    
    # 4. Load the fitted preprocessor to transform features identically
    preprocessor_path = MODELS_DIR / "preprocessor.pkl"
    if not preprocessor_path.exists():
        print(f"Error: Preprocessor not found at {preprocessor_path}. Train the fraud model first.")
        sys.exit(1)
    preprocessor = joblib.load(preprocessor_path)
    
    # 5. Split train/validation/test ensuring campaign-level isolation
    # Use a reproducible random seed for shuffling
    np.random.seed(42)
    unique_campaigns = sorted(fraud_df["campaign_id"].dropna().unique())
    np.random.shuffle(unique_campaigns)
    n_camps = len(unique_campaigns)
    n_train_camp = int(n_camps * 0.70)
    n_val_camp = int(n_camps * 0.15)
    train_camps = set(unique_campaigns[:n_train_camp])
    val_camps = set(unique_campaigns[n_train_camp:n_train_camp + n_val_camp])
    test_camps = set(unique_campaigns[n_train_camp + n_val_camp:])
    train_df = fraud_df[fraud_df["campaign_id"].isin(train_camps)].copy()
    val_df = fraud_df[fraud_df["campaign_id"].isin(val_camps)].copy()
    test_df = fraud_df[fraud_df["campaign_id"].isin(test_camps)].copy()
    
    # Prepare features and targets
    X_train = train_df[ALL_FEATURES]
    y_train = train_df["attack_label"]
    
    X_val = val_df[ALL_FEATURES]
    y_val = val_df["attack_label"]
    
    X_test = test_df[ALL_FEATURES]
    y_test = test_df["attack_label"]
    
    # Preprocess features
    X_train_proc = preprocessor.transform(X_train)
    X_val_proc = preprocessor.transform(X_val)
    X_test_proc = preprocessor.transform(X_test)
    
    # 6. Train Baseline Model 1: RandomForest Classifier
    print("Training Baseline Model: Multi-class RandomForest classifier...")
    rf_model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced"
    )
    rf_model.fit(X_train_proc, y_train)
    
    # Evaluate RandomForest on Test Set
    rf_test_preds = rf_model.predict(X_test_proc)
    rf_test_acc = accuracy_score(y_test, rf_test_preds)
    rf_test_macro_f1 = f1_score(y_test, rf_test_preds, average="macro", zero_division=0)
    rf_test_weighted_f1 = f1_score(y_test, rf_test_preds, average="weighted", zero_division=0)
    
    print("\n================================================")
    print("   RandomForest Classifier (Baseline) Metrics   ")
    print("================================================")
    print(f"Accuracy:    {rf_test_acc:.4f}")
    print(f"Macro F1:    {rf_test_macro_f1:.4f}")
    print(f"Weighted F1: {rf_test_weighted_f1:.4f}")
    
    y_test_names = [idx_to_attack[idx] for idx in y_test]
    rf_test_pred_names = [idx_to_attack[idx] for idx in rf_test_preds]
    print("\nRandomForest Classification Report:")
    print(classification_report(y_test_names, rf_test_pred_names, zero_division=0))
    
    # 7. Train Model 2: XGBoost Classifier (Experiment)
    print("\nTraining Model 2: Multi-class XGBoost classifier...")
    # Handle class imbalance using training sample weights
    train_sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)
    
    xgb_model = XGBClassifier(
        n_estimators=150,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        n_jobs=-1,
        eval_metric="mlogloss"
    )
    xgb_model.fit(X_train_proc, y_train, sample_weight=train_sample_weights)
    
    # Evaluate XGBoost on Test Set
    xgb_test_preds = xgb_model.predict(X_test_proc)
    xgb_test_acc = accuracy_score(y_test, xgb_test_preds)
    xgb_test_macro_f1 = f1_score(y_test, xgb_test_preds, average="macro", zero_division=0)
    xgb_test_weighted_f1 = f1_score(y_test, xgb_test_preds, average="weighted", zero_division=0)
    
    print("\n================================================")
    print("     XGBoost Classifier (Experiment) Metrics    ")
    print("================================================")
    print(f"Accuracy:    {xgb_test_acc:.4f}")
    print(f"Macro F1:    {xgb_test_macro_f1:.4f}")
    print(f"Weighted F1: {xgb_test_weighted_f1:.4f}")
    
    xgb_test_pred_names = [idx_to_attack[idx] for idx in xgb_test_preds]
    print("\nXGBoost Classification Report:")
    print(classification_report(y_test_names, xgb_test_pred_names, zero_division=0))
    
    # 8. Save Best Model
    if xgb_test_macro_f1 > rf_test_macro_f1:
        print(f"\nXGBoost outperforms RandomForest (Macro F1: {xgb_test_macro_f1:.4f} vs {rf_test_macro_f1:.4f}).")
        best_model = xgb_model
        model_name = "XGBoost"
    else:
        print(f"\nRandomForest outperforms XGBoost (Macro F1: {rf_test_macro_f1:.4f} vs {xgb_test_macro_f1:.4f}).")
        best_model = rf_model
        model_name = "RandomForest"
        
    print(f"Saving final attack classifier ({model_name}) to {MODELS_DIR}...")
    joblib.dump(best_model, MODELS_DIR / "attack_classifier.pkl")
    
    # Save class mapping
    class_mappings = {
        "attack_to_idx": attack_to_idx,
        "idx_to_attack": idx_to_attack
    }
    with open(MODELS_DIR / "attack_class_mapping.json", "w", encoding="utf-8") as f:
        json.dump(class_mappings, f, indent=2)
        
    print("=== Attack classifier training and saving complete! ===")

if __name__ == "__main__":
    main()
