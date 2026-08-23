"""Arrow schemas must not drift from the dataclasses, and every table must
round-trip through parquet losslessly -- this is what the streaming writer
in later phases will rely on.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.schema import TABLE_ARROW_SCHEMAS
from tests.schema.fixtures import (
    sample_device,
    sample_dispute,
    sample_graph_edge,
    sample_label,
    sample_mandate,
    sample_merchant,
    sample_party,
    sample_transaction,
)

SAMPLES = {
    "transactions": sample_transaction,
    "parties": sample_party,
    "devices": sample_device,
    "merchants": sample_merchant,
    "mandates": sample_mandate,
    "disputes": sample_dispute,
    "graph_edges": sample_graph_edge,
    "labels": sample_label,
}


@pytest.mark.parametrize("table_name", sorted(TABLE_ARROW_SCHEMAS))
def test_arrow_schema_field_names_match_dataclass(table_name: str) -> None:
    dataclass_fields = {f.name for f in dataclasses.fields(SAMPLES[table_name]())}
    arrow_fields = set(TABLE_ARROW_SCHEMAS[table_name].names)
    assert arrow_fields == dataclass_fields, table_name


@pytest.mark.parametrize("table_name", sorted(TABLE_ARROW_SCHEMAS))
def test_row_round_trips_through_parquet(table_name: str, tmp_path: Path) -> None:
    schema = TABLE_ARROW_SCHEMAS[table_name]
    row = dataclasses.asdict(SAMPLES[table_name]())

    table = pa.Table.from_pylist([row], schema=schema)
    path = tmp_path / f"{table_name}.parquet"
    pq.write_table(table, path)
    read_back = pq.read_table(path)

    assert read_back.schema.equals(schema)
    assert read_back.to_pylist()[0] == table.to_pylist()[0]


def test_all_eight_tables_registered() -> None:
    assert set(TABLE_ARROW_SCHEMAS) == {
        "transactions",
        "parties",
        "devices",
        "merchants",
        "mandates",
        "disputes",
        "graph_edges",
        "labels",
    }
