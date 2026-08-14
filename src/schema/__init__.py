"""Canonical data schema — one module per table, matching docs/data-schema-v1.md.

`devices` is the one table not in that doc; see devices.py for why it exists.
"""

from __future__ import annotations

import pyarrow as pa

from src.schema import (
    devices,
    disputes,
    graph_edges,
    labels,
    mandates,
    merchants,
    parties,
    transactions,
)
from src.schema.devices import Device
from src.schema.disputes import Dispute
from src.schema.graph_edges import GraphEdge
from src.schema.labels import Label
from src.schema.mandates import Mandate
from src.schema.merchants import Merchant
from src.schema.parties import Party
from src.schema.transactions import Transaction

__all__ = [
    "Transaction",
    "Party",
    "Device",
    "Merchant",
    "Mandate",
    "Dispute",
    "GraphEdge",
    "Label",
    "TABLE_ARROW_SCHEMAS",
]

# Registry used by the parquet writer and validation report — table name -> arrow schema.
TABLE_ARROW_SCHEMAS: dict[str, pa.Schema] = {
    "transactions": transactions.arrow_schema(),
    "parties": parties.arrow_schema(),
    "devices": devices.arrow_schema(),
    "merchants": merchants.arrow_schema(),
    "mandates": mandates.arrow_schema(),
    "disputes": disputes.arrow_schema(),
    "graph_edges": graph_edges.arrow_schema(),
    "labels": labels.arrow_schema(),
}
