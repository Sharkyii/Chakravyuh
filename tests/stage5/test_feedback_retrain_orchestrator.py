"""Regression coverage for the bug this session found and fixed live: a
retrain that pulls in stale gen3/4/5 retained-attack rows against a
differently-scaled baseline can spike training fraud prevalence by an order
of magnitude and collapse the retrained model's quality -- and the
orchestrator used to promote that model to `stage5/models/` unconditionally.

These tests mock training/feedback I/O so they run in milliseconds and never
touch real data or `stage5/models/`.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from stage5.training import feedback_retrain_orchestrator as orch


class _StubFeedbackStore:
    """No feedback rows in the store -- run_retrain() should bail out early."""

    def __init__(self, feedback_path):
        self.feedback_path = feedback_path
        self.feedback_dir = feedback_path.parent


def _write_feedback(path, rows):
    pd.DataFrame(rows).to_parquet(path, index=False)


def _baseline_df(n_legit: int, n_fraud: int) -> pd.DataFrame:
    rows = [{"txn_id": f"legit_{i}", "is_fraud": 0, "split": "train"} for i in range(n_legit)]
    rows += [{"txn_id": f"fraud_{i}", "is_fraud": 1, "split": "train"} for i in range(n_fraud)]
    return pd.DataFrame(rows)


def _stub_train_result(pr_auc: float) -> dict:
    return {
        "model": object(),
        "preprocessor": object(),
        "threshold": 0.5,
        "metrics": {
            "validation_metrics": {},
            "test_metrics": {"pr_auc": pr_auc, "fixed_fpr_operating_points": []},
        },
    }


@pytest.fixture
def orchestrator_env(tmp_path, monkeypatch):
    """Isolate run_retrain() from real disk state: models dir, feedback
    store, and the two training entry points it calls, all redirected."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setattr(orch, "MODELS_DIR", models_dir)

    feedback_path = data_dir / "analyst_feedback.parquet"
    monkeypatch.setattr(
        orch, "FeedbackStore", lambda: _StubFeedbackStore(feedback_path)
    )
    monkeypatch.setattr(orch, "RETAINED_ATTACKS_DIR", data_dir)

    return {"models_dir": models_dir, "data_dir": data_dir, "feedback_path": feedback_path}


def _write_previous_model(models_dir, pr_auc: float, version: str = "stage5_xgb_v2"):
    (models_dir / "model_metadata.json").write_text(json.dumps({
        "model_version": version,
        "test_metrics": {"pr_auc": pr_auc},
    }))


def test_no_feedback_file_returns_false(orchestrator_env, monkeypatch):
    monkeypatch.setattr(orch, "load_and_prepare", lambda: (_ for _ in ()).throw(
        AssertionError("should never reach training with no feedback")
    ))
    assert orch.run_retrain() is False


def test_empty_feedback_returns_false(orchestrator_env, monkeypatch):
    _write_feedback(orchestrator_env["feedback_path"], [])
    monkeypatch.setattr(orch, "load_and_prepare", lambda: (_ for _ in ()).throw(
        AssertionError("should never reach training with empty feedback")
    ))
    assert orch.run_retrain() is False


def test_quality_gate_rejects_regression_and_keeps_old_model(orchestrator_env, monkeypatch):
    """The exact bug this session reproduced: a retrain that comes back much
    worse than the deployed model must not overwrite it."""
    models_dir = orchestrator_env["models_dir"]
    _write_previous_model(models_dir, pr_auc=0.999)
    _write_feedback(orchestrator_env["feedback_path"], [
        {"transaction_id": "t1", "analyst_verdict": "FRAUD"},
    ])

    monkeypatch.setattr(orch, "load_and_prepare", lambda: _baseline_df(1000, 10))
    monkeypatch.setattr(orch, "train_fraud_model", lambda df: _stub_train_result(pr_auc=0.46))

    result = orch.run_retrain()

    assert result is False
    # Nothing was promoted: no new model/preprocessor files, metadata untouched.
    assert not (models_dir / "fraud_model.pkl").exists()
    assert not (models_dir / "preprocessor.pkl").exists()
    saved_meta = json.loads((models_dir / "model_metadata.json").read_text())
    assert saved_meta["model_version"] == "stage5_xgb_v2"
    # Feedback was NOT archived -- it must stay queued for the next attempt.
    assert orchestrator_env["feedback_path"].exists()


