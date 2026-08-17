from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from typing import Any

import os
import urllib.request
import urllib.error
import json
import numpy as np

from src.dataset.loader import PaymentDataset
from src.generators.ids import new_uuid
from src.schema.enums import DetectableAt


class AttackIntensity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(slots=True)
class AttackSpec:
    attack_id: str
    seed: int
    intensity: AttackIntensity
    config: dict[str, Any] = field(default_factory=dict)
    start_time: datetime | None = None
    end_time: datetime | None = None
    pretext: str | None = None
    campaign_size: int | None = None
    target_population: str | None = None
    temporal_strategy: str | None = None
    behavioral_strategy: str | None = None
    graph_strategy: str | None = None
    lookalike_generation: bool = False
    attack_specific: dict[str, Any] = field(default_factory=dict)


class ScenarioGenerator(ABC):
    """Reusable abstraction for deterministic attack scenario specification."""

    @abstractmethod
    def generate_spec(
        self,
        *,
        attack_id: str,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ) -> AttackSpec:
        """Create a validated AttackSpec for execution by an AttackGenerator."""


class TemplateScenarioGenerator(ScenarioGenerator):
    """Deterministic, local scenario-template generator for Stage 4."""

    _TEMPLATES: dict[str, dict[str, Any]] = {
        "scam_induced_push": {"pretext": "digital_arrest", "target_population": "consumer", "temporal_strategy": "burst", "behavioral_strategy": "coercion", "graph_strategy": "peer", "lookalike_generation": True},
        "mule_network": {"pretext": "pass_through", "target_population": "consumer", "temporal_strategy": "fanout", "behavioral_strategy": "network", "graph_strategy": "fan_in_fan_out", "lookalike_generation": True},
        "card_testing_probe": {"pretext": "probe_cycle", "target_population": "consumer", "temporal_strategy": "rapid_burst", "behavioral_strategy": "micro_amounts", "graph_strategy": "merchant", "lookalike_generation": True},
        "adversarial_evasion": {"pretext": "low_and_slow", "target_population": "consumer", "temporal_strategy": "distributed", "behavioral_strategy": "evasion", "graph_strategy": "peer", "lookalike_generation": True},
        "first_party_dispute": {"pretext": "friendly_fraud", "target_population": "consumer", "temporal_strategy": "post_settlement", "behavioral_strategy": "claimant_history", "graph_strategy": "merchant", "lookalike_generation": True},
        "stealth_mandate": {"pretext": "mandate_stealth", "target_population": "consumer", "temporal_strategy": "recurring", "behavioral_strategy": "mandate_reuse", "graph_strategy": "merchant", "lookalike_generation": True},
        "synthetic_merchant": {"pretext": "kyb_shell", "target_population": "merchant", "temporal_strategy": "growth_spike", "behavioral_strategy": "onboarding", "graph_strategy": "merchant", "lookalike_generation": True},
        "transaction_laundering": {"pretext": "laundering", "target_population": "merchant", "temporal_strategy": "pass_through", "behavioral_strategy": "split_flow", "graph_strategy": "network", "lookalike_generation": True},
        "credential_takeover": {"pretext": "session_compromise", "target_population": "consumer", "temporal_strategy": "device_change", "behavioral_strategy": "takeover", "graph_strategy": "device", "lookalike_generation": True},
        "synthetic_identity_bustout": {"pretext": "bustout", "target_population": "consumer", "temporal_strategy": "evolution", "behavioral_strategy": "credit_building", "graph_strategy": "account", "lookalike_generation": True},
        "subthreshold_fragmentation": {"pretext": "fragmentation", "target_population": "consumer", "temporal_strategy": "serial_split", "behavioral_strategy": "low_threshold", "graph_strategy": "multi_party", "lookalike_generation": True},
        "agentic_injection": {"pretext": "agentic_abuse", "target_population": "consumer", "temporal_strategy": "automation", "behavioral_strategy": "delegation", "graph_strategy": "merchant", "lookalike_generation": True},
        "insider_abuse": {"pretext": "insider_access", "target_population": "merchant", "temporal_strategy": "access_window", "behavioral_strategy": "inside_access", "graph_strategy": "merchant", "lookalike_generation": True},
    }

    def generate_spec(
        self,
        *,
        attack_id: str,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ) -> AttackSpec:
        attack_family = attack_id.strip().lower()
        if attack_family not in self._TEMPLATES:
            raise ValueError(f"unsupported scenario attack_id: {attack_id}")

        intensity_value = AttackIntensity(str(intensity).upper())
        template = self._TEMPLATES[attack_family].copy()
        template.update({k: v for k, v in (config or {}).items() if v is not None})
        base_size = {
            AttackIntensity.LOW: 12,
            AttackIntensity.MEDIUM: 25,
            AttackIntensity.HIGH: 55,
        }[intensity_value]
        return AttackSpec(
            attack_id=attack_family,
            seed=seed,
            intensity=intensity_value,
            config=config or {},
            pretext=template.get("pretext"),
            campaign_size=template.get("campaign_size", base_size),
            target_population=template.get("target_population"),
            temporal_strategy=template.get("temporal_strategy"),
            behavioral_strategy=template.get("behavioral_strategy"),
            graph_strategy=template.get("graph_strategy"),
            lookalike_generation=bool(template.get("lookalike_generation", False)),
            attack_specific={
                "pretext": template.get("pretext"),
                "target_population": template.get("target_population"),
                "temporal_strategy": template.get("temporal_strategy"),
                "behavioral_strategy": template.get("behavioral_strategy"),
                "graph_strategy": template.get("graph_strategy"),
            },
        )

    def validate_spec(self, spec: AttackSpec) -> None:
        if spec.attack_id not in self._TEMPLATES:
            raise ValueError(f"invalid template attack_id: {spec.attack_id}")
        if spec.campaign_size is not None and spec.campaign_size <= 0:
            raise ValueError("campaign_size must be positive")
        if spec.intensity not in AttackIntensity:
            raise ValueError("intensity must be one of LOW, MEDIUM, HIGH")


