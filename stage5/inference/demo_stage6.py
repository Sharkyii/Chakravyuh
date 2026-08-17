import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Setup project root
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.dataset.loader import load_dataset
from stage5.config.settings import STAGE5_DATA_DIR, ALL_FEATURES
from stage5.features.feature_engineering import build_features
from stage5.inference.pipeline import analyze_transaction, load_env_file

def main():
    print("=== Stage 6 Demonstration Script ===")
    
    # 1. Load data and features
    combined_dir = STAGE5_DATA_DIR / "combined"
    if not combined_dir.exists():
        print(f"Error: Combined dataset not found at {combined_dir}. Please run generate_training_data.py first.")
        sys.exit(1)
        
    print("Loading combined dataset...")
    dataset = load_dataset(combined_dir)
    
    print("Building features...")
    df = build_features(dataset)
    
    # Select samples from the test set or the dataset generally
    np.random.seed(42)
    unique_campaigns = sorted(df[df["campaign_id"].notna()]["campaign_id"].unique())
    np.random.shuffle(unique_campaigns)
    n_camps = len(unique_campaigns)
    n_train_camp = int(n_camps * 0.70)
    n_val_camp = int(n_camps * 0.15)
    test_camps = set(unique_campaigns[n_train_camp + n_val_camp:])
    
    test_df = df[df["campaign_id"].isin(test_camps) | (df["campaign_id"].isna() & df["payer_id"].isin(
        sorted(df[df["campaign_id"].isna()]["payer_id"].unique())[int(len(df[df["campaign_id"].isna()]["payer_id"].unique()) * 0.85):]
    ))].copy()
    
    legit_samples = test_df[test_df["is_fraud"] == False].head(2)
    fraud_samples = test_df[test_df["is_fraud"] == True].head(2)
    
    if len(legit_samples) == 0 or len(fraud_samples) == 0:
        print("Error: Could not find legitimate or fraudulent transactions in the test split!")
        sys.exit(1)
        
    samples = pd.concat([legit_samples, fraud_samples])
    
    # 2. Run analysis on each sample
    load_env_file()
    api_key_configured = bool(os.environ.get("google_gemini_api_key") or os.environ.get("GOOGLE_GEMINI_API_KEY"))
    
    print(f"\nAPI Key Configured: {api_key_configured}")
    
    for idx, row in samples.iterrows():
        txn_dict = dict(row)
        true_label = "FRAUD" if txn_dict["is_fraud"] else "LEGITIMATE"
        attack_id = txn_dict.get("attack_id", "N/A")
        
        print("\n" + "="*60)
        print(f"TRANSACTION ID: {txn_dict['txn_id']}")
        print(f"True Label: {true_label} | True Attack: {attack_id}")
        print(f"Amount: {txn_dict['amount']} INR | Rail: {txn_dict['rail']}")
        print("="*60)
        
        # Analyze transaction
        print("\n--- Running Stage 6 Pipeline ---")
        assessment = analyze_transaction(txn_dict)
        
        print(f"Risk Score: {assessment['risk_score']:.1f}/100")
        print(f"Risk Level: {assessment['risk_level']}")
        print(f"Recommended Action: {assessment['action']}")
        print(f"Fraud Probability: {assessment['fraud_probability']*100:.2f}%")
        print(f"Predicted Attack Class: {assessment['top_attack_family']} ({assessment['top_attack_probability']*100:.2f}%)")
        print("Contributing Signals:")
        for sig in assessment['contributing_signals']:
            print(f"  - {sig}")
        if not assessment['contributing_signals']:
            print("  - None")
            
        print("\n--- GenAI Analyst Notes ---")
        notes = assessment["llm_analysis"]
        print(f"Fraud Explanation:\n{notes['fraud_explanation']}")
        print(f"\nAttack Interpretation:\n{notes['attack_family_interpretation']}")
        print("\nKey Evidence:")
        for ev in notes['key_evidence']:
            print(f"  - {ev}")
        print("\nInvestigation Steps:")
        for step in notes['investigation_steps']:
            print(f"  - {step}")
        print(f"\nCaveats & Uncertainty:\n{notes['uncertainty_caveats']}")
        
    # 3. Demonstrate LLM Fallback explicitly by temporarily clearing the key
    print("\n" + "#"*60)
    print("DEMONSTRATING GRACEFUL LLM FALLBACK (API KEY REMOVED)")
    print("#"*60)
    
    orig_key = os.environ.get("google_gemini_api_key")
    orig_key_upper = os.environ.get("GOOGLE_GEMINI_API_KEY")
    
    try:
        if "google_gemini_api_key" in os.environ:
            del os.environ["google_gemini_api_key"]
        if "GOOGLE_GEMINI_API_KEY" in os.environ:
            del os.environ["GOOGLE_GEMINI_API_KEY"]
            
        sample_fraud = dict(fraud_samples.iloc[0])
        print(f"\nAnalyzing Transaction: {sample_fraud['txn_id']} (Fraud)")
        fallback_assessment = analyze_transaction(sample_fraud)
        
        print(f"Risk Score: {fallback_assessment['risk_score']:.1f}/100")
        print(f"Risk Level: {fallback_assessment['risk_level']}")
        print(f"Recommended Action: {fallback_assessment['action']}")
        print("\n--- Fallback GenAI Analyst Notes ---")
        fallback_notes = fallback_assessment["llm_analysis"]
        print(f"Fraud Explanation:\n{fallback_notes['fraud_explanation']}")
        print(f"\nCaveats & Uncertainty:\n{fallback_notes['uncertainty_caveats']}")
        print("\nRESULT: Graceful fallback executed successfully.")
        
    finally:
        # Restore key
        if orig_key:
            os.environ["google_gemini_api_key"] = orig_key
        if orig_key_upper:
            os.environ["GOOGLE_GEMINI_API_KEY"] = orig_key_upper

if __name__ == "__main__":
    main()
