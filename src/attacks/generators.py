from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import numpy as np

from src.attacks.framework import (
    AttackGenerator,
    AttackIntensity,
    _build_campaign,
    _choose_device_for_party,
    _label_row,
    _money,
    _transaction_row,
)
from src.dataset.loader import PaymentDataset
from src.schema.enums import DetectableAt
from src.generators import calibration as cal


def _intensity_count(intensity: AttackIntensity | str, low: int, medium: int, high: int) -> int:
    intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
    return {AttackIntensity.LOW: low, AttackIntensity.MEDIUM: medium, AttackIntensity.HIGH: high}[intensity_value]


def _new_party_pair(baseline: PaymentDataset, rng: np.random.Generator, *, exclude: set[str] | None = None) -> tuple[str, str]:
    exclude = exclude or set()
    consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer" and row["party_id"] not in exclude]
    if len(consumer_ids) < 2:
        return (baseline.tables["parties"][0]["party_id"], baseline.tables["parties"][0]["party_id"])
    payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
    payee_pool = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer" and row["party_id"] != payer_id]
    if not payee_pool:
        payee_id = payer_id
    else:
        payee_id = payee_pool[int(rng.integers(0, len(payee_pool)))]
    return payer_id, payee_id


def _random_start_ts(baseline: PaymentDataset, rng: np.random.Generator) -> datetime:
    import inspect
    tx_count = len(baseline.transactions)
    if tx_count == 0:
        return cal.SIM_START
        
    max_duration_days = 2.0
    frame = inspect.currentframe()
    try:
        caller_frame = frame.f_back
        if caller_frame and "self" in caller_frame.f_locals:
            caller_self = caller_frame.f_locals["self"]
            class_name = caller_self.__class__.__name__
            if "StealthMandate" in class_name:
                max_duration_days = 60.0
            elif "FirstPartyDispute" in class_name:
                max_duration_days = 30.0
            elif "SyntheticIdentityBustout" in class_name:
                max_duration_days = 30.0
            elif "AdversarialEvasion" in class_name:
                max_duration_days = 7.0
            elif "InsiderAbuse" in class_name:
                max_duration_days = 5.0
            else:
                max_duration_days = 1.0
    finally:
        del frame
        
    sim_end_str = baseline.manifest.get("simulation_end")
    if not sim_end_str:
        idx = int(rng.integers(0, int(tx_count * 0.50)))
        return baseline.transactions[idx]["timestamp"]
    sim_end = datetime.fromisoformat(sim_end_str)
    first_ts = baseline.transactions[0]["timestamp"]
    if first_ts.tzinfo is not None and sim_end.tzinfo is None:
        sim_end = sim_end.replace(tzinfo=first_ts.tzinfo)
    cutoff_ts = sim_end - timedelta(days=max_duration_days + 1.0)
    valid_ts = [t["timestamp"] for t in baseline.transactions if t["timestamp"] <= cutoff_ts]
    if not valid_ts:
        return first_ts
    return valid_ts[int(rng.integers(0, len(valid_ts)))]