@dataclass(slots=True)
class AttackCampaign:
    campaign_id: str
    attack_id: str
    seed: int
    intensity: AttackIntensity
    start_time: datetime
    end_time: datetime
    affected_entities: list[str]
    attack_event_count: int
    pretext: str | None
    mule_party_id: str | None = None
    spec: AttackSpec | None = None


@dataclass(slots=True)
class AttackDataset:
    source_dir: Path
    output_dir: Path
    campaign: AttackCampaign
    transactions: list[dict[str, Any]]
    labels: list[dict[str, Any]]
    graph_edges: list[dict[str, Any]]
    manifest: dict[str, Any]


class AttackGenerator(ABC):
    """Reusable interface for synthetic attack families."""

    attack_id: str

    @abstractmethod
    def generate(
        self,
        baseline: PaymentDataset,
        *,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ) -> tuple[AttackCampaign, list[dict[str, Any]], list[dict[str, Any]]]:
        """Generate attack campaign metadata and canonical rows."""


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _money(value: float) -> Decimal:
    return Decimal(str(max(float(value), 0.01))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rng(seed: int, *extra: int) -> np.random.Generator:
    if extra:
        seed_seq = np.random.SeedSequence([seed, *extra])
        return np.random.default_rng(seed_seq)
    return np.random.default_rng(seed)


def _build_campaign(
    attack_id: str,
    *,
    seed: int,
    intensity: AttackIntensity | str,
    start_time: datetime,
    end_time: datetime,
    affected_entities: list[str],
    event_count: int,
    pretext: str | None,
    config: dict[str, Any] | None = None,
) -> AttackCampaign:
    intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())
    spec = AttackSpec(
        attack_id=attack_id,
        seed=seed,
        intensity=intensity_value,
        config=config or {},
        start_time=start_time,
        end_time=end_time,
    )
    return AttackCampaign(
        campaign_id=f"{attack_id}-{seed}-{intensity_value.value}-{new_uuid(_rng(seed, 17))[:12]}",
        attack_id=attack_id,
        seed=seed,
        intensity=intensity_value,
        start_time=start_time,
        end_time=end_time,
        affected_entities=affected_entities,
        attack_event_count=event_count,
        pretext=pretext,
        spec=spec,
    )


