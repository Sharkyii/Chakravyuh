"""
Prepare synthetic training data for model training.

Takes the consolidated synthetic_data.csv and prepares it for Gen 3/4/5
curriculum training by:
1. Adding required columns (split, is_fraud, timestamp)
2. Ensuring all feature columns exist
3. Creating train/val/test splits temporally

Output: parquet files matching the schema expected by train_fraud_model.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json

def prepare_synthetic_training_data(
    synthetic_csv_path: str = 'stage5/data/synthetic_augmented/synthetic_data.csv',
    output_dir: str = 'data/generated/stage5/combined',
    n_synthetic_rows: int = None
):
    """Load synthetic data and prepare for training."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading synthetic data from {synthetic_csv_path}...")
    df = pd.read_csv(synthetic_csv_path, nrows=n_synthetic_rows)

    print(f"  Loaded {len(df)} rows")
    print(f"  Columns: {list(df.columns)}")

    # All these rows are synthetic fraud (pattern-extracted from real data)
    df['is_fraud'] = 1
    df['is_legit_lookalike'] = 0

    # Create timestamps for temporal split
    # Spread transactions over 180 days
    df['timestamp'] = pd.date_range(
        start='2026-01-01',
        periods=len(df),
        freq=pd.Timedelta(days=180 / len(df))
    )

    # Temporal split: first 60% train, next 20% val, last 20% test
    train_cutoff = int(len(df) * 0.6)
    val_cutoff = int(len(df) * 0.8)

    df['split'] = 'test'
    df.loc[:train_cutoff, 'split'] = 'train'
    df.loc[train_cutoff:val_cutoff, 'split'] = 'validation'

    # Add required but optional feature columns (will be imputed during training)
    from stage5.config.settings import ALL_FEATURES

    for col in ALL_FEATURES:
        if col not in df.columns:
            df[col] = np.nan

    # Add metadata columns
    df['attack_id'] = 'synthetic_pattern_fraud'
    df['campaign_id'] = 'synthetic_v1'

    # Save as parquet (efficient, preserves types)
    transactions_out = output_dir / 'transactions.parquet'
    df.to_parquet(transactions_out, index=False)
    print(f"\n✓ Saved to {transactions_out}")

    # Create manifest
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'source': 'synthetic_data.csv',
        'n_rows': len(df),
        'split_counts': {
            'train': int((df['split'] == 'train').sum()),
            'validation': int((df['split'] == 'validation').sum()),
            'test': int((df['split'] == 'test').sum()),
        },
        'fraud_count': int(df['is_fraud'].sum()),
        'lookalike_count': int(df['is_legit_lookalike'].sum()),
    }

    manifest_out = output_dir / 'manifest.json'
    with open(manifest_out, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"✓ Saved manifest to {manifest_out}")

    return df, manifest


if __name__ == '__main__':
    df, manifest = prepare_synthetic_training_data()
    print("\n" + "="*70)
    print("PREPARATION COMPLETE")
    print("="*70)
    print(json.dumps(manifest, indent=2))
