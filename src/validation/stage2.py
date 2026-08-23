"""Stage 2 validation report for graph and dataset harness artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pyarrow as pa

from src.dataset.leakage import run_leakage_checks
from src.dataset.loader import EXPECTED_TABLES, PaymentDataset
from src.dataset.splits import TemporalSplitConfig, split_windows, temporal_split_transactions
from src.graph.builder import GraphBuildConfig, build_graph_edges
from src.schema import TABLE_ARROW_SCHEMAS


@dataclass(slots=True)
class Stage2ValidationReport:
    errors: list[str]
    summary: dict[str, Any]

    @property
    def ok(self) -> bool:
        return not self.errors


def _check_schema(table_name: str, rows: list[dict[str, Any]], errors: list[str]) -> None:
    try:
        pa.Table.from_pylist(rows, schema=TABLE_ARROW_SCHEMAS[table_name])
    except Exception as exc:  # pragma: no cover - pyarrow messages vary
        errors.append(f"{table_name} does not conform to schema: {exc}")


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p99": 0.0}
    values = sorted(values)
    return {
        "p50": values[int((len(values) - 1) * 0.50)],
        "p90": values[int((len(values) - 1) * 0.90)],
        "p99": values[int((len(values) - 1) * 0.99)],
    }


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = row[field]
        out[str(value)] = out.get(str(value), 0) + 1
    return dict(sorted(out.items()))


def validate_stage2_dataset(
    dataset: PaymentDataset, config: TemporalSplitConfig | None = None
) -> Stage2ValidationReport:
    """Validate Stage 2 graph, splits, labels, FKs, schemas and leakage checks."""
    errors: list[str] = []
    for table_name in EXPECTED_TABLES:
        _check_schema(table_name, dataset.tables[table_name], errors)

    leakage = run_leakage_checks(dataset, config)
    errors.extend(leakage.errors)
    splits = temporal_split_transactions(dataset.transactions, dataset.labels, config)
    windows = split_windows(config)

    split_graph_counts: dict[str, int] = {}
    for split_name, window in windows.items():
        edges = build_graph_edges(
            dataset.transactions,
            GraphBuildConfig(window_start=window.start, window_end=window.end),
        )
        split_graph_counts[split_name] = len(edges)
        for edge in edges:
            if edge.window_start != window.start or edge.window_end != window.end:
                errors.append(f"split graph edge crosses window: {split_name}")

    timestamps = [row["timestamp"] for row in dataset.transactions]
    graph_values = [float(row["edge_value_total"]) for row in dataset.graph_edges]
    graph_out_degrees = [float(row["src_out_degree"]) for row in dataset.graph_edges]
    graph_in_degrees = [float(row["dst_in_degree"]) for row in dataset.graph_edges]

    label_distribution = {
        "is_fraud_true": sum(1 for row in dataset.labels if row["is_fraud"]),
        "is_fraud_false": sum(1 for row in dataset.labels if not row["is_fraud"]),
        "lookalike_true": sum(1 for row in dataset.labels if row["is_legit_lookalike"]),
        "attack_metadata_rows": sum(
            1
            for row in dataset.labels
            if row["attack_id"] is not None
            or row["campaign_id"] is not None
            or row["pretext"] is not None
        ),
    }

    summary = {
        "passed": not errors,
        "table_row_counts": {name: len(dataset.tables[name]) for name in EXPECTED_TABLES},
        "timestamp_range": {
            "start": min(timestamps).isoformat() if timestamps else None,
            "end": max(timestamps).isoformat() if timestamps else None,
        },
        "graph_edge_count": len(dataset.graph_edges),
        "transactions_by_rail": _count_by(dataset.transactions, "rail"),
        "transactions_by_channel": _count_by(dataset.transactions, "channel"),
        "unique_parties": len({row["party_id"] for row in dataset.tables["parties"]}),
        "unique_merchants": len({row["merchant_id"] for row in dataset.tables["merchants"]}),
        "unique_devices": len({row["device_id"] for row in dataset.tables["devices"]}),
        "graph_out_degree_summary": _quantiles(graph_out_degrees),
        "graph_in_degree_summary": _quantiles(graph_in_degrees),
        "edge_value_summary": _quantiles(graph_values),
        "label_distribution": label_distribution,
        "temporal_split_sizes": {name: len(ids) for name, ids in splits.transaction_ids.items()},
        "temporal_split_ranges": {
            name: {"start": window.start.isoformat(), "end": window.end.isoformat()}
            for name, window in windows.items()
        },
        "split_graph_edge_counts": split_graph_counts,
        "leakage_checks": {"ok": leakage.ok, "errors": leakage.errors, "details": leakage.details},
        "foreign_key_checks": "passed" if not leakage.errors else "see leakage_checks.errors",
        "schema_checks": "passed" if not [e for e in errors if "schema" in e] else "failed",
    }
    if any(row["edge_value_total"] <= Decimal("0.00") for row in dataset.graph_edges):
        errors.append("graph edge with non-positive value_total")
    summary["passed"] = not errors
    return Stage2ValidationReport(errors=errors, summary=summary)
