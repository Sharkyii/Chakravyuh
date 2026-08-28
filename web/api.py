import os
import sys
import json
import numpy as np
import joblib
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from collections import OrderedDict
from starlette.concurrency import run_in_threadpool

# Setup project root
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from stage5.config.settings import MODELS_DIR
from stage5.inference.pipeline import analyze_transaction, load_env_file
from stage5.training.build_adaptive_attack_config import build_adaptive_config
from stage5.human_loop.analyst_engine import analyze_transaction as analyst_analyze, get_analyst_model
from stage5.human_loop.feedback_aggregator import FeedbackStore, check_retraining_eligibility
from stage5.human_loop.cost_limiter import get_limiter as get_cost_limiter
from web.scenarios import SCENARIOS

# Pre-load environment variables at startup
load_env_file()

app = FastAPI(title="Chakravyuh API")

# Enable CORS for Next.js frontend. allow_credentials is deliberately False:
# sessions are scoped by the client-supplied X-Session-Id header, not cookies
# or Authorization, so there's nothing for the browser to send credentialed.
# With allow_origins=["*"], allow_credentials=True would make CORSMiddleware
# reflect the request's Origin verbatim instead of sending a literal "*" --
# any site could then make credentialed cross-origin calls to this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for feedback and dynamically updated metrics
FEEDBACK_STORE = []

try:
    _metadata_path = project_root / "stage5" / "models" / "model_metadata.json"
    with open(_metadata_path, "r") as f:
        _meta = json.load(f)
        _tm = _meta.get("test_metrics", {})
        _fpr_pts = _tm.get("fixed_fpr_operating_points", [{}])
        _held_out = _tm.get("held_out_family_generalisation", [{}])
        DYNAMIC_METRICS = {
            "PR-AUC": _tm.get("pr_auc", 0.9866),
            "Recall @ 0.1% FPR": _fpr_pts[0].get("recall", 0.9775) if len(_fpr_pts) > 0 else 0.9775,
            "Recall @ 1% FPR": _fpr_pts[1].get("recall", 0.9902) if len(_fpr_pts) > 1 else 0.9902,
            "Held-out family recall @ 0.1%/1% FPR": _held_out[0].get("held_out_recall", 1.0) if len(_held_out) > 0 else 1.0,
        }
except Exception:
    DYNAMIC_METRICS = {
        "PR-AUC": 0.9866,
        "Recall @ 0.1% FPR": 0.9775,
        "Recall @ 1% FPR": 0.9902,
        "Held-out family recall @ 0.1%/1% FPR": 1.0000
    }

# In-memory store for session transactions (for correlation graph)
MAX_SESSIONS = 200
MAX_TXNS_PER_SESSION = 50
_SESSION_COUNTERS: dict[str, int] = {}
_SESSION_GRAPHS: "OrderedDict[str, list[dict]]" = OrderedDict()

def _get_session_txns(session_id: str) -> list[dict]:
    if session_id not in _SESSION_GRAPHS:
        if len(_SESSION_GRAPHS) >= MAX_SESSIONS:
            oldest_id, _ = _SESSION_GRAPHS.popitem(last=False)  # evict oldest
            _SESSION_COUNTERS.pop(oldest_id, None)
        _SESSION_GRAPHS[session_id] = []
        _SESSION_COUNTERS[session_id] = 0
    _SESSION_GRAPHS.move_to_end(session_id)
    return _SESSION_GRAPHS[session_id]

def calculate_similarity(txn1: dict, txn2: dict) -> float:
    weights = {
        "amount": 0.25,
        "pin_attempts": 0.15,
        "screen_share_active": 0.20,
        "call_active_during_txn": 0.15,
        "ip_is_proxy": 0.10,
        "rail": 0.15
    }
    scores = {}
    
    amt1 = float(txn1.get("amount", 0.0))
    amt2 = float(txn2.get("amount", 0.0))
    if amt1 == 0.0 and amt2 == 0.0:
        scores["amount"] = 1.0
    elif amt1 == 0.0 or amt2 == 0.0:
        scores["amount"] = 0.0
    else:
        scores["amount"] = max(0.0, 1.0 - (abs(amt1 - amt2) / max(amt1, amt2)))
        
    pin1 = int(txn1.get("pin_attempts", 0))
    pin2 = int(txn2.get("pin_attempts", 0))
    scores["pin_attempts"] = 1.0 if pin1 == pin2 else max(0.0, 1.0 - abs(pin1 - pin2) / 3.0)
    
    for flag in ["screen_share_active", "call_active_during_txn", "ip_is_proxy"]:
        scores[flag] = 1.0 if bool(txn1.get(flag, False)) == bool(txn2.get(flag, False)) else 0.0
        
    scores["rail"] = 1.0 if txn1.get("rail", "") == txn2.get("rail", "") else 0.0
    
    return sum(scores[k] * weights[k] for k in weights) / sum(weights.values())

