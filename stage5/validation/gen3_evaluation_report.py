"""
Gen 3 Evaluation Report: Comprehensive measurement showing improvement cycle.
Proves: Analyst feedback → Retrain → Better detector

Every number in this report is threaded through from the real curriculum_log
and model_metrics produced by stage5.training.curriculum_retrain -- nothing
here is a hardcoded placeholder. Narrative fields (what Gen 3 attacks are,
why the curriculum is structured this way) are static documentation, not
measurements.
"""
import json
from pathlib import Path
from datetime import datetime


def generate_gen3_evaluation_report(
    gen2_model_metrics: dict,
    gen3_model_metrics: dict,
    curriculum_log: dict,
    analyst_feedback_count: int,
    prior_gen_evasion: float = None,
    best_evasion: float = None,
    output_path: Path = None,
) -> dict:
    """
    Generate comprehensive Gen 3 evaluation report from real measurements.

    Returns:
        Report dictionary + saves to JSON
    """

    if output_path is None:
        output_path = Path(__file__).parent.parent / "data" / "gen3_evaluation_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gen3_test = gen3_model_metrics.get('test_metrics', {})
    gen2_test = gen2_model_metrics.get('test_metrics', {})

    target = 0.05
    status = "PASS" if (best_evasion is not None and best_evasion < target) else "FAIL"

    level_summary = {}
    for level_name, entry in curriculum_log.items():
        gen3_evasion_entry = entry.get('gen3_evasion', {})
        level_summary[level_name] = {
            "evasion": gen3_evasion_entry.get('evasion_percent'),
            "evasion_margin": gen3_evasion_entry.get('evasion_margin'),
            "status": entry.get('status'),
            "training_size": entry.get('training_size'),
        }

    report = {
        "timestamp": datetime.now().isoformat(),
        "title": "Gen 3 Adversarial Evaluation Report",
        "executive_summary": {
            "analyst_feedback_collected": analyst_feedback_count,
            "gen3_evasion_rate": f"{best_evasion*100:.1f}%" if best_evasion is not None else "n/a",
            "gen3_target": f"<{target*100:.1f}%",
            "status": status,
            "recommendation": "Deploy Gen 3-trained model" if status == "PASS" else "Continue Gen 3 hardening",
        },
        "model_performance_comparison": {
            "gen2_baseline": {
                "pr_auc": gen2_test.get('pr_auc'),
                "held_out_recall": _first_held_out_recall(gen2_test),
                "description": "Prior generation, before this retraining cycle",
            },
            "gen3_after_curriculum": {
                "pr_auc": gen3_test.get('pr_auc'),
                "held_out_recall": _first_held_out_recall(gen3_test),
                "description": "After curriculum retraining on Gen 3 attacks",
            },
        },
        "evasion_metrics": {
            "gen3_attacks_on_prior_model": {
                "evasion_rate": f"{prior_gen_evasion*100:.1f}%" if prior_gen_evasion is not None else "n/a",
                "status": "FAIL" if (prior_gen_evasion or 0) > target else "PASS",
                "note": "Why we retrained",
            },
            "gen3_attacks_on_gen3_model": {
                "evasion_rate": f"{best_evasion*100:.1f}%" if best_evasion is not None else "n/a",
                "status": status,
                "note": "After curriculum retraining",
            },
        },
        "curriculum_effectiveness": level_summary,
        "analyst_feedback_impact": {
            "feedback_collected": analyst_feedback_count,
            "impact": "Analyst verdicts mixed with synthetic + attack data during retraining, "
                      "providing ground truth beyond synthetic labels.",
        },
        "feature_importance": gen3_model_metrics.get('top_features', []),
        "closed_loop_cycle_proof": {
            "step_1_collect_feedback": f"{analyst_feedback_count} analyst verdicts collected",
            "step_2_generate_attacks": "Gen 3 attacks generated (feature-hiding curriculum)",
            "step_3_retrain": "Model retrained per curriculum level, best-evasion checkpoint kept",
            "step_4_measure_evasion": f"Evasion margin: {f'{best_evasion*100:.1f}%' if best_evasion is not None else 'n/a'} (target <{target*100:.0f}%)",
            "result": status,
        },
        "next_steps": {
            "if_pass": "Deploy Gen 3 model, or proceed to Gen 4 (ensemble attacks) for further hardening",
            "if_fail": "Add curriculum levels or extract more real attack patterns before proceeding",
        },
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return report


def _first_held_out_recall(test_metrics: dict):
    gens = test_metrics.get('held_out_family_generalisation', [])
    return gens[0]['held_out_recall'] if gens else None


def print_gen3_report(report: dict):
    """Pretty-print the Gen 3 evaluation report."""

    print("\n" + "="*70)
    print(report['title'].upper())
    print("="*70)

    print("\nEXECUTIVE SUMMARY")
    for key, value in report['executive_summary'].items():
        print(f"  {key}: {value}")

    print("\nEVASION METRICS")
    for key, value in report['evasion_metrics'].items():
        print(f"  {key}: {value['evasion_rate']} ({value['status']}) -- {value['note']}")

    print("\nMODEL COMPARISON")
    comp = report['model_performance_comparison']
    print(f"  Gen 2 PR-AUC: {comp['gen2_baseline']['pr_auc']}  |  Gen 3 PR-AUC: {comp['gen3_after_curriculum']['pr_auc']}")

    print("\nCONCLUSION")
    print(f"  Status: {report['executive_summary']['status']}")
    print(f"  Recommendation: {report['executive_summary']['recommendation']}")
    print("="*70)
