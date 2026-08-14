"""One realistic, valid instance of every table dataclass. Shared across
tests/schema/test_tables.py and test_arrow_schemas.py so the two suites
can't silently drift apart.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.schema.common import IST
from src.schema.devices import Device
from src.schema.disputes import Dispute
from src.schema.enums import (
    AuthMethod,
    AuthResult,
    Channel,
    Decision,
    DetectableAt,
    DeviceType,
    Direction,
    EnrolledVia,
    KycLevel,
    PartyType,
    Rail,
    VolumeGrowthCurve,
)
from src.schema.graph_edges import GraphEdge
from src.schema.labels import Label
from src.schema.mandates import Mandate
from src.schema.merchants import Merchant
from src.schema.parties import Party
from src.schema.transactions import Transaction

_T0 = datetime(2026, 8, 1, 9, 30, 0, tzinfo=IST)


def sample_transaction() -> Transaction:
    return Transaction(
        txn_id="11111111-1111-1111-1111-111111111111",
        timestamp=_T0,
        rail=Rail.UPI_P2M,
        channel=Channel.APP,
        direction=Direction.PUSH,
        payer_id="party-payer-1",
        payee_id="party-payee-1",
        merchant_id="merchant-1",
        amount=Decimal("499.00"),
        currency="INR",
        amount_is_round=False,
        mcc=5411,
        purpose_code="00",
        auth_method=AuthMethod.UPI_PIN,
        auth_result=AuthResult.SUCCESS,
        auth_latency_ms=1800,
        eci=None,
        liability_shift=None,
        exemption_claimed=None,
        decision=Decision.APPROVED,
        decline_reason=None,
        issuer_risk_score=0.12,
        device_id="device-1",
        device_is_known_for_payer=True,
        session_id="session-1",
        session_duration_s=45,
        time_on_confirm_screen_s=2.3,
        beneficiary_first_time=False,
        beneficiary_added_ago_s=5_184_000,
        pin_attempts=1,
        screen_share_active=False,
        call_active_during_txn=False,
        accessibility_service_active=False,
        paste_used_in_amount=False,
        is_agent_initiated=False,
        agent_declared_principal=None,
        ip_country="IN",
        ip_asn="AS55836",
        ip_is_proxy=False,
        geo_matches_billing=None,
        geo_matches_payer_home=True,
    )


def sample_party() -> Party:
    return Party(
        party_id="party-payer-1",
        party_type=PartyType.CONSUMER,
        account_age_days=820,
        kyc_level=KycLevel.FULL,
        kyc_completed_at=_T0,
        has_salary_credit=True,
        organic_spend_ratio=0.71,
        throughput_ratio_24h=0.34,
        distinct_counterparties_30d=6,
        home_pincode="400001",
        flagged_by_ffri=False,
    )


def sample_device() -> Device:
    return Device(
        device_id="device-1",
        primary_party_id="party-payer-1",
        device_type=DeviceType.ANDROID,
        os_name="Android",
        os_version="14",
        device_model="Pixel 8",
        fingerprint_hash="fp-abc123",
        is_emulator=False,
        is_shared_household_device=False,
        first_seen_at=_T0,
        last_seen_at=_T0,
        retired_at=None,
        replaced_device_id=None,
    )


def sample_merchant() -> Merchant:
    return Merchant(
        merchant_id="merchant-1",
        mcc_declared=5411,
        mcc_inferred_from_basket=5411,
        onboarded_at=_T0,
        kyb_level="full",
        kyb_docs_verified_against_registry=True,
        days_to_first_txn=3,
        volume_growth_curve=VolumeGrowthCurve.ORGANIC,
        chargeback_rate_30d=0.001,
        refund_rate_30d=0.02,
        decline_rate_30d=0.05,
        settlement_account_age_days=900,
        settlement_outflow_latency_h=24.0,
    )


def sample_mandate() -> Mandate:
    return Mandate(
        mandate_id="mandate-1",
        payer_id="party-payer-1",
        merchant_id="merchant-1",
        max_amount=Decimal("999.00"),
        actual_amount=Decimal("499.00"),
        frequency="monthly",
        created_at=_T0,
        enrolled_via=EnrolledVia.APP,
        vpa_matches_biller_directory=True,
        pre_debit_notification_opened=True,
        cancelled_at=None,
        re_registered_from_mandate_id=None,
    )


def sample_dispute() -> Dispute:
    return Dispute(
        dispute_id="dispute-1",
        txn_id="11111111-1111-1111-1111-111111111111",
        raised_at_offset_days=4,
        reason_code="10.4",
        claimant_prior_dispute_count=0,
        claimant_prior_dispute_rate=0.0,
        device_matched_original_txn=True,
        ce30_evidence_available=True,
    )


def sample_graph_edge() -> GraphEdge:
    return GraphEdge(
        src_party_id="party-payer-1",
        dst_party_id="party-payee-1",
        window_start=_T0,
        window_end=_T0,
        edge_count=3,
        edge_value_total=Decimal("1497.00"),
        mean_inter_arrival_s=3600.0,
        src_out_degree=2,
        dst_in_degree=5,
        is_two_hop_passthrough=False,
    )


def sample_label() -> Label:
    return Label(
        txn_id="11111111-1111-1111-1111-111111111111",
        is_fraud=False,
        attack_id=None,
        campaign_id=None,
        pretext=None,
        is_legit_lookalike=False,
        detectable_at=DetectableAt.PRE_AUTH,
    )
