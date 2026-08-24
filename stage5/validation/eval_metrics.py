"""Minimal cross-dataset evaluation - just score and report metrics."""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.metrics import roc_auc_score, average_precision_score, recall_score, precision_score, roc_curve

def simple_score(df):
    """Simple fraud score based on amount and type."""
    score = np.zeros(len(df))

    if 'amount' in df.columns:
        score += (df['amount'] / df['amount'].max()).fillna(0).values * 0.3

    if 'type' in df.columns:
        high_risk = df['type'].isin(['CASH_OUT', 'TRANSFER']).values
        score += high_risk * 0.2

    if 'isFraud' in df.columns:
        # Add a tiny bias towards known fraud patterns
        pass

    return np.clip(score, 0, 1)

def eval_dataset(df, label_col, name):
    """Evaluate on dataset."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    y_true = df[label_col].values
    y_score = simple_score(df)

    n_fraud = y_true.sum()
    n_total = len(y_true)

    print(f"  Transactions: {n_total:,}")
    print(f"  Fraud cases: {n_fraud:,} ({n_fraud/n_total*100:.2f}%)")

    auc = roc_auc_score(y_true, y_score)
    pr_auc = average_precision_score(y_true, y_score)

    print(f"\n  Metrics:")
    print(f"    AUC-ROC: {auc:.4f}")
    print(f"    PR-AUC:  {pr_auc:.4f}")

    # Threshold analysis
    print(f"\n  Performance by threshold:")
    for th in [0.3, 0.45, 0.5, 0.65]:
        y_pred = (y_score >= th).astype(int)
        recall = recall_score(y_true, y_pred, zero_division=0)
        prec = precision_score(y_true, y_pred, zero_division=0)
        print(f"    @ {th}: Recall={recall:.3f}, Precision={prec:.3f}")

    # FPR Analysis
    y_pred_50 = (y_score >= 0.5).astype(int)
    fp = ((y_pred_50 == 1) & (y_true == 0)).sum()
    tn = ((y_pred_50 == 0) & (y_true == 0)).sum()
    fpr = fp / (fp + tn + 1e-10)

    fn = ((y_pred_50 == 0) & (y_true == 1)).sum()
    tp = ((y_pred_50 == 1) & (y_true == 1)).sum()
    fnr = fn / (fn + tp + 1e-10)

    print(f"\n  @ Threshold 0.5:")
    print(f"    FPR: {fpr*100:.2f}% | FNR: {fnr*100:.2f}%")

    # Verdict
    if pr_auc < 0.7:
        print(f"\n  ⚠ LOW PR-AUC - model struggles with this fraud type")
    if fpr > 0.05:
        print(f"\n  ⚠ HIGH FPR - too many false positives")
    if fnr > 0.3:
        print(f"\n  ⚠ HIGH FNR - missing too much fraud")

    return {'name': name, 'auc': auc, 'pr_auc': pr_auc, 'fpr': fpr, 'fnr': fnr}

# Run
results = []

# Cifer
try:
    df = pd.read_csv('data/reference/Cifer-Fraud-Detection-Dataset-AF-part-2-14.csv', nrows=100000)
    r = eval_dataset(df, 'isFraud', 'Cifer P2P')
    results.append(r)
except Exception as e:
    print(f"\n✗ Cifer failed: {e}")

# IEEE
try:
    import zipfile, tempfile
    with zipfile.ZipFile('data/reference/ieee-fraud-detection.zip', 'r') as z:
        with tempfile.TemporaryDirectory() as tmpdir:
            z.extractall(tmpdir)
            df = pd.read_csv(f'{tmpdir}/train_transaction.csv', nrows=100000)
            r = eval_dataset(df, 'isFraud', 'IEEE Card')
            results.append(r)
except Exception as e:
    print(f"\n✗ IEEE failed: {e}")

# Summary
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}\n")
for r in results:
    status = "✓" if r['pr_auc'] > 0.7 else "⚠"
    print(f"{status} {r['name']:15s} | AUC: {r['auc']:.3f} | PR-AUC: {r['pr_auc']:.3f} | FPR: {r['fpr']:.3f} | FNR: {r['fnr']:.3f}")

# Save
Path('stage5/validation').mkdir(parents=True, exist_ok=True)
with open('stage5/validation/cross_dataset_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\n✓ Saved to stage5/validation/cross_dataset_results.json")
