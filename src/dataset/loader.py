"""Load generated Parquet datasets without hard-coded paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
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


_dataset_cache: dict[Path, PaymentDataset] = {}


def clear_dataset_cache(path: Path | None = None) -> None:
    """Clear the loaded dataset cache, or a specific path."""
    if path is None:
        _dataset_cache.clear()
    else:
        _dataset_cache.pop(Path(path).resolve(), None)


def load_dataset(source_dir: Path) -> PaymentDataset:
    """Load all expected generated Parquet tables plus manifest."""
    abs_dir = Path(source_dir).resolve()
    if abs_dir in _dataset_cache:
        return _dataset_cache[abs_dir]

    tables: dict[str, list[dict[str, Any]]] = {}
    for table_name in EXPECTED_TABLES:
        path = abs_dir / f"{table_name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"missing dataset table: {path}")
        with open(path, "rb") as f:
            table = pq.read_table(f)

        ts_cols = []
        for i, field in enumerate(table.schema):
            if pa.types.is_timestamp(field.type):
                ts_cols.append(field.name)
                naive_type = pa.timestamp(field.type.unit)
                table = table.set_column(i, field.name, table.column(field.name).cast(naive_type))

        pylist = table.to_pylist()

        if ts_cols:
            from datetime import timezone
            from src.schema.common import IST
            for row in pylist:
                for col in ts_cols:
                    val = row[col]
                    if val is not None:
                        row[col] = val.replace(tzinfo=timezone.utc).astimezone(IST)

        tables[table_name] = pylist

    manifest_path = abs_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    ds = PaymentDataset(source_dir=source_dir, tables=tables, manifest=manifest)
    _dataset_cache[abs_dir] = ds
    return ds
