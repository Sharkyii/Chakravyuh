"""Validation and summaries for the Stage 1 legitimate payment world."""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any

import pyarrow as pa

from src.generators import calibration as cal
from src.generators.legitimate import LegitimateDataset
from src.generators.population import PopulationBundle
from src.schema import TABLE_ARROW_SCHEMAS
from src.schema.enums import AuthMethod, AuthResult, Decision, Rail


@dataclass(slots=True)
class ValidationReport:
    """Validation result returned by the dataset generator CLI and tests."""

    errors: list[str]
    summary: dict[str, Any]

    @property
    def ok(self) -> bool:
        return not self.errors


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _rows_for_arrow(rows: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        converted: dict[str, Any] = {}
        for field in fields(row):
            value = getattr(row, field.name)
            converted[field.name] = value.value if hasattr(value, "value") else value
        out.append(converted)
    return out


def _check_arrow_schema(table_name: str, rows: list[Any], errors: list[str]) -> None:
    try:
        pa.Table.from_pylist(_rows_for_arrow(rows), schema=TABLE_ARROW_SCHEMAS[table_name])
    except Exception as exc:  # pragma: no cover - exact pyarrow message is version-specific
        errors.append(f"{table_name} does not conform to Arrow schema: {exc}")


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p99": 0.0}
    sorted_values = sorted(values)
    return {
        "p50": sorted_values[int((len(sorted_values) - 1) * 0.50)],
        "p90": sorted_values[int((len(sorted_values) - 1) * 0.90)],
        "p99": sorted_values[int((len(sorted_values) - 1) * 0.99)],
    }


def validate_legitimate_dataset(
    population: PopulationBundle, dataset: LegitimateDataset
) -> ValidationReport:
    """Validate Stage 1 transactions/labels against schema and FK invariants."""
    errors: list[str] = []
    transactions = dataset.transactions
    labels = dataset.labels

    party_ids = {p.party_id for p in population.all_party_rows()}
    consumer_ids = {p.party.party_id for p in population.parties}
    merchant_ids = {m.merchant.merchant_id for m in population.merchants}
    device_ids = {d.device_id for d in population.devices}
    device_by_id = {d.device_id: d for d in population.devices}

    _check_arrow_schema("transactions", transactions, errors)
    _check_arrow_schema("labels", labels, errors)

    txn_ids = [t.txn_id for t in transactions]
    if len(txn_ids) != len(set(txn_ids)):
        errors.append("duplicate transaction IDs found")
    if len(labels) != len(transactions):
        errors.append("label count does not match transaction count")
    if {label.txn_id for label in labels} != set(txn_ids):
        errors.append("labels do not exactly match transaction IDs")

    for label in labels:
        if label.is_fraud:
            errors.append(f"legitimate label is marked fraud: {label.txn_id}")
        if label.attack_id is not None or label.campaign_id is not None or label.pretext is not None:
            errors.append(f"legitimate label contains attack metadata: {label.txn_id}")
        if label.is_legit_lookalike:
            errors.append(f"Stage 1 label unexpectedly marked lookalike: {label.txn_id}")

    for txn in transactions:
        if txn.payer_id not in consumer_ids:
            errors.append(f"payer does not exist as consumer: {txn.txn_id}")
        if txn.payee_id not in party_ids:
            errors.append(f"payee does not exist: {txn.txn_id}")
        if txn.payer_id == txn.payee_id:
            errors.append(f"payer equals payee: {txn.txn_id}")
        if txn.merchant_id is None:
            if txn.mcc is not None:
                errors.append(f"P2P transaction has MCC: {txn.txn_id}")
        elif txn.merchant_id not in merchant_ids:
            errors.append(f"merchant does not exist: {txn.txn_id}")
        elif txn.payee_id != txn.merchant_id:
            errors.append(f"merchant transaction payee does not equal merchant_id: {txn.txn_id}")
        if txn.device_id not in device_ids:
            errors.append(f"device does not exist: {txn.txn_id}")
        else:
            device = device_by_id[txn.device_id]
            if not (device.first_seen_at <= txn.timestamp <= device.last_seen_at):
                errors.append(f"device not active at transaction timestamp: {txn.txn_id}")
            if device.retired_at is not None and txn.timestamp >= device.retired_at:
                errors.append(f"retired device used after retirement: {txn.txn_id}")
        if txn.device_is_known_for_payer != (txn.device_id in population.party_known_devices.get(txn.payer_id, [])):
            errors.append(f"device known flag inconsistent: {txn.txn_id}")
        if not (cal.SIM_START <= txn.timestamp < cal.SIM_END):
            errors.append(f"timestamp outside simulation window: {txn.txn_id}")
        if txn.amount <= Decimal("0.00"):
            errors.append(f"non-positive amount: {txn.txn_id}")
        if txn.currency != "INR":
            errors.append(f"unexpected currency: {txn.txn_id}")
        if not isinstance(txn.rail, Rail):
            errors.append(f"invalid rail enum: {txn.txn_id}")
        if txn.auth_method == AuthMethod.UPI_PIN and txn.auth_latency_ms is None:
            errors.append(f"UPI PIN transaction missing auth latency: {txn.txn_id}")
        if txn.auth_method == AuthMethod.NONE and txn.auth_latency_ms is not None:
            errors.append(f"no-auth transaction has auth latency: {txn.txn_id}")
        if txn.auth_result == AuthResult.FAILURE and txn.decision != Decision.DECLINED:
            errors.append(f"failed auth was not declined: {txn.txn_id}")
        if txn.decision == Decision.DECLINED and txn.decline_reason is None:
            errors.append(f"declined transaction missing reason: {txn.txn_id}")
        if txn.decision != Decision.DECLINED and txn.decline_reason is not None:
            errors.append(f"approved transaction has decline reason: {txn.txn_id}")
        if txn.beneficiary_added_ago_s < 0:
            errors.append(f"negative beneficiary age: {txn.txn_id}")
        if txn.session_duration_s <= 0 or txn.time_on_confirm_screen_s <= 0:
            errors.append(f"invalid session duration fields: {txn.txn_id}")
        if txn.pin_attempts < 0:
            errors.append(f"negative PIN attempts: {txn.txn_id}")
        if txn.is_agent_initiated or txn.agent_declared_principal is not None:
            errors.append(f"Stage 1 should not contain agent-initiated traffic: {txn.txn_id}")

    summary = summarize_legitimate_dataset(population, dataset)
    return ValidationReport(errors=errors, summary=summary)


def summarize_legitimate_dataset(
    population: PopulationBundle, dataset: LegitimateDataset
) -> dict[str, Any]:
    """Return compact deterministic summary statistics for logs/manifests."""
    transactions = dataset.transactions
    by_rail: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    by_auth: dict[str, int] = {}
    by_decision: dict[str, int] = {}
    per_party: dict[str, int] = {}
    per_merchant: dict[str, int] = {}
    known_count = 0
    first_count = 0
    amounts: list[float] = []

    for txn in transactions:
        by_rail[_enum_value(txn.rail)] = by_rail.get(_enum_value(txn.rail), 0) + 1
        by_channel[_enum_value(txn.channel)] = by_channel.get(_enum_value(txn.channel), 0) + 1
        by_auth[_enum_value(txn.auth_method)] = by_auth.get(_enum_value(txn.auth_method), 0) + 1
        by_decision[_enum_value(txn.decision)] = by_decision.get(_enum_value(txn.decision), 0) + 1
        per_party[txn.payer_id] = per_party.get(txn.payer_id, 0) + 1
        if txn.merchant_id is not None:
            per_merchant[txn.merchant_id] = per_merchant.get(txn.merchant_id, 0) + 1
        known_count += int(txn.device_is_known_for_payer)
        first_count += int(txn.beneficiary_first_time)
        amounts.append(float(txn.amount))

    return {
        "n_parties": len(population.all_party_rows()),
        "n_consumer_parties": len(population.parties),
        "n_merchants": len(population.merchants),
        "n_devices": len(population.devices),
        "n_transactions": len(transactions),
        "transactions_by_rail": dict(sorted(by_rail.items())),
        "transactions_by_channel": dict(sorted(by_channel.items())),
        "amount_quantiles": _quantiles(amounts),
        "transactions_per_party": _quantiles([float(v) for v in per_party.values()]),
        "transactions_per_merchant": _quantiles([float(v) for v in per_merchant.values()]),
        "known_device_rate": known_count / len(transactions) if transactions else 0.0,
        "first_time_beneficiary_rate": first_count / len(transactions) if transactions else 0.0,
        "authentication_method_distribution": dict(sorted(by_auth.items())),
        "approval_decline_distribution": dict(sorted(by_decision.items())),
    }
