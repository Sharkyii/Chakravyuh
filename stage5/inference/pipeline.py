import os
import sys
import json
import joblib
import urllib.request
import urllib.error
from pathlib import Path
import numpy as np
import pandas as pd
import shap

# Setup project root
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from stage5.config.settings import MODELS_DIR, ALL_FEATURES

DUMMY_KEYS = {
    "AQ.Ab8RN6Ida8we4qt5S64aCIwzkaJrsOb0bmB7HGcdrMdf9wVe8A",
    "AQ.Ab8RN6LMmERQfbtGJicIhBR6Z3owBauO48KcHDrRjlhjmb9-w",
    "AIzaSyYourActualKeyHere",
    "AIzaSyYour...yHere"
}

# Helper to load environmental variables manually (pattern from attacks framework)
def load_env_file() -> None:
    """Helper to parse a local .env file manually into os.environ."""
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
                        if key.lower() == "google_gemini_api_key":
                            # Always prioritize local .env file key
                            os.environ[key] = val
                            os.environ[key.upper()] = val
                        elif key not in os.environ:
                            os.environ[key] = val
                break
            except Exception:
                pass

# Global cache for artifacts and their on-disk mtimes
_artifacts = {}
_artifact_mtimes = {}

def load_artifacts():
    """Loads and caches models, preprocessors, and mappings from stage5/models/.

    Also tracks the mtime of each artifact file. If a file's mtime changes or a
    file is deleted, the cache is invalidated so stale models aren't served.
    Prevents silent ghost-model scenarios (e.g., a deleted pkl but cached copy still scoring).
    """
    global _artifacts, _artifact_mtimes

    preprocessor_path = MODELS_DIR / "preprocessor.pkl"
    fraud_model_path = MODELS_DIR / "fraud_model.pkl"
    attack_classifier_path = MODELS_DIR / "attack_classifier.pkl"
    mapping_path = MODELS_DIR / "attack_class_mapping.json"

    if not (preprocessor_path.exists() and fraud_model_path.exists()):
        raise FileNotFoundError("One or more Stage 5 model artifacts are missing in stage5/models/.")

    # attack_classifier/mapping are a secondary attack-family breakdown, not
    # the core fraud score -- treat them as optional so a missing/stale
    # classifier degrades the attack-family fields instead of taking down
    # fraud scoring entirely.
    has_attack_classifier = attack_classifier_path.exists() and mapping_path.exists()

    # Check if any artifact file has changed on disk (new mtime or missing from disk)
    current_mtimes = {
        "preprocessor": preprocessor_path.stat().st_mtime,
        "fraud_model": fraud_model_path.stat().st_mtime,
        "attack_classifier": attack_classifier_path.stat().st_mtime if has_attack_classifier else None,
        "mapping": mapping_path.stat().st_mtime if has_attack_classifier else None,
    }

    # Invalidate cache if any mtime changed — force reload
    if _artifact_mtimes != current_mtimes:
        _artifacts = {}
        _artifact_mtimes = {}

    if not _artifacts:

        preprocessor = joblib.load(preprocessor_path)
        fraud_model = joblib.load(fraud_model_path)

        attack_classifier = None
        idx_to_attack = {}
        attack_to_idx = {}
        if has_attack_classifier:
            attack_classifier = joblib.load(attack_classifier_path)
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            idx_to_attack = {int(k): v for k, v in mapping["idx_to_attack"].items()}
            attack_to_idx = {k: int(v) for k, v in mapping["attack_to_idx"].items()}

        # TreeExplainer needs no background dataset for tree models (unlike
        # KernelExplainer) and is fast enough to build once and cache -- this
        # is what actually delivers the "XGBoost has fast, mature SHAP
        # support" claim in docs/model-choice.md, rather than leaving it as
        # a documented-but-unimplemented reason for the model choice.
        shap_explainer = None
        try:
            if hasattr(fraud_model, "feature_importances_"):
                shap_explainer = shap.TreeExplainer(fraud_model)
        except Exception:
            shap_explainer = None  # non-tree best_model (e.g. Logistic Regression fallback)

        _artifacts = {
            "preprocessor": preprocessor,
            "fraud_model": fraud_model,
            "attack_classifier": attack_classifier,
            "idx_to_attack": idx_to_attack,
            "attack_to_idx": attack_to_idx,
            "shap_explainer": shap_explainer,
        }
        _artifact_mtimes = current_mtimes

    return _artifacts


