"""Unit tests for src/validation/marginals.py against small synthetic
transaction/graph_edges fixtures -- no generated dataset required."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.schema.common import IST
from src.validation.marginals import (
    DEFAULT_REFERENCE_DIR,
    REFERENCE_DATASETS,
    amount_distribution_by_mcc,
    amount_quantiles,
    categorical_cardinality,
    compute_marginals,
    gini,
    graph_degree_distribution,
    inter_arrival_seconds_by_party,
    load_all_references,
    load_reference,
    run_all_comparisons,
    summary_stats,
    temporal_patterns,
    transactions_per_entity,
)

_T0 = datetime(2026, 3, 2, 9, 0, 0, tzinfo=IST)  # a Monday


def _txn(
    txn_id: str,
    payer: str,
    payee: str,
    amount: str,
    ts: datetime,
    mcc: int | None = 5411,
    merchant_id: str | None = "merchant-1",
    device_id: str = "device-1",
) -> dict:
    return {
        "txn_id": txn_id,
        "payer_id": payer,
        "payee_id": payee,
        "amount": Decimal(amount),
        "timestamp": ts,
        "mcc": mcc,
        "merchant_id": merchant_id,
        "device_id": device_id,
    }


@pytest.fixture
def small_transactions() -> list[dict]:
    txns = []
    for i in range(20):
        payer = f"payer-{i % 4}"
        merchant = f"merchant-{i % 3}"
        mcc = [5411, 5812, 7011][i % 3]
        amount = "100.00" if mcc != 7011 else "5000.00"  # hotels (7011) pricier than grocery
        txns.append(
            _txn(
                f"txn-{i}",
                payer,
                merchant,
                amount,
                _T0 + timedelta(hours=i, minutes=i * 7),
                mcc=mcc,
                merchant_id=merchant,
                device_id=f"device-{i % 2}",
            )
        )
    # a P2P row with no MCC/merchant, must not blow up MCC/cardinality logic
    txns.append(_txn("txn-p2p", "payer-0", "payer-1", "250.00", _T0 + timedelta(days=1), mcc=None, merchant_id=None))
    return txns


@pytest.fixture
def small_graph_edges() -> list[dict]:
    return [
        {"src_party_id": "payer-0", "dst_party_id": "merchant-0", "src_out_degree": 3, "dst_in_degree": 1},
        {"src_party_id": "payer-0", "dst_party_id": "merchant-1", "src_out_degree": 3, "dst_in_degree": 2},
        {"src_party_id": "payer-0", "dst_party_id": "merchant-2", "src_out_degree": 3, "dst_in_degree": 1},
        {"src_party_id": "payer-1", "dst_party_id": "merchant-0", "src_out_degree": 1, "dst_in_degree": 1},
        {"src_party_id": "payer-2", "dst_party_id": "merchant-1", "src_out_degree": 1, "dst_in_degree": 2},
    ]


def test_summary_stats_empty() -> None:
    stats = summary_stats([])
    assert stats["n"] == 0
    assert stats["mean"] == 0.0


def test_summary_stats_basic_shape() -> None:
    stats = summary_stats([1, 2, 3, 4, 100])
    assert stats["n"] == 5
    assert stats["min"] == 1
    assert stats["max"] == 100
    assert stats["median"] == 3
    # heavy right tail -> mean pulled well above median
    assert stats["mean"] > stats["median"]
    assert stats["mean_to_median"] > 1.0


def test_amount_quantiles_matches_summary_stats() -> None:
    amounts = [Decimal("10.00"), Decimal("20.00"), Decimal("30.00")]
    result = amount_quantiles(amounts)
    assert result["n"] == 3
    assert result["mean"] == pytest.approx(20.0)


def test_gini_uniform_is_zero() -> None:
    assert gini([5, 5, 5, 5]) == pytest.approx(0.0, abs=1e-9)


def test_gini_concentrated_is_high() -> None:
    # one party holds almost everything -> high inequality
    concentrated = gini([1, 1, 1, 1, 100])
    even = gini([20, 21, 19, 20, 20])
    assert concentrated > even
    assert 0.0 <= concentrated <= 1.0


def test_gini_empty_is_zero() -> None:
    assert gini([]) == 0.0


def test_amount_distribution_by_mcc_excludes_p2p_rows(small_transactions) -> None:
    by_mcc = amount_distribution_by_mcc(small_transactions)
    assert None not in by_mcc
    assert set(by_mcc) == {5411, 5812, 7011}
    # hotels (7011) should show a materially higher median than grocery (5411)
    assert by_mcc[7011]["median"] > by_mcc[5411]["median"]


def test_inter_arrival_seconds_by_party_positive_gaps(small_transactions) -> None:
    result = inter_arrival_seconds_by_party(small_transactions)
    assert result["n"] > 0
    assert result["min"] >= 0.0
    assert result["mean"] > 0.0


def test_inter_arrival_handles_single_transaction_party() -> None:
    txns = [_txn("t1", "solo-payer", "merchant-1", "50.00", _T0)]
    result = inter_arrival_seconds_by_party(txns)
    assert result["n"] == 0  # no consecutive pair exists for a lone transaction


def test_categorical_cardinality(small_transactions) -> None:
    result = categorical_cardinality(small_transactions)
    assert result["n_distinct_mcc"] == 3
    assert result["n_distinct_merchants_transacted"] == 3
    assert result["devices_per_party"]["n"] == 4  # 4 distinct payers


def test_transactions_per_entity(small_transactions) -> None:
    result = transactions_per_entity(small_transactions, "payer_id")
    assert result["n"] == 4
    assert result["mean"] == pytest.approx(len(small_transactions) / 4)


def test_temporal_patterns_sums_to_one(small_transactions) -> None:
    temporal = temporal_patterns(small_transactions)
    assert sum(temporal["hour_of_day"].values()) == pytest.approx(1.0)
    assert sum(temporal["day_of_week"].values()) == pytest.approx(1.0)
    assert set(temporal["hour_of_day"]) == set(range(24))
    assert set(temporal["day_of_week"]) == set(range(7))


def test_temporal_patterns_empty_input() -> None:
    temporal = temporal_patterns([])
    assert temporal == {"hour_of_day": {}, "day_of_week": {}}


def test_graph_degree_distribution(small_graph_edges) -> None:
    result = graph_degree_distribution(small_graph_edges)
    assert result["n_parties_with_out_edges"] == 3
    assert result["n_parties_with_in_edges"] == 3
    assert 0.0 <= result["gini_src_out_degree"] <= 1.0
    assert 0.0 <= result["gini_dst_in_degree"] <= 1.0


def test_compute_marginals_end_to_end(small_transactions, small_graph_edges) -> None:
    result = compute_marginals(small_transactions, small_graph_edges)
    assert result.n_transactions == len(small_transactions)
    assert result.amount_overall["n"] == len(small_transactions)
    assert set(result.amount_by_mcc) == {5411, 5812, 7011}


@pytest.mark.parametrize("name", REFERENCE_DATASETS)
def test_reference_files_load_and_are_well_formed(name: str) -> None:
    reference = load_reference(name)
    assert "source" in reference or name == "general_notes"
    if name != "general_notes":
        assert "stats" in reference
        assert "not_usable_for" in reference


def test_load_all_references_returns_every_dataset() -> None:
    references = load_all_references()
    assert set(references) == set(REFERENCE_DATASETS)


def test_reference_dir_default_points_at_committed_data() -> None:
    assert DEFAULT_REFERENCE_DIR == Path("data/reference")


def test_run_all_comparisons_covers_all_six_areas(small_transactions, small_graph_edges) -> None:
    result = compute_marginals(small_transactions, small_graph_edges)
    findings = run_all_comparisons(result)
    areas = {f.area for f in findings}
    expected_areas = {
        "amount_distribution",
        "amount_distribution_per_mcc",
        "inter_arrival_time",
        "categorical_cardinality",
        "transactions_per_party",
        "temporal_patterns",
        "graph_degree_distribution",
    }
    assert expected_areas <= areas
    assert len(findings) > 0
    # every finding must be honest about missing references, never silently blank
    for f in findings:
        if f.reference_value is None:
            assert f.note, f"finding {f.metric!r} has no reference value and no explanatory note"
