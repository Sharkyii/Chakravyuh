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

# Stage 5 training-data baseline scale. Deliberately smaller than the
# calibration.py production defaults (220k/9k) to keep the full
# generate->train loop fast to iterate on, but large enough that layering
# attack campaigns on top doesn't push fraud+lookalike rows anywhere near
# baseline volume -- at the previous 3,000/150 scale, 13 families x 100
# campaigns each pushed fraud-adjacent rows into the same order of magnitude
# as the legitimate baseline, which alone can make a classifier look
# artificially good regardless of split methodology.
STAGE5_N_CONSUMERS = 20_000
STAGE5_N_MERCHANTS = 800

# Campaigns generated per attack family. Two competing constraints: total
# fraud+lookalike volume should stay a small minority of the dataset (not
# swamp it the way EXPANSION_FACTOR=100 against a 3k-consumer baseline did),
# but each of the 13 families -- especially the one held out entirely for
# generalisation testing -- needs enough absolute fraud rows that a per-split
# precision/recall estimate isn't noise. 40 campaigns/family against the 20k
# consumer baseline lands fraud+lookalike prevalence under ~1%, still well
# short of IEEE-CIS's ~3.5% enriched benchmark rate. Verify against the
# printed prevalence in generate_training_data.py's output after any change.
ATTACK_EXPANSION_FACTOR = 40

# Splits -- temporal, matching docs/master-project-brief.md section 6 rule 2
# ("split temporally, never randomly"). Windows are derived from
# src.dataset.splits.split_windows() over the simulation calendar, not by
# shuffling campaign/party ids.
TRAIN_RATIO = 0.60
VAL_RATIO = 0.20
TEST_RATIO = 0.20

# Held out entirely from train/validation regardless of timestamp, so test
# performance on it measures generalisation to an unseen attack family
# rather than memorisation -- brief section 7, risk mitigation table.
# synthetic_identity_bustout chosen because its signature (credit-building
# phase then a temporal utilisation spike) is structurally distinct from the
# other 12 families, and it isn't one of the flagship illustrative examples
# (scam_induced_push, mule_network) the walkthrough deck leans on.
HELD_OUT_ATTACK_FAMILY = "synthetic_identity_bustout"

# Headline evaluation operating points -- brief section 6 rule 3 and section 8:
# "lead with precision at 0.1% and 1% FPR... ROC-AUC secondary only", because
# UPI credits are final and a detector is a pre-auth control.
FIXED_FPR_TARGETS = [0.001, 0.01]

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
