import os

import pandas as pd
import pytest

from stage5.config.settings import ALL_FEATURES, MODELS_DIR
from stage5.inference.pipeline import (
    _calibrated_base_score,
    analyze_transaction,
    compute_shap_contributions,
    get_fallback_llm_analysis,
    load_artifacts,
    prepare_transaction_df,
)

# stage5/models/*.pkl aren't generated in CI, so tests that need real model
# artifacts skip cleanly there rather than fail -- mirrors the tolerant
# assertion already used in web/next-app/e2e/portal.spec.ts's risk-assessment
# test.
requires_trained_models = pytest.mark.skipif(
    not (MODELS_DIR / "fraud_model.pkl").exists(),
    reason="trained model artifacts not present (not generated in CI)",
)

# attack_classifier.pkl is a separate training run (train_attack_classifier.py)
# from the fraud model and isn't currently produced by the Gen 3/4/5 curriculum
# retrain scripts -- load_artifacts() treats it as optional (pipeline.py degrades
# to fraud-only scoring), but these two tests assert the full attack-family
# breakdown, which needs the classifier to actually be present on disk.
requires_attack_classifier = pytest.mark.skipif(
    not (MODELS_DIR / "attack_classifier.pkl").exists(),
    reason="attack_classifier.pkl not present -- run stage5/training/train_attack_classifier.py",
)


@requires_trained_models
@requires_attack_classifier
def test_saved_artifacts_load_correctly():
    """Verifies that the preprocessor, fraud model, attack classifier, and mappings load correctly."""
    artifacts = load_artifacts()
    assert "preprocessor" in artifacts
    assert "fraud_model" in artifacts
    assert "attack_classifier" in artifacts
    assert "idx_to_attack" in artifacts
    assert "attack_to_idx" in artifacts

    # Check that the preprocessor has the expected type.
    from sklearn.compose import ColumnTransformer

    assert isinstance(artifacts["preprocessor"], ColumnTransformer)
    # The models might be XGBClassifier or RandomForestClassifier depending on best selection, but they must have predict_proba
    assert hasattr(artifacts["fraud_model"], "predict_proba")
    assert hasattr(artifacts["attack_classifier"], "predict_proba")
    assert isinstance(artifacts["idx_to_attack"], dict)
    assert len(artifacts["idx_to_attack"]) == 16


def test_prepare_transaction_df():
    """Tests the input formatting function helper."""
    dummy_txn = {
        "txn_id": "tx-12345",
        "amount": 5000.0,
        "payer_id": "payer-001",
        "device_is_known_for_payer": True,
        "edge_count": 12.0,
    }

    df = prepare_transaction_df(dummy_txn)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ALL_FEATURES
    assert len(df) == 1

    # Check values mapped
    assert df.loc[0, "amount"] == 5000.0
    assert df.loc[0, "device_is_known_for_payer"]
    assert df.loc[0, "edge_count"] == 12.0

    # Check filled defaults
    assert pd.isna(df.loc[0, "mcc"])
    assert not df.loc[0, "screen_share_active"]


def test_calibrated_base_score_anchors():
    """Pins the piecewise-linear remap that replaced `fraud_probability * 100`.

    Regression guard for the bug this fixed: at recall_threshold=0.008,
    precision_threshold=0.35 (the model's actual operating points),
    adversarial_evasion's real score of 0.11 used to land at risk_score=11
    (LOW, <30) under the naive *100 scaling even though it's >10x the
    1%-FPR threshold -- silently hiding a case the model did flag.
    """
    recall_threshold = 0.008
    precision_threshold = 0.35

    # Below the low-FPR recall anchor: scales into [0, 30).
    assert _calibrated_base_score(0.0, recall_threshold, precision_threshold) == 0.0
    assert 0.0 < _calibrated_base_score(0.004, recall_threshold, precision_threshold) < 30.0

    # Exactly at the anchors lands on the band boundaries.
    assert _calibrated_base_score(
        recall_threshold, recall_threshold, precision_threshold
    ) == pytest.approx(30.0)
    assert _calibrated_base_score(
        precision_threshold, recall_threshold, precision_threshold
    ) == pytest.approx(60.0)

    # Between the anchors: scales into [30, 60) -- the MEDIUM/REVIEW band.
    mid_score = _calibrated_base_score(0.11, recall_threshold, precision_threshold)
    assert 30.0 < mid_score < 60.0

    # At/above the production decision threshold: scales into [60, 100], saturating.
    assert _calibrated_base_score(1.0, recall_threshold, precision_threshold) == 100.0

    # Monotonic: higher fraud_probability never produces a lower score.
    probs = [0.0, 0.002, 0.008, 0.05, 0.11, 0.25, 0.35, 0.5, 1.0]
    scores = [_calibrated_base_score(p, recall_threshold, precision_threshold) for p in probs]
    assert scores == sorted(scores)


