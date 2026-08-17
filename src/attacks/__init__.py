"""Synthetic attack framework for Stage 3/4 generation."""

from src.attacks.framework import (
    AttackCampaign,
    AttackDataset,
    AttackGenerator,
    AttackIntensity,
    AttackSpec,
    ScenarioGenerator,
    TemplateScenarioGenerator,
)
from src.attacks.registry import build_attack_generator, build_scenario_spec, generate_attack_dataset

__all__ = [
    "AttackGenerator",
    "ScenarioGenerator",
    "TemplateScenarioGenerator",
    "AttackIntensity",
    "AttackSpec",
    "AttackCampaign",
    "AttackDataset",
    "build_attack_generator",
    "build_scenario_spec",
    "generate_attack_dataset",
]
