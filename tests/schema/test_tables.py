"""Every table dataclass constructs from a valid row and exposes the field
names docs/data-schema-v1.md specifies (or, for `devices`, the fields the
conversation agreed to add).
"""

from __future__ import annotations

import dataclasses

from tests.schema.fixtures import (
    sample_device,
    sample_dispute,
    sample_graph_edge,
    sample_label,
    sample_mandate,
    sample_merchant,
    sample_party,
    sample_transaction,
)

EXPECTED_FIELDS = {
    "transactions": {
        "txn_id",
        "timestamp",
        "rail",
        "channel",
        "direction",
        "payer_id",
        "payee_id",
        "merchant_id",
        "amount",
        "currency",
        "amount_is_round",
        "mcc",
        "purpose_code",
        "auth_method",
        "auth_result",
        "auth_latency_ms",
        "eci",
        "liability_shift",
        "exemption_claimed",
        "decision",
        "decline_reason",
        "issuer_risk_score",
        "device_id",
        "device_is_known_for_payer",
        "session_id",
        "session_duration_s",
        "time_on_confirm_screen_s",
        "beneficiary_first_time",
        "beneficiary_added_ago_s",
        "pin_attempts",
        "screen_share_active",
        "call_active_during_txn",
        "accessibility_service_active",
        "paste_used_in_amount",
        "is_agent_initiated",
        "agent_declared_principal",
        "ip_country",
        "ip_asn",
        "ip_is_proxy",
        "geo_matches_billing",
        "geo_matches_payer_home",
    },
    "parties": {
        "party_id",
        "party_type",
        "account_age_days",
        "kyc_level",
        "kyc_completed_at",
        "has_salary_credit",
        "organic_spend_ratio",
        "throughput_ratio_24h",
        "distinct_counterparties_30d",
        "home_pincode",
        "flagged_by_ffri",
    },
    "merchants": {
        "merchant_id",
        "mcc_declared",
        "mcc_inferred_from_basket",
        "onboarded_at",
        "kyb_level",
        "kyb_docs_verified_against_registry",
        "days_to_first_txn",
        "volume_growth_curve",
        "chargeback_rate_30d",
        "refund_rate_30d",
        "decline_rate_30d",
        "settlement_account_age_days",
        "settlement_outflow_latency_h",
    },
    "mandates": {
        "mandate_id",
        "payer_id",
        "merchant_id",
        "max_amount",
        "actual_amount",
        "frequency",
        "created_at",
        "enrolled_via",
        "vpa_matches_biller_directory",
        "pre_debit_notification_opened",
        "cancelled_at",
        "re_registered_from_mandate_id",
    },
    "disputes": {
        "dispute_id",
        "txn_id",
        "raised_at_offset_days",
        "reason_code",
        "claimant_prior_dispute_count",
        "claimant_prior_dispute_rate",
        "device_matched_original_txn",
        "ce30_evidence_available",
    },
    "graph_edges": {
        "src_party_id",
        "dst_party_id",
        "window_start",
        "window_end",
        "edge_count",
        "edge_value_total",
        "mean_inter_arrival_s",
        "src_out_degree",
        "dst_in_degree",
        "is_two_hop_passthrough",
    },
    "labels": {
        "txn_id",
        "is_fraud",
        "attack_id",
        "campaign_id",
        "pretext",
        "is_legit_lookalike",
        "detectable_at",
    },
}

SAMPLES = {
    "transactions": sample_transaction,
    "parties": sample_party,
    "merchants": sample_merchant,
    "mandates": sample_mandate,
    "disputes": sample_dispute,
    "graph_edges": sample_graph_edge,
    "labels": sample_label,
}


def _field_names(instance) -> set[str]:
    return {f.name for f in dataclasses.fields(instance)}


def test_table_fields_match_schema_doc() -> None:
    for table_name, expected in EXPECTED_FIELDS.items():
        instance = SAMPLES[table_name]()
        assert _field_names(instance) == expected, table_name


def test_devices_table_has_agreed_fields() -> None:
    expected = {
        "device_id",
        "primary_party_id",
        "device_type",
        "os_name",
        "os_version",
        "device_model",
        "fingerprint_hash",
        "is_emulator",
        "is_shared_household_device",
        "first_seen_at",
        "last_seen_at",
        "retired_at",
        "replaced_device_id",
    }
    assert _field_names(sample_device()) == expected


def test_labels_is_fraud_false_in_phase_1() -> None:
    assert sample_label().is_fraud is False