def _transaction_row(
    *,
    rng: np.random.Generator,
    payer_id: str,
    payee_id: str,
    amount: Decimal,
    ts: datetime,
    device_id: str,
    known_device: bool,
    rail: str,
    channel: str,
    merchant_id: str | None = None,
    mcc: int | None = None,
    auth_method: str = "upi_pin",
    auth_result: str = "success",
    decision: str = "approved",
    decline_reason: str | None = None,
    session_duration_s: int = 30,
    time_on_confirm_screen_s: float = 4.0,
    beneficiary_first_time: bool = True,
    beneficiary_added_ago_s: int = 0,
    pin_attempts: int = 1,
    auth_latency_ms: int | None = None,
    screen_share_active: bool = False,
    call_active_during_txn: bool = False,
    accessibility_service_active: bool = False,
    paste_used_in_amount: bool = False,
    is_agent_initiated: bool = False,
    agent_declared_principal: str | None = None,
    geo_matches_home: bool = True,
    purpose_code: str | None = None,
    issuer_risk_score: float = 0.08,
    session_id: str | None = None,
    ip_country: str = "IN",
    ip_asn: str = "AS55836",
    ip_is_proxy: bool = False,
) -> dict[str, Any]:
    if session_id is None:
        session_id = new_uuid(rng)
    if auth_latency_ms is None:
        if auth_method == "none":
            auth_latency_ms = None
        else:
            auth_latency_ms = int(max(250, rng.lognormal(mean=7.35, sigma=0.45)))
    return {
        "txn_id": new_uuid(rng),
        "timestamp": ts,
        "rail": rail,
        "channel": channel,
        "direction": "push",
        "payer_id": payer_id,
        "payee_id": payee_id,
        "merchant_id": merchant_id,
        "amount": amount,
        "currency": "INR",
        "amount_is_round": amount % Decimal("100.00") == Decimal("0.00"),
        "mcc": mcc,
        "purpose_code": purpose_code,
        "auth_method": auth_method,
        "auth_result": auth_result,
        "auth_latency_ms": auth_latency_ms,
        "eci": None,
        "liability_shift": None,
        "exemption_claimed": None,
        "decision": decision,
        "decline_reason": decline_reason,
        "issuer_risk_score": float(min(max(issuer_risk_score, 0.0), 1.0)),
        "device_id": device_id,
        "device_is_known_for_payer": known_device,
        "session_id": session_id,
        "session_duration_s": session_duration_s,
        "time_on_confirm_screen_s": float(time_on_confirm_screen_s),
        "beneficiary_first_time": beneficiary_first_time,
        "beneficiary_added_ago_s": beneficiary_added_ago_s,
        "pin_attempts": pin_attempts,
        "screen_share_active": screen_share_active,
        "call_active_during_txn": call_active_during_txn,
        "accessibility_service_active": accessibility_service_active,
        "paste_used_in_amount": paste_used_in_amount,
        "is_agent_initiated": is_agent_initiated,
        "agent_declared_principal": agent_declared_principal,
        "ip_country": ip_country,
        "ip_asn": ip_asn,
        "ip_is_proxy": ip_is_proxy,
        "geo_matches_billing": None,
        "geo_matches_payer_home": geo_matches_home,
    }


def _label_row(
    txn_id: str,
    *,
    attack_id: str,
    campaign_id: str,
    pretext: str | None,
    detectable_at: DetectableAt,
) -> dict[str, Any]:
    return {
        "txn_id": txn_id,
        "is_fraud": True,
        "attack_id": attack_id,
        "campaign_id": campaign_id,
        "pretext": pretext,
        "is_legit_lookalike": False,
        "detectable_at": detectable_at.value,
    }


def _choose_device_for_party(baseline: PaymentDataset, party_id: str) -> str | None:
    for row in baseline.tables["devices"]:
        if row["primary_party_id"] == party_id:
            return row["device_id"]
    return None


def _choose_party_ids(baseline: PaymentDataset, *, n: int, exclude: set[str] | None = None) -> list[str]:
    exclude = exclude or set()
    party_rows = baseline.tables["parties"]
    ids = [row["party_id"] for row in party_rows if row["party_type"] == "consumer" and row["party_id"] not in exclude]
    if len(ids) < n:
        return sorted(ids)
    return sorted(ids)[:n]


def load_env_file() -> None:
    """Helper to parse a local .env file manually into os.environ."""
    import sys
    p = Path(".").resolve()
    for parent in [p] + list(p.parents):
        env_path = parent / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                            val = val[1:-1]
                        if "pytest" in sys.modules and key.lower() == "google_gemini_api_key" and key not in os.environ:
                            continue
                        os.environ[key] = val
                break
            except Exception:
                pass


