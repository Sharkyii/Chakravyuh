"""Table 3 — merchants. docs/data-schema-v1.md, "Table 3 — merchants".

merchant_id shares the parties.party_id id space (party_type=MERCHANT in
parties.py): this table adds business/MCC/KYB metadata on top of the
settlement-account row every merchant also has in `parties`.

kyb_level and volume-growth-adjacent free-text fields the doc didn't give an
explicit enum value list for are typed `str`, not an invented enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pyarrow as pa

from src.schema.enums import VolumeGrowthCurve


@dataclass(slots=True)
class Merchant:
    merchant_id: str
    mcc_declared: int
    mcc_inferred_from_basket: Optional[int]  # divergence = transaction-laundering signal
    onboarded_at: datetime
    kyb_level: str  # doc gives no explicit value set
    kyb_docs_verified_against_registry: bool  # format-valid vs registry-verified
    days_to_first_txn: int
    volume_growth_curve: VolumeGrowthCurve
    chargeback_rate_30d: float
    refund_rate_30d: float
    decline_rate_30d: float  # decline rate is your probe detector
    settlement_account_age_days: int
    settlement_outflow_latency_h: float  # bust-out signal


def arrow_schema() -> pa.Schema:
    ts_ms_ist = pa.timestamp("ms", tz="Asia/Kolkata")
    return pa.schema(
        [
            pa.field("merchant_id", pa.string(), nullable=False),
            pa.field("mcc_declared", pa.int32(), nullable=False),
            pa.field("mcc_inferred_from_basket", pa.int32(), nullable=True),
            pa.field("onboarded_at", ts_ms_ist, nullable=False),
            pa.field("kyb_level", pa.string(), nullable=False),
            pa.field("kyb_docs_verified_against_registry", pa.bool_(), nullable=False),
            pa.field("days_to_first_txn", pa.int32(), nullable=False),
            pa.field("volume_growth_curve", pa.string(), nullable=False),
            pa.field("chargeback_rate_30d", pa.float64(), nullable=False),
            pa.field("refund_rate_30d", pa.float64(), nullable=False),
            pa.field("decline_rate_30d", pa.float64(), nullable=False),
            pa.field("settlement_account_age_days", pa.int32(), nullable=False),
            pa.field("settlement_outflow_latency_h", pa.float64(), nullable=False),
        ]
    )
