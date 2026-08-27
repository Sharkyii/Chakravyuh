"""Table 1 — transactions. docs/data-schema-v1.md, "Table 1 — transactions".

One row per payment attempt, including declines. The core event table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pyarrow as pa

from src.schema.common import AMOUNT_PRECISION, AMOUNT_SCALE, Money
from src.schema.enums import (
    AuthMethod,
    AuthResult,
    Channel,
    Decision,
    Direction,
    ExemptionClaimed,
    Rail,
)


@dataclass(slots=True)
class Transaction:
    # Identity and routing
    txn_id: str
    timestamp: datetime
    rail: Rail
    channel: Channel
    direction: Direction
    payer_id: str
    payee_id: str
    merchant_id: Optional[str]  # null for P2P

    # Money
    amount: Money
    currency: str  # char(3)
    amount_is_round: bool
    mcc: Optional[int]  # card and P2M; null for P2P
    purpose_code: Optional[str]  # UPI; carries the Circle delegation flag

    # Authentication
    auth_method: AuthMethod
    auth_result: AuthResult
    auth_latency_ms: Optional[int]
    eci: Optional[str]  # card only
    liability_shift: Optional[bool]  # card only
    exemption_claimed: Optional[ExemptionClaimed]  # card only

    # Decision
    decision: Decision
    decline_reason: Optional[str]
    issuer_risk_score: float  # incumbent baseline model's score

    # Session and device
    device_id: str
    device_is_known_for_payer: bool
    session_id: str
    session_duration_s: int
    time_on_confirm_screen_s: float  # highest-value single field in the schema
    beneficiary_first_time: bool
    beneficiary_added_ago_s: int
    pin_attempts: int
    screen_share_active: bool
    call_active_during_txn: bool
    accessibility_service_active: bool
    paste_used_in_amount: bool
    is_agent_initiated: bool
    agent_declared_principal: Optional[str]

    # Geo
    ip_country: str
    ip_asn: str
    ip_is_proxy: bool
    geo_matches_billing: Optional[bool]  # card only
    geo_matches_payer_home: bool

    # UPI TPAP routing (UPI rails only; null for card/IMPS/NEFT/wallet/BNPL).
    # NPCI's UPI architecture lets one VPA/bank account be reachable through
    # several third-party apps (PhonePe, GPay, Paytm, ...), and PSPs manage
    # re-linking a VPA across bank accounts -- both fields track which app and
    # which underlying bank account actually handled this specific payment.
    tpap_app: Optional[str]
    linked_account_id: Optional[str]


def arrow_schema() -> pa.Schema:
    decimal_t = pa.decimal128(AMOUNT_PRECISION, AMOUNT_SCALE)
    ts_ms_ist = pa.timestamp("ms", tz="Asia/Kolkata")
    return pa.schema(
        [
            pa.field("txn_id", pa.string(), nullable=False),
            pa.field("timestamp", ts_ms_ist, nullable=False),
            pa.field("rail", pa.string(), nullable=False),
            pa.field("channel", pa.string(), nullable=False),
            pa.field("direction", pa.string(), nullable=False),
            pa.field("payer_id", pa.string(), nullable=False),
            pa.field("payee_id", pa.string(), nullable=False),
            pa.field("merchant_id", pa.string(), nullable=True),
            pa.field("amount", decimal_t, nullable=False),
            pa.field("currency", pa.string(), nullable=False),
            pa.field("amount_is_round", pa.bool_(), nullable=False),
            pa.field("mcc", pa.int32(), nullable=True),
            pa.field("purpose_code", pa.string(), nullable=True),
            pa.field("auth_method", pa.string(), nullable=False),
            pa.field("auth_result", pa.string(), nullable=False),
            pa.field("auth_latency_ms", pa.int32(), nullable=True),
            pa.field("eci", pa.string(), nullable=True),
            pa.field("liability_shift", pa.bool_(), nullable=True),
            pa.field("exemption_claimed", pa.string(), nullable=True),
            pa.field("decision", pa.string(), nullable=False),
            pa.field("decline_reason", pa.string(), nullable=True),
            pa.field("issuer_risk_score", pa.float64(), nullable=False),
            pa.field("device_id", pa.string(), nullable=False),
            pa.field("device_is_known_for_payer", pa.bool_(), nullable=False),
            pa.field("session_id", pa.string(), nullable=False),
            pa.field("session_duration_s", pa.int32(), nullable=False),
            pa.field("time_on_confirm_screen_s", pa.float64(), nullable=False),
            pa.field("beneficiary_first_time", pa.bool_(), nullable=False),
            pa.field("beneficiary_added_ago_s", pa.int64(), nullable=False),
            pa.field("pin_attempts", pa.int32(), nullable=False),
            pa.field("screen_share_active", pa.bool_(), nullable=False),
            pa.field("call_active_during_txn", pa.bool_(), nullable=False),
            pa.field("accessibility_service_active", pa.bool_(), nullable=False),
            pa.field("paste_used_in_amount", pa.bool_(), nullable=False),
            pa.field("is_agent_initiated", pa.bool_(), nullable=False),
            pa.field("agent_declared_principal", pa.string(), nullable=True),
            pa.field("ip_country", pa.string(), nullable=False),
            pa.field("ip_asn", pa.string(), nullable=False),
            pa.field("ip_is_proxy", pa.bool_(), nullable=False),
            pa.field("geo_matches_billing", pa.bool_(), nullable=True),
            pa.field("geo_matches_payer_home", pa.bool_(), nullable=False),
            pa.field("tpap_app", pa.string(), nullable=True),
            pa.field("linked_account_id", pa.string(), nullable=True),
        ]
    )