class LLMScenarioGenerator(ScenarioGenerator):
    """Scenario generator utilizing Gemini API with deterministic fallback."""

    def __init__(self, fallback_generator: ScenarioGenerator | None = None):
        self.fallback = fallback_generator or TemplateScenarioGenerator()

    def generate_spec(
        self,
        *,
        attack_id: str,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ) -> AttackSpec:
        load_env_file()
        api_key = os.environ.get("google_gemini_api_key") or os.environ.get("GOOGLE_GEMINI_API_KEY")
        if not api_key:
            return self.fallback.generate_spec(
                attack_id=attack_id, seed=seed, intensity=intensity, config=config
            )

        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())

        prompt = (
            f"You are a threat modeling system generating synthetic fraud attack scenarios "
            f"for payment systems (Mastercard Challenge 2026).\n"
            f"Generate a structured scenario for attack family: '{attack_id}' with intensity: '{intensity_value.value}'.\n"
            f"Your output must be JSON matching the specified schema. Be creative with the pretext "
            f"but remain realistic to the attack vector."
        )

        response_schema = {
            "type": "OBJECT",
            "properties": {
                "pretext": {"type": "STRING"},
                "campaign_size": {"type": "INTEGER"},
                "target_population": {"type": "STRING"},
                "temporal_strategy": {"type": "STRING"},
                "behavioral_strategy": {"type": "STRING"},
                "graph_strategy": {"type": "STRING"},
                "lookalike_generation": {"type": "BOOLEAN"},
            },
            "required": [
                "pretext",
                "campaign_size",
                "target_population",
                "temporal_strategy",
                "behavioral_strategy",
                "graph_strategy",
                "lookalike_generation",
            ]
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
                "temperature": 0.7,
            }
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        llm_data = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=12) as response:
                    resp_json = json.loads(response.read().decode("utf-8"))
                    text_content = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    llm_data = json.loads(text_content)
                    break
            except Exception:
                if attempt == 2:
                    return self.fallback.generate_spec(
                        attack_id=attack_id, seed=seed, intensity=intensity, config=config
                    )

        if not llm_data:
            return self.fallback.generate_spec(
                attack_id=attack_id, seed=seed, intensity=intensity, config=config
            )

        try:
            base_spec = self.fallback.generate_spec(
                attack_id=attack_id, seed=seed, intensity=intensity, config=config
            )

            pretext = llm_data.get("pretext")
            if not isinstance(pretext, str) or not pretext.strip():
                pretext = base_spec.pretext

            campaign_size = llm_data.get("campaign_size")
            if not isinstance(campaign_size, int) or campaign_size <= 0:
                campaign_size = base_spec.campaign_size

            target_pop = llm_data.get("target_population")
            if target_pop not in ("consumer", "merchant"):
                target_pop = base_spec.target_population

            temp_strat = llm_data.get("temporal_strategy")
            if not isinstance(temp_strat, str) or not temp_strat.strip():
                temp_strat = base_spec.temporal_strategy

            beh_strat = llm_data.get("behavioral_strategy")
            if not isinstance(beh_strat, str) or not beh_strat.strip():
                beh_strat = base_spec.behavioral_strategy

            graph_strat = llm_data.get("graph_strategy")
            if not isinstance(graph_strat, str) or not graph_strat.strip():
                graph_strat = base_spec.graph_strategy

            lookalike = llm_data.get("lookalike_generation")
            if not isinstance(lookalike, bool):
                lookalike = base_spec.lookalike_generation

            final_spec = AttackSpec(
                attack_id=base_spec.attack_id,
                seed=seed,
                intensity=intensity_value,
                config=config or {},
                pretext=pretext,
                campaign_size=campaign_size,
                target_population=target_pop,
                temporal_strategy=temp_strat,
                behavioral_strategy=beh_strat,
                graph_strategy=graph_strat,
                lookalike_generation=lookalike,
                attack_specific={
                    "pretext": pretext,
                    "target_population": target_pop,
                    "temporal_strategy": temp_strat,
                    "behavioral_strategy": beh_strat,
                    "graph_strategy": graph_strat,
                }
            )
            return final_spec
        except Exception:
            return self.fallback.generate_spec(
                attack_id=attack_id, seed=seed, intensity=intensity, config=config
            )


