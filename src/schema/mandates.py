"""Table 4 — mandates. docs/data-schema-v1.md, "Table 4 — mandates".

`frequency` is left as free-form `str`: the doc lists the field but gives no
explicit enum value set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pyarrow as pa

from src.schema.common import AMOUNT_PRECISION, AMOUNT_SCALE, Money
from src.schema.enums import EnrolledVia


@dataclass(slots=True)
class Mandate:
    mandate_id: str
    payer_id: str
    merchant_id: str
    max_amount: Money
    actual_amount: Money  # gap vs max_amount is the whole STEALTH-01 attack
    frequency: str
    created_at: datetime
    enrolled_via: EnrolledVia
    vpa_matches_biller_directory: bool  # the AGENT-01 detector
    pre_debit_notification_opened: bool  # notification != consent
    cancelled_at: Optional[datetime]
    re_registered_from_mandate_id: Optional[str]  # fk -> mandates; cancellation-evasion chain


def arrow_schema() -> pa.Schema:
    decimal_t = pa.decimal128(AMOUNT_PRECISION, AMOUNT_SCALE)
    ts_ms_ist = pa.timestamp("ms", tz="Asia/Kolkata")
    return pa.schema(
        [
            pa.field("mandate_id", pa.string(), nullable=False),
            pa.field("payer_id", pa.string(), nullable=False),
            pa.field("merchant_id", pa.string(), nullable=False),
            pa.field("max_amount", decimal_t, nullable=False),
            pa.field("actual_amount", decimal_t, nullable=False),
            pa.field("frequency", pa.string(), nullable=False),
            pa.field("created_at", ts_ms_ist, nullable=False),
            pa.field("enrolled_via", pa.string(), nullable=False),
            pa.field("vpa_matches_biller_directory", pa.bool_(), nullable=False),
            pa.field("pre_debit_notification_opened", pa.bool_(), nullable=False),
            pa.field("cancelled_at", ts_ms_ist, nullable=True),
            pa.field("re_registered_from_mandate_id", pa.string(), nullable=True),
        ]
    )
