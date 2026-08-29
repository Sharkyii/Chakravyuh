"""
Prepare synthetic training data for model training.

Combines two synthetic sources:
1. Legitimate transactions from Chakravyuh's own synthetic simulator
   (stage1/stage2 generators -- fully self-contained, no external data).
2. Fraud transactions from synthetic_data.csv (pattern-derived synthesis,
   already fraud-only).

A fraud detector needs both classes -- synthetic_data.csv alone is 100%
fraud and can't train a binary classifier on its own. Fraud rows are
downsampled to a realistic prevalence against the legitimate population
(the project's own settings.py flags trainable-but-unrealistic prevalence
as a known pitfall: "can make a classifier look artificially good").

Output: parquet at data/generated/stage5/combined/transactions.parquet,
matching the schema train_fraud_model.py expects.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
import json

from src.dataset.loader import load_dataset
from stage5.features.feature_engineering import build_features
from stage5.config.settings import (
    ALL_FEATURES, CATEGORICAL_FEATURES, NUMERICAL_FEATURES,
    BOOLEAN_FEATURES, BEHAVIORAL_FEATURES, GRAPH_FEATURES,
)

TARGET_FRAUD_PREVALENCE = 0.035  # matches settings.py's documented ~3.5% target


def _map_synthetic_fraud_to_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Map synthetic_data.csv's columns onto the model's ALL_FEATURES schema."""
    mapped = pd.DataFrame(index=df.index)

    mapped['amount'] = df.get('amount').combine_first(df.get('TransactionAmt')) if 'TransactionAmt' in df else df.get('amount')
    if 'step' in df.columns:
        step = pd.to_numeric(df['step'], errors='coerce')
        mapped['tx_hour'] = (step % 24)
        mapped['tx_dayofweek'] = ((step // 24) % 7)
    mapped['account_age_days'] = df.get('D1')
    mapped['beneficiary_added_ago_s'] = df.get('D2')
    mapped['time_since_prev_txn'] = df.get('D4')
    mapped['inter_txn_time_mean'] = df.get('D10')
    mapped['inter_txn_time_max'] = df.get('D15')
    mapped['geo_matches_billing'] = df['dist1'].apply(lambda v: (v < 50) if pd.notna(v) else np.nan) if 'dist1' in df else np.nan
    mapped['device_is_known_for_payer'] = df['DeviceType'].notna() if 'DeviceType' in df else np.nan
    mapped['txn_count_last_1h'] = df.get('C1')
    mapped['txn_count_last_24h'] = df.get('C2')
    mapped['unique_payee_count'] = df.get('C13')
    mapped['merchant_diversity'] = df.get('C14')
    mapped['mcc'] = df['category'].astype('category').cat.codes.replace(-1, np.nan) if 'category' in df else np.nan
    mapped['channel'] = df.get('ProductCD')
    mapped['auth_method'] = df.get('card4')
    mapped['rail'] = df.get('card6')
    mapped['historical_average_amount'] = df.get('oldbalanceOrg')
    mapped['amount_deviation'] = (
        (pd.to_numeric(df.get('newbalanceOrig'), errors='coerce') - pd.to_numeric(df.get('oldbalanceOrg'), errors='coerce'))
        if {'newbalanceOrig', 'oldbalanceOrg'}.issubset(df.columns) else np.nan
    )
    mapped['direction'] = df.get('type')

    for col in CATEGORICAL_FEATURES:
        if col not in mapped.columns:
            mapped[col] = pd.Series([None] * len(df), dtype='object')
    for col in NUMERICAL_FEATURES + BOOLEAN_FEATURES + BEHAVIORAL_FEATURES + GRAPH_FEATURES:
        if col not in mapped.columns:
            mapped[col] = np.nan

    mapped['is_fraud'] = 1
    mapped['is_legit_lookalike'] = 0
    mapped['attack_id'] = 'synthetic_pattern_fraud'
    mapped['campaign_id'] = 'synthetic_v1'
    return mapped


def prepare_synthetic_training_data(
    synthetic_fraud_csv: str = 'stage5/data/synthetic_augmented/synthetic_data.csv',
    legit_source_dir: str = 'data/generated/stage2',
    output_dir: str = 'data/generated/stage5/combined',
    target_fraud_prevalence: float = TARGET_FRAUD_PREVALENCE,
    random_state: int = 42,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading legitimate population from {legit_source_dir}...")
    dataset = load_dataset(Path(legit_source_dir))
    legit_df = build_features(dataset)
    legit_df = legit_df.reindex(columns=list(legit_df.columns) + [c for c in ALL_FEATURES if c not in legit_df.columns])
    if 'is_fraud' not in legit_df.columns:
        legit_df['is_fraud'] = 0
    if 'is_legit_lookalike' not in legit_df.columns:
        legit_df['is_legit_lookalike'] = 0
    if 'attack_id' not in legit_df.columns:
        legit_df['attack_id'] = None
    print(f"  {len(legit_df)} legitimate rows loaded, {legit_df['is_fraud'].sum()} already fraud-labelled")

    print(f"\nLoading synthetic fraud from {synthetic_fraud_csv}...")
    raw_fraud = pd.read_csv(synthetic_fraud_csv)
    print(f"  {len(raw_fraud)} synthetic fraud rows loaded")
    fraud_df = _map_synthetic_fraud_to_schema(raw_fraud)

    # Downsample fraud to a realistic prevalence against the legit population
    # rather than dumping all 200k+ rows against a much smaller legit base --
    # a near-1:1 fraud:legit ratio makes any classifier look artificially good.
    n_legit = len(legit_df)
    target_fraud_count = int(n_legit * target_fraud_prevalence / (1 - target_fraud_prevalence))
    target_fraud_count = min(target_fraud_count, len(fraud_df))
    fraud_df = fraud_df.sample(n=target_fraud_count, random_state=random_state).reset_index(drop=True)
    print(f"  Downsampled to {len(fraud_df)} rows (~{target_fraud_prevalence*100:.1f}% prevalence against {n_legit} legit rows)")

    # Synthetic fraud rows have no natural timestamp -- scatter them across
    # the same window as the legit population so the temporal split treats
    # them like any other transaction, not all-test or all-train.
    if 'timestamp' in legit_df.columns and legit_df['timestamp'].notna().any():
        t_min, t_max = legit_df['timestamp'].min(), legit_df['timestamp'].max()
    else:
        t_min, t_max = pd.Timestamp('2026-01-01'), pd.Timestamp('2026-06-30')
    rng = np.random.RandomState(random_state)
    span_seconds = max((t_max - t_min).total_seconds(), 1.0)
    fraud_df['timestamp'] = t_min + pd.to_timedelta(rng.uniform(0, span_seconds, size=len(fraud_df)), unit='s')

    # legit_df comes from Chakravyuh's own simulator and fraud_df's numeric
    # columns are renamed fields from a different source population --
    # same names, unrelated units (e.g. "amount" scale differs ~30x between
    # the two). Left as raw
    # values, several columns separate the classes almost perfectly on scale
    # alone, which is a data artifact, not a fraud signal. Quantile-normalize
    # each shared numeric column within its own source population first, so
    # both sides express "where does this row sit in its own distribution"
    # on a common 0-1 scale rather than incompatible raw units.
    shared_numeric = [
        c for c in (NUMERICAL_FEATURES + BEHAVIORAL_FEATURES)
        if c in legit_df.columns and c in fraud_df.columns
        and legit_df[c].notna().sum() >= 10 and fraud_df[c].notna().sum() >= 10
    ]
    print(f"\nQuantile-normalizing {len(shared_numeric)} shared numeric columns per source: {shared_numeric}")
    for col in shared_numeric:
        legit_df[col] = legit_df[col].rank(pct=True)
        fraud_df[col] = fraud_df[col].rank(pct=True)

    combined = pd.concat([legit_df, fraud_df], ignore_index=True, sort=False)
    combined = combined.sort_values('timestamp').reset_index(drop=True)

    from src.dataset.splits import TemporalSplitConfig, assign_split, split_windows
    from stage5.config.settings import TRAIN_RATIO, VAL_RATIO, TEST_RATIO

    windows = split_windows(TemporalSplitConfig(
        train_fraction=TRAIN_RATIO, validation_fraction=VAL_RATIO, test_fraction=TEST_RATIO
    ))
    combined['split'] = combined['timestamp'].apply(lambda ts: assign_split(ts, windows) or 'test')

    transactions_out = output_dir / 'transactions.parquet'
    combined.to_parquet(transactions_out, index=False)
    print(f"\nSaved to {transactions_out}")

    manifest = {
        'timestamp': datetime.now().isoformat(),
        'legit_source': legit_source_dir,
        'fraud_source': synthetic_fraud_csv,
        'n_rows': len(combined),
        'fraud_count': int(combined['is_fraud'].sum()),
        'fraud_prevalence': float(combined['is_fraud'].mean()),
        'split_counts': combined['split'].value_counts().to_dict(),
    }
    with open(output_dir / 'manifest.json', 'w') as f:
        json.dump(manifest, f, indent=2, default=str)
    print(json.dumps(manifest, indent=2, default=str))

    return combined, manifest


if __name__ == '__main__':
    prepare_synthetic_training_data()
