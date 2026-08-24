"""
Gen 4 Evaluation Report: Ensemble attack robustness assessment.
Shows how well detector handles feature trading attacks.

Numeric/status sections are built from real curriculum_log and model_metrics
passed in by the pipeline. The "what_is_gen4"/"trading_strategies_used"
sections are static documentation of the attack methodology, not measurements.
"""
import json
from pathlib import Path
from datetime import datetime


def generate_gen4_evaluation_report(
    gen3_model_metrics: dict,
    gen4_model_metrics: dict,
    curriculum_log: dict,
    gen4_evasion_rate: float,
    prior_gen_evasion: float = None,
    output_path: Path = None,
) -> dict:
    """Generate Gen 4 evaluation report from real measurements."""

    if output_path is None:
        output_path = Path(__file__).parent.parent / "data" / "gen4_evaluation_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    target = 0.15
    status = "PASS" if gen4_evasion_rate < target else "FAIL"
    gen3_test = gen3_model_metrics.get('test_metrics', {})
    gen4_test = gen4_model_metrics.get('test_metrics', {}) if gen4_model_metrics else {}

    level_summary = {}
    for level_name, entry in curriculum_log.items():
        gen_evasion_entry = entry.get('gen4_evasion', {})
        level_summary[level_name] = {
            "evasion": gen_evasion_entry.get('evasion_percent'),
            "evasion_margin": gen_evasion_entry.get('evasion_margin'),
            "status": entry.get('status'),
            "training_size": entry.get('training_size'),
        }

    report = {
        "timestamp": datetime.now().isoformat(),
        "title": "Gen 4 Ensemble Adversarial Evaluation Report",
        "executive_summary": {
            "gen4_evasion_rate": f"{gen4_evasion_rate*100:.1f}%",
            "gen4_target": f"<{target*100:.1f}%",
            "status": status,
            "recommendation": "Deploy Gen 4 model" if status == "PASS" else "Generate Gen 5 attacks",
        },
        "what_is_gen4": {
            "concept": "Ensemble attacks trade off multiple features simultaneously",
            "example_1": "Low edge_count BUT high transaction velocity",
            "example_2": "Old beneficiary age BUT unusual transaction amounts",
            "example_3": "Known device BUT proxy IP",
            "challenge": "Model can't rely on single feature — must learn feature combinations",
            "why_harder_than_gen3": "Gen 3 hides features. Gen 4 exposes conflicting signals.",
        },
        "trading_strategies_used": [
            {
                "name": "low_edge_high_velocity",
                "description": "Hide graph structure, expose transaction speed",
                "hiding": ["edge_count", "is_two_hop_passthrough"],
                "exposing": ["txn_count_last_1h", "amount_spent_last_1h"],
            },
            {
                "name": "established_payee_new_behavior",
                "description": "Hide beneficiary age, expose amount/timing anomalies",
                "hiding": ["beneficiary_added_ago_s"],
                "exposing": ["amount_deviation", "time_since_prev_txn"],
            },
            {
                "name": "known_device_new_ip",
                "description": "Hide device, expose IP anomaly",
                "hiding": ["device_is_known_for_payer"],
                "exposing": ["ip_is_proxy", "new_ip_indicator"],
            },
        ],
        "model_performance": {
            "gen3_baseline": {
                "pr_auc": gen3_test.get('pr_auc'),
                "held_out_recall": _first_held_out_recall(gen3_test),
            },
            "gen4_after_retrain": {
                "pr_auc": gen4_test.get('pr_auc'),
                "held_out_recall": _first_held_out_recall(gen4_test),
            },
        },
        "evasion_metrics": {
            "gen4_attacks_on_gen3_model": {
                "evasion_rate": f"{prior_gen_evasion*100:.1f}%" if prior_gen_evasion is not None else "n/a",
                "status": "FAIL" if (prior_gen_evasion or 0) > target else "PASS",
                "note": "Why we retrain",
            },
            "gen4_attacks_on_gen4_model": {
                "evasion_rate": f"{gen4_evasion_rate*100:.1f}%",
                "status": status,
                "note": "After ensemble curriculum retraining",
            },
        },
        "difficulty_levels": level_summary,
        "feature_importance": gen4_model_metrics.get('top_features', []) if gen4_model_metrics else [],
        "curriculum_effectiveness": {
            "success_criterion": f"<{target*100:.0f}% final evasion rate",
            "pass_fail": status,
        },
        "next_steps": {
            "if_pass": "Deploy Gen 4 model, or generate Gen 5 (multi-family attacks) for further hardening",
            "if_fail": "Add curriculum levels or revisit feature engineering",
        },
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return report


def _first_held_out_recall(test_metrics: dict):
    gens = test_metrics.get('held_out_family_generalisation', [])
    return gens[0]['held_out_recall'] if gens else None


def print_gen4_report(report: dict):
    """Pretty-print Gen 4 evaluation report."""

    print("\n" + "="*70)
    print(report['title'].upper())
    print("="*70)

    print("\nEXECUTIVE SUMMARY")
    for key, value in report['executive_summary'].items():
        print(f"  {key}: {value}")

    print("\nEVASION METRICS")
    for key, value in report['evasion_metrics'].items():
        print(f"  {key}: {value['evasion_rate']} ({value['status']}) -- {value['note']}")

    print("\nCONCLUSION")
    print(f"  Evasion Rate: {report['executive_summary']['gen4_evasion_rate']}")
    print(f"  Target: {report['executive_summary']['gen4_target']}")
    print(f"  Status: {report['executive_summary']['status']}")
    print(f"  Recommendation: {report['executive_summary']['recommendation']}")
    print("="*70)
