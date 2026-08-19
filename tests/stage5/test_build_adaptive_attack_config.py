"""issues.md I11 closed loop: build_adaptive_config() should derive an
adversarial_evasion config from a trained model's feature importances, and
fall back to {} gracefully when no model exists yet."""

from __future__ import annotations

import numpy as np
import joblib

from stage5.training.build_adaptive_attack_config import (
    BENEFICIARY_AGE_ADAPTIVE_FRACTION,
    TARGET_IMPORTANCE_THRESHOLD,
    build_adaptive_config,
)


class _StubPreprocessor:
    def __init__(self, names):
        self._names = names

    def get_feature_names_out(self):
        return np.array(self._names)


class _StubModel:
    def __init__(self, importances):
        self.feature_importances_ = np.array(importances)


def _write_stub_artifacts(models_dir, names, importances):
    joblib.dump(_StubModel(importances), models_dir / "fraud_model.pkl")
    joblib.dump(_StubPreprocessor(names), models_dir / "preprocessor.pkl")


def test_no_model_returns_empty_config(tmp_path, monkeypatch):
    monkeypatch.setattr("stage5.training.build_adaptive_attack_config.MODELS_DIR", tmp_path)
    assert build_adaptive_config() == {}


def test_edge_count_above_threshold_triggers_adaptive_routing(tmp_path, monkeypatch):
    monkeypatch.setattr("stage5.training.build_adaptive_attack_config.MODELS_DIR", tmp_path)
    names = ["num__edge_count", "num__amount", "cat__rail_upi_p2p"]
    importances = [TARGET_IMPORTANCE_THRESHOLD + 0.05, 0.1, 0.1]
    _write_stub_artifacts(tmp_path, names, importances)

    config = build_adaptive_config()
    assert config.get("adaptive_top_counterparty") is True
    assert "beneficiary_age_floor_s" not in config


def test_beneficiary_age_above_threshold_sets_floor(tmp_path, monkeypatch):
    monkeypatch.setattr("stage5.training.build_adaptive_attack_config.MODELS_DIR", tmp_path)
    names = ["num__beneficiary_added_ago_s", "num__amount"]
    importances = [TARGET_IMPORTANCE_THRESHOLD + 0.02, 0.1]
    _write_stub_artifacts(tmp_path, names, importances)

    config = build_adaptive_config()
    assert "adaptive_top_counterparty" not in config

    from src.generators import calibration as cal

    floor, ceiling = cal.LEGIT_EXISTING_BENEFICIARY_MIN_AGE_S, cal.LEGIT_EXISTING_BENEFICIARY_MAX_AGE_S
    expected = int(floor + BENEFICIARY_AGE_ADAPTIVE_FRACTION * (ceiling - floor))
    assert config["beneficiary_age_floor_s"] == expected


def test_below_threshold_features_produce_no_targeting(tmp_path, monkeypatch):
    monkeypatch.setattr("stage5.training.build_adaptive_attack_config.MODELS_DIR", tmp_path)
    names = ["num__edge_count", "num__beneficiary_added_ago_s"]
    importances = [TARGET_IMPORTANCE_THRESHOLD - 0.05, TARGET_IMPORTANCE_THRESHOLD - 0.05]
    _write_stub_artifacts(tmp_path, names, importances)

    assert build_adaptive_config() == {}