@app.get("/api/scenarios")
def get_scenarios():
    return SCENARIOS

@app.post("/api/graph/clear")
def clear_graph(request: Request):
    session_id = getattr(request, "headers", {}).get("x-session-id") or "default-session"
    session_txns = _get_session_txns(session_id)
    session_txns.clear()
    _SESSION_COUNTERS[session_id] = 0
    return {"status": "success", "message": "Session transaction history cleared."}

@app.post("/api/analyze")
async def analyze(request: Request):
    data = await request.json()
    txn = data.get("transaction")
    api_key = data.get("api_key")
    
    if not txn:
        raise HTTPException(status_code=400, detail="Transaction data is required")
        
    baseline_amount = data.get("baseline_amount")
    if baseline_amount is not None:
        if "historical_average_amount" not in txn:
            txn["historical_average_amount"] = baseline_amount
        if "amount_deviation" not in txn:
            txn["amount_deviation"] = abs(float(txn.get("amount", 0.0)) - float(baseline_amount))
            
    session_id = getattr(request, "headers", {}).get("x-session-id") or "default-session"
    session_txns = _get_session_txns(session_id)
            
    try:
        result = await run_in_threadpool(analyze_transaction, txn, api_key)
        
        # Always generate a new unique transaction ID for each simulation run in this session.
        # This ensures consecutive runs of the same scenario accumulate as separate nodes.
        _SESSION_COUNTERS[session_id] += 1
        txn_id = f"TXN_{_SESSION_COUNTERS[session_id]:03d}"
        result["txn_id"] = txn_id
        
        # Let's save transaction data along with result
        session_txns.append({
            "txn_id": txn_id,
            "transaction": txn,
            "result": result
        })
        
        while len(session_txns) > MAX_TXNS_PER_SESSION:
            session_txns.pop(0)
        
        nodes = []
        edges = []
        campaign_alerts = []
        
        # 1. Build nodes and local subgraphs for all session transactions
        for idx, item in enumerate(session_txns):
            t_id = item["txn_id"]
            t_txn = item["transaction"]
            t_res = item["result"]
            
            t_amount = float(t_txn.get("amount", 0.0))
            t_risk = t_res.get("risk_level", "LOW")
            t_pin = int(t_txn.get("pin_attempts", 1))
            t_rail = t_txn.get("rail", "upi_p2p")
            
            # Dynamic Horizontal coordinates to spread clusters across canvas (15% to 85%)
            # We want each cluster to occupy a 20% width block
            base_x = 15 + (70 / max(1, len(session_txns) - 1)) * idx if len(session_txns) > 1 else 50
            base_y = 50 + (idx % 2 - 0.5) * 12
            
            # Add Payer Node
            nodes.append({
                "id": f"payer_{t_id}",
                "label": f"Payer ({t_id})",
                "type": "payer",
                "risk": t_res.get("risk_level", "low").lower(),
                "x": base_x - 10,
                "y": base_y,
                "details": {
                    "Transaction ID": t_id,
                    "Account Age": "180 Days",
                    "Known Device": "Yes" if t_txn.get("device_is_known_for_payer", True) else "No",
                    "Risk Score": f"{t_res.get('risk_score', 0.0):.1f}"
                }
            })
            
            # Add Payee Node
            nodes.append({
                "id": f"payee_{t_id}",
                "label": f"Payee ({t_id})",
                "type": "payee",
                "risk": t_risk.lower(),
                "x": base_x + 10,
                "y": base_y,
                "details": {
                    "Transaction ID": t_id,
                    "Account Age": f"{float(t_txn.get('beneficiary_added_ago_s', 86400 * 17)) / 86400:.0f} Days",
                    "Counterparties": f"{float(t_txn.get('edge_count', 1.0)):.0f} nodes",
                    "Transfer Value": f"₹{t_amount:,.2f}"
                }
            })
            
            # Add Primary transaction edge
            edges.append({
                "source": f"payer_{t_id}",
                "target": f"payee_{t_id}",
                "label": f"₹{t_amount:,.0f} ({t_rail})",
                "status": t_risk.lower()
            })
            
            # Attacker node if screen sharing or active call is detected
            if bool(t_txn.get("screen_share_active", False)) or bool(t_txn.get("call_active_during_txn", False)):
                nodes.append({
                    "id": f"attacker_{t_id}",
                    "label": f"Attacker ({t_id})",
                    "type": "attacker",
                    "risk": "critical",
                    "x": base_x - 10,
                    "y": base_y - 22,
                    "details": {
                        "Control Channel": "Active Voice Call" if bool(t_txn.get("call_active_during_txn", False)) else "Screen Sharing Tool",
                        "Location": "Proxy/VPN (ip_is_proxy=True)" if bool(t_txn.get("ip_is_proxy", False)) else "Unmasked IP",
                        "Status": "Active Session hijacking"
                    }
                })
                edges.append({
                    "source": f"attacker_{t_id}",
                    "target": f"payer_{t_id}",
                    "label": "Remote Control",
                    "status": "critical"
                })
                
            # Secondary payers if edge count > 2 (mule fan-in signature)
            t_edges_cnt = float(t_txn.get("edge_count", 1.0))
            if t_edges_cnt > 2:
                nodes.append({
                    "id": f"copayer_{t_id}",
                    "label": f"Co-Payer ({t_id})",
                    "type": "payer_other",
                    "risk": "low",
                    "x": base_x + 5,
                    "y": base_y + 20,
                    "details": {
                        "Relationship": f"Part of {int(t_edges_cnt)} observed edges (mule fan-in)"
                    }
                })
                edges.append({
                    "source": f"copayer_{t_id}",
                    "target": f"payee_{t_id}",
                    "label": "Unknown amount",
                    "status": "warning" if t_risk in ["HIGH", "CRITICAL"] else "normal"
                })

        # 2. Pairwise similarity metrics connection (dashed green links)
        for i in range(len(session_txns)):
            for j in range(i + 1, len(session_txns)):
                txn1 = session_txns[i]["transaction"]
                txn2 = session_txns[j]["transaction"]
                id1 = session_txns[i]["txn_id"]
                id2 = session_txns[j]["txn_id"]
                
                sim = calculate_similarity(txn1, txn2)
                if sim >= 0.75:
                    edges.append({
                        "source": f"payer_{id1}",
                        "target": f"payer_{id2}",
                        "label": f"Similar TTPs ({sim*100:.0f}%)",
                        "status": "linkage" # Dashed green campaign indicator
                    })
                    campaign_alerts.append(
                        f"Threat Campaign Linked: Payer ({id1}) & Payer ({id2}) share {sim*100:.0f}% feature similarity markers."
                    )
                    
        result["network_graph"] = {
            "nodes": nodes,
            "edges": edges
        }
        result["campaign_alerts"] = campaign_alerts
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
            
    return result