class HybridScenarioGenerator(ScenarioGenerator):
    """Scenario generator that perturbs deterministic values using LLM as helper."""

    def __init__(self, fallback_generator: ScenarioGenerator | None = None):
        self.fallback = fallback_generator or TemplateScenarioGenerator()

    def generate_spec(
        self,
        *,
        attack_id: str,
        seed: int,
        intensity: AttackIntensity | str,
        config: dict[str, Any] | None = None,
    ) -> AttackSpec:
        load_env_file()
        api_key = os.environ.get("google_gemini_api_key") or os.environ.get("GOOGLE_GEMINI_API_KEY")

        base_spec = self.fallback.generate_spec(
            attack_id=attack_id, seed=seed, intensity=intensity, config=config
        )

        if not api_key:
            return base_spec

        intensity_value = intensity if isinstance(intensity, AttackIntensity) else AttackIntensity(str(intensity).upper())

        prompt = (
            f"We have a deterministic scenario template with the following properties:\n"
            f"Attack Family: {base_spec.attack_id}\n"
            f"Intensity: {intensity_value.value}\n"
            f"Pretext: {base_spec.pretext}\n"
            f"Campaign Size: {base_spec.campaign_size}\n"
            f"Target Population: {base_spec.target_population}\n"
            f"Temporal Strategy: {base_spec.temporal_strategy}\n"
            f"Behavioral Strategy: {base_spec.behavioral_strategy}\n"
            f"Graph Strategy: {base_spec.graph_strategy}\n"
            f"Lookalike Generation: {base_spec.lookalike_generation}\n\n"
            f"Refine/perturb this scenario spec slightly using Gemini. You can adjust the pretext "
            f"for realism, and vary the campaign_size by up to 20% (either up or down). "
            f"Return the refined values in the specified JSON schema."
        )

        response_schema = {
            "type": "OBJECT",
            "properties": {
                "pretext": {"type": "STRING"},
                "campaign_size": {"type": "INTEGER"},
                "target_population": {"type": "STRING"},
                "temporal_strategy": {"type": "STRING"},
                "behavioral_strategy": {"type": "STRING"},
                "graph_strategy": {"type": "STRING"},
                "lookalike_generation": {"type": "BOOLEAN"},
            },
            "required": [
                "pretext",
                "campaign_size",
                "target_population",
                "temporal_strategy",
                "behavioral_strategy",
                "graph_strategy",
                "lookalike_generation",
            ]
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
                "temperature": 0.5,
            }
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        llm_data = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=12) as response:
                    resp_json = json.loads(response.read().decode("utf-8"))
                    text_content = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    llm_data = json.loads(text_content)
                    break
            except Exception:
                if attempt == 2:
                    return base_spec

        if not llm_data:
            return base_spec

        try:
            campaign_size = llm_data.get("campaign_size", base_spec.campaign_size)
            if not isinstance(campaign_size, int) or campaign_size <= 0:
                campaign_size = base_spec.campaign_size
            else:
                max_diff = int(base_spec.campaign_size * 0.20)
                min_sz = max(1, base_spec.campaign_size - max_diff)
                max_sz = base_spec.campaign_size + max_diff
                campaign_size = max(min_sz, min(campaign_size, max_sz))

            pretext = llm_data.get("pretext")
            if not isinstance(pretext, str) or not pretext.strip():
                pretext = base_spec.pretext

            target_pop = llm_data.get("target_population")
            if target_pop not in ("consumer", "merchant"):
                target_pop = base_spec.target_population

            temp_strat = llm_data.get("temporal_strategy")
            if not isinstance(temp_strat, str) or not temp_strat.strip():
                temp_strat = base_spec.temporal_strategy

            beh_strat = llm_data.get("behavioral_strategy")
            if not isinstance(beh_strat, str) or not beh_strat.strip():
                beh_strat = base_spec.behavioral_strategy

            graph_strat = llm_data.get("graph_strategy")
            if not isinstance(graph_strat, str) or not graph_strat.strip():
                graph_strat = base_spec.graph_strategy

            lookalike = llm_data.get("lookalike_generation")
            if not isinstance(lookalike, bool):
                lookalike = base_spec.lookalike_generation

            return AttackSpec(
                attack_id=base_spec.attack_id,
                seed=seed,
                intensity=intensity_value,
                config=config or {},
                pretext=pretext,
                campaign_size=campaign_size,
                target_population=target_pop,
                temporal_strategy=temp_strat,
                behavioral_strategy=beh_strat,
                graph_strategy=graph_strat,
                lookalike_generation=lookalike,
                attack_specific={
                    "pretext": pretext,
                    "target_population": target_pop,
                    "temporal_strategy": temp_strat,
                    "behavioral_strategy": beh_strat,
                    "graph_strategy": graph_strat,
                }
            )
        except Exception:
            return base_spec


__all__ = [
    "AttackGenerator",
    "ScenarioGenerator",
    "TemplateScenarioGenerator",
    "LLMScenarioGenerator",
    "HybridScenarioGenerator",
    "AttackDataset",
    "AttackCampaign",
    "AttackSpec",
    "AttackIntensity",
    "_money",
    "_build_campaign",
    "_transaction_row",
    "_label_row",
    "_choose_device_for_party",
    "_choose_party_ids",
    "_enum_value",
    "load_env_file",
]
