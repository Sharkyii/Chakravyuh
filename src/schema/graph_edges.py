"""Table 6 — graph_edges. docs/data-schema-v1.md, "Table 6 — graph_edges".

Materialised, aggregated party-to-party edges over a time window — not
derived from transactions at training time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pyarrow as pa

from src.schema.common import AMOUNT_PRECISION, AMOUNT_SCALE, Money


@dataclass(slots=True)
class GraphEdge:
    src_party_id: str
    dst_party_id: str
    window_start: datetime
    window_end: datetime
    edge_count: int
    edge_value_total: Money
    mean_inter_arrival_s: float
    src_out_degree: int  # fan-out — mule primitive
    dst_in_degree: int  # fan-in — mule primitive
    is_two_hop_passthrough: bool


def arrow_schema() -> pa.Schema:
    decimal_t = pa.decimal128(AMOUNT_PRECISION, AMOUNT_SCALE)
    ts_ms_ist = pa.timestamp("ms", tz="Asia/Kolkata")
    return pa.schema(
        [
            pa.field("src_party_id", pa.string(), nullable=False),
            pa.field("dst_party_id", pa.string(), nullable=False),
            pa.field("window_start", ts_ms_ist, nullable=False),
            pa.field("window_end", ts_ms_ist, nullable=False),
            pa.field("edge_count", pa.int32(), nullable=False),
            pa.field("edge_value_total", decimal_t, nullable=False),
            pa.field("mean_inter_arrival_s", pa.float64(), nullable=False),
            pa.field("src_out_degree", pa.int32(), nullable=False),
            pa.field("dst_in_degree", pa.int32(), nullable=False),
            pa.field("is_two_hop_passthrough", pa.bool_(), nullable=False),
        ]
    )