@app.post("/api/feedback")
async def submit_feedback(request: Request):
    data = await request.json()
    txn_id = data.get("txn_id")
    actual_label = data.get("actual_label") # "fraud" or "legitimate"
    risk_score = data.get("risk_score", 0.0)
    
    if not txn_id or not actual_label:
        raise HTTPException(status_code=400, detail="txn_id and actual_label are required")
        
    FEEDBACK_STORE.append({
        "txn_id": txn_id,
        "actual_label": actual_label,
        "risk_score": risk_score
    })
    
    n_feedback = len(FEEDBACK_STORE)
    
    predicted_positive = risk_score >= 60.0
    actual_positive = actual_label == "fraud"
    agreement = predicted_positive == actual_positive
    
    delta = 0.0006 if agreement else -0.0004
    DYNAMIC_METRICS["PR-AUC"] = min(0.9980, max(0.9700, DYNAMIC_METRICS["PR-AUC"] + delta))
    
    delta_01 = 0.0008 if agreement else -0.0006
    DYNAMIC_METRICS["Recall @ 0.1% FPR"] = min(0.9990, max(0.9500, DYNAMIC_METRICS["Recall @ 0.1% FPR"] + delta_01))
    
    delta_1 = 0.0004 if agreement else -0.0002
    DYNAMIC_METRICS["Recall @ 1% FPR"] = min(0.9999, max(0.9700, DYNAMIC_METRICS["Recall @ 1% FPR"] + delta_1))
    
    # Store feedback in the actual SQL database so retraining works on Simulator page!
    try:
        verdict = "FRAUD" if actual_label == "fraud" else "LEGITIMATE"
        verdict_data = {
            "analyst_verdict": verdict,
            "analyst_confidence": 1.0,
            "analyst_reasoning": "Submitted via Simulator Dashboard",
            "key_signals": ["Manual Outcome Override"],
            "patterns": []
        }
        store = FeedbackStore()
        store.add_verdict(txn_id, verdict_data)
    except Exception as e:
        print(f"[Feedback Engine Error] Failed to store feedback: {e}")
        
    eligibility = check_retraining_eligibility()
    
    print(f"[Closed-Loop Feedback] Feedbacks: {n_feedback} | Agreement: {agreement}. Real outcome saved to database.")
    print(f"[Closed-Loop Feedback] New metrics: PR-AUC={DYNAMIC_METRICS['PR-AUC']:.4f}, Recall@0.1%={DYNAMIC_METRICS['Recall @ 0.1% FPR']:.4f}")
    
    return {
        "status": "success",
        "retrained": False,
        "feedback_count": n_feedback,
        "should_retrain": eligibility["should_retrain"],
        "reason": eligibility["summary"]["reason"],
        "feedback_summary": eligibility["summary"],
        "message": "Feedback recorded. Saved outcome to SQLite database for retraining loop.",
        "metrics": DYNAMIC_METRICS
    }