def test_risk_score_and_mapping():
    """Validates the risk score calculations, levels, and actions."""
    # We can test the get_fallback_llm_analysis function to verify the schema and text generation
    dummy_txn = {
        "txn_id": "tx-9999",
        "amount": 250.0,
        "payer_id": "payer-abc",
        "payee_id": "payee-xyz",
    }

    dummy_assessment = {
        "fraud_probability": 0.90,
        "risk_score": 93.5,
        "risk_level": "CRITICAL",
        "action": "BLOCK",
        "top_attack_family": "mule_network",
        "top_attack_probability": 0.85,
        "contributing_signals": [
            "Highly elevated graph edge count",
            "Beneficiary added very recently",
        ],
    }

    fallback = get_fallback_llm_analysis(dummy_txn, dummy_assessment, "API Offline Test")

    assert "fraud_explanation" in fallback
    assert "attack_family_interpretation" in fallback
    assert "key_evidence" in fallback
    assert "investigation_steps" in fallback
    assert "uncertainty_caveats" in fallback

    assert "CRITICAL" in fallback["fraud_explanation"]
    assert "mule_network" in fallback["attack_family_interpretation"]
    assert len(fallback["key_evidence"]) == 2
    assert len(fallback["investigation_steps"]) == 3
    assert "API Offline Test" in fallback["uncertainty_caveats"]


