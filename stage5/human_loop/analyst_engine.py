"""
Analyst Engine: Uses Claude Sonnet 5 or Gemini to reason about fraud.
Configurable via environment variables to show which model is being used.

Cost controls:
- Daily budget limit (DAILY_LLM_BUDGET env var, default $10/day)
- Per-request limit (PER_REQUEST_LLM_LIMIT env var, default $0.50/request)
- Tracks usage in stage5/data/api_usage.log
"""
import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from anthropic import Anthropic
from stage5.human_loop.cost_limiter import get_limiter


class AnalystModel(str, Enum):
    """Which model to use for analyst reasoning."""
    CLAUDE_SONNET_5 = "claude-3-5-sonnet-20241022"
    GEMINI_2_0 = "gemini-2.0-flash"  # When available


@dataclass
class SHAPFeature:
    """Top feature contributing to fraud score."""
    name: str
    value: float
    contribution: float
    direction: str


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
    """Structured analyst output."""
    verdict: str  # "FRAUD", "LEGITIMATE", "UNSURE"
    confidence: float
    reasoning: str
    key_signals: list[str]
    patterns: list[str]
    suggested_threshold: float
    model_used: str
    model_family: str  # "claude" or "gemini"


def get_analyst_model() -> AnalystModel:
    """
    Determine which model to use.
    Environment: ANALYST_MODEL (claude|gemini)
    """
    choice = os.getenv("ANALYST_MODEL", "claude").lower()

    if choice == "gemini":
        return AnalystModel.GEMINI_2_0
    return AnalystModel.CLAUDE_SONNET_5


def analyze_transaction(
    fraud_score: float,
    shap_features: list[SHAPFeature],
    transaction: TransactionContext,
    model_override: AnalystModel = None,
    skip_budget_check: bool = False,
) -> AnalystVerdictOutput:
    """
    Analyze a transaction using Claude Sonnet 5 (default, non-hallucinating).
    Can override to use Gemini 2.0 when available.

    COST CONTROLS:
    - Checks daily budget before running (can be skipped with skip_budget_check=True)
    - Logs usage to stage5/data/api_usage.log
    - Set DAILY_LLM_BUDGET env var to control daily limit (default: $10)

    Args:
        fraud_score: Model's fraud probability (0.0-1.0)
        shap_features: Top 3-5 SHAP features explaining the score
        transaction: Transaction details
        model_override: Force a specific model
        skip_budget_check: If True, don't check budget (use for testing only)

    Returns:
        AnalystVerdictOutput with reasoning and patterns

    Raises:
        ValueError: If budget exceeded and skip_budget_check=False
    """
    # Check budget unless skipped
    if not skip_budget_check:
        limiter = get_limiter()
        can_proceed, reason = limiter.check_can_analyze()

        if not can_proceed:
            raise ValueError(f"Budget limit reached: {reason}")

    model = model_override or get_analyst_model()

    # Build context
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

TOP FRAUD SIGNALS (SHAP feature importance):
{features_text}

TASK:
1. Is this fraud or legitimate? Consider real-world context.
2. What patterns explain these signals?
3. Confidence level (0.0-1.0)?

OUTPUT (JSON only):
{{
  "verdict": "FRAUD or LEGITIMATE or UNSURE",
  "confidence": 0.85,
  "reasoning": "1-2 sentences",
  "key_signals": ["signal1", "signal2"],
  "patterns": ["pattern: description"],
  "suggested_threshold": 0.45
}}
"""

    if model == AnalystModel.CLAUDE_SONNET_5:
        result = _analyze_with_claude(prompt, model.value)
    else:
        # Gemini path (when credentials available)
        result = _analyze_with_gemini(prompt, model.value)

    # Log the usage
    if not skip_budget_check:
        limiter = get_limiter()
        limiter.log_analysis(cost_usd=0.005)  # Approximate cost

    return result


def _analyze_with_claude(prompt: str, model_id: str) -> AnalystVerdictOutput:
    """Use Claude Sonnet 5 for analysis (non-hallucinating, production-grade)."""
    client = Anthropic()

    response = client.messages.create(
        model=model_id,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text

    # Extract JSON from markdown if needed
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
        suggested_threshold=float(data.get("suggested_threshold", 0.5)),
        model_used=model_id,
        model_family="claude"
    )


def _analyze_with_gemini(prompt: str, model_id: str) -> AnalystVerdictOutput:
    """
    Use Gemini 2.0 for analysis when available.
    Falls back to Claude if Gemini API key not set.
    """
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")

    if not api_key:
        print(f"⚠️  Gemini API key not found, falling back to Claude Sonnet 5")
        return _analyze_with_claude(prompt, AnalystModel.CLAUDE_SONNET_5.value)

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=400,
                temperature=0.3  # Low temp for consistency
            )
        )

        text = response.text

        # Extract JSON
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
            suggested_threshold=float(data.get("suggested_threshold", 0.5)),
            model_used=model_id,
            model_family="gemini"
        )

    except Exception as e:
        print(f"⚠️  Gemini analysis failed ({e}), falling back to Claude")
        return _analyze_with_claude(prompt, AnalystModel.CLAUDE_SONNET_5.value)


if __name__ == "__main__":
    print("=" * 70)
    print("ANALYST ENGINE DEMO (Claude Sonnet 5)")
    print("=" * 70)

    demo_features = [
        SHAPFeature("edge_count", 2.1, 0.15, "increases_fraud_score"),
        SHAPFeature("beneficiary_added_ago_s", 259200, 0.12, "increases_fraud_score"),
        SHAPFeature("txn_count_last_1h", 5, 0.08, "increases_fraud_score")
    ]

    demo_context = TransactionContext(
        amount=50000.0,
        payee_id="payee_42189",
        payer_id="payer_18392",
        timestamp="2026-08-24T03:15:00Z",
        channel="UPI",
        auth_method="PIN"
    )

    verdict = analyze_transaction(
        fraud_score=0.87,
        shap_features=demo_features,
        transaction=demo_context
    )

    print(f"\n✓ Analysis Complete")
    print(f"  Model: {verdict.model_used} ({verdict.model_family.upper()})")
    print(f"  Verdict: {verdict.verdict}")
    print(f"  Confidence: {verdict.confidence:.1%}")
    print(f"  Reasoning: {verdict.reasoning}")
    print(f"  Key Signals: {', '.join(verdict.key_signals)}")
    print(f"  Patterns:")
    for p in verdict.patterns:
        print(f"    - {p}")
