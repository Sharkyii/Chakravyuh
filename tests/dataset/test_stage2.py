from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow as pa

from src.dataset.leakage import run_leakage_checks
from src.dataset.loader import EXPECTED_TABLES, PaymentDataset, load_dataset
from src.dataset.splits import TemporalSplitConfig, temporal_split_transactions
from src.dataset.stage2 import build_stage2_dataset
from src.generators import calibration as cal
from src.generators.dataset import generate_stage1_dataset
from src.graph.builder import build_graph_edges
from src.schema import TABLE_ARROW_SCHEMAS
from src.validation.stage2 import validate_stage2_dataset


def _txn(txn_id: str, ts: datetime, payer: str, payee: str, amount: str) -> dict:
    return {
        "txn_id": txn_id,
        "timestamp": ts,
        "payer_id": payer,
        "payee_id": payee,
        "amount": Decimal(amount),
    }


def _small_stage2(tmp_path: Path) -> PaymentDataset:
    stage1 = tmp_path / "stage1"
    stage2 = tmp_path / "stage2"
    generate_stage1_dataset(seed=42, output_dir=stage1, n_consumers=80, n_merchants=12)
    report = build_stage2_dataset(input_dir=stage1, output_dir=stage2)
    assert report.ok
    return load_dataset(stage2)


def test_graph_construction_generates_schema_valid_edges():
    rows = [
        _txn("t1", cal.SIM_START + timedelta(hours=1), "a", "b", "10.00"),
        _txn("t2", cal.SIM_START + timedelta(hours=2), "a", "b", "15.00"),
        _txn("t3", cal.SIM_START + timedelta(hours=3), "a", "c", "20.00"),
        _txn("t4", cal.SIM_START + timedelta(hours=4), "b", "d", "5.00"),
    ]
    edges = build_graph_edges(rows)
    assert len(edges) == 3
    table = pa.Table.from_pylist([asdict(edge) for edge in edges], schema=TABLE_ARROW_SCHEMAS["graph_edges"])
    assert table.schema.equals(TABLE_ARROW_SCHEMAS["graph_edges"])


def test_graph_determinism_and_repeated_relationship_aggregation():
    rows = [
        _txn("t1", cal.SIM_START + timedelta(hours=1), "a", "b", "10.00"),
        _txn("t2", cal.SIM_START + timedelta(hours=3), "a", "b", "15.00"),
        _txn("t3", cal.SIM_START + timedelta(hours=5), "a", "c", "20.00"),
    ]
    a = build_graph_edges(rows)
    b = build_graph_edges(list(reversed(rows)))
    assert a == b
    edge_ab = next(edge for edge in a if edge.src_party_id == "a" and edge.dst_party_id == "b")
    assert edge_ab.edge_count == 2
    assert edge_ab.edge_value_total == Decimal("25.00")
    assert edge_ab.mean_inter_arrival_s == 7200.0
    assert edge_ab.src_out_degree == 2
    assert edge_ab.dst_in_degree == 1


def test_two_hop_passthrough_indicator_is_derived_from_timestamps():
    rows = [
        _txn("t1", cal.SIM_START + timedelta(hours=1), "a", "b", "10.00"),
        _txn("t2", cal.SIM_START + timedelta(hours=2), "b", "c", "9.00"),
    ]
    edge_ab = next(edge for edge in build_graph_edges(rows) if edge.src_party_id == "a")
    assert edge_ab.is_two_hop_passthrough is True


def test_temporal_split_ordering_and_no_overlap():
    rows = [
        {"txn_id": "train", "timestamp": cal.SIM_START + timedelta(days=1)},
        {"txn_id": "validation", "timestamp": cal.SIM_START + timedelta(days=55)},
        {"txn_id": "test", "timestamp": cal.SIM_START + timedelta(days=75)},
    ]
    labels = [{"txn_id": row["txn_id"]} for row in rows]
    splits = temporal_split_transactions(rows, labels)
    assert splits.transaction_ids["train"] == {"train"}
    assert splits.transaction_ids["validation"] == {"validation"}
    assert splits.transaction_ids["test"] == {"test"}
    assert not (splits.transaction_ids["train"] & splits.transaction_ids["validation"])


def test_stage2_loader_loads_all_expected_tables(tmp_path: Path):
    dataset = _small_stage2(tmp_path)
    assert set(dataset.tables) == set(EXPECTED_TABLES)
    metadata = dataset.metadata()
    assert metadata.row_counts["transactions"] > 0
    assert metadata.row_counts["graph_edges"] > 0
    assert metadata.dataset_version == "stage2-graph-harness-v1"


def test_label_integrity_and_valid_stage2_validation(tmp_path: Path):
    dataset = _small_stage2(tmp_path)
    report = validate_stage2_dataset(dataset)
    assert report.ok
    assert report.summary["label_distribution"]["is_fraud_true"] == 0
    assert report.summary["label_distribution"]["attack_metadata_rows"] == 0
    assert report.summary["leakage_checks"]["ok"] is True


def test_leakage_checks_detect_label_feature_column(tmp_path: Path):
    dataset = _small_stage2(tmp_path)
    dataset.transactions[0]["is_fraud"] = False
    report = run_leakage_checks(dataset)
    assert not report.ok
    assert any("label-only fields" in error for error in report.errors)


def test_leakage_checks_detect_duplicate_labels(tmp_path: Path):
    dataset = _small_stage2(tmp_path)
    dataset.labels.append(dict(dataset.labels[0]))
    report = run_leakage_checks(dataset)
    assert not report.ok
    assert any("duplicate labels" in error for error in report.errors)


def test_validation_fails_for_corrupted_device_reference(tmp_path: Path):
    dataset = _small_stage2(tmp_path)
    dataset.transactions[0]["device_id"] = "missing-device"
    report = validate_stage2_dataset(dataset)
    assert not report.ok
    assert any("invalid device reference" in error for error in report.errors)


def test_split_config_is_configurable():
    config = TemporalSplitConfig(train_fraction=0.5, validation_fraction=0.25, test_fraction=0.25)
    rows = [
        {"txn_id": "a", "timestamp": cal.SIM_START + timedelta(days=41)},
        {"txn_id": "b", "timestamp": cal.SIM_START + timedelta(days=42)},
        {"txn_id": "c", "timestamp": cal.SIM_START + timedelta(days=70)},
    ]
    labels = [{"txn_id": row["txn_id"]} for row in rows]
    splits = temporal_split_transactions(rows, labels, config)
    assert splits.transaction_ids["train"] == {"a"}
    assert splits.transaction_ids["validation"] == {"b"}
    assert splits.transaction_ids["test"] == {"c"}