def test_quality_gate_allows_comparable_model(orchestrator_env, monkeypatch, tmp_path):
    """A retrain that's not materially worse should still go live."""
    models_dir = orchestrator_env["models_dir"]
    _write_previous_model(models_dir, pr_auc=0.99)
    _write_feedback(orchestrator_env["feedback_path"], [
        {"transaction_id": "t1", "analyst_verdict": "FRAUD"},
    ])

    monkeypatch.setattr(orch, "load_and_prepare", lambda: _baseline_df(1000, 10))
    monkeypatch.setattr(orch, "train_fraud_model", lambda df: _stub_train_result(pr_auc=0.985))
    monkeypatch.setattr(orch.joblib, "dump", lambda obj, path: path.write_text("stub"))

    result = orch.run_retrain()

    assert result is True
    saved_meta = json.loads((models_dir / "model_metadata.json").read_text())
    assert saved_meta["model_version"] == "stage5_xgb_v3_retrained"
    assert saved_meta["test_metrics"]["pr_auc"] == 0.985


def test_no_previous_model_skips_gate(orchestrator_env, monkeypatch):
    """First-ever retrain (no previous_metadata.json yet) has nothing to
    compare against -- must not crash, must still promote."""
    _write_feedback(orchestrator_env["feedback_path"], [
        {"transaction_id": "t1", "analyst_verdict": "FRAUD"},
    ])

    monkeypatch.setattr(orch, "load_and_prepare", lambda: _baseline_df(1000, 10))
    monkeypatch.setattr(orch, "train_fraud_model", lambda df: _stub_train_result(pr_auc=0.5))
    monkeypatch.setattr(orch.joblib, "dump", lambda obj, path: path.write_text("stub"))

    result = orch.run_retrain()

    assert result is True


def test_retained_attacks_downsampled_to_prevalence_cap(orchestrator_env, monkeypatch):
    """The other half of the fix: retained-attack rows that would blow past
    MAX_RETAINED_ATTACK_PREVALENCE against the current baseline get
    downsampled, not concatenated wholesale. Reproduces the exact shape of
    the bug: a small baseline (like the 2k-consumer container dataset) plus
    the real curriculum run's ~4.3k retained rows, all fraud."""
    models_dir = orchestrator_env["models_dir"]
    _write_previous_model(models_dir, pr_auc=0.99)
    _write_feedback(orchestrator_env["feedback_path"], [
        {"transaction_id": "t1", "analyst_verdict": "FRAUD"},
    ])

    monkeypatch.setattr(orch, "load_and_prepare", lambda: _baseline_df(2000, 10))

    # Retained attacks alone (4000 rows, all fraud) would push prevalence to
    # ~66% if concatenated wholesale -- must be capped well under that.
    retained = pd.DataFrame(
        [{"txn_id": f"retained_{i}", "is_fraud": 1} for i in range(4000)]
    )
    retained.to_parquet(orchestrator_env["data_dir"] / "gen3_retained_attacks.parquet", index=False)

    captured = {}

    def _capture_and_train(df):
        captured["df"] = df
        return _stub_train_result(pr_auc=0.985)

    monkeypatch.setattr(orch, "train_fraud_model", _capture_and_train)
    monkeypatch.setattr(orch.joblib, "dump", lambda obj, path: path.write_text("stub"))

    result = orch.run_retrain()

    assert result is True
    trained_df = captured["df"]
    fraud_count = int((trained_df["is_fraud"] == 1).sum())
    total = len(trained_df)
    prevalence = fraud_count / total
    assert fraud_count < 2000, "the full 4000 retained rows must not all survive the cap"
    assert prevalence <= orch.MAX_RETAINED_ATTACK_PREVALENCE + 1e-6, (
        f"post-merge prevalence {prevalence:.3f} exceeds the cap -- this is the exact "
        f"bug that collapsed test PR-AUC from ~0.999 to ~0.46 in production"
    )