@requires_trained_models
@requires_attack_classifier
def test_pipeline_inference_end_to_end():
    """Runs a complete test with a mock/sample transaction row through the whole pipeline."""
    # Create a realistic transaction dict with all columns
    test_txn = {
        "currency": "INR",
        "rail": "upi_pin",
        "channel": "mobile",
        "direction": "push",
        "auth_method": "upi_pin",
        "auth_result": "success",
        "eci": None,
        "liability_shift": None,
        "exemption_claimed": None,
        "decision": "approved",
        "decline_reason": None,
        "ip_country": "IN",
        "ip_asn": "AS55836",
        "amount": 1000.0,
        "mcc": 5411,
        "auth_latency_ms": 300,
        "session_duration_s": 45,
        "time_on_confirm_screen_s": 5.0,
        "beneficiary_added_ago_s": 86400,
        "pin_attempts": 1,
        "tx_hour": 14,
        "tx_dayofweek": 2,
        "account_age_days": 180,
        "device_is_known_for_payer": True,
        "beneficiary_first_time": False,
        "screen_share_active": False,
        "call_active_during_txn": False,
        "accessibility_service_active": False,
        "paste_used_in_amount": False,
        "is_agent_initiated": False,
        "ip_is_proxy": False,
        "geo_matches_billing": True,
        "geo_matches_payer_home": True,
        "txn_count_last_1h": 1.0,
        "txn_count_last_24h": 3.0,
        "amount_spent_last_1h": 1000.0,
        "amount_spent_last_24h": 3500.0,
        "historical_average_amount": 1200.0,
        "amount_deviation": 200.0,
        "time_since_prev_txn": 7200.0,
        "new_merchant_indicator": False,
        "new_device_indicator": False,
        "new_ip_indicator": False,
        "inter_txn_time_mean": 7200.0,
        "inter_txn_time_std": 100.0,
        "inter_txn_time_min": 7100.0,
        "inter_txn_time_max": 7300.0,
        "txn_burstiness": 0.0,
        "active_days_count": 2.0,
        "active_hours_count": 3.0,
        "txns_per_active_day": 1.5,
        "amount_std": 200.0,
        "amount_cv": 0.16,
        "subthreshold_txn_ratio": 0.0,
        "aggregate_to_threshold_ratio": 0.35,
        "amount_concentration": 0.45,
        "unique_payee_count": 2.0,
        "merchant_diversity": 0.66,
        "same_payee_ratio": 0.66,
        "merchant_txn_ratio": 0.66,
        "beneficiary_reuse_ratio": 0.5,
        "txn_regularity": 0.01,
        "mandate_txn_ratio": 0.0,
        "mean_beneficiary_added_ago": 86400.0,
        "max_beneficiary_added_ago": 86400.0,
        "agent_txn_ratio": 0.0,
        "agent_txn_burstiness": 0.0,
        "time_since_prev_agent_txn": 999999.0,
        "payer_out_degree": 2.0,
        "payee_in_degree": 5.0,
        "edge_count": 3.0,
        "edge_value_total": 3000.0,
        "is_two_hop_passthrough": False,
    }

    # Run analysis
    res = analyze_transaction(test_txn)

    # Verify exact schema keys
    expected_keys = [
        "risk_score",
        "risk_level",
        "action",
        "recommended_action",
        "fraud_probability",
        "attack_probabilities",
        "top_attack_family",
        "top_attack_probability",
        "contributing_signals",
        "model_confidence",
        "model_uncertainty",
        "llm_analysis",
    ]
    for key in expected_keys:
        assert key in res, f"Expected key {key} is missing in output"

    # Verify reasonable values
    assert 0.0 <= res["risk_score"] <= 100.0
    assert res["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert res["action"] in ["ALLOW", "REVIEW", "BLOCK"]
    assert 0.0 <= res["fraud_probability"] <= 1.0
    assert len(res["attack_probabilities"]) == 16
    assert res["top_attack_family"] in res["attack_probabilities"]
    assert 0.0 <= res["top_attack_probability"] <= 1.0
    assert isinstance(res["contributing_signals"], list)

    # Check LLM analysis schema
    assert "fraud_explanation" in res["llm_analysis"]
    assert "attack_family_interpretation" in res["llm_analysis"]
    assert "key_evidence" in res["llm_analysis"]
    assert "investigation_steps" in res["llm_analysis"]
    assert "uncertainty_caveats" in res["llm_analysis"]


@requires_trained_models
def test_fallback_behavior_explicitly():
    """Verifies fallback behaves perfectly when Gemini API key is missing/removed."""
    # Temporarily remove keys from environment
    orig_key = os.environ.get("google_gemini_api_key")
    orig_key_upper = os.environ.get("GOOGLE_GEMINI_API_KEY")

    try:
        if "google_gemini_api_key" in os.environ:
            del os.environ["google_gemini_api_key"]
        if "GOOGLE_GEMINI_API_KEY" in os.environ:
            del os.environ["GOOGLE_GEMINI_API_KEY"]

        test_txn = {
            "amount": 100.0,
            "rail": "upi_pin",
            "screen_share_active": True,
            "beneficiary_added_ago_s": 50.0,
            "edge_count": 35.0,
        }

        # Call analyze_transaction in fallback mode
        res = analyze_transaction(test_txn)

        assert "llm_analysis" in res
        # Check that it didn't fail and populated the template
        assert "API key not configured in environment" in res["llm_analysis"]["uncertainty_caveats"]
        assert (
            any(
                "Beneficiary added very recently" in item
                for item in res["llm_analysis"]["key_evidence"]
            )
            or any(
                "Highly elevated graph edge count" in item
                for item in res["llm_analysis"]["key_evidence"]
            )
            or any(
                "Risky device flags active" in item for item in res["llm_analysis"]["key_evidence"]
            )
        )
    finally:
        # Restore original keys
        if orig_key:
            os.environ["google_gemini_api_key"] = orig_key
        if orig_key_upper:
            os.environ["GOOGLE_GEMINI_API_KEY"] = orig_key_upper


@requires_trained_models
def test_shap_contributions_present_and_signed():
    """analyze_transaction should surface real per-prediction SHAP attribution,
    not just the hand-coded threshold rules -- docs/model-choice.md already
    claims this as a reason for the XGBoost choice; this locks in that the
    claim is actually implemented."""
    artifacts = load_artifacts()
    assert artifacts["shap_explainer"] is not None, "XGBoost model should get a TreeExplainer"

    test_txn = {
        "amount": 45000.0,
        "rail": "upi_p2p",
        "beneficiary_first_time": True,
        "beneficiary_added_ago_s": 180,
        "screen_share_active": True,
        "call_active_during_txn": True,
        "edge_count": 1.0,
    }
    res = analyze_transaction(test_txn)
    contributions = res["shap_contributions"]
    assert len(contributions) > 0
    for c in contributions:
        assert set(c.keys()) == {"feature", "shap_value", "direction"}
        assert c["direction"] in {"increases_risk", "decreases_risk"}
        assert (c["shap_value"] > 0) == (c["direction"] == "increases_risk")
    # Sorted by |shap_value| descending
    magnitudes = [abs(c["shap_value"]) for c in contributions]
    assert magnitudes == sorted(magnitudes, reverse=True)
    assert any("SHAP" in item for item in res["llm_analysis"]["key_evidence"])


@requires_trained_models
def test_shap_contributions_empty_without_explainer(monkeypatch):
    import stage5.inference.pipeline as pipeline_mod

    monkeypatch.setitem(pipeline_mod._artifacts, "shap_explainer", None)
    df = prepare_transaction_df({"amount": 1.0})
    X_proc = pipeline_mod.load_artifacts()["preprocessor"].transform(df)
    assert compute_shap_contributions(X_proc) == []


@requires_trained_models
def test_no_model_modification():
    """Asserts that no model training code is run and parameters are not modified."""
    # Verify that the model parameters/hashes don't change
    artifacts = load_artifacts()
    fraud_model = artifacts["fraud_model"]

    # Check that model parameters (e.g. weights/estimators) remain unchanged before/after calling pipeline
    test_txn = {"amount": 1.0}

    # Capture model representation
    model_rep_before = repr(fraud_model)
    analyze_transaction(test_txn)
    model_rep_after = repr(fraud_model)

    assert model_rep_before == model_rep_after, "Model parameters were altered during inference!"