def compute_shap_contributions(X_proc: np.ndarray, top_k: int = 6) -> list[dict]:
    """Real per-prediction feature attribution for one transaction's fraud
    score, not the hand-coded threshold rules below. Returns [] gracefully
    if no tree explainer is available (e.g. the saved model isn't a tree)."""
    artifacts = load_artifacts()
    explainer = artifacts["shap_explainer"]
    if explainer is None:
        return []

    try:
        raw_values = explainer.shap_values(X_proc)
        # Binary XGBClassifier: TreeExplainer returns a single (n, n_features)
        # array of log-odds contributions toward the positive (fraud) class.
        row = np.asarray(raw_values)[0] if np.asarray(raw_values).ndim == 2 else np.asarray(raw_values)
        feature_names = artifacts["preprocessor"].get_feature_names_out()
        pairs = list(zip(feature_names, row))
        pairs.sort(key=lambda p: abs(p[1]), reverse=True)
        return [
            {
                "feature": name.split("__", 1)[-1] if "__" in name else name,
                "shap_value": float(value),
                "direction": "increases_risk" if value > 0 else "decreases_risk",
            }
            for name, value in pairs[:top_k]
            if abs(value) > 1e-6
        ]
    except Exception:
        return []

def prepare_transaction_df(transaction: dict) -> pd.DataFrame:
    """Prepares a single-row DataFrame matching the 75 features expected by the preprocessor."""
    row_dict = {}
    for col in ALL_FEATURES:
        if col in transaction:
            row_dict[col] = transaction[col]
        else:
            # Handle defaults so SimpleImputer can work
            # Boolean features
            if col in [
                "device_is_known_for_payer", "beneficiary_first_time", "screen_share_active",
                "call_active_during_txn", "accessibility_service_active", "paste_used_in_amount",
                "is_agent_initiated", "ip_is_proxy", "geo_matches_billing", "geo_matches_payer_home"
            ]:
                row_dict[col] = False
            else:
                # Use np.nan for numerical and categorical so SimpleImputer imputes them correctly
                row_dict[col] = np.nan
                
    # Align pin_attempts UI representation:
    # If the auth method is a PIN-based rail (e.g. upi_pin) and pin_attempts is 0,
    # it represents "0 failed attempts", meaning the user entered the PIN once successfully.
    # Therefore, 0 failed attempts translates to 1 total attempt.
    if row_dict.get("auth_method") == "upi_pin" and row_dict.get("pin_attempts") == 0:
        row_dict["pin_attempts"] = 1

    return pd.DataFrame([row_dict], columns=ALL_FEATURES)

def get_fallback_llm_analysis(transaction: dict, risk_assessment: dict, error_msg: str = "") -> dict:
    """Generates a structured template analyst summary when the LLM API is unavailable."""
    fraud_prob = risk_assessment["fraud_probability"]
    risk_score = risk_assessment["risk_score"]
    risk_level = risk_assessment["risk_level"]
    top_attack = risk_assessment["top_attack_family"]
    top_prob = risk_assessment["top_attack_probability"]
    signals = risk_assessment["contributing_signals"]
    shap_contributions = risk_assessment.get("shap_contributions", [])

    explanation = (
        f"The transaction was assessed with a fraud probability of {fraud_prob*100:.1f}%, "
        f"resulting in a combined risk score of {risk_score:.1f}/100 and a risk level of {risk_level}."
    )
    if risk_level in ["HIGH", "CRITICAL"]:
        explanation += " The transaction triggers multiple anomaly thresholds and should be blocked."
    elif risk_level == "MEDIUM":
        explanation += " The transaction shows moderate risk indicators and requires review."
    else:
        explanation += " No significant risk was identified."
        
    if top_attack:
        interpretation = (
            f"The attack classifier predicted '{top_attack}' with a confidence of {top_prob*100:.1f}%. "
            f"This classification represents the closest matches among known fraud campaign patterns."
        )
    else:
        interpretation = (
            "Attack-family classification is unavailable for this prediction; "
            "the fraud score above is based on the primary detection model only."
        )
    
    key_evidence = list(signals) if signals else []
    for c in shap_contributions[:3]:
        verb = "raised" if c["shap_value"] > 0 else "lowered"
        key_evidence.append(f"{c['feature']} {verb} the model's fraud score ({c['shap_value']:+.3f} log-odds, SHAP)")
    if not key_evidence:
        key_evidence = ["Model prediction score"]

    investigation_steps = [
        "Review payer transaction history for velocity spikes.",
        "Verify if the device and IP location match the billing address.",
        "Check graph path to see if payee is associated with known mule accounts."
    ]
    
    caveat = "LLM API is currently unavailable. Using pre-computed rule-based template for analyst notes."
    if error_msg:
        caveat += f" (Reason: {error_msg})"
        
    return {
        "fraud_explanation": explanation,
        "attack_family_interpretation": interpretation,
        "key_evidence": key_evidence,
        "investigation_steps": investigation_steps,
        "uncertainty_caveats": caveat
    }

