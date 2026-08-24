"""
Analysis Impact Report: Show exactly what each analyst review will do.
Before running any analysis, show full transparency about:
1. What Claude analyzes
2. What data is collected
3. How it drives retraining
"""


def generate_impact_report(
    fraud_score: float,
    transaction_amount: float,
    shap_features: list[dict],
    current_feedback_count: int = 0,
) -> dict:
    """
    Generate a detailed impact report before running analysis.

    Shows:
    - What Claude will analyze
    - Cost impact ($0.005 per call)
    - Progress toward retrain trigger (50 verdicts needed)
    - What happens after this analysis
    """

    # Calculate progress
    verdicts_needed = 50
    progress_toward_retrain = (current_feedback_count / verdicts_needed) * 100
    fraud_verdicts_needed = 20
    remaining_to_retrain = verdicts_needed - current_feedback_count

    # Build the report
    report = {
        "transaction_summary": {
            "amount": f"₹{transaction_amount:,.0f}",
            "model_fraud_score": f"{fraud_score*100:.1f}%",
            "top_signals": [f["name"] for f in shap_features[:3]],
        },
        "analysis_scope": {
            "what_claude_analyzes": [
                f"Transaction amount: ₹{transaction_amount:,.0f}",
                f"Model fraud score: {fraud_score*100:.1f}%",
                f"Top {len(shap_features)} fraud signals from SHAP",
                "Transaction context (timing, payee, channel, auth)",
                "Real-world fraud patterns",
            ],
            "outputs_generated": [
                "Verdict (FRAUD / LEGITIMATE / UNSURE)",
                "Analyst confidence (0-100%)",
                "Reasoning (why is this fraud/legitimate?)",
                "Key signals (which features matter)",
                "Patterns (mule network, account takeover, etc)",
            ]
        },
        "cost_impact": {
            "cost_per_call": "$0.005",
            "daily_budget": "$1.00",
            "max_runs_today": 20,
            "this_will_cost": "$0.005"
        },
        "feedback_collection": {
            "current_feedback": current_feedback_count,
            "progress_to_retrain_trigger": f"{progress_toward_retrain:.1f}%",
            "verdicts_needed_for_retrain": verdicts_needed,
            "after_this_analysis": {
                "new_count": current_feedback_count + 1,
                "progress_percent": f"{((current_feedback_count + 1) / verdicts_needed) * 100:.1f}%",
                "verdicts_remaining": max(0, remaining_to_retrain - 1)
            }
        },
        "retrain_workflow": {
            "step_1_this_analysis": "Claude analyzes transaction (cost: $0.005)",
            "step_2_you_verdict": "You submit your verdict (Fraud/Legitimate/Unsure) + confidence + notes",
            "step_3_storage": "Verdict stored in: stage5/data/analyst_feedback.parquet",
            "step_4_accumulation": f"When {verdicts_needed} verdicts collected → Auto-trigger retrain",
            "step_5_retraining": "Retraining process:",
            "step_5_details": [
                "Load analyst-confirmed fraud verdicts",
                "Mix with existing synthetic training data",
                "Retrain fraud model + attack classifier",
                "Evaluate on new harder attacks (Gen 3)",
                "Measure improvement vs baseline",
                "If improved, promote as new production model"
            ]
        },
        "what_happens_with_feedback": {
            "with_1_verdict": "Baseline established, patterns noted",
            "with_10_verdicts": "Enough to identify common analyst disagreements with model",
            "with_20_verdicts": "Enough confirmed fraud to start curriculum learning",
            "with_50_verdicts": "✓ TRIGGER RETRAIN - Auto-start model improvement cycle"
        },
        "next_phase_adversarial": {
            "after_retraining": "Generate harder attacks (Gen 3, Gen 4) targeting top features",
            "evasion_test": "Test: How many Gen 3 attacks slip through new model?",
            "if_evasion_low": "✓ Model is robust, ready for production",
            "if_evasion_high": "❌ Generate even harder attacks (Gen 5), retrain again"
        },
        "transparency": {
            "you_control": [
                "You click to trigger each analysis (no auto-run)",
                "You decide verdict (Claude is advisor, not authority)",
                "You provide confidence level (controls weight in retraining)",
                "You can see cost in real-time before clicking"
            ],
            "Claude_only_does": [
                "Analyzes SHAP features → generates reasoning",
                "Suggests verdict based on patterns (you can override)",
                "Never executes retraining (that's manual trigger)"
            ]
        }
    }

    return report


def format_impact_report(report: dict) -> str:
    """Format the impact report for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("ANALYSIS IMPACT REPORT: What Happens When You Click")
    lines.append("=" * 70)

    lines.append("\n📊 TRANSACTION BEING ANALYZED")
    for key, value in report["transaction_summary"].items():
        lines.append(f"  {key}: {value}")

    lines.append("\n🤖 WHAT CLAUDE ANALYZES")
    for item in report["analysis_scope"]["what_claude_analyzes"]:
        lines.append(f"  • {item}")

    lines.append("\n📝 OUTPUTS GENERATED")
    for item in report["analysis_scope"]["outputs_generated"]:
        lines.append(f"  • {item}")

    lines.append("\n💰 COST IMPACT")
    lines.append(f"  Cost per call: {report['cost_impact']['cost_per_call']}")
    lines.append(f"  Daily budget: {report['cost_impact']['daily_budget']}")
    lines.append(f"  This will cost: {report['cost_impact']['this_will_cost']}")
    lines.append(f"  This call will be #{report['feedback_collection']['after_this_analysis']['new_count']} of {report['cost_impact']['max_runs_today']} max today")

    lines.append("\n📈 PROGRESS TO RETRAINING")
    lines.append(f"  Current feedback: {report['feedback_collection']['current_feedback']}")
    lines.append(f"  Needed for retrain: {report['feedback_collection']['verdicts_needed_for_retrain']}")
    lines.append(f"  After this: {report['feedback_collection']['after_this_analysis']['verdicts_remaining']} more needed")
    lines.append(f"  Progress: {report['feedback_collection']['progress_to_retrain_trigger']:.1f}% → {report['feedback_collection']['after_this_analysis']['progress_percent']}")

    lines.append("\n🔄 THE RETRAINING WORKFLOW")
    lines.append(f"  Step 1: {report['retrain_workflow']['step_1_this_analysis']}")
    lines.append(f"  Step 2: {report['retrain_workflow']['step_2_you_verdict']}")
    lines.append(f"  Step 3: {report['retrain_workflow']['step_3_storage']}")
    lines.append(f"  Step 4: {report['retrain_workflow']['step_4_accumulation']}")
    lines.append(f"  Step 5: {report['retrain_workflow']['step_5_retraining']}")
    for detail in report['retrain_workflow']['step_5_details']:
        lines.append(f"         • {detail}")

    lines.append("\n🎯 WHO CONTROLS WHAT")
    lines.append("  YOU DECIDE:")
    for item in report['transparency']['you_control']:
        lines.append(f"    • {item}")
    lines.append("  CLAUDE ONLY DOES:")
    for item in report['transparency']['Claude_only_does']:
        lines.append(f"    • {item}")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


if __name__ == "__main__":
    # Demo
    report = generate_impact_report(
        fraud_score=0.87,
        transaction_amount=50000,
        shap_features=[
            {"name": "edge_count", "value": 2.1, "contribution": 0.15},
            {"name": "beneficiary_added_ago_s", "value": 259200, "contribution": 0.12},
            {"name": "txn_count_last_1h", "value": 5, "contribution": 0.08},
        ],
        current_feedback_count=12
    )

    print(format_impact_report(report))
