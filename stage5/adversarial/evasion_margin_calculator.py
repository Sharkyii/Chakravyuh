"""
Measure evasion margin: % of attacks that slip through detector.
Key metric for evaluating adversarial robustness.
"""
import numpy as np
from pathlib import Path
from typing import dict
import json


def measure_evasion_margin(
    model,
    attack_variants: np.ndarray,
    target_labels: np.ndarray,
    threshold: float = 0.45,
    generation: str = 'gen3'
) -> dict:
    """
    Calculate evasion margin for a set of attacks.

    Evasion margin = (fraud_cases_not_caught) / (total_fraud_cases)

    Args:
        model: Trained fraud detector
        attack_variants: Feature matrix of attack variants
        target_labels: True labels (should all be 1/fraud)
        threshold: Decision threshold for fraud classification
        generation: Gen 1/2/3/4/5 (for context)

    Returns:
        {
            'evasion_margin': 0.032,
            'caught': 97,
            'slipped': 3,
            'total': 100,
            'threshold_used': 0.45,
            'evasion_percent': '3.2%',
            'status': 'PASS' if < target else 'FAIL',
            'target': 0.05,
            'generation': 'gen3'
        }
    """

    # Get fraud probabilities
    predictions = model.predict_proba(attack_variants)[:, 1]

    # Count how many were caught (score > threshold)
    caught = np.sum(predictions > threshold)
    total = len(predictions)
    slipped = total - caught

    evasion_margin = slipped / total if total > 0 else 0

    # Targets by generation
    targets = {
        'gen1': 0.01,   # Almost none slip through
        'gen2': 0.00,   # Perfect recall
        'gen3': 0.05,   # <5% evasion acceptable
        'gen4': 0.15,   # <15% evasion for ensemble attacks
        'gen5': 0.30,   # <30% evasion for cross-family (hard limit)
    }

    target = targets.get(generation, 0.05)
    status = 'PASS' if evasion_margin <= target else 'FAIL'

    return {
        'generation': generation,
        'evasion_margin': evasion_margin,
        'evasion_percent': f'{evasion_margin * 100:.1f}%',
        'caught': int(caught),
        'slipped': int(slipped),
        'total': int(total),
        'threshold_used': threshold,
        'target': target,
        'target_percent': f'{target * 100:.1f}%',
        'status': status,
        'margin_to_target': evasion_margin - target,
    }


def compare_generations(
    model_dict: dict,
    attack_variants_dict: dict,
    generations: list = ['gen1', 'gen2', 'gen3']
) -> dict:
    """
    Compare evasion margins across multiple attack generations.

    Shows how well detector handles increasingly harder attacks.

    Args:
        model_dict: {gen1_model, gen2_model, gen3_model, ...}
        attack_variants_dict: {gen1_attacks, gen2_attacks, gen3_attacks, ...}
        generations: Which to compare

    Returns:
        {
            'gen1': {evasion_margin, status, ...},
            'gen2': {...},
            'gen3': {...},
            'summary': {
                'best_gen': 'gen1',
                'weakest_gen': 'gen3',
                'trend': 'degrading (expected)'
            }
        }
    """

    results = {}

    for gen in generations:
        model = model_dict.get(f'{gen}_model')
        attacks = attack_variants_dict.get(f'{gen}_attacks')
        labels = attack_variants_dict.get(f'{gen}_labels')

        if model is None or attacks is None:
            continue

        margin = measure_evasion_margin(model, attacks, labels, generation=gen)
        results[gen] = margin

    # Summary
    if results:
        evasion_margins = [v['evasion_margin'] for v in results.values()]
        best_gen = min(results.items(), key=lambda x: x[1]['evasion_margin'])[0]
        worst_gen = max(results.items(), key=lambda x: x[1]['evasion_margin'])[0]

        # Check if trend is degrading (expected) or improving (unexpected)
        gen_order = ['gen1', 'gen2', 'gen3', 'gen4', 'gen5']
        gen_indices = [gen_order.index(g) for g in results.keys() if g in gen_order]
        margins_in_order = [results[gen_order[i]]['evasion_margin'] for i in sorted(gen_indices)]

        # Trend: are later generations harder? (margins should increase)
        if len(margins_in_order) > 1:
            is_degrading = all(margins_in_order[i] <= margins_in_order[i+1] for i in range(len(margins_in_order)-1))
            trend = 'degrading (expected)' if is_degrading else 'improving (unexpected)'
        else:
            trend = 'unknown (single generation)'

        results['summary'] = {
            'best_gen': best_gen,
            'worst_gen': worst_gen,
            'trend': trend,
            'all_pass': all(v['status'] == 'PASS' for v in results.values() if 'status' in v),
        }

    return results


def save_evasion_report(
    measurements: dict,
    output_path: Path,
    generation: str = 'gen3'
):
    """
    Save evasion measurements to JSON report.

    Args:
        measurements: Output from measure_evasion_margin or compare_generations
        output_path: Where to save the report
        generation: gen1/2/3/4/5
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        'generation': generation,
        'timestamp': str(np.datetime64('now')),
        'measurements': measurements,
        'interpretation': {
            'evasion_margin': 'Percentage of attack variants that slip through detector',
            'caught': 'Number of fraud cases correctly flagged',
            'slipped': 'Number of fraud cases that evaded detection',
            'status': 'PASS if evasion_margin <= target for generation, FAIL otherwise',
            'target': {
                'gen1': '1% (baseline)',
                'gen2': '0% (perfect)',
                'gen3': '5% (acceptable difficulty)',
                'gen4': '15% (harder)',
                'gen5': '30% (hard limit)',
            }
        }
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    return output_path