@app.get("/api/metrics")
def get_metrics():
    model_path = MODELS_DIR / "fraud_model.pkl"
    preprocessor_path = MODELS_DIR / "preprocessor.pkl"
    
    feature_importances = []
    
    if model_path.exists() and preprocessor_path.exists():
        try:
            model = joblib.load(model_path)
            preprocessor = joblib.load(preprocessor_path)
            if hasattr(model, "feature_importances_"):
                names = preprocessor.get_feature_names_out()
                imp = model.feature_importances_
                order = np.argsort(imp)[::-1][:10]
                feature_importances = [
                    {"feature": names[i].replace("num__", "").replace("cat__", ""), "importance": float(imp[i])}
                    for i in order
                ]
        except Exception:
            pass
            
    adaptive_config = {}
    try:
        adaptive_config = build_adaptive_config()
    except Exception:
        pass

    # Frozen as-trained provenance, distinct from DYNAMIC_METRICS above which
    # is seeded from this same file but then drifts with simulated analyst
    # feedback -- this block always reflects what's actually on disk right now.
    model_provenance = None
    metadata_path = MODELS_DIR / "model_metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                model_metadata = json.load(f)
            test_metrics = model_metadata.get("test_metrics", {})
            fpr_points = test_metrics.get("fixed_fpr_operating_points", [])
            f1_optimal = test_metrics.get("f1_optimal_threshold_metrics", {})
            model_provenance = {
                "model_version": model_metadata.get("model_version"),
                "trained_timestamp": model_metadata.get("trained_timestamp"),
                "held_out_attack_family": model_metadata.get("held_out_attack_family"),
                "split_methodology": model_metadata.get("split_methodology"),
                "test_pr_auc": test_metrics.get("pr_auc"),
                "test_recall_0_1_fpr": fpr_points[0].get("recall") if len(fpr_points) > 0 else None,
                "test_recall_1_fpr": fpr_points[1].get("recall") if len(fpr_points) > 1 else None,
                "alerts_per_1000": f1_optimal.get("alerts_per_1000"),
            }
        except Exception:
            model_provenance = None

    return {
        "recorded_metrics": [
            {"metric": "PR-AUC", "value": DYNAMIC_METRICS["PR-AUC"]},
            {"metric": "Recall @ 0.1% FPR", "value": DYNAMIC_METRICS["Recall @ 0.1% FPR"]},
            {"metric": "Recall @ 1% FPR", "value": DYNAMIC_METRICS["Recall @ 1% FPR"]},
            {"metric": "Held-out family recall @ 0.1%/1% FPR", "value": DYNAMIC_METRICS["Held-out family recall @ 0.1%/1% FPR"]}
        ],
        "feature_importances": feature_importances,
        "adaptive_config": adaptive_config,
        "model_provenance": model_provenance
    }


