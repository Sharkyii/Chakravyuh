"""Table 5 — disputes. docs/data-schema-v1.md, "Table 5 — disputes"."""

from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa


@dataclass(slots=True)
class Dispute:
    dispute_id: str
    txn_id: str
    raised_at_offset_days: int
    reason_code: str
    # first-party fraud is only visible across a claimant's history
    claimant_prior_dispute_count: int
    claimant_prior_dispute_rate: float
    device_matched_original_txn: bool
    ce30_evidence_available: bool


def arrow_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("dispute_id", pa.string(), nullable=False),
            pa.field("txn_id", pa.string(), nullable=False),
            pa.field("raised_at_offset_days", pa.int32(), nullable=False),
            pa.field("reason_code", pa.string(), nullable=False),
            pa.field("claimant_prior_dispute_count", pa.int32(), nullable=False),
            pa.field("claimant_prior_dispute_rate", pa.float64(), nullable=False),
            pa.field("device_matched_original_txn", pa.bool_(), nullable=False),
            pa.field("ce30_evidence_available", pa.bool_(), nullable=False),
        ]
    )
