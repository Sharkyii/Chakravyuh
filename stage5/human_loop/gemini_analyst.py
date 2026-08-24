"""
Gemini-powered fraud analyst: converts SHAP explanations into human-readable reasoning.
Takes model predictions + feature attributions, outputs analyst-style verdict & patterns.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic


@dataclass
class SHAPFeature:
    """Top feature contributing to fraud score."""
    name: str
    value: float
    contribution: float
    direction: str  # "increases_fraud_score" or "decreases_fraud_score"


@dataclass
class TransactionContext:
    """Transaction being reviewed."""
    amount: float
    payee_id: str
    payer_id: str
    timestamp: str
    channel: str
    auth_method: str


@dataclass
class AnalystVerdictOutput:
    """Structured output from Gemini analysis."""
    verdict: str  # "FRAUD", "LEGITIMATE", "UNSURE"
    confidence: float  # 0.0-1.0
    reasoning: str
    key_signals: list[str]
    patterns: list[str]
    suggested_threshold: float


def analyze_transaction(
    fraud_score: float,
    shap_features: list[SHAPFeature],
    transaction: TransactionContext,
    model_version: str = "unknown",
) -> AnalystVerdictOutput:
    """
    Call Claude to reason about a potentially fraudulent transaction.

    Args:
        fraud_score: Model's fraud probability (0.0-1.0)
        shap_features: Top 3-5 SHAP features explaining the score
        transaction: Transaction details
        model_version: Which model version scored this

    Returns:
        AnalystVerdictOutput with reasoning and patterns
    """

    # Build context for Claude
    features_text = "\n".join([
        f"  • {f.name}: {f.value:.3f} ({f.direction}, contribution: {f.contribution:+.3f})"
        for f in shap_features
    ])

    prompt = f"""You are an expert payment fraud analyst reviewing a transaction flagged by an ML model.

TRANSACTION DETAILS:
- Amount: {transaction.amount:.2f} {transaction.channel}
- Payer → Payee: {transaction.payer_id} → {transaction.payee_id}
- Timestamp: {transaction.timestamp}
- Auth Method: {transaction.auth_method}
- Model fraud score: {fraud_score:.1%}

TOP FRAUD SIGNALS (from SHAP explainability):
{features_text}

ANALYSIS TASK:
1. Is this actually fraud? Consider legitimate explanations for the signals.
2. What real-world patterns would explain these signals?
3. How confident are you? (0.0-1.0)

OUTPUT (JSON only, no preamble):
{{
  "verdict": "FRAUD or LEGITIMATE or UNSURE",
  "confidence": 0.85,
  "reasoning": "1-2 sentence explanation of your decision",
  "key_signals": ["signal1", "signal2"],
  "patterns": ["pattern1: explanation", "pattern2: explanation"],
  "suggested_threshold": 0.45
}}

Examples of valid patterns:
- "new_payee + fast_timing: mule network characteristic"
- "high_amount + evening_time: legitimate high-value weekend transfer"
- "device_change + ip_change + amount_spike: classic account takeover"
- "beneficiary_age_3_days + low_edge_count: newly added beneficiary (could be legitimate)"
"""

    client = Anthropic()
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )

    # Parse response
    text = response.content[0].text

    # Try to extract JSON if wrapped in markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    data = json.loads(text)

    return AnalystVerdictOutput(
        verdict=data.get("verdict", "UNSURE").upper(),
        confidence=float(data.get("confidence", 0.5)),
        reasoning=data.get("reasoning", ""),
        key_signals=data.get("key_signals", []),
        patterns=data.get("patterns", []),
        suggested_threshold=float(data.get("suggested_threshold", 0.5))
    )


def batch_analyze_transactions(
    transactions: list[dict],
    model_version: str = "unknown"
) -> list[dict]:
    """
    Analyze multiple transactions, storing results.

    Args:
        transactions: List of dicts with fraud_score, shap_features, transaction details
        model_version: Model that scored them

    Returns:
        List of dicts with original + analyst verdict
    """

    results = []
    for i, txn in enumerate(transactions):
        print(f"Analyzing transaction {i+1}/{len(transactions)}...")

        shap_features = [
            SHAPFeature(
                name=f["name"],
                value=f["value"],
                contribution=f["contribution"],
                direction=f["direction"]
            )
            for f in txn.get("shap_features", [])[:5]
        ]

        context = TransactionContext(
            amount=txn["amount"],
            payee_id=txn["payee_id"],
            payer_id=txn["payer_id"],
            timestamp=txn["timestamp"],
            channel=txn.get("channel", "UPI"),
            auth_method=txn.get("auth_method", "PIN")
        )

        try:
            verdict = analyze_transaction(
                fraud_score=txn["fraud_score"],
                shap_features=shap_features,
                transaction=context,
                model_version=model_version
            )

            results.append({
                **txn,
                "analyst_verdict": verdict.verdict,
                "analyst_confidence": verdict.confidence,
                "analyst_reasoning": verdict.reasoning,
                "key_signals": verdict.key_signals,
                "patterns": verdict.patterns,
                "suggested_threshold": verdict.suggested_threshold
            })
        except Exception as e:
            print(f"  Error analyzing transaction {i}: {e}")
            results.append({
                **txn,
                "analyst_verdict": "ERROR",
                "analyst_confidence": 0.0,
                "analyst_reasoning": str(e),
                "key_signals": [],
                "patterns": [],
                "suggested_threshold": 0.5
            })

    return results


if __name__ == "__main__":
    # Demo: analyze a synthetic fraud case
    demo_transaction = {
        "fraud_score": 0.87,
        "amount": 50000.0,
        "payee_id": "payee_42189",
        "payer_id": "payer_18392",
        "timestamp": "2026-08-24T03:15:00Z",
        "channel": "UPI",
        "auth_method": "PIN",
        "shap_features": [
            {
                "name": "edge_count",
                "value": 2.1,
                "contribution": 0.15,
                "direction": "increases_fraud_score"
            },
            {
                "name": "beneficiary_added_ago_s",
                "value": 259200,  # 3 days
                "contribution": 0.12,
                "direction": "increases_fraud_score"
            },
            {
                "name": "txn_count_last_1h",
                "value": 5,
                "contribution": 0.08,
                "direction": "increases_fraud_score"
            }
        ]
    }

    print("=" * 70)
    print("DEMO: Gemini Analyst Review")
    print("=" * 70)

    verdict = analyze_transaction(
        fraud_score=demo_transaction["fraud_score"],
        shap_features=[
            SHAPFeature(**f) for f in demo_transaction["shap_features"]
        ],
        transaction=TransactionContext(
            amount=demo_transaction["amount"],
            payee_id=demo_transaction["payee_id"],
            payer_id=demo_transaction["payer_id"],
            timestamp=demo_transaction["timestamp"],
            channel=demo_transaction["channel"],
            auth_method=demo_transaction["auth_method"]
        )
    )

    print(f"\nAnalyst Verdict: {verdict.verdict}")
    print(f"Confidence: {verdict.confidence:.1%}")
    print(f"Reasoning: {verdict.reasoning}")
    print(f"Key Signals: {', '.join(verdict.key_signals)}")
    print(f"Patterns:")
    for pattern in verdict.patterns:
        print(f"  - {pattern}")
    print(f"Suggested Threshold: {verdict.suggested_threshold:.2f}")
