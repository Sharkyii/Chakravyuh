"""Table 2 — parties. docs/data-schema-v1.md, "Table 2 — parties".

Accounts and VPAs, both sides of a transaction. Mule detection lives here
and in graph_edges. Merchants also get a parties row (party_type=MERCHANT);
merchants.py adds business/KYB metadata keyed by the same id.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pyarrow as pa

from src.schema.enums import KycLevel, PartyType


@dataclass(slots=True)
class Party:
    party_id: str
    party_type: PartyType
    account_age_days: int
    kyc_level: KycLevel
    kyc_completed_at: Optional[datetime]
    has_salary_credit: bool  # strongest mule discriminator available
    organic_spend_ratio: float  # P2M spend / total outflow
    throughput_ratio_24h: float  # outflow / inflow; ~1.0 == pass-through
    distinct_counterparties_30d: int
    home_pincode: str
    flagged_by_ffri: bool  # DoT Financial Fraud Risk Indicator; model its lag


def arrow_schema() -> pa.Schema:
    ts_ms_ist = pa.timestamp("ms", tz="Asia/Kolkata")
    return pa.schema(
        [
            pa.field("party_id", pa.string(), nullable=False),
            pa.field("party_type", pa.string(), nullable=False),
            pa.field("account_age_days", pa.int32(), nullable=False),
            pa.field("kyc_level", pa.string(), nullable=False),
            pa.field("kyc_completed_at", ts_ms_ist, nullable=True),
            pa.field("has_salary_credit", pa.bool_(), nullable=False),
            pa.field("organic_spend_ratio", pa.float64(), nullable=False),
            pa.field("throughput_ratio_24h", pa.float64(), nullable=False),
            pa.field("distinct_counterparties_30d", pa.int32(), nullable=False),
            pa.field("home_pincode", pa.string(), nullable=False),
            pa.field("flagged_by_ffri", pa.bool_(), nullable=False),
        ]
    )
