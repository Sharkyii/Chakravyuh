from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pyarrow as pa

from src.dataset.loader import EXPECTED_TABLES, PaymentDataset
from src.schema import TABLE_ARROW_SCHEMAS
from src.schema.enums import DetectableAt


@dataclass(slots=True)
class AttackValidationReport:
    errors: list[str]
    summary: dict[str, Any]

    @property
    def ok(self) -> bool:
        return not self.errors


def _check_schema(table_name: str, rows: list[dict[str, Any]], errors: list[str]) -> None:
    try:
        pa.Table.from_pylist(rows, schema=TABLE_ARROW_SCHEMAS[table_name])
    except Exception as exc:  # pragma: no cover - pyarrow messages vary by version
        errors.append(f"{table_name} does not conform to schema: {exc}")


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = row.get(field)
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def validate_attack_dataset(dataset: PaymentDataset, attack_id: str) -> AttackValidationReport:
    """Validate attack-specific outputs without reusing the baseline leakage checker."""
    errors: list[str] = []
    for table_name in EXPECTED_TABLES:
        _check_schema(table_name, dataset.tables[table_name], errors)

    attack_labels = [row for row in dataset.labels if row["attack_id"] == attack_id]
    if not attack_labels:
        errors.append(f"no rows were generated for attack {attack_id}")

    attack_txn_ids = {row["txn_id"] for row in attack_labels}
    transaction_ids = {row["txn_id"] for row in dataset.transactions}
    if not attack_txn_ids.issubset(transaction_ids):
        errors.append(f"attack labels reference missing transactions for {attack_id}")

    if any(row["is_fraud"] is not True for row in attack_labels):
        errors.append(f"non-fraud label in {attack_id} campaign")
    if any(row["campaign_id"] is None for row in attack_labels):
        errors.append(f"campaign_id missing for {attack_id} attack labels")
    if any(row["pretext"] is None for row in attack_labels):
        errors.append(f"pretext missing for {attack_id} attack labels")
    if any(row["is_legit_lookalike"] is not False for row in attack_labels):
        errors.append(f"lookalike flag incorrectly set for {attack_id}")
    if any(
        row["detectable_at"] not in {item.value for item in DetectableAt} for row in attack_labels
    ):
        errors.append(f"invalid detectable_at for {attack_id}")

    campaign_ids = {row["campaign_id"] for row in attack_labels if row["campaign_id"] is not None}
    if len(campaign_ids) > 1:
        errors.append(f"attack rows for {attack_id} span multiple campaign IDs")
    if len(attack_labels) != len(attack_txn_ids):
        errors.append(f"duplicate attack labels detected for {attack_id}")

    attack_transaction_rows = [
        row for row in dataset.transactions if row["txn_id"] in attack_txn_ids
    ]
    if not attack_transaction_rows:
        errors.append(f"no attack transaction rows for {attack_id}")
    else:
        from datetime import datetime

        sim_start_str = dataset.manifest.get("simulation_start")
        sim_end_str = dataset.manifest.get("simulation_end")
        sim_start = datetime.fromisoformat(sim_start_str) if sim_start_str else None
        sim_end = datetime.fromisoformat(sim_end_str) if sim_end_str else None
        for row in attack_transaction_rows:
            ts = row["timestamp"]
            if sim_start is not None and ts < sim_start:
                errors.append(f"attack transaction outside simulation window: {row['txn_id']}")
            if sim_end is not None and ts >= sim_end:
                errors.append(f"attack transaction outside simulation window: {row['txn_id']}")

    party_ids = {row["party_id"] for row in dataset.tables["parties"]}
    device_ids = {row["device_id"] for row in dataset.tables["devices"]}
    merchant_ids = {row["merchant_id"] for row in dataset.tables["merchants"]}
    for row in attack_transaction_rows:
        if row["payer_id"] not in party_ids:
            errors.append(f"attack transaction references missing payer: {row['txn_id']}")
        if row["payee_id"] not in party_ids:
            errors.append(f"attack transaction references missing payee: {row['txn_id']}")
        if row["device_id"] not in device_ids:
            errors.append(f"attack transaction references missing device: {row['txn_id']}")
        if row["merchant_id"] is not None and row["merchant_id"] not in merchant_ids:
            errors.append(f"attack transaction references missing merchant: {row['txn_id']}")

    summary = {
        "attack_id": attack_id,
        "n_attack_rows": len(attack_labels),
        "campaign_ids": sorted(campaign_ids),
        "attack_row_distribution": _count_by(attack_labels, "attack_id"),
        "attack_pretexts": _count_by(attack_labels, "pretext"),
        "passed": not errors,
    }
    return AttackValidationReport(errors=errors, summary=summary)