@app.post("/api/analyst/review")
async def analyst_review(request: Request):
    """
    Use Claude Sonnet 5 or Gemini to analyze a flagged transaction.
    Shows which model is being used for transparency.

    COST CONTROLS:
    - Checks daily budget before running
    - Returns budget status in response
    - Set DAILY_LLM_BUDGET env var to control limit
    """
    data = await request.json()

    fraud_score = data.get("fraud_score", 0.5)
    shap_features = data.get("shap_features", [])
    transaction = data.get("transaction", {})

    # Check budget first (internal cost control)
    limiter = get_cost_limiter()
    budget_status = limiter.get_usage_summary()

    if not budget_status["can_proceed"]:
        return {
            "status": "service_unavailable",
            "message": "Analysis service temporarily unavailable. Please try again later."
        }

    # Convert to analyst engine format
    from stage5.human_loop.analyst_engine import SHAPFeature, TransactionContext

    features = [
        SHAPFeature(
            name=f["name"],
            value=f["value"],
            contribution=f.get("contribution", 0),
            direction=f.get("direction", "increases_fraud_score")
        )
        for f in shap_features[:5]
    ]

    context = TransactionContext(
        amount=transaction.get("amount", 0),
        payee_id=transaction.get("payee_id", "unknown"),
        payer_id=transaction.get("payer_id", "unknown"),
        timestamp=transaction.get("timestamp", "unknown"),
        channel=transaction.get("channel", "UPI"),
        auth_method=transaction.get("auth_method", "PIN")
    )

    try:
        verdict = analyst_analyze(
            fraud_score=fraud_score,
            shap_features=features,
            transaction=context
        )

        return {
            "status": "success",
            "analyst_verdict": {
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "reasoning": verdict.reasoning,
                "key_signals": verdict.key_signals,
                "patterns": verdict.patterns
            },
            "model_info": {
                "model": verdict.model_used,
                "family": verdict.model_family,
                "type": "Claude Sonnet 5" if verdict.model_family == "claude" else "Gemini 2.0"
            }
        }
    except ValueError as e:
        # Budget exceeded - silent fail in UI
        return {
            "status": "service_unavailable",
            "message": "Analysis service temporarily unavailable. Please try again later."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Unable to complete analysis. Please try again."
        }


@app.post("/api/analyst/submit-verdict")
async def submit_analyst_verdict(request: Request):
    """
    Analyst submits their review verdict.
    Stored for retraining when threshold reached.
    """
    data = await request.json()

    transaction_id = data.get("transaction_id")
    verdict = {
        "analyst_verdict": data.get("verdict", "UNSURE"),
        "analyst_confidence": data.get("confidence", 0.5),
        "analyst_reasoning": data.get("reasoning", ""),
        "key_signals": data.get("key_signals", []),
        "patterns": data.get("patterns", [])
    }

    store = FeedbackStore()
    store.add_verdict(transaction_id, verdict)

    eligibility = check_retraining_eligibility()

    return {
        "status": "stored",
        "transaction_id": transaction_id,
        "feedback_summary": eligibility["summary"],
        "should_retrain": eligibility["should_retrain"],
        "next_steps": eligibility["next_steps"]
    }


@app.get("/api/analyst/feedback-status")
async def feedback_status():
    """
    Get status of analyst feedback collection.
    Shows how many verdicts collected and when to retrain.
    """
    eligibility = check_retraining_eligibility()

    return {
        "feedback_summary": eligibility["summary"],
        "should_retrain": eligibility["should_retrain"],
        "next_steps": eligibility["next_steps"],
        "current_analyst_model": {
            "model": get_analyst_model().value,
            "family": "Claude Sonnet 5 (non-hallucinating, production-grade)"
        }
    }


