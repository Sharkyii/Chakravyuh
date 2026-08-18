from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

import os
from src.attacks.framework import (
    AttackDataset,
    AttackGenerator,
    AttackIntensity,
    TemplateScenarioGenerator,
    LLMScenarioGenerator,
    HybridScenarioGenerator,
    load_env_file,
)
from src.attacks.generators import (
    AdversarialEvasionAttack,
    AgenticInjectionAttack,
    CardTestingProbeAttack,
    CredentialTakeoverAttack,
    FirstPartyDisputeAttack,
    InsiderAbuseAttack,
    MuleNetworkAttack,
    ScamInducedPushAttack,
    StealthMandateAttack,
    SubthresholdFragmentationAttack,
    SyntheticIdentityBustoutAttack,
    SyntheticMerchantAttack,
    TransactionLaunderingAttack,
    make_legit_lookalike_rows,
)
from src.dataset.loader import EXPECTED_TABLES, PaymentDataset, load_dataset
from src.graph.builder import GraphBuildConfig, build_graph_edges
from src.schema import TABLE_ARROW_SCHEMAS
from src.validation.attacks import validate_attack_dataset


def build_attack_generator(attack_id: str) -> AttackGenerator:
    factory = {
        "scam_induced_push": ScamInducedPushAttack,
        "mule_network": MuleNetworkAttack,
        "card_testing_probe": CardTestingProbeAttack,
        "adversarial_evasion": AdversarialEvasionAttack,
        "first_party_dispute": FirstPartyDisputeAttack,
        "stealth_mandate": StealthMandateAttack,
        "synthetic_merchant": SyntheticMerchantAttack,
        "transaction_laundering": TransactionLaunderingAttack,
        "credential_takeover": CredentialTakeoverAttack,
        "synthetic_identity_bustout": SyntheticIdentityBustoutAttack,
        "subthreshold_fragmentation": SubthresholdFragmentationAttack,
        "agentic_injection": AgenticInjectionAttack,
        "insider_abuse": InsiderAbuseAttack,
    }
    try:
        return factory[attack_id]()
    except KeyError as exc:
        raise ValueError(f"unsupported attack_id: {attack_id}") from exc


def build_scenario_spec(
    *,
    attack_id: str,
    seed: int,
    intensity: str | AttackIntensity = AttackIntensity.MEDIUM,
    config: dict[str, Any] | None = None,
) -> Any:
    load_env_file()
    mode = os.environ.get("SCENARIO_GENERATOR_MODE", "deterministic").strip().lower()
    if mode == "llm":
        generator = LLMScenarioGenerator()
    elif mode == "hybrid":
        generator = HybridScenarioGenerator()
    else:
        generator = TemplateScenarioGenerator()
    return generator.generate_spec(attack_id=attack_id, seed=seed, intensity=intensity, config=config)


def _write_table(path: Path, table_name: str, rows: list[dict[str, Any]]) -> None:
    pq.write_table(pa.Table.from_pylist(rows, schema=TABLE_ARROW_SCHEMAS[table_name]), path)


def _manifest_for_attack(
    *,
    attack_id: str,
    campaign: Any,
    baseline: PaymentDataset,
    n_attack_txns: int,
    output_dir: Path,
) -> dict[str, Any]:
    return {
        "dataset_version": f"attack-{attack_id}-v1",
        "seed": campaign.seed,
        "baseline_dataset_version": baseline.manifest.get("dataset_version"),
        "baseline_dir": str(baseline.source_dir),
        "simulation_start": baseline.manifest.get("simulation_start"),
        "simulation_end": baseline.manifest.get("simulation_end"),
        "attack_id": attack_id,
        "campaign_id": campaign.campaign_id,
        "pretext": campaign.pretext,
        "intensity": campaign.intensity.value,
        "n_transactions": n_attack_txns,
        "generator": f"src.attacks.generators.{attack_id}",
        "notes": "Stage 3 synthetic attack scenario layered on baseline Stage 2 dataset; baseline remains unchanged.",
        "output_dir": str(output_dir),
    }


def write_attack_dataset(
    *,
    result: AttackDataset,
    baseline: PaymentDataset,
    output_dir: Path,
    clean: bool = True,
) -> None:
    from src.dataset.loader import clear_dataset_cache
    clear_dataset_cache(output_dir)

    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # legit_lookalike rows are additive to the *written* dataset only -- they
    # are not part of result.transactions/result.labels, which stay pure
    # attack-only (one campaign, is_fraud=True) for callers that inspect the
    # AttackDataset return value directly.
    lookalike_txs, lookalike_labels = make_legit_lookalike_rows(
        attack_rows=result.transactions, attack_labels=result.labels, seed=result.campaign.seed
    )
    combined_transactions = baseline.transactions + result.transactions + lookalike_txs
    combined_labels = baseline.labels + result.labels + lookalike_labels
    final_graph = build_graph_edges(combined_transactions, GraphBuildConfig())

    for table_name in EXPECTED_TABLES:
        source_path = baseline.source_dir / f"{table_name}.parquet"
        target_path = output_dir / f"{table_name}.parquet"
        if table_name == "transactions":
            _write_table(target_path, table_name, combined_transactions)
        elif table_name == "labels":
            _write_table(target_path, table_name, combined_labels)
        elif table_name == "graph_edges":
            _write_table(target_path, table_name, [asdict(edge) for edge in final_graph])
        elif source_path.exists():
            shutil.copy2(source_path, target_path)

    manifest = _manifest_for_attack(
        attack_id=result.campaign.attack_id,
        campaign=result.campaign,
        baseline=baseline,
        n_attack_txns=len(result.transactions),
        output_dir=output_dir,
    )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = validate_attack_dataset(load_dataset(output_dir), result.campaign.attack_id)
    (output_dir / "validation_report.json").write_text(
        json.dumps({"ok": report.ok, "errors": report.errors, "summary": report.summary}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report.ok:
        raise ValueError("Attack validation failed: " + "; ".join(report.errors[:10]))


def generate_attack_dataset(
    attack_id: str,
    *,
    seed: int,
    baseline_dir: Path | str,
    intensity: str | AttackIntensity = AttackIntensity.MEDIUM,
    output_dir: Path | str | None = None,
    clean: bool = True,
) -> AttackDataset:
    baseline = load_dataset(Path(baseline_dir))
    generator = build_attack_generator(attack_id)
    attack_campaign, attack_txs, attack_labels = generator.generate(
        baseline,
        seed=seed,
        intensity=intensity,
    )
    if output_dir is None:
        output_path = Path("data/generated/attacks") / attack_id.upper() / f"seed-{seed}"
    else:
        output_path = Path(output_dir)
    graph_edges = build_graph_edges(baseline.transactions + attack_txs, GraphBuildConfig())
    result = AttackDataset(
        source_dir=baseline.source_dir,
        output_dir=output_path,
        campaign=attack_campaign,
        transactions=attack_txs,
        labels=attack_labels,
        graph_edges=[asdict(edge) for edge in graph_edges],
        manifest={},
    )
    write_attack_dataset(result=result, baseline=baseline, output_dir=output_path, clean=clean)
    result.manifest = json.loads((output_path / "manifest.json").read_text(encoding="utf-8"))
    return result


__all__ = ["build_attack_generator", "build_scenario_spec", "generate_attack_dataset", "write_attack_dataset"]
