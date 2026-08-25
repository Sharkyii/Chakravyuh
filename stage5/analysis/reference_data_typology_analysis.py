"""
Analyze reference datasets (IEEE, Cifer, BankSim) to identify fraud typologies
NOT yet covered by the current 13 synthetic attack families.

This is pattern ANALYSIS only — extract structural signatures that inspired
new synthetic attack designs, but never train on or include real data.
"""
import sys
from pathlib import Path
import json
from collections import defaultdict

import numpy as np
import pandas as pd
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reference"


def analyze_ieee_fraud_patterns():
    """
    Analyze IEEE fraud dataset for patterns (card fraud, device clustering).
    """
    print("\n" + "="*80)
    print("IEEE FRAUD DATASET: Pattern Analysis")
    print("="*80)

    csv_path = DATA_DIR / "ieee-fraud-detection" / "train_transaction.csv"
    if not csv_path.exists():
        print("  IEEE train_transaction.csv not found (expected if not extracted)")
        return {}

    try:
        df = pd.read_csv(csv_path, nrows=100000)  # Sample for speed
    except Exception as e:
        print(f"  ERROR loading IEEE data: {e}")
        return {}

    patterns = {}

    # Pattern 1: Device fan-out (multiple payers per device)
    if 'DeviceInfo' in df.columns and 'card1' in df.columns:
        fraud_df = df[df['isFraud'] == 1]

        device_card_pairs = fraud_df.groupby('DeviceInfo')['card1'].nunique()
        multi_card_devices = (device_card_pairs > 1).sum()

        patterns['device_multi_card'] = {
            'description': 'Devices transacting with multiple distinct cards',
            'count': int(multi_card_devices),
            'pct_of_fraud': float(multi_card_devices / len(fraud_df) * 100) if len(fraud_df) > 0 else 0,
            'median_cards_per_device': float(device_card_pairs.median()),
            'max_cards_per_device': int(device_card_pairs.max()),
        }

        print(f"\n  Device fan-out fraud:")
        print(f"    Devices with 2+ distinct cards: {multi_card_devices} ({patterns['device_multi_card']['pct_of_fraud']:.1f}%)")
        print(f"    Median cards per compromised device: {patterns['device_multi_card']['median_cards_per_device']:.0f}")

    # Pattern 2: Time-of-day clustering (sudden shift from normal behavior)
    if 'TransactionDT' in df.columns:
        fraud_df = df[df['isFraud'] == 1]
        legit_df = df[df['isFraud'] == 0]

        # Extract hour of day
        fraud_df = fraud_df.copy()
        legit_df = legit_df.copy()
        fraud_df['hour'] = (fraud_df['TransactionDT'] // 3600) % 24
        legit_df['hour'] = (legit_df['TransactionDT'] // 3600) % 24

        fraud_hours = fraud_df['hour'].value_counts().sort_index()
        legit_hours = legit_df['hour'].value_counts().sort_index()

        # KL divergence-like: hour entropy difference
        max_fraud_hour_pct = fraud_hours.max() / len(fraud_df) * 100
        max_legit_hour_pct = legit_hours.max() / len(legit_df) * 100

        patterns['time_of_day_concentration'] = {
            'description': 'Fraud concentrated in specific hours vs. legitimate spread',
            'fraud_peak_hour_pct': float(max_fraud_hour_pct),
            'legit_peak_hour_pct': float(max_legit_hour_pct),
            'concentration_ratio': float(max_fraud_hour_pct / max_legit_hour_pct) if max_legit_hour_pct > 0 else 0,
        }

        print(f"\n  Time-of-day concentration:")
        print(f"    Fraud peak hour: {max_fraud_hour_pct:.1f}%")
        print(f"    Legit peak hour: {max_legit_hour_pct:.1f}%")
        print(f"    Concentration ratio: {patterns['time_of_day_concentration']['concentration_ratio']:.2f}x")

    return patterns


def analyze_cifer_fraud_patterns():
    """
    Analyze Cifer dataset for balance-drain and mule-network patterns.
    """
    print("\n" + "="*80)
    print("CIFER FRAUD DATASET: Pattern Analysis")
    print("="*80)

    csv_path = DATA_DIR / "Cifer-Fraud-Detection-Dataset-AF-part-2-14.csv"
    if not csv_path.exists():
        print("  Cifer CSV not found")
        return {}

    try:
        df = pd.read_csv(csv_path, nrows=100000)
    except Exception as e:
        print(f"  ERROR loading Cifer data: {e}")
        return {}

    patterns = {}

    # Pattern 1: Balance drain (receive then liquidate)
    if 'oldbalanceDest' in df.columns and 'newbalanceDest' in df.columns and 'isFraud' in df.columns:
        fraud_df = df[df['isFraud'] == 1].copy()
        legit_df = df[df['isFraud'] == 0].copy()

        # Calculate balance drain ratio
        fraud_df['balance_drained'] = (fraud_df['oldbalanceDest'] - fraud_df['newbalanceDest']).clip(lower=0)
        legit_df['balance_drained'] = (legit_df['oldbalanceDest'] - legit_df['newbalanceDest']).clip(lower=0)

        fraud_high_drain = (fraud_df['balance_drained'] / (fraud_df['oldbalanceDest'] + 1) > 0.5).sum()
        legit_high_drain = (legit_df['balance_drained'] / (legit_df['oldbalanceDest'] + 1) > 0.5).sum()

        patterns['balance_drain_exit'] = {
            'description': 'Receiver account liquidated within a transaction',
            'fraud_high_drain_pct': float(fraud_high_drain / len(fraud_df) * 100) if len(fraud_df) > 0 else 0,
            'legit_high_drain_pct': float(legit_high_drain / len(legit_df) * 100) if len(legit_df) > 0 else 0,
        }

        print(f"\n  Balance drain pattern:")
        print(f"    Fraud with >50% balance drained: {patterns['balance_drain_exit']['fraud_high_drain_pct']:.1f}%")
        print(f"    Legit with >50% balance drained: {patterns['balance_drain_exit']['legit_high_drain_pct']:.1f}%")

    # Pattern 2: Mule network (account receiving from multiple sources, fanning out to single beneficiary)
    if 'nameOrig' in df.columns and 'nameDest' in df.columns:
        fraud_df = df[df['isFraud'] == 1].copy()

        # For fraud rows, count how many distinct senders target the same receiver
        inbound_to_receiver = fraud_df.groupby('nameDest')['nameOrig'].nunique()
        outbound_from_sender = fraud_df.groupby('nameOrig')['nameDest'].nunique()

        receivers_with_multi_inbound = (inbound_to_receiver > 2).sum()
        senders_with_multi_outbound = (outbound_from_sender > 2).sum()

        patterns['mule_network'] = {
            'description': 'Account receiving from multiple sources or sending to multiple destinations',
            'fraud_receivers_multi_inbound': int(receivers_with_multi_inbound),
            'fraud_senders_multi_outbound': int(senders_with_multi_outbound),
        }

        print(f"\n  Mule network pattern:")
        print(f"    Fraud receivers with 3+ inbound: {receivers_with_multi_inbound}")
        print(f"    Fraud senders with 3+ outbound: {senders_with_multi_outbound}")

    return patterns


def analyze_banksim_patterns():
    """
    Analyze BankSim for category anomalies and step-function velocity changes.
    """
    print("\n" + "="*80)
    print("BANKSIM DATASET: Pattern Analysis")
    print("="*80)

    csv_path = DATA_DIR / "bs140513_032310.csv"
    if not csv_path.exists():
        print("  BankSim CSV not found")
        return {}

    try:
        df = pd.read_csv(csv_path, nrows=100000)
    except Exception as e:
        print(f"  ERROR loading BankSim data: {e}")
        return {}

    patterns = {}

    # Pattern 1: Category shift (payer's MCC suddenly changes from baseline)
    if 'category' in df.columns and 'fraud' in df.columns:
        fraud_df = df[df['fraud'] == 1]
        legit_df = df[df['fraud'] == 0]

        # Naïve category concentration
        fraud_top_cat_pct = fraud_df['category'].value_counts().iloc[0] / len(fraud_df) * 100 if len(fraud_df) > 0 else 0
        legit_top_cat_pct = legit_df['category'].value_counts().iloc[0] / len(legit_df) * 100 if len(legit_df) > 0 else 0

        patterns['category_concentration'] = {
            'description': 'Transactions concentrated in specific MCC/category',
            'fraud_top_category_pct': float(fraud_top_cat_pct),
            'legit_top_category_pct': float(legit_top_cat_pct),
            'concentration_ratio': float(fraud_top_cat_pct / legit_top_cat_pct) if legit_top_cat_pct > 0 else 0,
        }

        print(f"\n  Category concentration:")
        print(f"    Fraud top category: {fraud_top_cat_pct:.1f}%")
        print(f"    Legit top category: {legit_top_cat_pct:.1f}%")

    # Pattern 2: Velocity step function (amount jumps 2-5x from baseline)
    if 'amount' in df.columns:
        fraud_df = df[df['fraud'] == 1]

        # Group by transaction window, look for jumps
        fraud_mean_amt = fraud_df['amount'].mean()
        fraud_std_amt = fraud_df['amount'].std()
        legit_mean_amt = df[df['fraud'] == 0]['amount'].mean()

        patterns['amount_step_change'] = {
            'description': 'Transaction amount increases significantly from baseline',
            'fraud_avg_amount': float(fraud_mean_amt),
            'legit_avg_amount': float(legit_mean_amt),
            'amount_ratio': float(fraud_mean_amt / legit_mean_amt) if legit_mean_amt > 0 else 0,
        }

        print(f"\n  Transaction amount anomaly:")
        print(f"    Fraud avg amount: {fraud_mean_amt:.2f}")
        print(f"    Legit avg amount: {legit_mean_amt:.2f}")
        print(f"    Ratio: {patterns['amount_step_change']['amount_ratio']:.2f}x")

    return patterns


def main():
    print("="*80)
    print("REFERENCE DATA TYPOLOGY ANALYSIS")
    print("(Pattern extraction ONLY — no training data leakage)")
    print("="*80)

    all_patterns = {}

    # Run each analysis
    all_patterns['ieee'] = analyze_ieee_fraud_patterns()
    all_patterns['cifer'] = analyze_cifer_fraud_patterns()
    all_patterns['banksim'] = analyze_banksim_patterns()

    # Save to a report
    out_dir = Path(__file__).resolve().parent.parent / "reports"
    out_dir.mkdir(exist_ok=True)

    report_path = out_dir / "reference_data_typology_patterns.json"
    with open(report_path, 'w') as f:
        json.dump(all_patterns, f, indent=2, default=str)

    print("\n" + "="*80)
    print("TYPOLOGY ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nPatterns saved: {report_path}")

    # Summary of gaps
    print("\nGAPS IN CURRENT 13 FAMILIES (based on reference patterns):")
    print("  1. Device fan-out (multiple cards on one device) — not in current set")
    print("  2. Balance-drain exit fraud (receiver liquidation) — not covered")
    print("  3. Category/MCC novelty (payer changes spending patterns) — implicit in testing but not explicit")
    print("\nRECOMMENDATION: Design 2-3 new synthetic families to fill these gaps")


if __name__ == "__main__":
    main()
