from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.attacks.registry import (
    build_attack_generator,
    generate_attack_dataset as _orig_generate_attack_dataset,
)
from src.dataset.loader import load_dataset
from src.dataset.stage2 import build_stage2_dataset
from src.generators.dataset import generate_stage1_dataset


_test_attacks_dir: Path | None = None


@pytest.fixture(scope="session", autouse=True)
def setup_test_attacks_dir(tmp_path_factory):
    global _test_attacks_dir
    _test_attacks_dir = tmp_path_factory.mktemp("test_attacks")


def generate_attack_dataset(
    attack_id: str,
    *,
    seed: int,
    baseline_dir: Path | str,
    intensity: str | Any = "MEDIUM",
    output_dir: Path | str | None = None,
    clean: bool = True,
) -> Any:
    if output_dir is None and _test_attacks_dir is not None:
        output_dir = _test_attacks_dir / attack_id / f"seed-{seed}"
    return _orig_generate_attack_dataset(
        attack_id,
        seed=seed,
        baseline_dir=baseline_dir,
        intensity=intensity,
        output_dir=output_dir,
        clean=clean,
    )


ATTACK_IDS = [
    "scam_induced_push",
    "mule_network",
    "card_testing_probe",
    "adversarial_evasion",
    "first_party_dispute",
    "stealth_mandate",
    "synthetic_merchant",
    "transaction_laundering",
    "credential_takeover",
    "synthetic_identity_bustout",
    "subthreshold_fragmentation",
    "agentic_injection",
    "insider_abuse",
]


