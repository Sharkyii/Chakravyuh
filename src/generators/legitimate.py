"""Legitimate payment-world transaction generator.

This module turns the population generator's persistent party targets into a
baseline stream of legitimate transactions. It intentionally does not generate
fraud, attacks, lookalikes, graph aggregates, disputes, or model features. The
goal is a realistic decision-time payment log that later attack generators can
augment without changing the schema contract.

The target fields on `parties` are realised approximately: each consumer's
P2M-vs-P2P choice is biased by `organic_spend_ratio`, transaction volume by
income persona, and the counterparty pool by `distinct_counterparties_30d`.
Exact rolling aggregates are left for a later validation/reporting stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

import numpy as np

from src.generators import calibration as cal
from src.generators.ids import new_uuid
from src.generators.population import GeneratedMerchant, GeneratedParty, PopulationBundle
from src.schema.devices import Device
from src.schema.enums import (
    AuthMethod,
    AuthResult,
    Channel,
    Decision,
    Direction,
    ExemptionClaimed,
    Rail,
)
from src.schema.labels import Label
from src.schema.merchants import Merchant
from src.schema.transactions import Transaction


@dataclass(slots=True)
class LegitimateDataset:
    """In-memory Stage 1 output: legitimate transactions plus separate labels."""

    transactions: list[Transaction]
    labels: list[Label]


def _weighted_choice(rng: np.random.Generator, weights: dict):
    keys = list(weights.keys())
    probs = np.array(list(weights.values()), dtype=np.float64)
    return keys[rng.choice(len(keys), p=probs)]


def _money(value: float) -> Decimal:
    return Decimal(str(max(value, 1.0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _amount_for_rail(
    rng: np.random.Generator, rail: Rail, income_type: str, mcc: int | None
) -> Decimal:
    persona_multiplier = {"salaried": 1.15, "gig": 0.95, "none": 0.65}[income_type]
    if rail in {Rail.CARD_CNP, Rail.CARD_CP}:
        value = rng.lognormal(mean=6.35, sigma=0.85) * persona_multiplier
    elif rail in {Rail.IMPS, Rail.NEFT}:
        value = rng.lognormal(mean=7.55, sigma=0.95) * persona_multiplier
    elif rail == Rail.WALLET:
        value = rng.lognormal(mean=4.8, sigma=0.75) * persona_multiplier
    else:
        value = rng.lognormal(mean=5.55, sigma=0.9) * persona_multiplier
    if mcc is not None:
        # issues.md I16 -- MCC-conditioned amount shape, sourced qualitatively
        # against BankSim's documented category-amount relationship (see
        # calibration.MCC_AMOUNT_MULTIPLIER's comment).
        value *= cal.MCC_AMOUNT_MULTIPLIER.get(mcc, cal.DEFAULT_MCC_AMOUNT_MULTIPLIER)
    return _money(value)


def _is_round_amount(amount: Decimal) -> bool:
    return amount % Decimal("100.00") == Decimal("0.00") or amount % Decimal("500.00") == Decimal(
        "0.00"
    )


def _day_weights(total_days: int) -> np.ndarray:
    """Per-day sampling weights over the simulation window, following
    calibration.DAY_OF_WEEK_WEIGHTS (issues.md I15). Computed once per
    generator run, not per transaction -- see generate_legitimate_transactions.
    """
    weights = np.array(
        [
            cal.DAY_OF_WEEK_WEIGHTS[(cal.SIM_START + timedelta(days=d)).weekday()]
            for d in range(total_days)
        ],
        dtype=np.float64,
    )
    return weights / weights.sum()


def _timestamp(rng: np.random.Generator, total_days: int, day_weights: np.ndarray) -> datetime:
    day_offset = int(rng.choice(total_days, p=day_weights))
    seconds_into_day = int(rng.integers(0, 86_400))
    base = cal.SIM_START + timedelta(days=day_offset, seconds=seconds_into_day)
    # Human payments cluster outside sleeping hours; retain a small overnight tail.
    if rng.random() < 0.88 and base.hour < 6:
        base = base + timedelta(hours=int(rng.integers(7, 15)))
    if base >= cal.SIM_END:
        base = cal.SIM_END - timedelta(milliseconds=1)
    return base


def _active_devices(devices: Iterable[Device], timestamp: datetime) -> list[Device]:
    return [
        d
        for d in devices
        if d.first_seen_at <= timestamp <= d.last_seen_at
        and (d.retired_at is None or timestamp < d.retired_at)
    ]


def _choose_device(
    rng: np.random.Generator,
    payer_id: str,
    timestamp: datetime,
    devices_by_id: dict[str, Device],
    all_devices: list[Device],
    known_devices: dict[str, list[str]],
) -> tuple[str, bool]:
    known_active = _active_devices(
        (devices_by_id[did] for did in known_devices.get(payer_id, []) if did in devices_by_id),
        timestamp,
    )
    if known_active and rng.random() < cal.LEGIT_KNOWN_DEVICE_PROB:
        return known_active[int(rng.integers(0, len(known_active)))].device_id, True

    active = _active_devices(all_devices, timestamp)
    if not active and known_active:
        return known_active[0].device_id, True
    if not active:
        return all_devices[int(rng.integers(0, len(all_devices)))].device_id, False
    chosen = active[int(rng.integers(0, len(active)))]
    return chosen.device_id, chosen.device_id in known_devices.get(payer_id, [])


def _rail_and_channel(rng: np.random.Generator, is_p2m: bool) -> tuple[Rail, Channel]:
    if is_p2m:
        rail = Rail(_weighted_choice(rng, cal.LEGIT_P2M_RAIL_WEIGHTS))
        if rail == Rail.UPI_P2M:
            channel = Channel.QR_STATIC if rng.random() < 0.55 else Channel.QR_DYNAMIC
        elif rail == Rail.CARD_CP:
            channel = Channel.POS
        elif rail == Rail.CARD_CNP:
            channel = Channel.APP if rng.random() < 0.65 else Channel.WEB
        else:
            channel = Channel.APP
    else:
        rail = Rail(_weighted_choice(rng, cal.LEGIT_P2P_RAIL_WEIGHTS))
        channel = Channel.APP if rng.random() < 0.92 else Channel.WEB
    return rail, channel


def _auth_fields(
    rng: np.random.Generator, rail: Rail, decision: Decision
) -> tuple[AuthMethod, AuthResult, int | None, str | None, bool | None, ExemptionClaimed | None]:
    if rail == Rail.CARD_CNP:
        r = rng.random()
        if r < 0.05:
            method = AuthMethod.CVV_ONLY
        elif r < 0.65:
            method = AuthMethod.THREE_DS_FRICTIONLESS
        else:
            method = AuthMethod.THREE_DS_CHALLENGE_OTP
        eci = "05" if method != AuthMethod.CVV_ONLY else "07"
        liability_shift = method != AuthMethod.CVV_ONLY
        exemption = (
            ExemptionClaimed.TRA
            if method == AuthMethod.THREE_DS_FRICTIONLESS
            else ExemptionClaimed.NONE
        )
    elif rail == Rail.CARD_CP:
        method = AuthMethod.NONE
        eci = None
        liability_shift = None
        exemption = None
    elif rail == Rail.WALLET:
        method = AuthMethod.NONE if rng.random() < 0.55 else AuthMethod.UPI_PIN
        eci = None
        liability_shift = None
        exemption = None
    else:
        if rail == Rail.UPI_P2M and rng.random() < 0.02:
            method = AuthMethod.MANDATE_NO_AFA
        else:
            method = AuthMethod.UPI_PIN
        eci = None
        liability_shift = None
        exemption = None

    if decision == Decision.DECLINED and rng.random() < 0.45:
        result = AuthResult.FAILURE
    elif rng.random() < cal.LEGIT_AUTH_FAILURE_PROB:
        result = AuthResult.FAILURE
    else:
        result = AuthResult.SUCCESS if method != AuthMethod.NONE else AuthResult.NOT_ATTEMPTED

    if method in {AuthMethod.NONE, AuthMethod.LITE_NONE}:
        latency = None
    else:
        latency = int(max(250, rng.lognormal(mean=7.35, sigma=0.45)))
    return method, result, latency, eci, liability_shift, exemption


def _session_fields(
    rng: np.random.Generator, amount: Decimal, first_time: bool, auth_method: AuthMethod
) -> tuple[int, float, int, bool, bool, bool, bool]:
    base = 24 + float(np.log1p(float(amount))) * 4
    if first_time:
        base += float(rng.uniform(8, 35))
    duration = int(max(5, rng.normal(base, 18)))
    confirm = float(max(0.4, rng.lognormal(mean=0.75 + (0.35 if first_time else 0.0), sigma=0.55)))
    if auth_method in {
        AuthMethod.NONE,
        AuthMethod.THREE_DS_FRICTIONLESS,
        AuthMethod.THREE_DS_CHALLENGE_OTP,
        AuthMethod.CVV_ONLY,
    }:
        pin_attempts = 0
    else:
        pin_attempts = 1 + int(rng.random() < 0.035) + int(rng.random() < 0.004)
    screen_share = bool(rng.random() < 0.0015)
    call_active = bool(rng.random() < 0.018)
    accessibility = bool(rng.random() < 0.006)
    paste_used = bool(rng.random() < 0.028)
    return duration, confirm, pin_attempts, screen_share, call_active, accessibility, paste_used


def _issuer_score(
    rng: np.random.Generator,
    known_device: bool,
    first_time: bool,
    amount: Decimal,
    decision: Decision,
) -> float:
    score = 0.04 + (0.08 if first_time else 0.0) + (0.07 if not known_device else 0.0)
    score += min(float(amount) / 100_000.0, 0.2)
    score += 0.18 if decision == Decision.DECLINED else 0.0
    score += float(rng.normal(0.0, 0.025))
    return float(min(max(score, 0.0), 1.0))


def _merchant_choice(
    rng: np.random.Generator, merchants: list[GeneratedMerchant]
) -> GeneratedMerchant:
    weights = np.array([m.volume_weight for m in merchants], dtype=np.float64)
    weights = weights / weights.sum()
    return merchants[int(rng.choice(len(merchants), p=weights))]


def _counterparties_for_party(
    rng: np.random.Generator, party: GeneratedParty, parties: list[GeneratedParty]
) -> list[GeneratedParty]:
    count = int(max(1, party.party.distinct_counterparties_30d))
    count = min(count, max(1, len(parties) - 1))
    choices: list[GeneratedParty] = []
    while len(choices) < count:
        candidate = parties[int(rng.integers(0, len(parties)))]
        if candidate.party.party_id != party.party.party_id and candidate not in choices:
            choices.append(candidate)
    return choices


def generate_legitimate_transactions(seed: int, population: PopulationBundle) -> LegitimateDataset:
    """Generate deterministic legitimate transactions and matching non-fraud labels."""
    seed_seq = np.random.SeedSequence(seed)
    txn_rng, choice_rng = (np.random.default_rng(s) for s in seed_seq.spawn(2))
    devices_by_id = {d.device_id: d for d in population.devices}
    consumer_parties = population.parties
    merchant_by_id: dict[str, Merchant] = {
        m.merchant.merchant_id: m.merchant for m in population.merchants
    }

    rows: list[Transaction] = []
    labels: list[Label] = []

    total_days = max(1, (cal.SIM_END - cal.SIM_START).days)
    day_weights = _day_weights(total_days)

    for gp in consumer_parties:
        mean_count = cal.LEGIT_TXN_MEAN_BY_INCOME_TYPE[gp.income_type]
        n_txns = int(max(1, txn_rng.poisson(mean_count)))
        counterparties = _counterparties_for_party(choice_rng, gp, consumer_parties)
        seen_payees: set[str] = set()

        # Sticky per-party primary TPAP app and linked bank account -- set up
        # once per party, matching `counterparties` above, so a genuine
        # person's UPI transactions overwhelmingly route through the same
        # app/account rather than resampling on every transaction.
        primary_tpap_app = str(choice_rng.choice(cal.TPAP_APP_POOL))
        secondary_tpap_apps = [a for a in cal.TPAP_APP_POOL if a != primary_tpap_app]
        linked_account_ids = [
            f"{gp.party.party_id}_acct{i}" for i in range(cal.LEGIT_N_LINKED_ACCOUNTS_PER_PARTY)
        ]
        primary_linked_account_id = linked_account_ids[0]
        secondary_linked_account_ids = linked_account_ids[1:]

        for _ in range(n_txns):
            ts = _timestamp(txn_rng, total_days, day_weights)
            is_p2m = bool(txn_rng.random() < gp.party.organic_spend_ratio)
            rail, channel = _rail_and_channel(txn_rng, is_p2m)

            if rail.value.startswith("upi_"):
                tpap_app = (
                    str(txn_rng.choice(secondary_tpap_apps))
                    if txn_rng.random() < cal.LEGIT_TPAP_APP_SWITCH_PROB and secondary_tpap_apps
                    else primary_tpap_app
                )
                linked_account_id = (
                    str(txn_rng.choice(secondary_linked_account_ids))
                    if txn_rng.random() < cal.LEGIT_LINKED_ACCOUNT_SWITCH_PROB
                    and secondary_linked_account_ids
                    else primary_linked_account_id
                )
            else:
                tpap_app = None
                linked_account_id = None

            if is_p2m:
                gm = _merchant_choice(txn_rng, population.merchants)
                payee_id = gm.party.party_id
                merchant_id = gm.merchant.merchant_id
                merchant = merchant_by_id[merchant_id]
                mcc = merchant.mcc_declared
            else:
                payee = counterparties[int(txn_rng.integers(0, len(counterparties)))]
                payee_id = payee.party.party_id
                merchant_id = None
                mcc = None

            amount = _amount_for_rail(txn_rng, rail, gp.income_type, mcc)

            first_time = payee_id not in seen_payees
            seen_payees.add(payee_id)
            if first_time:
                beneficiary_added_ago_s = int(
                    txn_rng.integers(
                        cal.LEGIT_FIRST_BENEFICIARY_ADDED_MIN_S,
                        cal.LEGIT_FIRST_BENEFICIARY_ADDED_MAX_S,
                    )
                )
            else:
                beneficiary_added_ago_s = int(
                    txn_rng.integers(
                        cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S,
                        cal.LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S,
                    )
                )

            device_id, known_device = _choose_device(
                txn_rng,
                gp.party.party_id,
                ts,
                devices_by_id,
                population.devices,
                population.party_known_devices,
            )
            decision = (
                Decision.DECLINED
                if txn_rng.random() < cal.LEGIT_DECLINE_PROB
                else Decision.APPROVED
            )
            auth_method, auth_result, auth_latency, eci, liability_shift, exemption = _auth_fields(
                txn_rng, rail, decision
            )
            if auth_result == AuthResult.FAILURE:
                decision = Decision.DECLINED
            decline_reason = None
            if decision == Decision.DECLINED:
                decline_reason = (
                    "auth_failed" if auth_result == AuthResult.FAILURE else "issuer_decline"
                )
            (
                session_duration,
                confirm_time,
                pin_attempts,
                screen_share,
                call_active,
                accessibility,
                paste,
            ) = _session_fields(txn_rng, amount, first_time, auth_method)
            score = _issuer_score(txn_rng, known_device, first_time, amount, decision)

            txn = Transaction(
                txn_id=new_uuid(txn_rng),
                timestamp=ts,
                rail=rail,
                channel=channel,
                direction=Direction.PUSH,
                payer_id=gp.party.party_id,
                payee_id=payee_id,
                merchant_id=merchant_id,
                amount=amount,
                currency="INR",
                amount_is_round=_is_round_amount(amount),
                mcc=mcc,
                purpose_code="00" if rail.value.startswith("upi_") else None,
                auth_method=auth_method,
                auth_result=auth_result,
                auth_latency_ms=auth_latency,
                eci=eci,
                liability_shift=liability_shift,
                exemption_claimed=exemption,
                decision=decision,
                decline_reason=decline_reason,
                issuer_risk_score=score,
                device_id=device_id,
                device_is_known_for_payer=known_device,
                session_id=new_uuid(txn_rng),
                session_duration_s=session_duration,
                time_on_confirm_screen_s=confirm_time,
                beneficiary_first_time=first_time,
                beneficiary_added_ago_s=beneficiary_added_ago_s,
                pin_attempts=pin_attempts,
                screen_share_active=screen_share,
                call_active_during_txn=call_active,
                accessibility_service_active=accessibility,
                paste_used_in_amount=paste,
                is_agent_initiated=False,
                agent_declared_principal=None,
                ip_country="IN",
                ip_asn=str(txn_rng.choice(cal.IP_ASN_POOL)),
                ip_is_proxy=bool(txn_rng.random() < 0.006),
                geo_matches_billing=None if rail not in {Rail.CARD_CNP, Rail.CARD_CP} else True,
                geo_matches_payer_home=bool(txn_rng.random() < 0.94),
                tpap_app=tpap_app,
                linked_account_id=linked_account_id,
            )
            rows.append(txn)
            labels.append(
                Label(
                    txn_id=txn.txn_id,
                    is_fraud=False,
                    attack_id=None,
                    campaign_id=None,
                    pretext=None,
                    is_legit_lookalike=False,
                    detectable_at=None,
                )
            )

    order = sorted(range(len(rows)), key=lambda i: (rows[i].timestamp, rows[i].txn_id))
    return LegitimateDataset(
        transactions=[rows[i] for i in order],
        labels=[labels[i] for i in order],
    )