def _make_legit_lookalike_rows(*, attack_rows: list[dict[str, Any]], attack_labels: list[dict[str, Any]], seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lookalike_rows: list[dict[str, Any]] = []
    lookalike_labels: list[dict[str, Any]] = []
    if not attack_rows:
        return lookalike_rows, lookalike_labels
    for idx, row in enumerate(attack_rows):
        variant = dict(row)
        variant["txn_id"] = f"lookalike-{seed}-{idx}-{variant['txn_id']}"
        variant["amount"] = (row["amount"] * Decimal("0.82") + Decimal("5.00")).quantize(Decimal("0.01"))
        variant["beneficiary_first_time"] = True if idx % 2 == 0 else False
        variant["time_on_confirm_screen_s"] = max(2.0, float(row["time_on_confirm_screen_s"]) * 0.9)
        variant["session_duration_s"] = max(20, int(row["session_duration_s"]) - 5)
        variant["issuer_risk_score"] = min(0.18, max(0.03, float(row["issuer_risk_score"]) * 0.75))
        variant["decision"] = "approved"
        lookalike_rows.append(variant)
        lookalike_labels.append({
            "txn_id": variant["txn_id"],
            "is_fraud": False,
            "attack_id": None,
            "campaign_id": None,
            "pretext": None,
            "is_legit_lookalike": True,
            "detectable_at": row.get("detectable_at", DetectableAt.POST_AUTH.value),
        })
    return lookalike_rows, lookalike_labels


class ScamInducedPushAttack(AttackGenerator):
    attack_id = "scam_induced_push"

    def generate(
        self,
        baseline: PaymentDataset,
        *,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        attack_cfg = {"pretext": config.get("pretext", "digital_arrest") if config else "digital_arrest"}
        
        source_party_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = source_party_ids[int(rng.integers(0, len(source_party_ids)))]
        payee_id = source_party_ids[int(rng.integers(0, len(source_party_ids)))]
        if payer_id == payee_id:
            payee_id = source_party_ids[(source_party_ids.index(payer_id) + 1) % len(source_party_ids)]
            
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        known = True if device_id else False
        
        n_events = {AttackIntensity.LOW: 3, AttackIntensity.MEDIUM: 6, AttackIntensity.HIGH: 10}[intensity_value]
        n_events += int(rng.integers(-1, 2))  # vary campaign size stochastically
        n_events = max(2, n_events)
        
        start_ts = _random_start_ts(baseline, rng)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        first_added_ago = int(rng.integers(30, 240))
        
        for i in range(n_events):
            amount = _money(float(rng.lognormal(mean=5.2, sigma=0.65)) * (1.3 + 0.15 * i))
            # Vary timing steps stochastically
            event_ts = start_ts + timedelta(minutes=float(rng.uniform(3.0, 18.0)) * i)
            
            # First is new beneficiary; subsequent use the same existing beneficiary
            if i == 0:
                first_time = True
                added_ago = first_added_ago
            else:
                first_time = False
                added_ago = int((event_ts - start_ts).total_seconds()) + first_added_ago
                
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=payee_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=known,
                rail="upi_p2p",
                channel="app",
                merchant_id=None,
                mcc=None,
                auth_method="upi_pin",
                auth_result="success",
                decision="approved",
                session_duration_s=int(40 + rng.integers(10, 140)),
                time_on_confirm_screen_s=float(rng.uniform(1.8, 6.0)),
                beneficiary_first_time=first_time,
                beneficiary_added_ago_s=added_ago,
                pin_attempts=1 + int(rng.random() < 0.05),
                screen_share_active=bool(rng.random() < 0.25),
                call_active_during_txn=bool(rng.random() < 0.9),
                accessibility_service_active=False,
                paste_used_in_amount=False,
                geo_matches_home=True,
                purpose_code="00",
                issuer_risk_score=0.12,
            )
            rows.append(txn)
            labels.append(
                _label_row(
                    txn["txn_id"],
                    attack_id=self.attack_id,
                    campaign_id="",
                    pretext=attack_cfg["pretext"],
                    detectable_at=DetectableAt.POST_AUTH,
                )
            )
            
        campaign = _build_campaign(
            self.attack_id,
            seed=seed,
            intensity=intensity_value,
            start_time=rows[0]["timestamp"],
            end_time=rows[-1]["timestamp"],
            affected_entities=[payer_id, payee_id],
            event_count=len(rows),
            pretext=attack_cfg["pretext"],
            config={"target_population": "consumer"},
        )
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class MuleNetworkAttack(AttackGenerator):
    attack_id = "mule_network"

    def generate(
        self,
        baseline: PaymentDataset,
        *,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        
        n_sources = max(3, 2 + int(intensity_value == AttackIntensity.HIGH) * 3) + int(rng.integers(-1, 2))
        n_sources = max(2, n_sources)
        source_ids = consumer_ids[:n_sources]
        
        mule_id = consumer_ids[min(len(consumer_ids) - 1, 50)]
        destination_id = consumer_ids[min(len(consumer_ids) - 1, 120)]
        
        start_ts = _random_start_ts(baseline, rng)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        # Decide if mule relationship is pre-existing or new
        is_mule_new = rng.random() < 0.60
        first_added_ago = int(rng.integers(40, 300))
        
        for idx, source_id in enumerate(source_ids):
            device_id = _choose_device_for_party(baseline, source_id) or baseline.tables["devices"][0]["device_id"]
            for step in range(2):
                payee_id = mule_id if step == 0 else destination_id
                amount = _money(float(rng.lognormal(mean=4.2, sigma=0.6)) + idx * 10.0 + float(rng.normal(0, 15)))
                
                # Vary transfer delay stochastically
                event_ts = start_ts + timedelta(minutes=float(rng.uniform(6.0, 24.0)) * idx + float(rng.uniform(1.0, 6.0)) * step)
                
                if step == 0:
                    first_time = is_mule_new and (idx == 0)
                    added_ago = first_added_ago if first_time else int(rng.integers(cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S, cal.LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S))
                else:
                    first_time = True
                    added_ago = int(rng.integers(20, 120))
                    
                txn = _transaction_row(
                    rng=rng,
                    payer_id=source_id,
                    payee_id=payee_id,
                    amount=amount,
                    ts=event_ts,
                    device_id=device_id,
                    known_device=True,
                    rail="upi_p2p",
                    channel="app",
                    merchant_id=None,
                    mcc=None,
                    auth_method="upi_pin",
                    auth_result="success",
                    decision="approved",
                    session_duration_s=int(30 + idx * 5 + rng.integers(-5, 10)),
                    time_on_confirm_screen_s=float(rng.uniform(1.5, 4.5)),
                    beneficiary_first_time=first_time,
                    beneficiary_added_ago_s=added_ago,
                    pin_attempts=1 + int(rng.random() < 0.05),
                    screen_share_active=False,
                    call_active_during_txn=False,
                    geo_matches_home=True,
                    purpose_code="00",
                    issuer_risk_score=0.09,
                )
                rows.append(txn)
                labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="pass_through", detectable_at=DetectableAt.POST_AUTH))
                
        campaign = _build_campaign(
            self.attack_id,
            seed=seed,
            intensity=intensity_value,
            start_time=rows[0]["timestamp"],
            end_time=rows[-1]["timestamp"],
            affected_entities=source_ids + [mule_id, destination_id],
            event_count=len(rows),
            pretext="pass_through",
            config={"mule_party_id": mule_id},
        )
        campaign.mule_party_id = mule_id
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class CardTestingProbeAttack(AttackGenerator):
    attack_id = "card_testing_probe"

    def generate(
        self,
        baseline: PaymentDataset,
        *,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        
        # Select multiple baseline merchants to vary destination structure
        merchants = baseline.tables["merchants"]
        merchant_pool = [m["merchant_id"] for m in merchants]
        
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        n_events = _intensity_count(intensity_value, 4, 8, 15)
        n_events += int(rng.integers(-1, 3))
        n_events = max(4, n_events)
        
        start_ts = _random_start_ts(baseline, rng)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        for i in range(n_events):
            merchant_id = merchant_pool[int(rng.integers(0, len(merchant_pool)))]
            # Card testing: very small micro-amounts
            amount = _money(float(rng.uniform(1.00, 12.00)))
            
            # Rapid card test successions
            event_ts = start_ts + timedelta(seconds=float(rng.uniform(15.0, 90.0)) * i)
            
            # Differentiate decisions stochastically (probes have declines)
            decision = "declined" if (i == 0 or rng.random() < 0.35) else "approved"
            decline_reason = "auth_failed" if decision == "declined" else None
            auth_result = "failure" if decision == "declined" else "success"
            
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=merchant_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="card_cnp",
                channel="web",
                merchant_id=merchant_id,
                mcc=merchants[0]["mcc_declared"],
                auth_method="cvv_only",
                auth_result=auth_result,
                decision=decision,
                decline_reason=decline_reason,
                session_duration_s=int(40 + rng.integers(5, 45)),
                time_on_confirm_screen_s=float(rng.uniform(1.5, 4.0)),
                beneficiary_first_time=False,
                beneficiary_added_ago_s=int(rng.integers(60, 600)),
                pin_attempts=0,  # Card CNP uses CVV only, so 0 PIN attempts
                screen_share_active=bool(rng.random() < 0.08),
                call_active_during_txn=bool(rng.random() < 0.25),
                geo_matches_home=(rng.random() < 0.95),
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="micro_probe", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(
            self.attack_id,
            seed=seed,
            intensity=intensity_value,
            start_time=rows[0]["timestamp"],
            end_time=rows[-1]["timestamp"],
            affected_entities=[payer_id],
            event_count=len(rows),
            pretext="micro_probe",
            config={"probe_mcc": merchants[0]["mcc_declared"]},
        )
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class AdversarialEvasionAttack(AttackGenerator):
    attack_id = "adversarial_evasion"

    def generate(
        self,
        baseline: PaymentDataset,
        *,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        payee_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        if payer_id == payee_id:
            payee_id = consumer_ids[(consumer_ids.index(payer_id) + 1) % len(consumer_ids)]
            
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        n_events = {AttackIntensity.LOW: 2, AttackIntensity.MEDIUM: 4, AttackIntensity.HIGH: 7}[intensity_value]
        n_events += int(rng.integers(-1, 2))
        n_events = max(2, n_events)
        
        start_ts = _random_start_ts(baseline, rng)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        for i in range(n_events):
            amount = _money(210.0 + i * 80.0 + float(rng.normal(0, 30)))
            # Low and slow spread stochastically
            event_ts = start_ts + timedelta(hours=float(rng.uniform(4.0, 20.0)) * i)
            
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=payee_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="upi_p2p",
                channel="app",
                merchant_id=None,
                mcc=None,
                auth_method="upi_pin",
                auth_result="success",
                decision="approved",
                session_duration_s=int(23 + i * 7 + rng.integers(-4, 8)),
                time_on_confirm_screen_s=float(rng.uniform(2.2, 4.5)),
                beneficiary_first_time=False,
                beneficiary_added_ago_s=int(rng.integers(cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S, cal.LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S)),
                pin_attempts=1 + int(rng.random() < 0.03),
                screen_share_active=False,
                call_active_during_txn=False,
                accessibility_service_active=False,
                paste_used_in_amount=False,
                geo_matches_home=True,
                purpose_code="00",
                issuer_risk_score=0.07,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="low_and_slow", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(
            self.attack_id,
            seed=seed,
            intensity=intensity_value,
            start_time=rows[0]["timestamp"],
            end_time=rows[-1]["timestamp"],
            affected_entities=[payer_id, payee_id],
            event_count=len(rows),
            pretext="low_and_slow",
            config={"low_and_slow": True},
        )
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class FirstPartyDisputeAttack(AttackGenerator):
    attack_id = "first_party_dispute"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        merchant_row = baseline.tables["merchants"][int(rng.integers(0, len(baseline.tables["merchants"])))]
        merchant_id = merchant_row["merchant_id"]
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        start_ts = _random_start_ts(baseline, rng)
        
        n_events = _intensity_count(intensity_value, 2, 5, 9)
        n_events += int(rng.integers(-1, 2))
        n_events = max(2, n_events)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        for i in range(n_events):
            # Friendly fraud: spread stochastically over days
            event_ts = start_ts + timedelta(days=float(rng.uniform(1.0, 4.0)) * i, hours=float(rng.uniform(-3.0, 5.0)))
            
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=merchant_id,
                amount=_money(120.0 + i * 35.0 + float(rng.normal(0, 15))),
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="card_cnp",
                channel="web",
                merchant_id=merchant_id,
                mcc=merchant_row["mcc_declared"],
                auth_method="cvv_only",
                auth_result="success",
                decision="approved",
                session_duration_s=int(20 + i * 5 + rng.integers(-3, 6)),
                time_on_confirm_screen_s=float(rng.uniform(1.5, 4.0)),
                beneficiary_first_time=False,
                beneficiary_added_ago_s=int(rng.integers(cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S, cal.LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S)),
                pin_attempts=0,  # Card CNP uses CVV only, so 0 PIN attempts
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=True,
                purpose_code=None,
                issuer_risk_score=0.11,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="friendly_fraud", detectable_at=DetectableAt.POST_SETTLEMENT))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, merchant_id], event_count=len(rows), pretext="friendly_fraud", config={"merchant_id": merchant_id})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class StealthMandateAttack(AttackGenerator):
    attack_id = "stealth_mandate"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        merchant_row = baseline.tables["merchants"][int(rng.integers(0, len(baseline.tables["merchants"])))]
        merchant_id = merchant_row["merchant_id"]
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        start_ts = _random_start_ts(baseline, rng)
        
        n_events = _intensity_count(intensity_value, 3, 6, 12)
        n_events += int(rng.integers(-1, 3))
        n_events = max(3, n_events)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        for idx in range(n_events):
            # Recurring charge: spread stochastically over weeks
            event_ts = start_ts + timedelta(days=float(rng.uniform(2.5, 9.5)) * idx)
            amount = _money(19.0 + idx * 7.0 + float(rng.normal(0, 3)))
            
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=merchant_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="upi_mandate",
                channel="app",
                merchant_id=merchant_id,
                mcc=merchant_row["mcc_declared"],
                auth_method="mandate_no_afa",
                auth_result="success",
                decision="approved",
                session_duration_s=int(14 + idx + rng.integers(-2, 4)),
                time_on_confirm_screen_s=float(rng.uniform(0.8, 2.0)),
                beneficiary_first_time=False,
                beneficiary_added_ago_s=int(rng.integers(cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S, cal.LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S)),
                pin_attempts=0,  # Mandate recurring has no PIN checks, so 0 PIN attempts
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=True,
                purpose_code=None,
                issuer_risk_score=0.09,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="mandate_stealth", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, merchant_id], event_count=len(rows), pretext="mandate_stealth", config={"merchant_id": merchant_id})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class SyntheticMerchantAttack(AttackGenerator):
    attack_id = "synthetic_merchant"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        merchant_row = baseline.tables["merchants"][int(rng.integers(0, len(baseline.tables["merchants"])))]
        merchant_id = merchant_row["merchant_id"]
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        start_ts = _random_start_ts(baseline, rng)
        
        n_events = _intensity_count(intensity_value, 3, 8, 14)
        n_events += int(rng.integers(-1, 3))
        n_events = max(3, n_events)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        first_added_ago = int(rng.integers(10, 60))
        
        for i in range(n_events):
            # Rapid UPI P2M payments
            event_ts = start_ts + timedelta(minutes=float(rng.uniform(10.0, 45.0)) * i)
            amount = _money(180.0 + i * 60.0 + float(rng.normal(0, 20)))
            
            # Setup beneficiary
            if i == 0:
                first_time = True
                added_ago = first_added_ago
            else:
                first_time = False
                added_ago = int((event_ts - start_ts).total_seconds()) + first_added_ago
                
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=merchant_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="upi_p2m",
                channel="app",
                merchant_id=merchant_id,
                mcc=merchant_row["mcc_declared"],
                auth_method="upi_pin",
                auth_result="success",
                decision="approved",
                session_duration_s=int(18 + i * 2 + rng.integers(-3, 5)),
                time_on_confirm_screen_s=float(rng.uniform(1.2, 3.5)),
                beneficiary_first_time=first_time,
                beneficiary_added_ago_s=added_ago,
                pin_attempts=1 + int(rng.random() < 0.05),
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=True,
                purpose_code="00",
                issuer_risk_score=0.10,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="kyb_shell", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, merchant_id], event_count=len(rows), pretext="kyb_shell", config={"merchant_id": merchant_id})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class TransactionLaunderingAttack(AttackGenerator):
    attack_id = "transaction_laundering"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        merchant_ids = [row["merchant_id"] for row in baseline.tables["merchants"]]
        payer_id, payee_id = _new_party_pair(baseline, rng)
        merchant_id = merchant_ids[int(rng.integers(0, len(merchant_ids)))]
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        n_events = _intensity_count(intensity_value, 3, 6, 10)
        n_events += int(rng.integers(-1, 2))
        n_events = max(3, n_events)
        
        start_ts = _random_start_ts(baseline, rng)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        first_added_ago = int(rng.integers(40, 200))
        
        for i in range(n_events):
            event_ts = start_ts + timedelta(minutes=float(rng.uniform(15.0, 45.0)) * i)
            amount = _money(70.0 + i * 40.0 + float(rng.normal(0, 10)))
            
            # Setup beneficiary
            if i == 0:
                first_time = True
                added_ago = first_added_ago
            else:
                first_time = False
                added_ago = int((event_ts - start_ts).total_seconds()) + first_added_ago
                
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=payee_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="card_cnp",
                channel="web",
                merchant_id=merchant_id,
                mcc=baseline.tables["merchants"][0]["mcc_declared"],
                auth_method="cvv_only",
                auth_result="success",
                decision="approved",
                session_duration_s=int(22 + i * 4 + rng.integers(-3, 6)),
                time_on_confirm_screen_s=float(rng.uniform(1.2, 3.2)),
                beneficiary_first_time=first_time,
                beneficiary_added_ago_s=added_ago,
                pin_attempts=0,  # Card CNP uses CVV only, so 0 PIN attempts
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=True,
                purpose_code=None,
                issuer_risk_score=0.12,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="laundering", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, payee_id, merchant_id], event_count=len(rows), pretext="laundering", config={"merchant_id": merchant_id})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class CredentialTakeoverAttack(AttackGenerator):
    attack_id = "credential_takeover"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        payee_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        if payer_id == payee_id:
            payee_id = consumer_ids[(consumer_ids.index(payer_id) + 1) % len(consumer_ids)]
            
        old_device = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        new_device = baseline.tables["devices"][int(rng.integers(0, len(baseline.tables["devices"])))] ["device_id"]
        
        start_ts = _random_start_ts(baseline, rng)
        
        n_events = _intensity_count(intensity_value, 2, 5, 10)
        n_events += int(rng.integers(-1, 2))
        n_events = max(2, n_events)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        first_added_ago = int(rng.integers(10, 60))
        
        for i in range(n_events):
            event_ts = start_ts + timedelta(minutes=float(rng.uniform(10.0, 45.0)) * i)
            amount = _money(400.0 + i * 120.0 + float(rng.normal(0, 50)))
            
            # Setup beneficiary
            if i == 0:
                first_time = True
                added_ago = first_added_ago
            else:
                first_time = False
                added_ago = int((event_ts - start_ts).total_seconds()) + first_added_ago
                
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=payee_id,
                amount=amount,
                ts=event_ts,
                device_id=new_device if i > 0 else old_device,
                known_device=(i == 0),
                rail="upi_p2p",
                channel="app",
                merchant_id=None,
                mcc=None,
                auth_method="upi_pin",
                auth_result="success",
                decision="approved",
                session_duration_s=int(18 + i * 3 + rng.integers(-2, 5)),
                time_on_confirm_screen_s=float(rng.uniform(0.8, 2.2)),
                beneficiary_first_time=first_time,
                beneficiary_added_ago_s=added_ago,
                pin_attempts=1 + int(rng.random() < 0.05),
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=False,
                purpose_code="00",
                issuer_risk_score=0.16,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="session_compromise", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, payee_id, old_device, new_device], event_count=len(rows), pretext="session_compromise", config={"new_device_id": new_device})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class SyntheticIdentityBustoutAttack(AttackGenerator):
    attack_id = "synthetic_identity_bustout"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        payee_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        if payer_id == payee_id:
            payee_id = consumer_ids[(consumer_ids.index(payer_id) + 1) % len(consumer_ids)]
            
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        start_ts = _random_start_ts(baseline, rng)
        
        n_events = _intensity_count(intensity_value, 3, 7, 12)
        n_events += int(rng.integers(-1, 3))
        n_events = max(3, n_events)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        for i in range(n_events):
            # Slow credit-building phase then rapid max-out phase
            if i > 2:
                event_ts = start_ts + timedelta(days=12 + float(rng.uniform(0.1, 0.8)) * (i - 2))
                amount = _money(150.0 + i * 110.0 + float(rng.normal(0, 30)))
            else:
                event_ts = start_ts + timedelta(days=i * 4 + float(rng.uniform(-0.5, 0.5)))
                amount = _money(25.0 + i * 10.0 + float(rng.normal(0, 5)))
                
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=payee_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="card_cnp",
                channel="web",
                merchant_id=None,
                mcc=None,
                auth_method="cvv_only",
                auth_result="success",
                decision="approved",
                session_duration_s=int(20 + i * 6 + rng.integers(-3, 6)),
                time_on_confirm_screen_s=float(rng.uniform(1.2, 3.5)),
                beneficiary_first_time=(i < 2),
                beneficiary_added_ago_s=int(90 + i * 12 + rng.integers(-10, 20)),
                pin_attempts=0,  # Card CNP uses CVV only, so 0 PIN attempts
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=True,
                purpose_code=None,
                issuer_risk_score=0.06 + i * 0.03,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="bustout", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, payee_id], event_count=len(rows), pretext="bustout", config={"growth_phase": "credit_building"})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class SubthresholdFragmentationAttack(AttackGenerator):
    attack_id = "subthreshold_fragmentation"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        payee_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        if payer_id == payee_id:
            payee_id = consumer_ids[(consumer_ids.index(payer_id) + 1) % len(consumer_ids)]
            
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        start_ts = _random_start_ts(baseline, rng)
        
        n_events = _intensity_count(intensity_value, 4, 7, 12)
        n_events += int(rng.integers(-1, 3))
        n_events = max(4, n_events)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        first_added_ago = int(rng.integers(15, 60))
        
        for i in range(n_events):
            # Fragmentation: amounts strictly under alert thresholds (e.g. 100 Rs)
            amount = _money(float(rng.uniform(15.00, 95.00)))
            
            # Rapid micro-transfers
            event_ts = start_ts + timedelta(minutes=float(rng.uniform(2.0, 15.0)) * i)
            
            # Setup beneficiary
            if i == 0:
                first_time = True
                added_ago = first_added_ago
            else:
                first_time = False
                added_ago = int((event_ts - start_ts).total_seconds()) + first_added_ago
                
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=payee_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="upi_p2p",
                channel="app",
                merchant_id=None,
                mcc=None,
                auth_method="upi_pin",
                auth_result="success",
                decision="approved",
                session_duration_s=int(17 + i + rng.integers(-2, 4)),
                time_on_confirm_screen_s=float(rng.uniform(1.2, 3.2)),
                beneficiary_first_time=first_time,
                beneficiary_added_ago_s=added_ago,
                pin_attempts=1 + int(rng.random() < 0.05),
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=True,
                purpose_code="00",
                issuer_risk_score=0.08,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="fragmentation", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, payee_id], event_count=len(rows), pretext="fragmentation", config={"split_pattern": "serial"})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class AgenticInjectionAttack(AttackGenerator):
    attack_id = "agentic_injection"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        payee_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        if payer_id == payee_id:
            payee_id = consumer_ids[(consumer_ids.index(payer_id) + 1) % len(consumer_ids)]
            
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        start_ts = _random_start_ts(baseline, rng)
        
        n_events = _intensity_count(intensity_value, 2, 4, 8)
        n_events += int(rng.integers(-1, 2))
        n_events = max(2, n_events)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        first_added_ago = int(rng.integers(30, 180))
        
        for i in range(n_events):
            event_ts = start_ts + timedelta(minutes=float(rng.uniform(6.0, 20.0)) * i)
            amount = _money(210.0 + i * 90.0 + float(rng.normal(0, 25)))
            
            # Setup beneficiary
            if i == 0:
                first_time = True
                added_ago = first_added_ago
            else:
                first_time = False
                added_ago = int((event_ts - start_ts).total_seconds()) + first_added_ago
                
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=payee_id,
                amount=amount,
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="upi_p2m",
                channel="agent",
                merchant_id=None,
                mcc=None,
                auth_method="upi_pin",
                auth_result="success",
                decision="approved",
                session_duration_s=int(31 + i * 8 + rng.integers(-3, 6)),
                time_on_confirm_screen_s=float(rng.uniform(1.0, 2.5)),
                beneficiary_first_time=first_time,
                beneficiary_added_ago_s=added_ago,
                pin_attempts=1 + int(rng.random() < 0.05),
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=True,
                is_agent_initiated=True,
                agent_declared_principal="payer",
                purpose_code="00",
                issuer_risk_score=0.1,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="agentic_abuse", detectable_at=DetectableAt.POST_AUTH))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, payee_id], event_count=len(rows), pretext="agentic_abuse", config={"agent_mode": True})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


