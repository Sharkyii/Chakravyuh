"""Build `graph_edges` from transaction rows.

The graph is derived only from observed payment relationships. For a dataset or
split window, each directed edge aggregates payer -> payee transactions whose
timestamps fall inside that window. The aggregate is deterministic and contains
no label or attack information.

`is_two_hop_passthrough` is a dataset-window property: it marks an incoming edge
when the destination later sends funds to a different party inside the same
window. It is useful as an offline graph artifact, but it is not a pre-transaction
feature for events earlier than the downstream payment.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from src.generators import calibration as cal
from src.schema.graph_edges import GraphEdge


@dataclass(slots=True)
class GraphBuildConfig:
    """Configuration for deterministic graph-edge aggregation."""

    window_start: datetime = cal.SIM_START
    window_end: datetime = cal.SIM_END
    passthrough_window: timedelta = timedelta(hours=24)


@dataclass(slots=True)
class _EdgeAccumulator:
    src: str
    dst: str
    timestamps: list[datetime]
    value_total: Decimal = Decimal("0.00")
    is_two_hop_passthrough: bool = False


def _value(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row[name]
    return getattr(row, name)


def _transactions_in_window(rows: Iterable[Any], config: GraphBuildConfig) -> list[Any]:
    return sorted(
        (
            row for row in rows
            if config.window_start <= _value(row, "timestamp") < config.window_end
        ),
        key=lambda row: (_value(row, "timestamp"), _value(row, "txn_id")),
    )


def build_graph_edges(
    transactions: Iterable[Any], config: GraphBuildConfig | None = None
) -> list[GraphEdge]:
    """Aggregate transactions into deterministic graph-edge rows."""
    cfg = config or GraphBuildConfig()
    rows = _transactions_in_window(transactions, cfg)
    accumulators: dict[tuple[str, str], _EdgeAccumulator] = {}

    for row in rows:
        src = str(_value(row, "payer_id"))
        dst = str(_value(row, "payee_id"))
        key = (src, dst)
        if key not in accumulators:
            accumulators[key] = _EdgeAccumulator(src=src, dst=dst, timestamps=[])
        acc = accumulators[key]
        acc.timestamps.append(_value(row, "timestamp"))
        acc.value_total += _value(row, "amount")

    outgoing_events: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for row in rows:
        outgoing_events[str(_value(row, "payer_id"))].append(
            (_value(row, "timestamp"), str(_value(row, "payee_id")))
        )

    for row in rows:
        src = str(_value(row, "payer_id"))
        dst = str(_value(row, "payee_id"))
        timestamp = _value(row, "timestamp")
        for later_time, later_dst in outgoing_events.get(dst, []):
            if timestamp < later_time <= timestamp + cfg.passthrough_window and later_dst != src:
                accumulators[(src, dst)].is_two_hop_passthrough = True
                break

    src_out_degree: dict[str, int] = defaultdict(int)
    dst_in_degree: dict[str, int] = defaultdict(int)
    src_to_dst: dict[str, set[str]] = defaultdict(set)
    dst_to_src: dict[str, set[str]] = defaultdict(set)
    for src, dst in accumulators:
        src_to_dst[src].add(dst)
        dst_to_src[dst].add(src)
    for src, dsts in src_to_dst.items():
        src_out_degree[src] = len(dsts)
    for dst, srcs in dst_to_src.items():
        dst_in_degree[dst] = len(srcs)

    edges: list[GraphEdge] = []
    for key in sorted(accumulators):
        acc = accumulators[key]
        timestamps = sorted(acc.timestamps)
        if len(timestamps) > 1:
            gaps = [
                (timestamps[i] - timestamps[i - 1]).total_seconds()
                for i in range(1, len(timestamps))
            ]
            mean_inter_arrival_s = float(sum(gaps) / len(gaps))
        else:
            mean_inter_arrival_s = 0.0
        edges.append(
            GraphEdge(
                src_party_id=acc.src,
                dst_party_id=acc.dst,
                window_start=cfg.window_start,
                window_end=cfg.window_end,
                edge_count=len(timestamps),
                edge_value_total=acc.value_total,
                mean_inter_arrival_s=mean_inter_arrival_s,
                src_out_degree=src_out_degree[acc.src],
                dst_in_degree=dst_in_degree[acc.dst],
                is_two_hop_passthrough=acc.is_two_hop_passthrough,
            )
        )
    return edges
