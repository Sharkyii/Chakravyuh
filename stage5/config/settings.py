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
#
# Target scale is 100_000/4_000 (below), but this machine has 14GB RAM and a
# full generate+build_features pass at 100k consumers OOM-killed a prior run
# (exit 137) with the rest of the desktop also competing for memory. A
# measured attempt at 40_000/1_600 peaked at 7.1GB RSS for baseline
# generation ALONE (measured via /usr/bin/time -v) and fully exhausted the
# 2GB swap -- roughly 3.4x a naive linear-from-15k estimate, so scaling
# empirically observed peak-RSS from a smaller run is not safe to trust
# linearly on this generator.
#
# 20_000/800 succeeded for baseline gen + attack layering (both completed
# cleanly, peaks 6.1GB and 3.9GB respectively), but stage5/training/
# train_fraud_model.py's build_features() call -- BehavioralFeatureTracker's
# sequential per-payer state accumulation over the resulting 692,851-row
# combined dataset -- exceeded 7.1GB RSS and was STILL CLIMBING when killed,
# never reaching a plateau. This is the heaviest step measured so far,
# heavier than either generation step alone. Note ATTACK_EXPANSION_FACTOR
# does not meaningfully affect this: attack+lookalike rows are only ~1% of
# total volume (7,296 of 692,851) by design, so total row count is
# essentially the baseline's row count -- the real lever is
# STAGE5_N_CONSUMERS, not the expansion factor.
#
# Reduced to 8_000/320 (40% of 20k, same 25:1 ratio) for build_features() to
# have a chance of completing. Restore to 100_000/4_000 when running on a
# machine with more headroom.
STAGE5_N_CONSUMERS = 8_000
STAGE5_N_MERCHANTS = 320

# Campaigns generated per attack family. Two competing constraints: total
# fraud+lookalike volume should stay a small minority of the dataset (not
# swamp it the way EXPANSION_FACTOR=100 against a 3k-consumer baseline did),
# but each of the 16 families -- especially the one held out entirely for
# generalisation testing -- needs enough absolute fraud rows that a per-split
# precision/recall estimate isn't noise. 40 campaigns/family against the 20k
# consumer baseline measured at 0.53% fraud+lookalike prevalence -- below the
# ~1-5% target range printed by generate_training_data.py itself. Bumped to
# 80 (measured cost: attack layering alone peaked at 3.9GB RSS / ~3 minutes
# at 40, well under this machine's headroom, so doubling campaign count is
# cheap). Verify against the printed prevalence in generate_training_data.py's
# output after any change.
ATTACK_EXPANSION_FACTOR = 80

# Canonical Stage 5 training families.  Keep the campaign seed separate for
# each family: generate_training_data.py expands it into a non-overlapping
# per-campaign seed range so generated transaction ids remain unique.
ATTACK_FAMILIES = (
    {"attack_id": "scam_induced_push", "seed": 101, "intensity": "MEDIUM"},
    {"attack_id": "mule_network", "seed": 102, "intensity": "MEDIUM"},
    {"attack_id": "card_testing_probe", "seed": 103, "intensity": "MEDIUM"},
    {"attack_id": "adversarial_evasion", "seed": 104, "intensity": "MEDIUM"},
    {"attack_id": "first_party_dispute", "seed": 105, "intensity": "MEDIUM"},
    {"attack_id": "stealth_mandate", "seed": 106, "intensity": "MEDIUM"},
    {"attack_id": "synthetic_merchant", "seed": 107, "intensity": "MEDIUM"},
    {"attack_id": "transaction_laundering", "seed": 108, "intensity": "MEDIUM"},
    {"attack_id": "credential_takeover", "seed": 109, "intensity": "MEDIUM"},
    {"attack_id": "synthetic_identity_bustout", "seed": 110, "intensity": "MEDIUM"},
    {"attack_id": "subthreshold_fragmentation", "seed": 111, "intensity": "MEDIUM"},
    {"attack_id": "agentic_injection", "seed": 112, "intensity": "MEDIUM"},
    {"attack_id": "insider_abuse", "seed": 113, "intensity": "MEDIUM"},
    {"attack_id": "device_fan_out", "seed": 114, "intensity": "MEDIUM"},
    {"attack_id": "balance_drain_exit", "seed": 115, "intensity": "MEDIUM"},
    {"attack_id": "tpap_account_switch", "seed": 116, "intensity": "MEDIUM"},
)

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
    "distinct_tpap_count_last_1h",
    "distinct_tpap_count_last_24h",
    "distinct_linked_account_count_last_1h",
    "distinct_linked_account_count_last_24h",
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
