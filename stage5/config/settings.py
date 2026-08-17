import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STAGE5_DIR = BASE_DIR / "stage5"
DATA_DIR = BASE_DIR / "data"
STAGE2_OUTPUT_DIR = DATA_DIR / "generated" / "stage2"
STAGE5_DATA_DIR = DATA_DIR / "generated" / "stage5"
MODELS_DIR = STAGE5_DIR / "models"
REPORTS_DIR = STAGE5_DIR / "reports"

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Splits
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Columns to drop to prevent target leakage
LEAKAGE_COLUMNS = [
    "attack_id",
    "campaign_id",
    "pretext",
    "is_fraud",
    "is_legit_lookalike",
    "detectable_at",
    "generator_metadata",
    "scenario_id"
]

# Transaction columns used as features
CATEGORICAL_FEATURES = [
    "currency",
    "rail",
    "channel",
    "direction",
    "auth_method",
    "auth_result",
    "eci",
    "liability_shift",
    "exemption_claimed",
    "decision",
    "decline_reason",
    "ip_country",
    "ip_asn"
]

NUMERICAL_FEATURES = [
    "amount",
    "mcc",
    "auth_latency_ms",
    "session_duration_s",
    "time_on_confirm_screen_s",
    "beneficiary_added_ago_s",
    "pin_attempts",
    "tx_hour",
    "tx_dayofweek",
    "account_age_days"
]

BOOLEAN_FEATURES = [
    "device_is_known_for_payer",
    "beneficiary_first_time",
    "screen_share_active",
    "call_active_during_txn",
    "accessibility_service_active",
    "paste_used_in_amount",
    "is_agent_initiated",
    "ip_is_proxy",
    "geo_matches_billing",
    "geo_matches_payer_home"
]

BEHAVIORAL_FEATURES = [
    "txn_count_last_1h",
    "txn_count_last_24h",
    "amount_spent_last_1h",
    "amount_spent_last_24h",
    "historical_average_amount",
    "amount_deviation",
    "time_since_prev_txn",
    "new_merchant_indicator",
    "new_device_indicator",
    "new_ip_indicator",
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
    "time_since_prev_agent_txn"
]

GRAPH_FEATURES = [
    "payer_out_degree",
    "payee_in_degree",
    "edge_count",
    "edge_value_total",
    "is_two_hop_passthrough"
]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES + BOOLEAN_FEATURES + BEHAVIORAL_FEATURES + GRAPH_FEATURES
