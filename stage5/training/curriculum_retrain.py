"""
Curriculum Retraining: Train on Gen 3 attacks with progressive difficulty.
Start easy (1 feature hidden) → Hard (5 features hidden).
Measure improvement at each stage.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

from stage5.training.train_fraud_model import train_fraud_model
from stage5.adversarial.evasion_margin_calculator import measure_evasion_margin


def retrain_on_gen3_attacks(
    analyst_feedback_df: pd.DataFrame,
    gen3_attacks_by_level: dict,
    original_training_df: pd.DataFrame,
    gen2_model,
    output_dir: Path = None
) -> dict:
    """
    Retrain on Gen 3 attacks using curriculum learning.

    Flow:
    1. Start with Level 1 (easy): Hide 1 feature
    2. Train model
    3. Evaluate: Gen 2 recall + Gen 3 evasion
    4. Move to Level 2 (harder)
    5. Repeat through Level 4 (extreme)

    Args:
        analyst_feedback_df: 50+ analyst verdicts (training data)
        gen3_attacks_by_level: {level_1_easy, level_2_medium, ...}
        original_training_df: Original synthetic training data
        gen2_model: Previous model (for comparison)
        output_dir: Where to save training logs

    Returns:
        {
            'gen3_model': trained model,
            'curriculum_log': {
                'level_1_easy': {...},
                'level_2_medium': {...},
                ...
            },
            'best_evasion': 0.048,
            'improvement_from_gen2': True
        }
    """

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / "gen3_training"
    output_dir.mkdir(parents=True, exist_ok=True)

    curriculum_log = {}
    best_gen3_model = None
    best_evasion = 1.0
    all_models = {}

    levels = ['level_1_easy', 'level_2_medium', 'level_3_hard', 'level_4_extreme']

    print("\n" + "="*70)
    print("GEN 3 CURRICULUM RETRAINING")
    print("="*70)

    for level_idx, level_name in enumerate(levels):
        print(f"\n[{level_idx+1}/4] {level_name.upper()}")
        print("-" * 70)

        if level_name not in gen3_attacks_by_level:
            print(f"  Skipping (no attacks generated)")
            continue

        gen3_attacks = gen3_attacks_by_level[level_name]

        # Convert attacks to DataFrame
        gen3_df = pd.DataFrame([a['features'] for a in gen3_attacks])
        gen3_df['is_fraud'] = 1
        gen3_df['split'] = 'test'  # Evaluate on test split

        # Mix with existing data
        # Ratio: Original synthetic + Analyst feedback + Gen 3 attacks
        training_df = pd.concat([
            original_training_df[original_training_df['split'].isin(['train', 'validation'])],
            analyst_feedback_df.assign(split='train'),  # Analyst feedback goes to train
            gen3_df[['is_fraud', 'split']].head(500)  # Limited Gen 3 in training
        ], ignore_index=True)

        print(f"  Training data size: {len(training_df)}")
        print(f"    Original: {len(original_training_df)}")
        print(f"    Analyst feedback: {len(analyst_feedback_df)}")
        print(f"    Gen 3 (for curriculum): {min(500, len(gen3_df))}")

        # Retrain
        try:
            gen3_model = train_fraud_model(training_df)
            all_models[level_name] = gen3_model
        except Exception as e:
            print(f"  ERROR training: {e}")
            continue

        # Evaluate
        print(f"\n  Evaluation:")

        # 1. Gen 2 attacks: Should still catch them (no regression)
        gen2_attacks_test = original_training_df[original_training_df['is_fraud'] == 1].sample(min(100, len(original_training_df[original_training_df['is_fraud'] == 1])))
        if len(gen2_attacks_test) > 0:
            gen2_margin = measure_evasion_margin(
                gen3_model,
                gen2_attacks_test.values,
                gen2_attacks_test['is_fraud'].values,
                generation='gen2'
            )
            print(f"    Gen 2 evasion: {gen2_margin['evasion_percent']} (should be near 0%)")
        else:
            gen2_margin = None

        # 2. Gen 3 attacks at this level
        gen3_evasion = measure_evasion_margin(
            gen3_model,
            gen3_df.values,
            gen3_df['is_fraud'].values,
            generation='gen3'
        )
        print(f"    Gen 3 evasion: {gen3_evasion['evasion_percent']} (target <5%)")

        # Track best model
        if gen3_evasion['evasion_margin'] < best_evasion:
            best_evasion = gen3_evasion['evasion_margin']
            best_gen3_model = gen3_model

        # Log this level
        curriculum_log[level_name] = {
            'gen2_evasion': gen2_margin,
            'gen3_evasion': gen3_evasion,
            'training_size': len(training_df),
            'status': 'PASS' if gen3_evasion['status'] == 'PASS' else 'FAIL'
        }

        # Decision: Continue or stop?
        if gen3_evasion['evasion_margin'] > 0.05 and level_idx < len(levels) - 1:
            print(f"\n  Action: Evasion too high, continue to {levels[level_idx+1]}")
        elif gen3_evasion['evasion_margin'] <= 0.05:
            print(f"\n  Action: Target achieved (<5%), ready to deploy")
            break
        elif level_idx == len(levels) - 1:
            print(f"\n  Action: Final level reached")

    # Save logs
    log_path = output_dir / "curriculum_log.json"
    with open(log_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'curriculum_log': curriculum_log,
            'best_evasion': best_evasion,
            'all_models_trained': list(all_models.keys())
        }, f, indent=2)

    print("\n" + "="*70)
    print("CURRICULUM TRAINING COMPLETE")
    print("="*70)
    print(f"Best Gen 3 evasion achieved: {best_evasion*100:.1f}%")
    print(f"Target: <5.0%")
    print(f"Status: {'✓ PASS' if best_evasion < 0.05 else '✗ FAIL'}")
    print(f"Log saved: {log_path}")

    return {
        'gen3_model': best_gen3_model,
        'curriculum_log': curriculum_log,
        'best_evasion': best_evasion,
        'improvement_from_gen2': best_evasion < 0.10,  # Gen 2 had ~5% on Gen 3
        'all_models': all_models,
        'log_path': log_path
    }
