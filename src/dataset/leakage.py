"""Explicit leakage checks for generated payment datasets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.dataset.loader import PaymentDataset
from src.dataset.splits import TemporalSplitConfig, assign_split, temporal_split_transactions
from src.schema.enums import DetectableAt

LABEL_ONLY_COLUMNS = {"is_fraud", "attack_id", "campaign_id", "pretext", "is_legit_lookalike", "detectable_at"}


@dataclass(slots=True)
class LeakageReport:
    """Result of leakage checks intended to gate future ML training."""

    errors: list[str]
    details: dict[str, Any]

    @property
    def ok(self) -> bool:
        return not self.errors


def run_leakage_checks(
    dataset: PaymentDataset, config: TemporalSplitConfig | None = None
) -> LeakageReport:
    """Run deterministic split, label and graph leakage checks."""
    errors: list[str] = []
    splits = temporal_split_transactions(dataset.transactions, dataset.labels, config)

    txn_counts = Counter(row["txn_id"] for row in dataset.transactions)
    duplicate_txns = sorted(txn_id for txn_id, count in txn_counts.items() if count > 1)
    if duplicate_txns:
        errors.append(f"duplicate transaction IDs: {duplicate_txns[:5]}")

    label_counts = Counter(row["txn_id"] for row in dataset.labels)
    duplicate_labels = sorted(txn_id for txn_id, count in label_counts.items() if count > 1)
    if duplicate_labels:
        errors.append(f"duplicate labels: {duplicate_labels[:5]}")

    if set(txn_counts) != set(label_counts):
        errors.append("transaction IDs and label IDs do not match exactly")

    for split_name, ids in splits.transaction_ids.items():
        for other_name, other_ids in splits.transaction_ids.items():
            if split_name < other_name and ids & other_ids:
                errors.append(f"duplicate transaction IDs across {split_name}/{other_name}")
    for split_name, ids in splits.label_ids.items():
        for other_name, other_ids in splits.label_ids.items():
            if split_name < other_name and ids & other_ids:
                errors.append(f"duplicate label IDs across {split_name}/{other_name}")

    for row in dataset.transactions:
        split_name = assign_split(row["timestamp"], splits.windows)
        if split_name is None:
            errors.append(f"transaction outside temporal split boundaries: {row['txn_id']}")

    ordered_windows = [splits.windows[name] for name in ("train", "validation", "test")]
    if not (
        ordered_windows[0].end == ordered_windows[1].start
        and ordered_windows[1].end == ordered_windows[2].start
        and ordered_windows[0].start < ordered_windows[0].end <= ordered_windows[1].end <= ordered_windows[2].end
    ):
        errors.append("temporal split windows are not strictly ordered")

    if dataset.transactions:
        leaked_columns = sorted(set(dataset.transactions[0]) & LABEL_ONLY_COLUMNS)
        if leaked_columns:
            errors.append(f"label-only fields present in transaction features: {leaked_columns}")

    party_ids = {row["party_id"] for row in dataset.tables["parties"]}
    merchant_ids = {row["merchant_id"] for row in dataset.tables["merchants"]}
    device_ids = {row["device_id"] for row in dataset.tables["devices"]}
    for row in dataset.transactions:
        if row["payer_id"] not in party_ids or row["payee_id"] not in party_ids:
            errors.append(f"invalid transaction party reference: {row['txn_id']}")
        if row["merchant_id"] is not None and row["merchant_id"] not in merchant_ids:
            errors.append(f"invalid merchant reference: {row['txn_id']}")
        if row["device_id"] not in device_ids:
            errors.append(f"invalid device reference: {row['txn_id']}")

    allowed_detectable_at = {item.value for item in DetectableAt}
    for row in dataset.labels:
        if row["is_fraud"] is not False:
            errors.append(f"baseline label is fraud: {row['txn_id']}")
        if row["attack_id"] is not None or row["campaign_id"] is not None or row["pretext"] is not None:
            errors.append(f"baseline label contains attack metadata: {row['txn_id']}")
        if row["is_legit_lookalike"] is not False:
            errors.append(f"baseline label marked lookalike: {row['txn_id']}")
        if row["detectable_at"] is not None and row["detectable_at"] not in allowed_detectable_at:
            errors.append(f"invalid detectable_at value: {row['txn_id']}")

    for edge in dataset.graph_edges:
        if edge["src_party_id"] not in party_ids or edge["dst_party_id"] not in party_ids:
            errors.append(f"invalid graph edge party reference: {edge['src_party_id']}->{edge['dst_party_id']}")
        if edge["window_start"] >= edge["window_end"]:
            errors.append(f"invalid graph edge window: {edge['src_party_id']}->{edge['dst_party_id']}")
        if edge["window_start"] < ordered_windows[0].start or edge["window_end"] > ordered_windows[-1].end:
            errors.append(f"graph edge outside dataset window: {edge['src_party_id']}->{edge['dst_party_id']}")

    details = {
        "transaction_duplicates": len(duplicate_txns),
        "label_duplicates": len(duplicate_labels),
        "split_sizes": {name: len(ids) for name, ids in splits.transaction_ids.items()},
        "label_feature_columns_present": sorted(set(dataset.transactions[0]) & LABEL_ONLY_COLUMNS) if dataset.transactions else [],
        "full_window_graph_edges": len(dataset.graph_edges),
    }
    return LeakageReport(errors=errors, details=details)