def call_gemini_api(prompt: str, api_key: str) -> dict:
    """Makes a structured JSON request to the Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "fraud_explanation": {"type": "STRING"},
            "attack_family_interpretation": {"type": "STRING"},
            "key_evidence": {
                "type": "ARRAY",
                "items": {"type": "STRING"}
            },
            "investigation_steps": {
                "type": "ARRAY",
                "items": {"type": "STRING"}
            },
            "uncertainty_caveats": {"type": "STRING"}
        },
        "required": [
            "fraud_explanation",
            "attack_family_interpretation",
            "key_evidence",
            "investigation_steps",
            "uncertainty_caveats"
        ]
    }
    
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
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=12) as response:
        resp_json = json.loads(response.read().decode("utf-8"))
        text_content = resp_json["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text_content)

def _ramp_up(value: float, low: float, high: float) -> float:
    """Continuous 0.0->1.0 severity ramp, linear between `low` and `high`.
    `low` must stay equal to the original step-function's activation
    threshold (the point below which the signal was, and still must be,
    exactly 0) -- otherwise inputs the original design judged benign start
    picking up phantom risk credit just for being non-zero, inflating
    false-positive pressure on legitimate low-risk traffic. Only the region
    at/above `low` is made continuous, replacing the old flat plateau
    between the two step thresholds."""
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def _ramp_down(value: float, full_risk_at: float, zero_at: float) -> float:
    """Inverse of _ramp_up, for signals where a *smaller* value is riskier
    (e.g. beneficiary age): 1.0 at/below `full_risk_at`, 0.0 at/above
    `zero_at` (which must match the original step function's cutoff),
    linear in between."""
    return 1.0 - _ramp_up(value, low=full_risk_at, high=zero_at)


def analyze_transaction(transaction: dict, api_key: str | None = None) -> dict:
    """Runs a transaction through the Stage 6 risk fusion & analyst pipeline."""
    # 1. Load pre-trained models
    artifacts = load_artifacts()
    preprocessor = artifacts["preprocessor"]
    fraud_model = artifacts["fraud_model"]
    attack_classifier = artifacts["attack_classifier"]
    idx_to_attack = artifacts["idx_to_attack"]
    
    # 2. Build feature DataFrame and preprocess
    df = prepare_transaction_df(transaction)
    X_proc = preprocessor.transform(df)
    
    # 3. Model Predictions
    fraud_probs = fraud_model.predict_proba(X_proc)[0]
    fraud_probability = float(fraud_probs[1])

    shap_contributions = compute_shap_contributions(X_proc)

    attack_probabilities = {}
    top_attack_family = None
    top_attack_probability = 0.0
    if attack_classifier is not None:
        attack_probs = attack_classifier.predict_proba(X_proc)[0]
        for idx, prob in enumerate(attack_probs):
            atk_name = idx_to_attack[idx]
            attack_probabilities[atk_name] = float(prob)

        best_idx = int(np.argmax(attack_probs))
        top_attack_family = idx_to_attack[best_idx]
        top_attack_probability = float(attack_probs[best_idx])
    
    # 4. Risk Fusion Engine
    base_score = fraud_probability * 100.0
    
    # Attack expected severity weighting
    attack_severity_map = {
        "adversarial_evasion": 0.80,
        "agentic_injection": 0.85,
        "card_testing_probe": 0.60,
        "credential_takeover": 0.95,
        "first_party_dispute": 0.40,
        "insider_abuse": 0.85,
        "mule_network": 1.00,
        "scam_induced_push": 0.90,
        "stealth_mandate": 0.70,
        "subthreshold_fragmentation": 0.75,
        "synthetic_identity_bustout": 1.00,
        "synthetic_merchant": 0.85,
        "transaction_laundering": 0.85,
    }
    
    expected_severity = sum(prob * attack_severity_map.get(name, 0.5) for name, prob in attack_probabilities.items())
    
    # Find contributing risk signals and compute a normalized behavioral/graph anomaly index
    contributing_signals = []
    device_risk_flag = 0.0
    ben_added_flag = 0.0
    edge_count_flag = 0.0
    dev_flag = 0.0
    pin_flag = 0.0
    proxy_flag = 0.0
    context_flag = 0.0
    amt_flag = 0.0
    
    # Screen sharing / Active calls / Accessibility
    screen_share = bool(transaction.get("screen_share_active", False))
    call_active = bool(transaction.get("call_active_during_txn", False))
    accessibility = bool(transaction.get("accessibility_service_active", False))
    if screen_share or call_active or accessibility:
        device_risk_flag = 1.0
        flags = []
        if screen_share: flags.append("screen sharing")
        if call_active: flags.append("active call")
        if accessibility: flags.append("accessibility service")
        contributing_signals.append(f"Risky device flags active: {', '.join(flags)}")
        
    # Beneficiary age (smaller age = higher risk). zero_at=3600 matches the
    # original step function's cutoff exactly -- ages >= 1h stay at 0 risk,
    # same as before; only the 300s-3600s band is now a ramp instead of a
    # flat 0.5 plateau.
    ben_age = transaction.get("beneficiary_added_ago_s")
    if ben_age is not None and pd.notna(ben_age):
        ben_age = float(ben_age)
        ben_added_flag = _ramp_down(ben_age, full_risk_at=300.0, zero_at=3600.0)
        if ben_age < 300:
            contributing_signals.append(f"Beneficiary added very recently ({ben_age:.1f}s ago)")
        elif ben_age < 3600:
            contributing_signals.append(f"Beneficiary added recently ({ben_age/60:.1f} minutes ago)")

    # Graph counts. low/high=10/30 match the original cutoffs exactly --
    # counts at or below 10 stay at 0 risk and at/above 30 stay at max
    # severity, same as before. Only the 10-30 band, which used to be a flat
    # 0.5 plateau, is now a continuous ramp.
    edge_count = transaction.get("edge_count")
    if edge_count is not None and pd.notna(edge_count):
        edge_count = float(edge_count)
        edge_count_flag = _ramp_up(edge_count, low=10.0, high=30.0)
        if edge_count > 30:
            contributing_signals.append(f"Highly elevated graph edge count ({edge_count})")
        elif edge_count > 10:
            contributing_signals.append(f"Moderately elevated graph edge count ({edge_count})")

    # Deviation from historical average. low/high=2.0/4.0 match the original
    # cutoffs exactly, same reasoning as edge_count above.
    amt_dev = transaction.get("amount_deviation")
    hist_avg = transaction.get("historical_average_amount")
    if amt_dev is not None and pd.notna(amt_dev) and hist_avg is not None and pd.notna(hist_avg) and float(hist_avg) > 0:
        ratio = float(amt_dev) / float(hist_avg)
        dev_flag = _ramp_up(ratio, low=2.0, high=4.0)
        if ratio > 4.0:
            contributing_signals.append(f"Significant transaction amount deviation ({ratio:.1f}x historical average)")
        elif ratio > 2.0:
            contributing_signals.append(f"Moderate transaction amount deviation ({ratio:.1f}x historical average)")

    # PIN attempts. low=1 matches the original cutoff (0 or 1 attempts stay at
    # 0 risk); high=5 is the Studio's slider max, not an original step
    # threshold -- unlike the other flags, pin_attempts is an integer with no
    # continuous values to smooth between the old anchors (1 and >2 was
    # already just two adjacent integers), so the real bug (3, 4, 5 attempts
    # all flatlining at 1.0) is fixed by ramping across the full 2-5 range.
    pin_attempts = transaction.get("pin_attempts")
    if pin_attempts is not None and pd.notna(pin_attempts):
        pin_attempts = int(pin_attempts)
        pin_flag = _ramp_up(float(pin_attempts), low=1.0, high=5.0)
        if pin_attempts > 2:
            contributing_signals.append(f"Multiple failed PIN attempts ({pin_attempts})")
        elif pin_attempts > 1:
            contributing_signals.append(f"Elevated PIN attempts ({pin_attempts})")
            
    # IP is proxy
    if bool(transaction.get("ip_is_proxy", False)):
        proxy_flag = 1.0
        contributing_signals.append("Transaction routed through a proxy IP")
        
    # New device or new IP
    new_device = bool(transaction.get("new_device_indicator", False))
    new_ip = bool(transaction.get("new_ip_indicator", False))
    if new_device or new_ip:
        context_flag = 0.5
        contexts = []
        if new_device: contexts.append("new device")
        if new_ip: contexts.append("new IP")
        contributing_signals.append(f"Transaction from new context: {', '.join(contexts)}")
        
    # High transaction amount check. low/high=25000/100000 match the original
    # cutoffs exactly, same reasoning as edge_count above.
    amount_val = transaction.get("amount", 0.0)
    if amount_val is not None and pd.notna(amount_val):
        amount_val = float(amount_val)
        amt_flag = _ramp_up(amount_val, low=25000.0, high=100000.0)
        if amount_val > 100000.0:
            contributing_signals.append(f"High transaction amount (₹{amount_val:,.2f})")
        elif amount_val > 25000.0:
            contributing_signals.append(f"Moderately high transaction amount (₹{amount_val:,.2f})")
            
    # Anomaly Index calculation
    # Industry-grade hybrid risk fusion formula:
    # We combine the ML base score and behavioral/graph anomaly scores.
    # Anomaly weights reflect threat severity (e.g. screen sharing/PIN bypass are high-risk indicators).
    behavioral_score = (
        (device_risk_flag * 30.0) +
        (pin_flag * 25.0) +
        (amt_flag * 25.0) +
        (dev_flag * 20.0) +
        (ben_added_flag * 20.0) +
        (edge_count_flag * 15.0) +
        (proxy_flag * 15.0) +
        (context_flag * 15.0)
    )
    
    # Attack classifier adjustment (independent of fraud_probability to preserve signals)
    attack_adjustment = expected_severity * 10.0
    
    # Combine scores. If there are critical behavioral anomalies (e.g. screen share + failed PINs),
    # they can independently drive the risk score even if the ML model is bypassed.
    risk_score_raw = max(base_score, behavioral_score) + attack_adjustment
    
    # Critical Policy Overrides (safety net for key attack/takeover signatures)
    pin_attempts_val = transaction.get("pin_attempts")
    if pin_attempts_val is not None and pd.notna(pin_attempts_val):
        pin_attempts_val = int(pin_attempts_val)
        # 1. PIN brute-forcing on high-value transfer (Takeover signature)
        if pin_attempts_val >= 3 and amount_val > 10000.0:
            severity = max(_ramp_up(float(pin_attempts_val), low=3.0, high=5.0),
                            _ramp_up(amount_val, low=10000.0, high=100000.0))
            risk_score_raw = max(risk_score_raw, 85.0 + 10.0 * severity)
            if "Multiple PIN failures on high-value transaction" not in contributing_signals:
                contributing_signals.append("Multiple PIN failures on high-value transaction")
                
    # 2. Coerced push scam signature (active device sharing + active call + high amount)
    if device_risk_flag == 1.0 and amount_val > 25000.0:
        risk_score_raw = max(risk_score_raw, 90.0 + 8.0 * _ramp_up(amount_val, low=25000.0, high=100000.0))
        if "Active device sharing/call on high-value transaction" not in contributing_signals:
            contributing_signals.append("Active device sharing/call on high-value transaction")
            
    risk_score = min(100.0, max(0.0, risk_score_raw))
    
    # Map to outputs
    if risk_score >= 80.0:
        risk_level = "CRITICAL"
        action = "BLOCK"
    elif risk_score >= 60.0:
        risk_level = "HIGH"
        action = "BLOCK"
    elif risk_score >= 30.0:
        risk_level = "MEDIUM"
        action = "REVIEW"
    else:
        risk_level = "LOW"
        action = "ALLOW"
        
    # Model confidence & uncertainty (derived from probability margins)
    fraud_uncertainty = 1.0 - abs(fraud_probability - 0.5) * 2.0
    fraud_confidence = 1.0 - fraud_uncertainty
    
    if fraud_probability >= 0.5:
        overall_confidence = fraud_confidence * 0.7 + top_attack_probability * 0.3
    else:
        overall_confidence = fraud_confidence
        
    overall_uncertainty = 1.0 - overall_confidence
    
    risk_assessment = {
        "risk_score": float(risk_score),
        "risk_level": risk_level,
        "action": action,
        "recommended_action": action,
        "fraud_probability": float(fraud_probability),
        "attack_probabilities": attack_probabilities,
        "top_attack_family": top_attack_family,
        "top_attack_probability": float(top_attack_probability),
        "contributing_signals": contributing_signals,
        "shap_contributions": shap_contributions,
        "model_confidence": float(overall_confidence),
        "model_uncertainty": float(overall_uncertainty),
    }
    
    # 5. LLM Analyst Intelligence Layer
    if api_key is None:
        load_env_file()
        api_key = os.environ.get("google_gemini_api_key") or os.environ.get("GOOGLE_GEMINI_API_KEY")
    
    if api_key in DUMMY_KEYS or (api_key and "your" in api_key.lower()):
        api_key = None
    
    llm_analysis = None
    if api_key:
        # Build prompt
        context_lines = [
            f"Transaction ID: {transaction.get('txn_id', 'unknown')}",
            f"Amount: {transaction.get('amount', 'unknown')} {transaction.get('currency', 'INR')}",
            f"Payer ID: {transaction.get('payer_id', 'unknown')}",
            f"Payee ID: {transaction.get('payee_id', 'unknown')}",
            f"Rail: {transaction.get('rail', 'unknown')}",
            f"Channel: {transaction.get('channel', 'unknown')}",
            f"Auth Method: {transaction.get('auth_method', 'unknown')}",
            f"MCC: {transaction.get('mcc', 'unknown')}",
        ]
        
        evidence_lines = [
            f"Fraud Probability: {fraud_probability*100:.2f}%",
            f"Predicted Attack Family: {top_attack_family or 'unavailable'} (Classifier Confidence: {top_attack_probability*100:.2f}%)",
            f"Calculated Risk Score: {risk_score:.1f}/100",
            f"Recommended Action: {action}",
            f"Risk Level: {risk_level}",
            "Active Risk Signals:",
        ]
        for signal in contributing_signals:
            evidence_lines.append(f"  - {signal}")
        if not contributing_signals:
            evidence_lines.append("  - None")

        if shap_contributions:
            evidence_lines.append("Top model feature attributions (SHAP, signed log-odds contribution to fraud score):")
            for c in shap_contributions:
                arrow = "+" if c["shap_value"] > 0 else ""
                evidence_lines.append(f"  - {c['feature']}: {arrow}{c['shap_value']:.3f} ({c['direction'].replace('_', ' ')})")


        prompt = (
            "You are Chakravyuh GenAI Analyst, a specialized AI assistant for Mastercard instant payment fraud detection.\n"
            "Analyze the following transaction context and ML-derived evidence to generate a structured risk explanation. "
            "Do NOT invent any facts or override the model's predictions. Your goal is to interpret the model's findings "
            "for a human analyst.\n\n"
            "### TRANSACTION CONTEXT\n"
            + "\n".join(context_lines) + "\n\n"
            "### MACHINE LEARNING EVIDENCE\n"
            + "\n".join(evidence_lines) + "\n\n"
            "Please output a JSON object containing the following keys:\n"
            "1. 'fraud_explanation': a concise paragraph explaining why this transaction was flagged (or cleared), summarizing the risk.\n"
            "2. 'attack_family_interpretation': a detailed interpretation of the predicted attack family (e.g. how the signals align with that type of fraud).\n"
            "3. 'key_evidence': a list of the 2-4 most critical data points supporting this assessment.\n"
            "4. 'investigation_steps': a list of 3-4 actionable next steps for a human fraud analyst to verify this incident.\n"
            "5. 'uncertainty_caveats': any limitations, model confidence warnings, or potential false-positive/negative scenarios.\n\n"
            "Ensure the output is valid JSON matching the schema and contains no markdown block wrapper."
        )
        
        try:
            llm_analysis = call_gemini_api(prompt, api_key)
        except Exception as e:
            # Graceful fallback on API error/timeout
            llm_analysis = get_fallback_llm_analysis(transaction, risk_assessment, str(e))
    else:
        # Fallback when API key is missing
        llm_analysis = get_fallback_llm_analysis(transaction, risk_assessment, "API key not configured in environment")
        
    risk_assessment["llm_analysis"] = llm_analysis
    return risk_assessment
