from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.generators import calibration as cal
from src.generators.dataset import generate_stage1_dataset
from src.generators.legitimate import generate_legitimate_transactions
from src.generators.population import generate_population
from src.schema import TABLE_ARROW_SCHEMAS
from src.schema.enums import AuthMethod, AuthResult, Decision
from src.validation.legitimate import validate_legitimate_dataset

N_TEST_PARTIES = 400
N_TEST_MERCHANTS = 60


@pytest.fixture
def small_population(monkeypatch):
    monkeypatch.setattr(cal, "N_CONSUMER_PARTIES", N_TEST_PARTIES)
    monkeypatch.setattr(cal, "N_MERCHANTS", N_TEST_MERCHANTS)
    return generate_population(seed=42)


def _signature(dataset):
    return [
        (
            t.txn_id,
            t.timestamp,
            t.payer_id,
            t.payee_id,
            t.amount,
            t.rail,
            t.device_id,
        )
        for t in dataset.transactions
    ]


def test_legitimate_generation_is_deterministic(small_population):
    a = generate_legitimate_transactions(seed=42, population=small_population)
    b = generate_legitimate_transactions(seed=42, population=small_population)
    assert _signature(a) == _signature(b)
    assert [label.txn_id for label in a.labels] == [label.txn_id for label in b.labels]


def test_different_seed_changes_transactions(small_population):
    a = generate_legitimate_transactions(seed=1, population=small_population)
    b = generate_legitimate_transactions(seed=2, population=small_population)
    assert _signature(a) != _signature(b)


def test_generated_dataset_validates(small_population):
    dataset = generate_legitimate_transactions(seed=42, population=small_population)
    report = validate_legitimate_dataset(small_population, dataset)
    assert report.errors == []
    assert report.summary["n_transactions"] == len(dataset.transactions)
    assert report.summary["known_device_rate"] > 0.95


def test_foreign_keys_and_temporal_bounds(small_population):
    dataset = generate_legitimate_transactions(seed=42, population=small_population)
    party_ids = {p.party_id for p in small_population.all_party_rows()}
    consumer_ids = {p.party.party_id for p in small_population.parties}
    merchant_ids = {m.merchant.merchant_id for m in small_population.merchants}
    device_ids = {d.device_id for d in small_population.devices}

    for txn in dataset.transactions:
        assert txn.payer_id in consumer_ids
        assert txn.payee_id in party_ids
        assert txn.payer_id != txn.payee_id
        assert txn.device_id in device_ids
        assert cal.SIM_START <= txn.timestamp < cal.SIM_END
        if txn.merchant_id is not None:
            assert txn.merchant_id in merchant_ids
            assert txn.payee_id == txn.merchant_id
            assert txn.mcc is not None


def test_value_ranges_and_auth_consistency(small_population):
    dataset = generate_legitimate_transactions(seed=42, population=small_population)
    for txn in dataset.transactions:
        assert txn.amount > 0
        assert txn.currency == "INR"
        assert 0.0 <= txn.issuer_risk_score <= 1.0
        assert txn.session_duration_s > 0
        assert txn.time_on_confirm_screen_s > 0
        assert txn.beneficiary_added_ago_s >= 0
        assert txn.pin_attempts >= 0
        if txn.auth_method == AuthMethod.NONE:
            assert txn.auth_latency_ms is None
        if txn.auth_result == AuthResult.FAILURE:
            assert txn.decision == Decision.DECLINED
        if txn.decision == Decision.DECLINED:
            assert txn.decline_reason is not None


def test_legitimate_labels_have_no_attack_metadata(small_population):
    dataset = generate_legitimate_transactions(seed=42, population=small_population)
    txn_ids = {t.txn_id for t in dataset.transactions}
    assert {label.txn_id for label in dataset.labels} == txn_ids
    for label in dataset.labels:
        assert label.is_fraud is False
        assert label.attack_id is None
        assert label.campaign_id is None
        assert label.pretext is None
        assert label.is_legit_lookalike is False
        assert label.detectable_at is None


def test_stage1_writer_outputs_schema_valid_parquet(tmp_path: Path):
    out = tmp_path / "stage1"
    report = generate_stage1_dataset(
        seed=42,
        output_dir=out,
        n_consumers=120,
        n_merchants=20,
    )
    assert report.ok

    for table_name, schema in TABLE_ARROW_SCHEMAS.items():
        path = out / f"{table_name}.parquet"
        assert path.exists()
        assert pq.read_table(path).schema.equals(schema)

    assert (out / "manifest.json").exists()
    assert (out / "validation_report.json").exists()
