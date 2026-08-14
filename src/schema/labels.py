"""Table 7 — labels. docs/data-schema-v1.md, "Table 7 — labels".

Ground truth. Never a feature. Never joined at inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pyarrow as pa

from src.schema.enums import DetectableAt


@dataclass(slots=True)
class Label:
    txn_id: str
    is_fraud: bool
    attack_id: Optional[str]  # matches the attack-catalogue slug
    campaign_id: Optional[str]
    # merged-variant discriminator, e.g. digital_arrest / kyc_expiry / romance /
    # job_task / bank_official — free-form: the catalogue isn't closed to new pretexts
    pretext: Optional[str]
    is_legit_lookalike: bool  # the most important label in the schema
    detectable_at: Optional[DetectableAt]


def arrow_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("txn_id", pa.string(), nullable=False),
            pa.field("is_fraud", pa.bool_(), nullable=False),
            pa.field("attack_id", pa.string(), nullable=True),
            pa.field("campaign_id", pa.string(), nullable=True),
            pa.field("pretext", pa.string(), nullable=True),
            pa.field("is_legit_lookalike", pa.bool_(), nullable=False),
            pa.field("detectable_at", pa.string(), nullable=True),
        ]
    )
