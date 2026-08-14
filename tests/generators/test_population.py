from __future__ import annotations

import numpy as np
import pytest

from src.generators import calibration as cal
from src.generators.population import (
    generate_devices,
    generate_merchants,
    generate_parties,
    generate_population,
)

N_SMALL = 5_000

# generate_population() reads N_CONSUMER_PARTIES/N_MERCHANTS from calibration
# at call time, so patching them here shrinks the full-pipeline integration
# tests without touching the real production-scale values.
N_TEST_PARTIES = 3_000
N_TEST_MERCHANTS = 300


def _rng(seed: int = 42) -> np.random.Generator:
    return np.random.default_rng(seed)


@pytest.fixture
def small_population(monkeypatch):
    monkeypatch.setattr(cal, "N_CONSUMER_PARTIES", N_TEST_PARTIES)
    monkeypatch.setattr(cal, "N_MERCHANTS", N_TEST_MERCHANTS)


# --- reproducibility -------------------------------------------------------


def test_parties_reproducible():
    a = generate_parties(_rng(42), N_SMALL)
    b = generate_parties(_rng(42), N_SMALL)
    assert [gp.party.party_id for gp in a] == [gp.party.party_id for gp in b]
    assert [gp.party.organic_spend_ratio for gp in a] == [gp.party.organic_spend_ratio for gp in b]


def test_full_population_reproducible(small_population):
    a = generate_population(seed=7)
    b = generate_population(seed=7)
    assert [gp.party.party_id for gp in a.parties] == [gp.party.party_id for gp in b.parties]
    assert [gm.merchant.merchant_id for gm in a.merchants] == [
        gm.merchant.merchant_id for gm in b.merchants
    ]
    assert [d.device_id for d in a.devices] == [d.device_id for d in b.devices]


def test_different_seeds_differ():
    a = generate_parties(_rng(1), N_SMALL)
    b = generate_parties(_rng(2), N_SMALL)
    assert [gp.party.party_id for gp in a] != [gp.party.party_id for gp in b]


# --- scale and uniqueness ---------------------------------------------------


def test_population_scale_matches_calibration(small_population):
    bundle = generate_population(seed=42)
    assert len(bundle.parties) == N_TEST_PARTIES
    assert len(bundle.merchants) == N_TEST_MERCHANTS


def test_ids_are_unique(small_population):
    bundle = generate_population(seed=42)
    party_ids = [gp.party.party_id for gp in bundle.parties] + [
        gm.party.party_id for gm in bundle.merchants
    ]
    assert len(party_ids) == len(set(party_ids))
    device_ids = [d.device_id for d in bundle.devices]
    assert len(device_ids) == len(set(device_ids))


@pytest.mark.slow
def test_full_scale_smoke():
    """Runs generate_population() at real production scale, once."""
    bundle = generate_population(seed=42)
    assert len(bundle.parties) == cal.N_CONSUMER_PARTIES
    assert len(bundle.merchants) == cal.N_MERCHANTS
    party_ids = {gp.party.party_id for gp in bundle.parties} | {
        gm.party.party_id for gm in bundle.merchants
    }
    assert len(party_ids) == cal.N_CONSUMER_PARTIES + cal.N_MERCHANTS


# --- fk integrity ------------------------------------------------------------


def test_merchant_party_id_equals_merchant_id():
    merchants = generate_merchants(_rng(42), 500)
    for gm in merchants:
        assert gm.party.party_id == gm.merchant.merchant_id


def test_devices_reference_known_parties():
    parties = generate_parties(_rng(42), N_SMALL)
    party_ids = {gp.party.party_id for gp in parties}
    devices, known = generate_devices(_rng(42), parties)

    device_ids = {d.device_id for d in devices}
    for d in devices:
        assert d.primary_party_id in party_ids
        if d.replaced_device_id is not None:
            assert d.replaced_device_id in device_ids

    assert set(known.keys()) <= party_ids
    for pid, dids in known.items():
        for did in dids:
            assert did in device_ids


def test_every_consumer_has_at_least_one_known_device():
    parties = generate_parties(_rng(42), N_SMALL)
    _, known = generate_devices(_rng(42), parties)
    for gp in parties:
        assert len(known.get(gp.party.party_id, [])) >= 1


# --- value ranges ------------------------------------------------------------


def test_party_ratio_fields_in_unit_interval():
    parties = generate_parties(_rng(42), N_SMALL)
    for gp in parties:
        assert 0.0 <= gp.party.organic_spend_ratio <= 1.0
        assert 0.0 <= gp.party.throughput_ratio_24h <= 1.0
        assert gp.party.account_age_days >= 0
        assert gp.party.distinct_counterparties_30d >= 1


def test_merchant_rate_fields_in_unit_interval():
    merchants = generate_merchants(_rng(42), 500)
    for gm in merchants:
        m = gm.merchant
        assert 0.0 <= m.chargeback_rate_30d <= 1.0
        assert 0.0 <= m.refund_rate_30d <= 1.0
        assert 0.0 <= m.decline_rate_30d <= 1.0
        assert m.settlement_account_age_days >= 0
        assert m.settlement_outflow_latency_h > 0


def test_device_upgrade_chain_is_consistent():
    parties = generate_parties(_rng(0), N_SMALL)
    devices, _ = generate_devices(_rng(0), parties)
    by_id = {d.device_id: d for d in devices}
    for d in devices:
        if d.replaced_device_id is not None:
            old = by_id[d.replaced_device_id]
            assert old.retired_at == d.first_seen_at
            assert old.retired_at is not None


# --- marginals within tolerance of calibration weights -----------------------


@pytest.mark.parametrize("income_type,weight", cal.INCOME_TYPE_WEIGHTS.items())
def test_income_type_marginal_close_to_calibration(income_type, weight):
    parties = generate_parties(_rng(42), 40_000)
    share = sum(1 for gp in parties if gp.income_type == income_type) / len(parties)
    assert abs(share - weight) < 0.03


def test_has_salary_credit_matches_salaried_income_type():
    parties = generate_parties(_rng(42), N_SMALL)
    for gp in parties:
        assert gp.party.has_salary_credit == (gp.income_type == "salaried")
