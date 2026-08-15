"""Load generated Parquet datasets without hard-coded paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


EXPECTED_TABLES = (
    "transactions",
    "labels",
    "parties",
    "devices",
    "merchants",
    "mandates",
    "disputes",
    "graph_edges",
)


@dataclass(slots=True)
class DatasetMetadata:
    """Small metadata object for generated datasets."""

    source_dir: Path
    dataset_version: str | None
    seed: int | None
    row_counts: dict[str, int]
    transaction_start: str | None
    transaction_end: str | None


@dataclass(slots=True)
class PaymentDataset:
    """Loaded generated payment dataset as Arrow pylist rows."""

    source_dir: Path
    tables: dict[str, list[dict[str, Any]]]
    manifest: dict[str, Any]

    @property
    def transactions(self) -> list[dict[str, Any]]:
        return self.tables["transactions"]

    @property
    def labels(self) -> list[dict[str, Any]]:
        return self.tables["labels"]

    @property
    def graph_edges(self) -> list[dict[str, Any]]:
        return self.tables["graph_edges"]

    def metadata(self) -> DatasetMetadata:
        timestamps = [row["timestamp"] for row in self.transactions]
        return DatasetMetadata(
            source_dir=self.source_dir,
            dataset_version=self.manifest.get("dataset_version"),
            seed=self.manifest.get("seed"),
            row_counts={name: len(rows) for name, rows in sorted(self.tables.items())},
            transaction_start=min(timestamps).isoformat() if timestamps else None,
            transaction_end=max(timestamps).isoformat() if timestamps else None,
        )


def load_dataset(source_dir: Path) -> PaymentDataset:
    """Load all expected generated Parquet tables plus manifest."""
    tables: dict[str, list[dict[str, Any]]] = {}
    for table_name in EXPECTED_TABLES:
        path = source_dir / f"{table_name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"missing dataset table: {path}")
        tables[table_name] = pq.read_table(path).to_pylist()

    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return PaymentDataset(source_dir=source_dir, tables=tables, manifest=manifest)
