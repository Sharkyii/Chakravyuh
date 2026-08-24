"""
Generate augmented synthetic fraud data from real benchmark datasets
(Cifer P2P, BankSim, IEEE-CIS) using a conditional Gaussian copula fit
on each dataset's genuine fraud rows.

Run: python -m stage5.generation.generate_from_real_data
"""

import json
import zipfile
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from stage5.generation.real_fraud_synthesizer import ConditionalGaussianCopula, fidelity_report

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "stage5" / "data" / "synthetic_augmented"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_cifer(multiplier: int = 15) -> dict:
    path = REPO_ROOT / "data" / "reference" / "Cifer-Fraud-Detection-Dataset-AF-part-2-14.csv"
    df = pd.read_csv(path)
    fraud = df[df['isFraud'] == 1].copy()

    cat_cols = ['type']
    cont_cols = ['amount', 'oldbalanceOrg', 'newbalanceOrig', 'oldbalanceDest', 'newbalanceDest', 'step']

    copula = ConditionalGaussianCopula().fit(fraud, cat_cols, cont_cols)
    n_synth = len(fraud) * multiplier
    synth = copula.sample(n_synth, random_state=42)

    out_path = OUT_DIR / "cifer_synthetic_fraud.csv"
    synth.to_csv(out_path, index=False)

    report = fidelity_report(fraud, synth, cont_cols, cat_cols)
    return {
        'dataset': 'Cifer P2P',
        'real_fraud_seeds': len(fraud),
        'synthetic_rows_generated': len(synth),
        'multiplier': multiplier,
        'output_file': str(out_path),
        'fidelity': report,
    }


def run_banksim(multiplier: int = 10) -> dict:
    zip_path = REPO_ROOT / "data" / "reference" / "banksimdata.zip"
    with zipfile.ZipFile(zip_path) as z:
        with z.open('bs140513_032310.csv') as f:
            df = pd.read_csv(f)

    for col in ['customer', 'age', 'gender', 'zipcodeOri', 'merchant', 'zipMerchant', 'category']:
        df[col] = df[col].str.strip("'")

    fraud = df[df['fraud'] == 1].copy()
    fraud['age'] = pd.to_numeric(fraud['age'], errors='coerce').fillna(-1)  # 'U' = unknown age in BankSim

    cat_cols = ['category', 'gender']
    cont_cols = ['amount', 'step', 'age']

    copula = ConditionalGaussianCopula().fit(fraud, cat_cols, cont_cols)
    n_synth = len(fraud) * multiplier
    synth = copula.sample(n_synth, random_state=42)

    out_path = OUT_DIR / "banksim_synthetic_fraud.csv"
    synth.to_csv(out_path, index=False)

    report = fidelity_report(fraud, synth, cont_cols, cat_cols)
    return {
        'dataset': 'BankSim',
        'real_fraud_seeds': len(fraud),
        'synthetic_rows_generated': len(synth),
        'multiplier': multiplier,
        'output_file': str(out_path),
        'fidelity': report,
    }


def run_ieee(multiplier: int = 5) -> dict:
    zip_path = REPO_ROOT / "data" / "reference" / "ieee-fraud-detection.zip"
    txn_cols = ['TransactionID', 'isFraud', 'TransactionAmt', 'ProductCD', 'card4', 'card6',
                'C1', 'C2', 'C13', 'C14', 'D1', 'D2', 'D4', 'D10', 'D15', 'dist1']

    with zipfile.ZipFile(zip_path) as z:
        with z.open('train_transaction.csv') as f:
            txn = pd.read_csv(f, usecols=txn_cols)
        fraud_ids = txn.loc[txn['isFraud'] == 1, 'TransactionID']

        with z.open('train_identity.csv') as f:
            ident = pd.read_csv(f, usecols=['TransactionID', 'DeviceType'])

    fraud = txn[txn['isFraud'] == 1].merge(ident, on='TransactionID', how='left')

    cont_cols = ['TransactionAmt', 'C1', 'C2', 'C13', 'C14', 'D1', 'D2', 'D4', 'D10', 'D15', 'dist1']
    cat_cols = ['ProductCD', 'card4', 'card6', 'DeviceType']

    for col in cont_cols:
        fraud[col] = fraud[col].fillna(fraud[col].median())
    for col in cat_cols:
        fraud[col] = fraud[col].fillna('missing')

    copula = ConditionalGaussianCopula().fit(fraud, cat_cols, cont_cols)
    n_synth = len(fraud) * multiplier
    synth = copula.sample(n_synth, random_state=42)

    out_path = OUT_DIR / "ieee_synthetic_fraud.csv"
    synth.to_csv(out_path, index=False)

    report = fidelity_report(fraud, synth, cont_cols, cat_cols)
    return {
        'dataset': 'IEEE Card',
        'real_fraud_seeds': len(fraud),
        'synthetic_rows_generated': len(synth),
        'multiplier': multiplier,
        'output_file': str(out_path),
        'fidelity': report,
    }


def main():
    results = {}
    for name, fn in [('cifer', run_cifer), ('banksim', run_banksim), ('ieee', run_ieee)]:
        print(f"\n{'='*70}\nGenerating: {name}\n{'='*70}")
        try:
            results[name] = fn()
            r = results[name]
            print(f"  Real fraud seeds:  {r['real_fraud_seeds']:,}")
            print(f"  Synthetic rows:    {r['synthetic_rows_generated']:,} ({r['multiplier']}x)")
            print(f"  Saved to:          {r['output_file']}")
        except Exception as e:
            print(f"  FAILED: {e}")
            results[name] = {'status': 'FAILED', 'error': str(e)}

    summary_path = OUT_DIR / "generation_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull fidelity report saved to: {summary_path}")


if __name__ == '__main__':
    main()
