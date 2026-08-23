# ruff: noqa: E402
import sys
from pathlib import Path
import numpy as np
import pytest

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.dataset.loader import load_dataset
from stage5.config.settings import STAGE5_DATA_DIR, ALL_FEATURES, BEHAVIORAL_FEATURES
from stage5.features.feature_engineering import build_features


# data/generated/ is gitignored and isn't generated in CI (generation is
# itself the "slow" work the -m "not slow" marker excludes elsewhere).
@pytest.mark.skipif(
    not (STAGE5_DATA_DIR / "combined").exists(),
    reason="generated Stage 5 dataset not present (not generated in CI)",
)
def test_new_features_are_correctly_generated_and_available():
    combined_dir = STAGE5_DATA_DIR / "combined"
    assert combined_dir.exists(), f"Combined data directory not found at {combined_dir}"

    dataset = load_dataset(combined_dir)
    # Take a small sample of the transactions for fast test execution
    dataset.tables["transactions"] = dataset.tables["transactions"][:200]
    df = build_features(dataset)

    new_expected_features = [
        "inter_txn_time_mean",
        "inter_txn_time_std",
        "inter_txn_time_min",
        "inter_txn_time_max",
        "txn_burstiness",
        "active_days_count",
        "active_hours_count",
        "txns_per_active_day",
        "amount_std",
        "amount_cv",
        "subthreshold_txn_ratio",
        "aggregate_to_threshold_ratio",
        "amount_concentration",
        "unique_payee_count",
        "merchant_diversity",
        "same_payee_ratio",
        "merchant_txn_ratio",
        "beneficiary_reuse_ratio",
        "txn_regularity",
        "mandate_txn_ratio",
        "mean_beneficiary_added_ago",
        "max_beneficiary_added_ago",
        "agent_txn_ratio",
        "agent_txn_burstiness",
        "time_since_prev_agent_txn",
    ]

    for f in new_expected_features:
        assert f in BEHAVIORAL_FEATURES, f"{f} is missing from BEHAVIORAL_FEATURES"
        assert f in ALL_FEATURES, f"{f} is missing from ALL_FEATURES"
        assert f in df.columns, f"{f} is missing from df.columns"

    for f in new_expected_features:
        vals = df[f].fillna(-999)
        assert not np.isnan(vals.values).any(), f"NaNs found in feature {f}"

    leakage_keywords = [
        "attack_id",
        "campaign_id",
        "pretext",
        "is_fraud",
        "is_legit_lookalike",
        "detectable_at",
        "scenario_id",
    ]
    for f in new_expected_features:
        for keyword in leakage_keywords:
            assert keyword not in f, f"Potential leakage in feature name: {f} contains {keyword}"
