"""
Lookalike Fidelity Check: are legitimate lookalike rows actually hard to
separate from fraud rows, or trivially different?

Per the brief: "Without them [lookalikes] the classifier separates two
trivially different distributions, reports 0.99 AUC, and any judge who has
worked in payments knows the number is meaningless."

This loads the same combined dataset + feature pipeline train_fraud_model.py
uses (load_dataset -> build_features), then compares fraud rows against their
paired legit-lookalike rows and against the general legitimate population.
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import euclidean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.dataset.loader import load_dataset
from stage5.features.feature_engineering import build_features
from stage5.config.settings import NUMERICAL_FEATURES, BEHAVIORAL_FEATURES, GRAPH_FEATURES


def load_training_data():
    combined_dir = Path('data/generated/stage5/combined')
    if not combined_dir.exists():
        return None
    dataset = load_dataset(combined_dir)
    return build_features(dataset)


def analyze_lookalike_fidelity(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"status": "FAIL", "reason": "No training data loaded"}

    is_fraud = df['is_fraud'] == 1
    is_lookalike = df.get('is_legit_lookalike', pd.Series(False, index=df.index)).fillna(False).astype(bool)
    is_legitimate = (~is_fraud) & (~is_lookalike)

    fraud_count, lookalike_count, legit_count = int(is_fraud.sum()), int(is_lookalike.sum()), int(is_legitimate.sum())

    print(f"\nDataset composition:")
    print(f"  Fraud rows:      {fraud_count:,}")
    print(f"  Lookalike rows:  {lookalike_count:,}")
    print(f"  Legitimate rows: {legit_count:,}")
    print(f"  Total:           {len(df):,}")

    if fraud_count == 0 or lookalike_count == 0:
        return {
            "status": "INCOMPLETE",
            "reason": f"No fraud ({fraud_count}) or no lookalikes ({lookalike_count})",
            "composition": {"fraud": fraud_count, "lookalike": lookalike_count, "legitimate": legit_count},
        }

    numeric_cols = [c for c in NUMERICAL_FEATURES + BEHAVIORAL_FEATURES + GRAPH_FEATURES if c in df.columns]
    print(f"  Numeric features analyzed: {len(numeric_cols)}")

    fraud_rows = df.loc[is_fraud, numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0).values
    lookalike_rows = df.loc[is_lookalike, numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0).values
    legit_sample_n = min(5000, legit_count)
    legit_rows = (
        df.loc[is_legitimate, numeric_cols]
        .sample(legit_sample_n, random_state=42)
        .apply(pd.to_numeric, errors='coerce')
        .fillna(0)
        .values
    )

    # Scale each feature by its overall std so no single large-magnitude
    # feature (e.g. amount) dominates the Euclidean distance.
    all_std = df[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0).values.std(axis=0)
    all_std[all_std == 0] = 1.0
    fraud_scaled = fraud_rows / all_std
    lookalike_scaled = lookalike_rows / all_std
    legit_scaled = legit_rows / all_std

    fraud_centroid = fraud_scaled.mean(axis=0)
    lookalike_centroid = lookalike_scaled.mean(axis=0)
    legit_centroid = legit_scaled.mean(axis=0)

    fraud_to_lookalike_dist = euclidean(fraud_centroid, lookalike_centroid)
    fraud_to_legit_dist = euclidean(fraud_centroid, legit_centroid)
    lookalike_to_legit_dist = euclidean(lookalike_centroid, legit_centroid)

    overlap_count = 0
    for i in range(len(numeric_cols)):
        f_mean, l_mean = fraud_rows[:, i].mean(), lookalike_rows[:, i].mean()
        f_std, l_std = fraud_rows[:, i].std() + 1e-6, lookalike_rows[:, i].std() + 1e-6
        f_range = (f_mean - f_std, f_mean + f_std)
        l_range = (l_mean - l_std, l_mean + l_std)
        if not (f_range[1] < l_range[0] or l_range[1] < f_range[0]):
            overlap_count += 1
    overlap_pct = (overlap_count / len(numeric_cols)) * 100

    print(f"\n  Feature overlap (fraud vs lookalike): {overlap_pct:.1f}% of features have overlapping ranges")
    print(f"\n  Centroid distances (std-scaled):")
    print(f"    Fraud <-> Lookalike: {fraud_to_lookalike_dist:.3f}")
    print(f"    Fraud <-> Legit:     {fraud_to_legit_dist:.3f}")
    print(f"    Lookalike <-> Legit: {lookalike_to_legit_dist:.3f}")

    separation_ratio = fraud_to_lookalike_dist / (lookalike_to_legit_dist + 1e-6)
    print(f"\n  Separation ratio (Fraud-Lookalike / Lookalike-Legit): {separation_ratio:.2f}")
    print(f"    < 1.0 = lookalikes sit closer to fraud (GOOD -- hard negative)")
    print(f"    > 1.0 = lookalikes sit closer to legit (BAD -- trivial separation risk)")

    if separation_ratio > 1.5 or overlap_pct < 30:
        verdict, reason = "FAIL", "Lookalikes too similar to legitimate rows -- trivial separation risk"
    elif separation_ratio > 1.0 or overlap_pct < 50:
        verdict, reason = "BORDERLINE", "Lookalikes have partial overlap with fraud but drift toward legit"
    else:
        verdict, reason = "PASS", "Good feature overlap -- lookalikes resemble fraud, not just legit"

    return {
        "status": verdict,
        "reason": reason,
        "metrics": {
            "fraud_count": fraud_count, "lookalike_count": lookalike_count, "legitimate_count": legit_count,
            "feature_overlap_pct": float(overlap_pct),
            "centroid_distances": {
                "fraud_to_lookalike": float(fraud_to_lookalike_dist),
                "fraud_to_legit": float(fraud_to_legit_dist),
                "lookalike_to_legit": float(lookalike_to_legit_dist),
            },
            "separation_ratio": float(separation_ratio),
        },
    }


def main():
    print("=" * 70)
    print("LOOKALIKE FIDELITY CHECK")
    print("=" * 70)

    df = load_training_data()
    result = analyze_lookalike_fidelity(df)

    print(f"\n{'=' * 70}")
    print(f"VERDICT: {result['status']}")
    print(f"{'=' * 70}")
    print(f"  {result['reason']}")

    report_path = Path('stage5/validation/lookalike_fidelity_report.json')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")


if __name__ == '__main__':
    main()
