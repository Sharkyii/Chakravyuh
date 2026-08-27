"""Regression tests for family-specific, calibrated curriculum hardening."""

import numpy as np
import pandas as pd
import pytest

from stage5.adversarial.gen3_config import GEN3_SPECS
from stage5.adversarial.gen3_generator import Gen3AttackGenerator
from stage5.training import curriculum_retrain


def test_gen3_templates_are_drawn_from_requested_family(monkeypatch):
    """A Gen3 curriculum cannot turn another family's row into its template."""
    monkeypatch.setattr(
        "stage5.adversarial.gen3_generator.get_top_features", lambda *_args, **_kwargs: []
    )
    training_df = pd.DataFrame([
        {"is_fraud": True, "attack_id": "adversarial_evasion", "template": "requested"},
        {"is_fraud": True, "attack_id": "mule_network", "template": "other"},
        {"is_fraud": False, "attack_id": None, "template": "legitimate"},
    ])
    generator = Gen3AttackGenerator(object(), training_df)

    attacks = generator._generate_level_attacks(
        "adversarial_evasion", n_samples=10, n_features_to_hide=0, difficulty_multiplier=1.0
    )

    assert {attack["features"]["template"] for attack in attacks} == {"requested"}


def test_gen3_rejects_a_family_without_fraud_templates(monkeypatch):
    """Missing templates fail loudly instead of falling back to another family."""
    monkeypatch.setattr(
        "stage5.adversarial.gen3_generator.get_top_features", lambda *_args, **_kwargs: []
    )
    generator = Gen3AttackGenerator(
        object(), pd.DataFrame([{"is_fraud": False, "attack_id": None}])
    )

    with pytest.raises(ValueError, match="family-specific Gen 3 curriculum"):
        generator._generate_level_attacks(
            "adversarial_evasion", n_samples=1, n_features_to_hide=0, difficulty_multiplier=1.0
        )


def test_gen3_uses_current_credential_takeover_family_name():
    """The curriculum targets a canonical detector family, not a dead alias."""
    assert "credential_takeover" in GEN3_SPECS
    assert "account_takeover" not in GEN3_SPECS


def test_curriculum_threshold_is_derived_at_one_percent_fpr(monkeypatch):
    """Evasion checks use the checkpoint's calibrated operating point."""
    class IdentityPreprocessor:
        def transform(self, X):
            return X

    class Model:
        def predict_proba(self, X):
            return np.tile([0.2, 0.8], (len(X), 1))

    observed = {}

    def fake_fixed_fpr(y_true, probabilities, target_fpr):
        observed["labels"] = y_true.tolist()
        observed["target_fpr"] = target_fpr
        observed["probabilities"] = probabilities.tolist()
        return {"threshold": 0.83}

    monkeypatch.setattr(curriculum_retrain, "precision_recall_at_fixed_fpr", fake_fixed_fpr)
    reference_df = pd.DataFrame({
        "split": ["test", "test"], "is_fraud": [0, 1],
    })

    threshold = curriculum_retrain._fixed_fpr_threshold(
        Model(), IdentityPreprocessor(), reference_df
    )

    assert threshold == 0.83
    assert observed["labels"] == [0, 1]
    assert observed["target_fpr"] == 0.01