@pytest.fixture(scope="session")
def baseline_stage2(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("baseline_data")
    stage1_dir = tmp_path / "stage1"
    stage2_dir = tmp_path / "stage2"
    generate_stage1_dataset(
        seed=42, output_dir=stage1_dir, n_consumers=250, n_merchants=30, clean=True
    )
    build_stage2_dataset(stage1_dir, stage2_dir, clean=True)
    return load_dataset(stage2_dir)


def test_attack_generators_follow_common_interface():
    for attack_id in ATTACK_IDS:
        generator = build_attack_generator(attack_id)
        assert generator.attack_id == attack_id
        assert hasattr(generator, "generate")


def test_attack_campaigns_are_deterministic_and_seed_sensitive(baseline_stage2):
    a = generate_attack_dataset(
        "scam_induced_push",
        seed=42,
        baseline_dir=baseline_stage2.source_dir,
        intensity="MEDIUM",
        clean=True,
    )
    b = generate_attack_dataset(
        "scam_induced_push",
        seed=42,
        baseline_dir=baseline_stage2.source_dir,
        intensity="MEDIUM",
        clean=True,
    )
    c = generate_attack_dataset(
        "scam_induced_push",
        seed=43,
        baseline_dir=baseline_stage2.source_dir,
        intensity="MEDIUM",
        clean=True,
    )

    assert a.campaign.campaign_id == b.campaign.campaign_id
    assert a.transactions[0]["txn_id"] == b.transactions[0]["txn_id"]
    assert a.campaign.campaign_id != c.campaign.campaign_id


def test_template_scenario_generator_and_registry_support_baseline_compatibility(baseline_stage2):
    from src.attacks.framework import TemplateScenarioGenerator
    from src.attacks.registry import build_scenario_spec

    spec = build_scenario_spec(attack_id="stealth_mandate", seed=42, intensity="HIGH")
    assert spec.attack_id == "stealth_mandate"
    assert spec.intensity.value == "HIGH"
    assert spec.lookalike_generation is True

    scenario = TemplateScenarioGenerator()
    second = scenario.generate_spec(attack_id="first_party_dispute", seed=42, intensity="LOW")
    assert second.attack_id == "first_party_dispute"
    assert second.campaign_size is not None

    out = generate_attack_dataset(
        "first_party_dispute",
        seed=17,
        baseline_dir=baseline_stage2.source_dir,
        intensity="MEDIUM",
        clean=True,
    )
    assert out.campaign.attack_id == "first_party_dispute"
    assert len(out.labels) > 0


def test_stage4_generators_have_valid_registry_entries(baseline_stage2):
    for attack_id in ATTACK_IDS:
        output = generate_attack_dataset(
            attack_id,
            seed=23 + ATTACK_IDS.index(attack_id),
            baseline_dir=baseline_stage2.source_dir,
            intensity="LOW",
            clean=True,
        )
        assert output.campaign.attack_id == attack_id
        assert all(row["campaign_id"] == output.campaign.campaign_id for row in output.labels)


def test_attack_labels_are_correct_and_schema_valid(baseline_stage2):
    output = generate_attack_dataset(
        "scam_induced_push",
        seed=7,
        baseline_dir=baseline_stage2.source_dir,
        intensity="LOW",
        clean=True,
    )
    attack_rows = [row for row in output.labels if row["attack_id"] == "scam_induced_push"]
    assert attack_rows
    assert all(row["is_fraud"] is True for row in attack_rows)
    assert all(row["campaign_id"] == output.campaign.campaign_id for row in attack_rows)
    assert all(row["is_legit_lookalike"] is False for row in attack_rows)
    assert all(row["detectable_at"] is not None for row in attack_rows)


def test_mule_network_generates_fanin_fanout_pass_through(baseline_stage2):
    output = generate_attack_dataset(
        "mule_network",
        seed=11,
        baseline_dir=baseline_stage2.source_dir,
        intensity="MEDIUM",
        clean=True,
    )
    edges = output.graph_edges
    assert len(edges) >= 2
    assert any(edge["dst_party_id"] == output.campaign.mule_party_id for edge in edges)
    assert output.campaign.mule_party_id is not None


def test_card_testing_probe_has_repeated_attempt_pattern(baseline_stage2):
    output = generate_attack_dataset(
        "card_testing_probe",
        seed=3,
        baseline_dir=baseline_stage2.source_dir,
        intensity="HIGH",
        clean=True,
    )
    attack_txns = [
        row
        for row in output.transactions
        if row["txn_id"]
        in {
            label["txn_id"] for label in output.labels if label["attack_id"] == "card_testing_probe"
        }
    ]
    assert len(attack_txns) >= 4
    assert len({row["merchant_id"] for row in attack_txns if row["merchant_id"] is not None}) >= 1
    assert any(row["decision"] == "declined" for row in attack_txns)


def test_adversarial_evasion_reduces_obvious_anomalies(baseline_stage2):
    output = generate_attack_dataset(
        "adversarial_evasion",
        seed=9,
        baseline_dir=baseline_stage2.source_dir,
        intensity="MEDIUM",
        clean=True,
    )
    attack_txns = [
        row
        for row in output.transactions
        if row["txn_id"]
        in {
            label["txn_id"]
            for label in output.labels
            if label["attack_id"] == "adversarial_evasion"
        }
    ]
    assert len(attack_txns) >= 2
    assert all(row["device_is_known_for_payer"] is True for row in attack_txns)
    assert all(row["beneficiary_first_time"] is False for row in attack_txns)
    assert all(row["geo_matches_payer_home"] is True for row in attack_txns)


def test_adversarial_evasion_adaptive_top_counterparty(baseline_stage2):
    """issues.md I11 closed loop: config={"adaptive_top_counterparty": True}
    should route every campaign event through the payer's single busiest
    existing relationship instead of spreading across a small pool."""
    generator = build_attack_generator("adversarial_evasion")
    _campaign, rows, _labels = generator.generate(
        baseline_stage2, seed=42, intensity="HIGH", config={"adaptive_top_counterparty": True}
    )
    payees = {row["payee_id"] for row in rows}
    assert len(payees) == 1, "adaptive mode should concentrate every event on one counterparty"


def test_adversarial_evasion_beneficiary_age_floor_override(baseline_stage2):
    from src.generators import calibration as cal

    generator = build_attack_generator("adversarial_evasion")
    floor = cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S + 1_000_000
    _campaign, rows, _labels = generator.generate(
        baseline_stage2, seed=7, intensity="MEDIUM", config={"beneficiary_age_floor_s": floor}
    )
    assert all(row["beneficiary_added_ago_s"] >= floor for row in rows)


def test_adversarial_evasion_default_config_unchanged(baseline_stage2):
    """No config (or an empty one) must reproduce the pre-I11 pool-based
    routing -- the adaptive path is opt-in, not a behavior change for
    existing callers."""
    generator = build_attack_generator("adversarial_evasion")
    _campaign, none_cfg_rows, _labels = generator.generate(
        baseline_stage2, seed=3, intensity="HIGH"
    )
    _campaign2, empty_cfg_rows, _labels2 = generator.generate(
        baseline_stage2, seed=3, intensity="HIGH", config={}
    )
    assert [r["txn_id"] for r in none_cfg_rows] == [r["txn_id"] for r in empty_cfg_rows]


def test_attack_intensity_changes_behavior(baseline_stage2):
    low = generate_attack_dataset(
        "scam_induced_push",
        seed=99,
        baseline_dir=baseline_stage2.source_dir,
        intensity="LOW",
        clean=True,
    )
    medium = generate_attack_dataset(
        "scam_induced_push",
        seed=99,
        baseline_dir=baseline_stage2.source_dir,
        intensity="MEDIUM",
        clean=True,
    )
    high = generate_attack_dataset(
        "scam_induced_push",
        seed=99,
        baseline_dir=baseline_stage2.source_dir,
        intensity="HIGH",
        clean=True,
    )

    assert len(low.transactions) < len(medium.transactions) < len(high.transactions)
    assert low.campaign.spec.intensity != high.campaign.spec.intensity


def test_attack_dataset_remains_in_simulation_window(baseline_stage2):
    from datetime import datetime

    sim_start = datetime.fromisoformat(baseline_stage2.manifest["simulation_start"])
    sim_end = datetime.fromisoformat(baseline_stage2.manifest["simulation_end"])
    for attack_id in ATTACK_IDS:
        output = generate_attack_dataset(
            attack_id,
            seed=13,
            baseline_dir=baseline_stage2.source_dir,
            intensity="MEDIUM",
            clean=True,
        )
        for row in output.transactions:
            assert row["timestamp"] >= sim_start
            assert row["timestamp"] < sim_end


def test_env_loading(tmp_path):
    import os
    from src.attacks.framework import load_env_file

    # Write temporary .env in current cwd or parent path
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        with open(".env", "w", encoding="utf-8") as f:
            f.write("TEST_ENV_VAR_X=hello_world\nSCENARIO_GENERATOR_MODE=llm\n")
        load_env_file()
        assert os.environ.get("TEST_ENV_VAR_X") == "hello_world"
        assert os.environ.get("SCENARIO_GENERATOR_MODE") == "llm"
    finally:
        os.chdir(orig_cwd)


def test_llm_generator_fallback():
    import os
    from src.attacks.framework import LLMScenarioGenerator

    # Temporarily remove API key from environment
    old_key = os.environ.pop("google_gemini_api_key", None)
    old_key_upper = os.environ.pop("GOOGLE_GEMINI_API_KEY", None)

    try:
        generator = LLMScenarioGenerator()
        spec = generator.generate_spec(attack_id="scam_induced_push", seed=10, intensity="MEDIUM")
        assert spec.attack_id == "scam_induced_push"
        assert spec.pretext == "digital_arrest"
        assert spec.campaign_size == 25
    finally:
        if old_key is not None:
            os.environ["google_gemini_api_key"] = old_key
        if old_key_upper is not None:
            os.environ["GOOGLE_GEMINI_API_KEY"] = old_key_upper


def test_hybrid_generator_fallback():
    import os
    from src.attacks.framework import HybridScenarioGenerator

    old_key = os.environ.pop("google_gemini_api_key", None)
    old_key_upper = os.environ.pop("GOOGLE_GEMINI_API_KEY", None)

    try:
        generator = HybridScenarioGenerator()
        spec = generator.generate_spec(attack_id="mule_network", seed=10, intensity="LOW")
        assert spec.attack_id == "mule_network"
        assert spec.pretext == "pass_through"
        assert spec.campaign_size == 12
    finally:
        if old_key is not None:
            os.environ["google_gemini_api_key"] = old_key
        if old_key_upper is not None:
            os.environ["GOOGLE_GEMINI_API_KEY"] = old_key_upper