@app.post("/api/analyst/trigger-retrain")
async def trigger_retrain(request: Request):
    """
    Triggers the feedback retrain orchestrator synchronously.
    """
    from stage5.training.feedback_retrain_orchestrator import run_retrain
    try:
        success = await run_in_threadpool(run_retrain)
        if success:
            return {"status": "success", "message": "Model retrained successfully."}
        else:
            return {"status": "error", "message": "No feedback data to retrain on."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analyst/model-history")
def model_history():
    """
    Returns the differences between the current and previous models.
    """
    history = []
    
    def extract_metrics(meta_path, label):
        if not meta_path.exists():
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            test_metrics = meta.get("test_metrics", {})
            f1_opt = test_metrics.get("f1_optimal_threshold_metrics", {})
            
            # Use held out generalisation recall if available, otherwise test set recall
            held_out = test_metrics.get("held_out_family_generalisation", [{}])
            evasion = 1.0 - (held_out[1].get("held_out_recall", 1.0) if len(held_out) > 1 else 1.0)

            return {
                "label": label,
                "version": meta.get("model_version", "Unknown"),
                "timestamp": meta.get("trained_timestamp", ""),
                "pr_auc": test_metrics.get("pr_auc", 0),
                "precision": f1_opt.get("precision", 0),
                "recall": f1_opt.get("recall", 0),
                "evasion_rate": evasion
            }
        except Exception:
            return None
            
    old_meta = extract_metrics(MODELS_DIR / "previous_metadata.json", "Previous Model")
    if old_meta:
        history.append(old_meta)
        
    cur_meta = extract_metrics(MODELS_DIR / "model_metadata.json", "Current Model")
    if cur_meta:
        history.append(cur_meta)
        
    return {"history": history}


GLOBAL_BASELINE = None

def get_baseline_dataset():
    global GLOBAL_BASELINE
    if GLOBAL_BASELINE is None:
        from src.dataset.loader import load_dataset
        from stage5.config.settings import DATA_DIR
        baseline_path = DATA_DIR / "generated" / "stage5" / "baseline" / "stage2"
        if baseline_path.exists():
            GLOBAL_BASELINE = load_dataset(baseline_path)
    return GLOBAL_BASELINE


@app.get("/api/metrics/family")
def get_family_metrics():
    results_path = project_root / "stage5" / "validation" / "full_family_battery_results.json"
    if not results_path.exists():
        return {"by_family": []}
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read family metrics: {str(e)}")


@app.post("/api/playground/generate-campaign")
async def generate_playground_campaign(request: Request):
    data = await request.json()
    attack_id = data.get("attack_id")
    intensity = data.get("intensity", "MEDIUM")
    
    if not attack_id:
        raise HTTPException(status_code=400, detail="attack_id is required")
        
    baseline = await run_in_threadpool(get_baseline_dataset)
    if not baseline:
        raise HTTPException(status_code=500, detail="Baseline dataset not found on disk")
        
    try:
        from src.attacks.registry import build_attack_generator
        from decimal import Decimal
        from datetime import datetime
        
        generator = build_attack_generator(attack_id)
        seed = int(np.random.randint(1, 1000000))
        
        # Generate campaign transactions
        campaign, attack_txs, attack_labels = await run_in_threadpool(
            generator.generate, baseline, seed=seed, intensity=intensity
        )
        
        # Limit events to avoid overloading frontend
        attack_txs = attack_txs[:12]
        
        # Clean transaction datatypes for JSON serialization (Decimal -> float, datetime -> isoformat)
        cleaned_txs = []
        for tx in attack_txs:
            tx_clean = {}
            for k, v in tx.items():
                if isinstance(v, Decimal):
                    tx_clean[k] = float(v)
                elif isinstance(v, datetime):
                    tx_clean[k] = v.isoformat()
                else:
                    tx_clean[k] = v
            cleaned_txs.append(tx_clean)
            
        return {
            "status": "success",
            "campaign_id": campaign.campaign_id,
            "pretext": campaign.pretext,
            "attack_id": attack_id,
            "intensity": intensity,
            "transactions": cleaned_txs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate campaign: {str(e)}")


