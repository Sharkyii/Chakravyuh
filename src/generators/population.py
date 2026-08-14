"""Population generators: parties, devices, merchants.

Two schema fields deserve a note before reading the code:

`parties.organic_spend_ratio`, `parties.throughput_ratio_24h` and
`parties.distinct_counterparties_30d` are defined in docs/data-schema-v1.md
as aggregates over a party's actual transactions. Those transactions don't
exist yet at population-generation time -- the legitimate transaction
generator (src/generators/legitimate.py) hasn't been built. So this module
generates them as *persistent persona targets*: values the legitimate
generator is built to realise when it produces each party's transactions,
not values computed backwards from transactions. Over a 12-week window with
enough transactions per party the realised behaviour should converge close
to the target; the validation report can check that convergence directly.
This is a deliberate design choice, not an oversight -- flag if it should
work the other way round.

`merchants` needs an internal notion of relative transaction volume (a few
large merchants, many small ones) to drive later generation, but the schema
has no such field and none should be invented. That weight lives only on
`GeneratedMerchant`, the in-memory wrapper below -- it is never written to
the `merchants` parquet table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np

from src.generators import calibration as cal
from src.generators.ids import new_uuid
from src.schema.devices import Device
from src.schema.enums import DeviceType, KycLevel, PartyType, VolumeGrowthCurve
from src.schema.merchants import Merchant
from src.schema.parties import Party


@dataclass(slots=True)
class GeneratedParty:
    party: Party
    income_type: str  # "salaried" | "gig" | "none" -- see calibration.INCOME_TYPE_WEIGHTS
    home_city: str


@dataclass(slots=True)
class GeneratedMerchant:
    merchant: Merchant
    party: Party  # party_type=MERCHANT, party_id == merchant.merchant_id
    volume_weight: float  # relative transaction-volume share; generator-internal only


@dataclass(slots=True)
class PopulationBundle:
    parties: list[GeneratedParty]
    merchants: list[GeneratedMerchant]
    devices: list[Device]
    # party_id -> device_ids that party can transact from (own + shared household).
    party_known_devices: dict[str, list[str]] = field(default_factory=dict)

    def all_party_rows(self) -> list[Party]:
        return [gp.party for gp in self.parties] + [gm.party for gm in self.merchants]

    def all_merchant_rows(self) -> list[Merchant]:
        return [gm.merchant for gm in self.merchants]


def _weighted_choice(rng: np.random.Generator, weights: dict):
    keys = list(weights.keys())
    probs = np.array(list(weights.values()), dtype=np.float64)
    return keys[rng.choice(len(keys), p=probs)]


def _random_pincode(rng: np.random.Generator) -> tuple[str, str]:
    city, prefix, _ = cal.CITY_PINCODE_WEIGHTS[
        rng.choice(len(cal.CITY_PINCODE_WEIGHTS), p=[w for _, _, w in cal.CITY_PINCODE_WEIGHTS])
    ]
    if city == "other":
        prefix = f"{rng.integers(100, 999):03d}"
    suffix = f"{rng.integers(0, 999):03d}"
    return city, f"{prefix}{suffix}"


def generate_parties(rng: np.random.Generator, n: int) -> list[GeneratedParty]:
    """Consumer parties. Merchant-type parties come from generate_merchants."""
    out: list[GeneratedParty] = []
    for _ in range(n):
        is_new = rng.random() < cal.ACCOUNT_AGE_NEW_FRACTION
        if is_new:
            account_age_days = int(rng.uniform(0, cal.ACCOUNT_AGE_NEW_MAX_DAYS))
        else:
            age = rng.gamma(
                cal.ACCOUNT_AGE_ESTABLISHED_GAMMA_SHAPE, cal.ACCOUNT_AGE_ESTABLISHED_GAMMA_SCALE
            )
            account_age_days = int(min(age, cal.ACCOUNT_AGE_ESTABLISHED_MAX_DAYS))

        kyc_level = KycLevel(_weighted_choice(rng, cal.KYC_LEVEL_WEIGHTS))
        kyc_completed_at = (
            None if kyc_level == KycLevel.NONE
            else cal.SIM_START - timedelta(days=account_age_days)
        )

        income_type = _weighted_choice(rng, cal.INCOME_TYPE_WEIGHTS)
        targets = cal.PERSONA_TARGETS[income_type]
        organic_spend_ratio = float(rng.beta(*targets["organic_spend_ratio"]))
        throughput_ratio_24h = float(rng.beta(*targets["throughput_ratio_24h"]))
        distinct_counterparties_30d = int(
            max(1, rng.poisson(cal.DISTINCT_COUNTERPARTIES_30D_MEAN[income_type]))
        )

        city, pincode = _random_pincode(rng)

        party = Party(
            party_id=new_uuid(rng),
            party_type=PartyType.CONSUMER,
            account_age_days=account_age_days,
            kyc_level=kyc_level,
            kyc_completed_at=kyc_completed_at,
            has_salary_credit=(income_type == "salaried"),
            organic_spend_ratio=organic_spend_ratio,
            throughput_ratio_24h=throughput_ratio_24h,
            distinct_counterparties_30d=distinct_counterparties_30d,
            home_pincode=pincode,
            flagged_by_ffri=bool(rng.random() < cal.FFRI_FALSE_POSITIVE_RATE),
        )
        out.append(GeneratedParty(party=party, income_type=income_type, home_city=city))
    return out


def generate_merchants(rng: np.random.Generator, n: int) -> list[GeneratedMerchant]:
    out: list[GeneratedMerchant] = []
    # Pareto-distributed relative volume share -> long tail of small merchants.
    raw_weights = rng.pareto(cal.MERCHANT_VOLUME_PARETO_ALPHA, size=n) + 1.0
    volume_weights = raw_weights / raw_weights.sum()

    for i in range(n):
        onboarded_before_window = rng.random() < cal.MERCHANT_ONBOARDED_BEFORE_WINDOW_FRACTION
        if onboarded_before_window:
            lookback = rng.uniform(1, cal.MERCHANT_ONBOARDING_LOOKBACK_DAYS)
            onboarded_at = cal.SIM_START - timedelta(days=lookback)
        else:
            offset = rng.uniform(0, cal.SIM_WEEKS * 7)
            onboarded_at = cal.SIM_START + timedelta(days=offset)

        settlement_account_age_days = max(0, (cal.SIM_START - onboarded_at).days) + int(
            rng.integers(0, 10)
        )

        mcc = int(_weighted_choice(rng, cal.MCC_WEIGHTS))

        merchant_id = new_uuid(rng)
        merchant = Merchant(
            merchant_id=merchant_id,
            mcc_declared=mcc,
            mcc_inferred_from_basket=mcc,  # no laundering signal in the legitimate population
            onboarded_at=onboarded_at,
            kyb_level=_weighted_choice(rng, cal.KYB_LEVEL_WEIGHTS),
            kyb_docs_verified_against_registry=bool(
                rng.random() < cal.KYB_DOCS_VERIFIED_AGAINST_REGISTRY_PROB
            ),
            days_to_first_txn=int(1 + rng.poisson(3)),
            volume_growth_curve=VolumeGrowthCurve(
                _weighted_choice(rng, cal.VOLUME_GROWTH_CURVE_WEIGHTS)
            ),
            chargeback_rate_30d=float(rng.beta(*cal.CHARGEBACK_RATE_30D_BETA)),
            refund_rate_30d=float(rng.beta(*cal.REFUND_RATE_30D_BETA)),
            decline_rate_30d=float(rng.beta(*cal.DECLINE_RATE_30D_BETA)),
            settlement_account_age_days=settlement_account_age_days,
            settlement_outflow_latency_h=float(
                max(
                    1.0,
                    rng.normal(
                        cal.SETTLEMENT_OUTFLOW_LATENCY_H_MEAN, cal.SETTLEMENT_OUTFLOW_LATENCY_H_SD
                    ),
                )
            ),
        )
        merchant_party = Party(
            party_id=merchant_id,
            party_type=PartyType.MERCHANT,
            account_age_days=max(0, (cal.SIM_START - onboarded_at).days),
            kyc_level=KycLevel.FULL if merchant.kyb_level == "full" else KycLevel.MIN_KYC,
            kyc_completed_at=onboarded_at,
            has_salary_credit=False,
            organic_spend_ratio=1.0,  # a merchant's own inflow is all P2M by definition
            throughput_ratio_24h=float(
                min(1.0, 1.0 / max(merchant.settlement_outflow_latency_h / 24.0, 1.0))
            ),
            distinct_counterparties_30d=0,  # filled in once transactions exist (step 3+)
            home_pincode="",  # merchants don't have a consumer home pincode
            flagged_by_ffri=False,
        )
        out.append(
            GeneratedMerchant(merchant=merchant, party=merchant_party, volume_weight=float(volume_weights[i]))
        )
    return out


def _make_device(
    rng: np.random.Generator,
    primary_party_id: str,
    first_seen_at,
    last_seen_at,
    is_shared: bool,
    retired_at=None,
    replaced_device_id: str | None = None,
) -> Device:
    device_type = DeviceType(_weighted_choice(rng, cal.DEVICE_TYPE_WEIGHTS))
    os_choices = cal.OS_NAME_VERSION[device_type.value]
    os_name, os_version = os_choices[rng.integers(0, len(os_choices))]
    return Device(
        device_id=new_uuid(rng),
        primary_party_id=primary_party_id,
        device_type=device_type,
        os_name=os_name,
        os_version=os_version,
        device_model=str(rng.choice(cal.DEVICE_MODELS[device_type.value])),
        fingerprint_hash=new_uuid(rng),
        is_emulator=False,
        is_shared_household_device=is_shared,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        retired_at=retired_at,
        replaced_device_id=replaced_device_id,
    )


def generate_devices(
    rng: np.random.Generator, parties: list[GeneratedParty]
) -> tuple[list[Device], dict[str, list[str]]]:
    devices: list[Device] = []
    known: dict[str, list[str]] = {}

    patterns = [_weighted_choice(rng, cal.DEVICE_PATTERN_WEIGHTS) for _ in parties]

    household_candidates = [
        gp.party.party_id for gp, pat in zip(parties, patterns) if pat == "shared_household"
    ]
    rng.shuffle(household_candidates)
    households = [
        household_candidates[i : i + 2] for i in range(0, len(household_candidates) - 1, 2)
    ]
    paired: dict[str, list[str]] = {}
    for pair in households:
        paired[pair[0]] = pair
        paired[pair[1]] = pair

    long_before = cal.SIM_START - timedelta(days=int(cal.POPULATION_LOOKBACK_DAYS * 0.5))

    for gp, pattern in zip(parties, patterns):
        pid = gp.party.party_id
        if pattern == "shared_household" and pid in paired:
            pair = paired[pid]
            if pid == pair[0]:
                dev = _make_device(rng, pid, long_before, cal.SIM_END, is_shared=True)
                devices.append(dev)
                known[pair[0]] = [dev.device_id]
                known[pair[1]] = [dev.device_id]
            continue  # second member of the pair handled when the first is processed

        if pattern == "upgraded_during_window":
            switch_day = rng.uniform(1, cal.SIM_WEEKS * 7 - 1)
            switch_at = cal.SIM_START + timedelta(days=switch_day)
            old = _make_device(rng, pid, long_before, switch_at, is_shared=False, retired_at=switch_at)
            new = _make_device(
                rng, pid, switch_at, cal.SIM_END, is_shared=False, replaced_device_id=old.device_id
            )
            devices.extend([old, new])
            known[pid] = [old.device_id, new.device_id]

        elif pattern == "multi_device":
            primary = _make_device(rng, pid, long_before, cal.SIM_END, is_shared=False)
            secondary = _make_device(rng, pid, cal.SIM_START, cal.SIM_END, is_shared=False)
            devices.extend([primary, secondary])
            known[pid] = [primary.device_id, secondary.device_id]

        else:  # stable_single, and the odd-one-out from household pairing
            dev = _make_device(rng, pid, long_before, cal.SIM_END, is_shared=False)
            devices.append(dev)
            known[pid] = [dev.device_id]

    return devices, known


def generate_population(seed: int) -> PopulationBundle:
    seed_seq = np.random.SeedSequence(seed)
    party_rng, merchant_rng, device_rng = (
        np.random.default_rng(s) for s in seed_seq.spawn(3)
    )

    parties = generate_parties(party_rng, cal.N_CONSUMER_PARTIES)
    merchants = generate_merchants(merchant_rng, cal.N_MERCHANTS)
    devices, known = generate_devices(device_rng, parties)

    return PopulationBundle(
        parties=parties, merchants=merchants, devices=devices, party_known_devices=known
    )
