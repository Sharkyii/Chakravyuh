"""
Curriculum Retraining: train on a generation's attacks with progressive
difficulty levels, measuring evasion at each stage. Used by Gen 3, 4, and 5
pipelines alike -- the mechanics don't depend on which generation's attacks
are being fed in, only the level names and target evasion threshold differ.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

from stage5.training.train_fraud_model import train_fraud_model
from stage5.adversarial.evasion_margin_calculator import measure_evasion_margin
from stage5.config.settings import ALL_FEATURES


def _as_feature_frame(attacks: list) -> pd.DataFrame:
    """Attack dicts -> a DataFrame aligned to the model's full feature schema.

    Any ALL_FEATURES column the attack generator didn't populate is left NaN;
    the preprocessor's imputers handle that the same as a genuinely missing
    real-world field.
    """
    df = pd.DataFrame([a['features'] for a in attacks])
    return df.reindex(columns=ALL_FEATURES)


def retrain_on_gen3_attacks(
    analyst_feedback_df: pd.DataFrame,
    gen3_attacks_by_level: dict,
    original_training_df: pd.DataFrame,
    gen2_model,
    gen2_preprocessor=None,
    generation_label: str = 'gen3',
    target_evasion: float = 0.05,
    output_dir: Path = None
) -> dict:
    """
    Retrain on a generation's attacks using curriculum learning.

    Flow:
    1. Start with the easiest level
    2. Train model
    3. Evaluate: prior-generation recall (no regression) + this generation's evasion
    4. Move to the next level
    5. Repeat through the hardest level, stopping early once target_evasion is met

    Args:
        analyst_feedback_df: analyst verdicts (training data)
        gen3_attacks_by_level: {level_name: [attack, ...], ...} -- level names
            and count are whatever the generation's attack generator produced;
            this function makes no assumption about their spelling.
        original_training_df: Original synthetic training data (needs 'split',
            'is_fraud', and the model's feature columns)
        gen2_model: Previous generation's model (used only for before/after
            evasion comparison, not required to be non-None)
        gen2_preprocessor: the fitted ColumnTransformer gen2_model was trained
            with. Required to score gen2_model correctly -- an XGBClassifier
            can't take raw categorical/unscaled features directly.
        generation_label: passed through to measure_evasion_margin for
            logging/context, and used to name output files
        target_evasion: stop the curriculum early once evasion drops at or
            below this value (Gen 3: 0.05, Gen 4: 0.15, Gen 5: 0.25 per the
            brief's escalating targets)
        output_dir: Where to save training logs

    Returns:
        {
            'model': trained model (best-evasion checkpoint),
            'preprocessor': that checkpoint's fitted ColumnTransformer,
            'model_metrics': that checkpoint's real train_fraud_model() metrics,
            'curriculum_log': {level_name: {...}, ...},
            'best_evasion': float,
            'improvement_from_gen2': bool,
            'prior_gen_evasion': float | None,  # this generation's attacks against gen2_model, before retraining
        }
    """

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / f"{generation_label}_training"
    output_dir.mkdir(parents=True, exist_ok=True)

    curriculum_log = {}
    best_model = None
    best_preprocessor = None
    best_model_metrics = None
    best_threshold = None
    best_evasion = 1.0
    all_models = {}

    levels = list(gen3_attacks_by_level.keys())

    print("\n" + "="*70)
    print(f"{generation_label.upper()} CURRICULUM RETRAINING")
    print("="*70)

    # Baseline: how badly does the PRIOR model do against these new attacks,
    # before any retraining? This is "why we retrain" -- the evasion measurement
    # that motivates this whole cycle, not something to leave hardcoded.
    prior_gen_evasion = None
    if gen2_model is not None and gen2_preprocessor is not None:
        all_attacks_flat = [a for lvl in gen3_attacks_by_level.values() for a in lvl]
        if all_attacks_flat:
            baseline_X = _as_feature_frame(all_attacks_flat)
            baseline_y = np.ones(len(baseline_X))
            baseline_margin = measure_evasion_margin(
                gen2_model, baseline_X, baseline_y,
                generation=generation_label, preprocessor=gen2_preprocessor,
            )
            prior_gen_evasion = baseline_margin['evasion_margin']
            print(f"\n  Baseline: {generation_label} attacks vs prior-generation model: "
                  f"{prior_gen_evasion*100:.1f}% evasion (why we retrain)")

    for level_idx, level_name in enumerate(levels):
        print(f"\n[{level_idx+1}/{len(levels)}] {level_name.upper()}")
        print("-" * 70)

        gen3_attacks = gen3_attacks_by_level[level_name]
        if not gen3_attacks:
            print(f"  Skipping (no attacks generated)")
            continue

        gen3_df = _as_feature_frame(gen3_attacks)
        gen3_df['is_fraud'] = 1
        gen3_df['split'] = 'test'

        training_df = pd.concat([
            original_training_df[original_training_df['split'].isin(['train', 'validation'])],
            analyst_feedback_df.assign(split='train') if len(analyst_feedback_df) else analyst_feedback_df,
            gen3_df.head(500),
        ], ignore_index=True, sort=False)

        print(f"  Training data size: {len(training_df)}")
        print(f"    Original: {len(original_training_df)}")
        print(f"    Analyst feedback: {len(analyst_feedback_df)}")
        print(f"    {generation_label} (for curriculum): {min(500, len(gen3_df))}")

        try:
            train_result = train_fraud_model(training_df)
            level_model = train_result['model']
            level_preprocessor = train_result['preprocessor']
            all_models[level_name] = level_model
        except Exception as e:
            print(f"  ERROR training: {e}")
            continue

        print(f"\n  Evaluation:")

        # "No regression" check: this freshly retrained model should still
        # catch fraud the original data already had labelled.
        gen2_margin = None
        prior_fraud = original_training_df[original_training_df['is_fraud'] == 1]
        gen2_attacks_test = prior_fraud.sample(min(100, len(prior_fraud)), random_state=42) if len(prior_fraud) else prior_fraud
        if len(gen2_attacks_test) > 0:
            gen2_margin = measure_evasion_margin(
                level_model, gen2_attacks_test.reindex(columns=ALL_FEATURES),
                gen2_attacks_test['is_fraud'].values, generation='prior',
                preprocessor=level_preprocessor,
            )
            print(f"    Prior-gen evasion: {gen2_margin['evasion_percent']} (should be near 0%)")

        this_gen_evasion = measure_evasion_margin(
            level_model, gen3_df[ALL_FEATURES], gen3_df['is_fraud'].values,
            generation=generation_label, preprocessor=level_preprocessor,
        )
        print(f"    {generation_label} evasion: {this_gen_evasion['evasion_percent']} (target <{target_evasion*100:.0f}%)")

        # <=, not <: if every level ties (e.g. all at the 1.0 sentinel because
        # this attack family is hard enough that no level improves at all),
        # the pipeline must still come out of this with *some* checkpoint
        # saved -- a strict "<" would leave best_model as None forever and
        # crash Stage 3's report generation instead of just reporting a
        # genuinely bad (but real) result.
        if this_gen_evasion['evasion_margin'] <= best_evasion:
            best_evasion = this_gen_evasion['evasion_margin']
            best_model = level_model
            best_preprocessor = level_preprocessor
            best_model_metrics = train_result['metrics']
            best_threshold = train_result['threshold']

        curriculum_log[level_name] = {
            'prior_gen_evasion': gen2_margin,
            f'{generation_label}_evasion': this_gen_evasion,
            'training_size': len(training_df),
            'status': 'PASS' if this_gen_evasion['status'] == 'PASS' else 'FAIL',
        }

        if this_gen_evasion['evasion_margin'] > target_evasion and level_idx < len(levels) - 1:
            print(f"\n  Action: Evasion too high, continue to {levels[level_idx+1]}")
        elif this_gen_evasion['evasion_margin'] <= target_evasion:
            print(f"\n  Action: Target achieved (<{target_evasion*100:.0f}%), ready to deploy")
            break
        elif level_idx == len(levels) - 1:
            print(f"\n  Action: Final level reached")

    log_path = output_dir / "curriculum_log.json"
    with open(log_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'generation': generation_label,
            'curriculum_log': curriculum_log,
            'best_evasion': best_evasion,
            'prior_gen_evasion': prior_gen_evasion,
            'all_models_trained': list(all_models.keys()),
        }, f, indent=2, default=str)

    print("\n" + "="*70)
    print("CURRICULUM TRAINING COMPLETE")
    print("="*70)
    print(f"Best {generation_label} evasion achieved: {best_evasion*100:.1f}%")
    print(f"Target: <{target_evasion*100:.0f}%")
    print(f"Status: {'PASS' if best_evasion < target_evasion else 'FAIL'}")
    print(f"Log saved: {log_path}")

    return {
        'model': best_model,
        'preprocessor': best_preprocessor,
        'model_metrics': best_model_metrics,
        'threshold': best_threshold,
        'curriculum_log': curriculum_log,
        'best_evasion': best_evasion,
        'prior_gen_evasion': prior_gen_evasion,
        'improvement_from_gen2': (prior_gen_evasion is not None and best_evasion < prior_gen_evasion),
        'all_models': all_models,
        'log_path': log_path,
    }