class InsiderAbuseAttack(AttackGenerator):
    attack_id = "insider_abuse"

    def generate(self, baseline: PaymentDataset, *, seed: int, intensity: AttackIntensity | str, config: dict[str, Any] | None = None):
        rng = np.random.default_rng(seed)
        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
        consumer_ids = [row["party_id"] for row in baseline.tables["parties"] if row["party_type"] == "consumer"]
        payer_id = consumer_ids[int(rng.integers(0, len(consumer_ids)))]
        merchant_row = baseline.tables["merchants"][int(rng.integers(0, len(baseline.tables["merchants"])))]
        merchant_id = merchant_row["merchant_id"]
        device_id = _choose_device_for_party(baseline, payer_id) or baseline.tables["devices"][0]["device_id"]
        
        start_ts = _random_start_ts(baseline, rng)
        
        n_events = _intensity_count(intensity_value, 2, 5, 9)
        n_events += int(rng.integers(-1, 2))
        n_events = max(2, n_events)
        
        rows: list[dict[str, Any]] = []
        labels: list[dict[str, Any]] = []
        
        for i in range(n_events):
            # Slow timing (multi-hour/day intervals)
            event_ts = start_ts + timedelta(hours=float(rng.uniform(4.0, 18.0)) * i)
            
            txn = _transaction_row(
                rng=rng,
                payer_id=payer_id,
                payee_id=merchant_id,
                amount=_money(150.0 + i * 25.0 + float(rng.normal(0, 10))),
                ts=event_ts,
                device_id=device_id,
                known_device=True,
                rail="neft",
                channel="web",
                merchant_id=merchant_id,
                mcc=merchant_row["mcc_declared"],
                auth_method="none",
                auth_result="success",
                decision="approved",
                session_duration_s=int(12 + i + rng.integers(-2, 3)),
                time_on_confirm_screen_s=float(rng.uniform(0.5, 1.8)),
                beneficiary_first_time=False,
                beneficiary_added_ago_s=int(rng.integers(cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S, cal.LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S)),
                pin_attempts=0,  # NEFT uses no PIN, so 0 attempts
                screen_share_active=False,
                call_active_during_txn=False,
                geo_matches_home=True,
                purpose_code=None,
                issuer_risk_score=0.11,
            )
            rows.append(txn)
            labels.append(_label_row(txn["txn_id"], attack_id=self.attack_id, campaign_id="", pretext="insider_access", detectable_at=DetectableAt.POST_SETTLEMENT))
            
        campaign = _build_campaign(self.attack_id, seed=seed, intensity=intensity_value, start_time=rows[0]["timestamp"], end_time=rows[-1]["timestamp"], affected_entities=[payer_id, merchant_id], event_count=len(rows), pretext="insider_access", config={"merchant_id": merchant_id})
        for label in labels:
            label["campaign_id"] = campaign.campaign_id
            
        return campaign, rows, labels


__all__ = [
    "ScamInducedPushAttack",
    "MuleNetworkAttack",
    "CardTestingProbeAttack",
    "AdversarialEvasionAttack",
    "FirstPartyDisputeAttack",
    "StealthMandateAttack",
    "SyntheticMerchantAttack",
    "TransactionLaunderingAttack",
    "CredentialTakeoverAttack",
    "SyntheticIdentityBustoutAttack",
    "SubthresholdFragmentationAttack",
    "AgenticInjectionAttack",
    "InsiderAbuseAttack",
]
